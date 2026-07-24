"""RAG agent module.

Provides the RAGAgent class which augments LLM responses with retrieved context."""

import asyncio
import logging
from enum import Enum
from pydantic import Field, field_validator, model_validator
from typing import Callable, Optional

from .chat_agent import ChatAgent
from ...schemas import Memory, Message
from ...schemas.oxy import OxyRequest, OxyState
from ...utils.token_utils import KnowledgeTruncator, TokenEstimator

logger = logging.getLogger(__name__)

_DEFAULT_COLLAPSE_PROMPT = (
    "Please summarise the following text concisely, preserving the key facts:\n\n{text}"
)


class OverflowStrategy(str, Enum):
    """Strategy to apply when retrieved knowledge exceeds the token budget.

    - IGNORE:         pass the full text unchanged (original behaviour, default).
    - TRUNCATE:       keep the largest fitting prefix, log a warning, continue.
    - RAISE:          raise ValueError immediately so the caller can decide.
    - MAP_REDUCE:     split into chunks, summarise each with the LLM, then
                      recursively collapse until the result fits the budget.
    """

    TRUNCATE = "truncate"
    RAISE = "raise"
    IGNORE = "ignore"
    MAP_REDUCE = "map_reduce"


class RAGAgent(ChatAgent):
    """A retrieval-augmented agent that fetches relevant context before LLM generation.

    Context-window protection
    -------------------------
    Set ``max_knowledge_tokens`` to a positive integer to enable overflow
    detection.  When the retrieved knowledge exceeds that budget:

    * ``overflow_strategy=IGNORE`` (default) — passes the full text unchanged (original behaviour).
    * ``overflow_strategy=TRUNCATE`` — silently truncates and logs a warning.
    * ``overflow_strategy=RAISE``    — raises ``ValueError``.
    * ``overflow_strategy=MAP_REDUCE`` — splits into chunks, summarises each with the LLM,
      then recursively collapses until the combined summary fits the budget.
      Requires ``max_knowledge_tokens`` to be set.
    """

    knowledge_placeholder: str = Field("knowledge", min_length=1)

    func_retrieve_knowledge: Callable = Field(
        exclude=True, description="Retrieve knowledge function"
    )

    # ---- context-window protection fields -----------------------------------
    max_knowledge_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Maximum tokens allowed for retrieved knowledge. "
            "None disables overflow checking (legacy behaviour)."
        ),
    )
    overflow_strategy: OverflowStrategy = Field(
        default=OverflowStrategy.IGNORE,
        description="Action to take when retrieved knowledge exceeds max_knowledge_tokens.",
    )
    collapse_prompt: str = Field(
        default=_DEFAULT_COLLAPSE_PROMPT,
        description=(
            "Prompt template used when overflow_strategy=MAP_REDUCE to summarise each chunk. "
            "Must contain the placeholder '{text}'."
        ),
    )
    collapse_max_retries: int = Field(
        default=3,
        ge=1,
        description=(
            "Maximum number of recursive collapse rounds for MAP_REDUCE strategy "
            "before raising ValueError."
        ),
    )

    @field_validator("collapse_prompt")
    @classmethod
    def _validate_collapse_prompt(cls, v: str) -> str:
        if "{text}" not in v:
            raise ValueError(
                "collapse_prompt must contain the '{text}' placeholder; "
                f"got: {v!r}"
            )
        try:
            v.format(text="")
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(
                f"collapse_prompt contains an unresolvable placeholder: {exc}. "
                "Only '{text}' is supported."
            ) from exc
        return v

    @model_validator(mode="after")
    def set_default_prompt(self) -> "RAGAgent":
        """Pydantic model validator that injects the default RAG prompt if none provided."""
        if not self.prompt:
            self.prompt = (
                    "You are a helpful assistant. You can refer to the following information to answer the questions.\n${"
                    + self.knowledge_placeholder
                    + "}"
            )
        if self.overflow_strategy == OverflowStrategy.MAP_REDUCE and self.max_knowledge_tokens is None:
            logger.warning(
                "RAGAgent '%s': overflow_strategy=MAP_REDUCE requires max_knowledge_tokens to be set; "
                "knowledge will be passed through unchanged until max_knowledge_tokens is configured.",
                self.name,
            )
        return self

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def knowledge_fits(self, knowledge: str) -> bool:
        """Return True if *knowledge* fits within the configured token budget.

        Always returns True when ``max_knowledge_tokens`` is not set.
        """
        if self.max_knowledge_tokens is None:
            return True
        return KnowledgeTruncator.fits(
            knowledge, self.max_knowledge_tokens, self.llm_model
        )

    def apply_overflow_strategy(self, knowledge: str) -> str:
        """Apply the non-async overflow strategies (IGNORE / TRUNCATE / RAISE).

        MAP_REDUCE requires an async LLM call — use ``apply_overflow_strategy_async``
        for that strategy.  Calling this method with MAP_REDUCE raises RuntimeError.
        """
        if self.max_knowledge_tokens is None or self.overflow_strategy == OverflowStrategy.IGNORE:
            return knowledge

        if self.overflow_strategy == OverflowStrategy.RAISE:
            if not KnowledgeTruncator.fits(
                    knowledge, self.max_knowledge_tokens, self.llm_model
            ):
                raise ValueError(
                    f"Retrieved knowledge exceeds token budget "
                    f"({self.max_knowledge_tokens} tokens). "
                    "Set overflow_strategy=TRUNCATE to truncate automatically, "
                    "or increase max_knowledge_tokens."
                )
            return knowledge

        if self.overflow_strategy == OverflowStrategy.TRUNCATE:
            result, was_truncated = KnowledgeTruncator.truncate(
                knowledge, self.max_knowledge_tokens, self.llm_model
            )
            if was_truncated:
                original_tokens = TokenEstimator.count_tokens(knowledge, self.llm_model)
                logger.warning(
                    "RAGAgent '%s': retrieved knowledge truncated from ~%d tokens "
                    "to fit %d-token budget.",
                    self.name,
                    original_tokens,
                    self.max_knowledge_tokens,
                )
            return result

        raise RuntimeError(
            f"overflow_strategy={self.overflow_strategy!r} requires an async call; "
            "use apply_overflow_strategy_async instead."
        )

    async def apply_overflow_strategy_async(
            self, knowledge: str, oxy_request: OxyRequest
    ) -> str:
        """Apply the configured overflow strategy, including the async MAP_REDUCE path."""
        if self.overflow_strategy != OverflowStrategy.MAP_REDUCE:
            return self.apply_overflow_strategy(knowledge)

        if self.max_knowledge_tokens is None:
            return knowledge

        return await self._map_reduce_collapse(knowledge, oxy_request)

    # ------------------------------------------------------------------
    # MAP_REDUCE: recursive collapse
    # ------------------------------------------------------------------

    async def _collapse_chunk(self, chunk: str, oxy_request: OxyRequest) -> str:
        """Summarise a single chunk via the LLM."""
        prompt = self.collapse_prompt.format(text=chunk)
        temp_memory = Memory()
        temp_memory.add_message(Message.user_message(prompt))
        response = await oxy_request.call(
            callee=self.llm_model,
            arguments={"messages": temp_memory.to_dict_list()},
        )
        if response.state != OxyState.COMPLETED:
            logger.warning(
                "RAGAgent '%s': LLM call failed during MAP_REDUCE collapse (state=%s, output=%r); chunk dropped.",
                self.name,
                response.state,
                response.output,
            )
            return ""
        output = response.output
        return str(output) if output else ""

    async def _map_reduce_collapse(
            self, knowledge: str, oxy_request: OxyRequest
    ) -> str:
        """Recursively collapse *knowledge* until it fits within the token budget.

        Each round: split into chunks, summarise each concurrently, join results.
        Repeats until the combined text fits or collapse_max_retries is exhausted.
        Raises ValueError when retries are exhausted.
        """
        budget = self.max_knowledge_tokens
        text = knowledge

        for attempt in range(self.collapse_max_retries):
            if KnowledgeTruncator.fits(text, budget, self.llm_model):
                return text

            chunks = KnowledgeTruncator.split_to_chunks(
                text, budget, self.llm_model
            )
            if not chunks:
                return ""

            logger.info(
                "RAGAgent '%s': MAP_REDUCE collapse round %d — %d chunks.",
                self.name,
                attempt + 1,
                len(chunks),
            )

            results: list = await asyncio.gather(
                # Clone oxy_request per chunk so each call gets its own node ID
                # without overwriting the parent request's latest_node_ids.
                *[self._collapse_chunk(c, oxy_request.clone_with()) for c in chunks],
                return_exceptions=True,
            )
            summaries = []
            for i, r in enumerate(results):
                if isinstance(r, BaseException):
                    # Re-raise non-Exception base types (CancelledError, SystemExit, etc.)
                    if not isinstance(r, Exception):
                        raise r
                    logger.warning(
                        "RAGAgent '%s': _collapse_chunk[%d] raised %s; chunk dropped.",
                        self.name, i, type(r).__name__,
                    )
                elif r:
                    summaries.append(r)

            text = "\n\n".join(summaries)
            if not text:
                logger.warning(
                    "RAGAgent '%s': all chunk summaries returned empty in round %d.",
                    self.name,
                    attempt + 1,
                )
                return ""
            # Check after each round — the last round's result may already fit.
            if KnowledgeTruncator.fits(text, budget, self.llm_model):
                return text

        raise ValueError(
            f"RAGAgent '{self.name}': MAP_REDUCE failed to collapse knowledge "
            f"into {budget} tokens after {self.collapse_max_retries} rounds."
        )

    # ------------------------------------------------------------------
    # Pre-process override
    # ------------------------------------------------------------------

    async def _pre_process(self, oxy_request: OxyRequest) -> OxyRequest:
        """Retrieve relevant context and inject it into the request before execution."""
        oxy_request = await super()._pre_process(oxy_request)
        knowledge = await self.func_retrieve_knowledge(oxy_request)
        if knowledge is None:
            knowledge = ""
        knowledge = await self.apply_overflow_strategy_async(knowledge, oxy_request)
        oxy_request.arguments[self.knowledge_placeholder] = knowledge
        return oxy_request
