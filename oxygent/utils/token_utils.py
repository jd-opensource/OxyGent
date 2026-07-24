"""Token estimation and usage parsing utilities."""

import logging
from typing import Any, Optional

from ..config import Config
from ..schemas.usage import EstimationMethod, TokenUsage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalize SDK objects to plain dicts
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dict, Pydantic model, or plain object to a flat dict.

    - dict → returned as-is
    - object with ``model_dump()`` (Pydantic v2) → call it
    - object with ``to_dict()`` (common SDK pattern) → call it
    - other objects → collect public non-callable attributes from class + instance
    """
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    # Fallback: class-level + instance-level public non-callable attrs
    logger.warning(
        "Falling back to attribute introspection for %s",
        type(obj).__name__,
    )
    result = {}
    for klass in type(obj).__mro__:
        for k, v in vars(klass).items():
            if not k.startswith("_") and not callable(v):
                result.setdefault(k, v)
    for k, v in vars(obj).items():
        if not k.startswith("_"):
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Build TokenUsage from API response
# ---------------------------------------------------------------------------


def build_token_usage(
    usage_data: Any, messages: list[dict[str, Any]], output: str, model_name: str
) -> TokenUsage:
    """Build TokenUsage from API usage data, with fallback to estimation.

    Supports all major providers' response formats:

    - OpenAI / Doubao: ``prompt_tokens``, ``completion_tokens``,
      ``prompt_tokens_details.cached_tokens``,
      ``completion_tokens_details.reasoning_tokens``
    - DeepSeek / GLM: same as OpenAI, with top-level ``reasoning_tokens``
    - Gemini (OpenAI-compat): ``prompt_tokens``, ``completion_tokens``,
      top-level ``thoughts_tokens``
    - Gemini (native): ``promptTokenCount``, ``candidatesTokenCount``,
      ``thoughtsTokenCount``

    Args:
        usage_data: Usage dict or object from API response, or None.
        messages: Input messages (for fallback estimation).
        output: Output text (for fallback estimation).
        model_name: Model name tag.

    Returns:
        TokenUsage instance.
    """
    if usage_data is None:
        return TokenEstimator.estimate_usage(messages, output, model_name)

    u = _to_dict(usage_data)

    # --- input / output tokens ---
    # OpenAI: prompt_tokens; Gemini native: promptTokenCount; Anthropic: input_tokens
    input_tokens = u.get("prompt_tokens") or u.get("promptTokenCount") or u.get("input_tokens", 0)
    output_tokens = u.get("completion_tokens") or u.get("candidatesTokenCount") or u.get("output_tokens", 0)

    # --- total tokens (API-provided) ---
    # Gemini: total = prompt + completion + thoughts (thoughts NOT included in completion)
    # OpenAI: total = prompt + completion (reasoning already included in completion)
    total_tokens = u.get("total_tokens") or 0

    # --- cached tokens ---
    # cached_input_tokens: cache read hits (chain fallback)
    # 1. prompt_tokens_details.cached_tokens        -> OpenAI / Doubao / Alibaba Cloud
    # 2. top-level cache_read_input_tokens          -> Anthropic
    # 3. top-level prompt_cache_hit_tokens          -> DeepSeek
    # 4. top-level cachedContentTokenCount          -> Gemini native
    cached_input_tokens = 0
    prompt_details = u.get("prompt_tokens_details")
    if prompt_details:
        d = _to_dict(prompt_details)
        cached_input_tokens = d.get("cached_tokens") or 0
    if not cached_input_tokens:
        cached_input_tokens = u.get("cache_read_input_tokens") or 0
    if not cached_input_tokens:
        cached_input_tokens = u.get("prompt_cache_hit_tokens") or 0
    if not cached_input_tokens:
        cached_input_tokens = u.get("cachedContentTokenCount") or 0

    # cache_creation_input_tokens: cache writes (Anthropic / Alibaba Cloud)
    cache_creation_input_tokens = u.get("cache_creation_input_tokens") or 0

    # --- reasoning / thinking tokens ---
    # Priority: completion_tokens_details.reasoning_tokens (OpenAI/Doubao)
    #          > top-level reasoning_tokens  (DeepSeek, GLM)
    #          > top-level thoughts_tokens    (Gemini OpenAI-compat)
    #          > top-level thoughtsTokenCount (Gemini native)
    reasoning_tokens = 0
    completion_details = u.get("completion_tokens_details")
    if completion_details:
        reasoning_tokens = _to_dict(completion_details).get("reasoning_tokens") or 0
    if not reasoning_tokens:
        reasoning_tokens = u.get("reasoning_tokens") or 0
    if not reasoning_tokens:
        reasoning_tokens = u.get("thoughts_tokens") or 0
    if not reasoning_tokens:
        reasoning_tokens = u.get("thoughtsTokenCount") or 0

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        reasoning_tokens=reasoning_tokens,
        model_name=model_name,
        estimation_method=EstimationMethod.EXACT,
    )


# ---------------------------------------------------------------------------
# Session-level aggregation
# ---------------------------------------------------------------------------


def aggregate_token_usage(oxy_request: Any, usage: TokenUsage) -> None:
    """Aggregate token usage to session level in shared_data.

    Args:
        oxy_request: The current OxyRequest (carries shared_data).
        usage: TokenUsage from a single LLM call.
    """
    if not Config.get_token_tracking_enabled():
        return

    metrics = oxy_request.shared_data.setdefault("_metrics", {})
    if "token_usage" not in metrics:
        metrics["token_usage"] = {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "reasoning_tokens": 0,
            "request_count": 0,
            "by_model": {},
        }

    tm = metrics["token_usage"]
    tm["total_tokens"] += usage.total_tokens
    tm["input_tokens"] += usage.input_tokens
    tm["output_tokens"] += usage.output_tokens
    tm["cached_input_tokens"] += usage.cached_input_tokens
    tm["cache_creation_input_tokens"] += usage.cache_creation_input_tokens
    tm["reasoning_tokens"] += usage.reasoning_tokens
    tm["request_count"] += 1

    model_name = usage.model_name or "unknown"
    if model_name not in tm["by_model"]:
        tm["by_model"][model_name] = {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "reasoning_tokens": 0,
            "request_count": 0,
        }

    mm = tm["by_model"][model_name]
    mm["total_tokens"] += usage.total_tokens
    mm["input_tokens"] += usage.input_tokens
    mm["output_tokens"] += usage.output_tokens
    mm["cached_input_tokens"] += usage.cached_input_tokens
    mm["cache_creation_input_tokens"] += usage.cache_creation_input_tokens
    mm["reasoning_tokens"] += usage.reasoning_tokens
    mm["request_count"] += 1


# ---------------------------------------------------------------------------
# Token estimation (fallback when API doesn't return usage)
# ---------------------------------------------------------------------------


class TokenEstimator:
    """Utility class for estimating token counts when API doesn't provide usage."""

    _encoder_cache: dict[str, object] = {}

    @classmethod
    def get_encoder(cls, model_name: str) -> Optional[object]:
        """Get tiktoken encoder with caching."""
        normalized_name = model_name.lower().strip()
        if normalized_name in cls._encoder_cache:
            return cls._encoder_cache[normalized_name]

        try:
            import tiktoken

            encoding_map = Config.get_token_encoding_map()
            encoding_name = Config.get_token_default_encoding()
            for key, enc in encoding_map.items():
                if key in normalized_name:
                    encoding_name = enc
                    break

            encoder = tiktoken.get_encoding(encoding_name)
            cls._encoder_cache[normalized_name] = encoder
            return encoder
        except ImportError:
            logger.debug("tiktoken not installed, using character-based estimation")
            return None
        except Exception as e:
            logger.debug(
                f"Failed to get tiktoken encoder for model '{normalized_name}': {e}",
                exc_info=True,
            )
            return None

    @classmethod
    def count_tokens(cls, text: str, model_name: str = "default") -> int:
        """Count tokens in text."""
        if not text:
            return 0

        encoder = cls.get_encoder(model_name)
        if encoder is not None:
            return len(encoder.encode(text))
        # Fallback: ~4 characters per token, minimum 1 to avoid zero separator cost
        return max(1, len(text) // 4)

    @classmethod
    def estimate_messages_tokens(
        cls, messages: list[dict[str, Any]], model_name: str = "default"
    ) -> int:
        """Estimate token count for a list of messages.

        Overhead values are rough approximations, not exact:
        - ~4 tokens per message for role formatting (e.g. <|im_start|>role\\n...<|im_end|>)
        - ~85 tokens per image in low-detail mode
        - ~3 tokens for conversation-level priming

        These may vary across models and API versions.
        For accurate counts, always prefer the usage data returned by the API.
        """
        total = 0
        for msg in messages:
            # ~4 tokens per message for formatting (<|start|>role\n...<|end|>)
            total += 4
            content = msg.get("content", "")
            if isinstance(content, str):
                total += cls.count_tokens(content, model_name)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total += cls.count_tokens(part.get("text", ""), model_name)
                    elif isinstance(part, dict) and part.get("type") == "image_url":
                        # ~85 tokens for image in low-detail mode
                        total += 85
        # ~3 tokens for conversation-level formatting (priming assistant reply)
        return total + 3

    @classmethod
    def estimate_usage(
        cls, messages: list[dict[str, Any]], output: str, model_name: str
    ) -> TokenUsage:
        """Estimate full request token usage."""
        has_tiktoken = cls.get_encoder(model_name) is not None
        input_tokens = cls.estimate_messages_tokens(messages, model_name)
        output_tokens = cls.count_tokens(output, model_name)
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=model_name,
            estimation_method=(
                EstimationMethod.TIKTOKEN
                if has_tiktoken
                else EstimationMethod.APPROXIMATE
            ),
        )


# ---------------------------------------------------------------------------
# RAG knowledge context management
# ---------------------------------------------------------------------------


class KnowledgeTruncator:
    """Truncate and split retrieved knowledge to fit within a token budget.

    Typical flow:
    1. Call ``fits(text, budget)`` to check whether the knowledge fits as-is.
    2. If not, call ``truncate(text, budget)`` (simple tail-cut) or
       ``split_to_chunks(text, budget)`` (chunk list for map-reduce style use).
    """

    @classmethod
    def fits(cls, text: str, token_budget: int, model_name: str = "default") -> bool:
        """Return True if *text* fits within *token_budget* tokens."""
        return TokenEstimator.count_tokens(text, model_name) <= token_budget

    @classmethod
    def truncate(
        cls,
        text: str,
        token_budget: int,
        model_name: str = "default",
    ) -> tuple[str, bool]:
        """Truncate *text* to fit within *token_budget* tokens.

        Returns:
            (truncated_text, was_truncated): The (possibly shortened) text and
            a flag indicating whether any content was dropped.

        Strategy: binary-search on character index to find the largest prefix
        that fits, then snap to the nearest paragraph/sentence boundary.
        Falls back to a hard character cut when no boundary is found.
        """
        if not text:
            return text, False

        if cls.fits(text, token_budget, model_name):
            return text, False

        # Binary search on character position for the largest fitting prefix.
        lo, hi = 0, len(text)
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if TokenEstimator.count_tokens(text[:mid], model_name) <= token_budget:
                lo = mid
            else:
                hi = mid

        # Snap to nearest paragraph or sentence boundary to avoid mid-word cuts.
        candidate = text[:lo]
        for sep in ("\n\n", "\n", ". ", "。", " "):
            idx = candidate.rfind(sep)
            if idx > lo // 2:  # don't snap back more than half the content
                candidate = candidate[: idx + len(sep)].rstrip()
                break

        truncated = candidate or text[:lo]
        return truncated, True

    @classmethod
    def split_to_chunks(
        cls,
        text: str,
        chunk_token_size: int,
        model_name: str = "default",
        separator: str = "\n\n",
    ) -> list[str]:
        """Split *text* into a list of chunks each fitting within *chunk_token_size*.

        Splits on *separator* first; if a single paragraph exceeds the budget
        it is further split on whitespace, then hard-cut as a last resort.

        Returns:
            List of non-empty string chunks.
        """
        if not text:
            return []

        if chunk_token_size <= 0:
            raise ValueError(f"chunk_token_size must be > 0, got {chunk_token_size}")

        if not separator:
            raise ValueError("separator must be a non-empty string")

        paragraphs = text.split(separator)
        chunks: list[str] = []
        current_parts: list[str] = []
        current_tokens = 0
        sep_tokens = TokenEstimator.count_tokens(separator, model_name)

        for para in paragraphs:
            if not para.strip():
                continue

            para_tokens = TokenEstimator.count_tokens(para, model_name)

            if para_tokens > chunk_token_size:
                # Para itself is oversized — flush current buffer first
                if current_parts:
                    chunks.append(separator.join(current_parts))
                    current_parts, current_tokens = [], 0
                # Hard-cut the oversized para into token-sized pieces
                chunks.extend(
                    cls._hard_cut(para, chunk_token_size, model_name)
                )
                continue

            # Account for the separator that join() will insert between parts.
            join_cost = sep_tokens if current_parts else 0
            if current_tokens + join_cost + para_tokens > chunk_token_size and current_parts:
                chunks.append(separator.join(current_parts))
                current_parts, current_tokens = [], 0

            current_parts.append(para)
            current_tokens += (sep_tokens if len(current_parts) > 1 else 0) + para_tokens

        if current_parts:
            chunks.append(separator.join(current_parts))

        return chunks

    @classmethod
    def _hard_cut(
        cls, text: str, token_budget: int, model_name: str
    ) -> list[str]:
        """Cut *text* into pieces of at most *token_budget* tokens each."""
        pieces: list[str] = []
        remaining = text
        while remaining:
            piece, _ = cls.truncate(remaining, token_budget, model_name)
            if not piece:
                # Safety: avoid infinite loop if truncate returns empty
                piece = remaining[: max(1, len(remaining) // 2)]
            pieces.append(piece)
            remaining = remaining[len(piece):]
        return pieces
