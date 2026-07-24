"""Unit tests for RAGAgent — overflow strategies and MAP_REDUCE collapse."""

import asyncio
import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.agents.rag_agent import OverflowStrategy, RAGAgent
from oxygent.schemas import OxyRequest
from oxygent.utils.token_utils import TokenEstimator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def approx_tokens(text: str) -> int:
    return TokenEstimator.count_tokens(text, "default")


# ---------------------------------------------------------------------------
# DummyMAS
# ---------------------------------------------------------------------------

class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.background_tasks = {}
        self.vearch_client = AsyncMock()
        self.es_client = AsyncMock()

    def add_background_task(self, trace_id, task):
        self.background_tasks.setdefault(trace_id, set()).add(task)
        task.add_done_callback(
            lambda t: self.background_tasks.get(trace_id, set()).discard(t)
        )

    @staticmethod
    def is_agent(name):
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patched_config(monkeypatch):
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_agent_llm_model",
        lambda: "mock_llm",
        raising=True,
    )
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_agent_prompt",
        lambda: "",
        raising=True,
    )
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_vearch_config",
        lambda: {},
        raising=True,
    )


def make_request(mas):
    req = OxyRequest(
        arguments={"query": "hello"},
        caller="user",
        caller_category="user",
    )
    req.mas = mas
    return req


# ---------------------------------------------------------------------------
# Construction & prompt injection
# ---------------------------------------------------------------------------

def test_default_prompt_injected():
    agent = RAGAgent(name="rag", func_retrieve_knowledge=AsyncMock())
    assert "${knowledge}" in agent.prompt


def test_custom_prompt_preserved():
    agent = RAGAgent(
        name="rag",
        prompt="Custom prompt ${info}",
        func_retrieve_knowledge=AsyncMock(),
    )
    assert agent.prompt == "Custom prompt ${info}"


def test_custom_placeholder_in_prompt():
    agent = RAGAgent(
        name="rag",
        knowledge_placeholder="context",
        func_retrieve_knowledge=AsyncMock(),
    )
    assert "${context}" in agent.prompt


def test_empty_knowledge_placeholder_raises():
    with pytest.raises(Exception):
        RAGAgent(name="r", func_retrieve_knowledge=AsyncMock(), knowledge_placeholder="")


# ---------------------------------------------------------------------------
# collapse_prompt validation
# ---------------------------------------------------------------------------

def test_default_collapse_prompt_valid():
    agent = RAGAgent(name="r", func_retrieve_knowledge=AsyncMock())
    assert "{text}" in agent.collapse_prompt


def test_valid_custom_collapse_prompt():
    agent = RAGAgent(
        name="r",
        func_retrieve_knowledge=AsyncMock(),
        collapse_prompt="Please summarize: {text}",
    )
    assert agent.collapse_prompt == "Please summarize: {text}"


def test_collapse_prompt_missing_text_raises():
    with pytest.raises(Exception, match="\\{text\\}"):
        RAGAgent(
            name="r",
            func_retrieve_knowledge=AsyncMock(),
            collapse_prompt="Summarize the above.",
        )


def test_collapse_prompt_extra_placeholder_raises():
    with pytest.raises(Exception):
        RAGAgent(
            name="r",
            func_retrieve_knowledge=AsyncMock(),
            collapse_prompt="Summarize {text} for {audience}.",
        )


# ---------------------------------------------------------------------------
# knowledge_fits
# ---------------------------------------------------------------------------

def test_knowledge_fits_no_budget():
    agent = RAGAgent(name="r", func_retrieve_knowledge=AsyncMock())
    assert agent.knowledge_fits("any text" * 1000) is True


def test_knowledge_fits_within_budget():
    agent = RAGAgent(name="r", func_retrieve_knowledge=AsyncMock(), max_knowledge_tokens=500)
    assert agent.knowledge_fits("hello") is True


def test_knowledge_fits_exceeds_budget():
    agent = RAGAgent(name="r", func_retrieve_knowledge=AsyncMock(), max_knowledge_tokens=10)
    assert agent.knowledge_fits("word " * 100) is False


# ---------------------------------------------------------------------------
# apply_overflow_strategy — sync strategies
# ---------------------------------------------------------------------------

class TestOverflowStrategy:
    def _agent(self, strategy, budget=50):
        return RAGAgent(
            name="r",
            func_retrieve_knowledge=AsyncMock(),
            max_knowledge_tokens=budget,
            overflow_strategy=strategy,
        )

    def test_ignore_returns_full_text(self):
        agent = self._agent(OverflowStrategy.IGNORE)
        long_text = "word " * 200
        assert agent.apply_overflow_strategy(long_text) == long_text

    def test_raise_on_overflow(self):
        agent = self._agent(OverflowStrategy.RAISE, budget=5)
        with pytest.raises(ValueError, match="token budget"):
            agent.apply_overflow_strategy("word " * 100)

    def test_raise_no_error_when_fits(self):
        agent = self._agent(OverflowStrategy.RAISE, budget=1000)
        assert agent.apply_overflow_strategy("short text") == "short text"

    def test_truncate_shortens_text(self):
        agent = self._agent(OverflowStrategy.TRUNCATE, budget=20)
        result = agent.apply_overflow_strategy("token " * 200)
        assert approx_tokens(result) <= 20

    def test_truncate_leaves_short_text_unchanged(self):
        agent = self._agent(OverflowStrategy.TRUNCATE, budget=1000)
        assert agent.apply_overflow_strategy("short text") == "short text"

    def test_no_budget_returns_unchanged(self):
        agent = RAGAgent(name="r", func_retrieve_knowledge=AsyncMock())
        text = "word " * 500
        assert agent.apply_overflow_strategy(text) == text

    def test_map_reduce_on_sync_method_raises_runtime_error(self):
        """apply_overflow_strategy (sync) raises RuntimeError for MAP_REDUCE."""
        agent = RAGAgent(
            name="r",
            func_retrieve_knowledge=AsyncMock(),
            max_knowledge_tokens=10,
            overflow_strategy=OverflowStrategy.MAP_REDUCE,
        )
        with pytest.raises(RuntimeError, match="async"):
            agent.apply_overflow_strategy("word " * 100)


# ---------------------------------------------------------------------------
# _pre_process integration
# ---------------------------------------------------------------------------

class TestPreProcess:
    def _make_agent(self, retrieve_fn, budget=None, strategy=OverflowStrategy.TRUNCATE):
        agent = RAGAgent(
            name="rag",
            func_retrieve_knowledge=retrieve_fn,
            max_knowledge_tokens=budget,
            overflow_strategy=strategy,
        )
        mas = DummyMAS()
        agent.set_mas(mas)
        return agent

    @pytest.mark.asyncio
    async def test_knowledge_injected(self):
        async def retrieve(req):
            return "some knowledge"

        agent = self._make_agent(retrieve)
        req = make_request(agent.mas)
        result = await agent._pre_process(req)
        assert result.arguments["knowledge"] == "some knowledge"

    @pytest.mark.asyncio
    async def test_none_retrieval_becomes_empty_string(self):
        async def retrieve(req):
            return None

        agent = self._make_agent(retrieve)
        req = make_request(agent.mas)
        result = await agent._pre_process(req)
        assert result.arguments["knowledge"] == ""

    @pytest.mark.asyncio
    async def test_truncate_applied(self):
        async def retrieve(req):
            return "word " * 200

        agent = self._make_agent(retrieve, budget=30, strategy=OverflowStrategy.TRUNCATE)
        req = make_request(agent.mas)
        result = await agent._pre_process(req)
        assert approx_tokens(result.arguments["knowledge"]) <= 30

    @pytest.mark.asyncio
    async def test_raise_propagates(self):
        async def retrieve(req):
            return "word " * 200

        agent = self._make_agent(retrieve, budget=10, strategy=OverflowStrategy.RAISE)
        req = make_request(agent.mas)
        with pytest.raises(ValueError, match="token budget"):
            await agent._pre_process(req)

    @pytest.mark.asyncio
    async def test_ignore_passes_full_text(self):
        long_text = "word " * 300

        async def retrieve(req):
            return long_text

        agent = self._make_agent(retrieve, budget=10, strategy=OverflowStrategy.IGNORE)
        req = make_request(agent.mas)
        result = await agent._pre_process(req)
        assert result.arguments["knowledge"] == long_text

    @pytest.mark.asyncio
    async def test_custom_placeholder(self):
        async def retrieve(req):
            return "ctx"

        agent = RAGAgent(
            name="rag",
            func_retrieve_knowledge=retrieve,
            knowledge_placeholder="ctx_data",
        )
        mas = DummyMAS()
        agent.set_mas(mas)
        result = await agent._pre_process(make_request(mas))
        assert result.arguments["ctx_data"] == "ctx"


# ---------------------------------------------------------------------------
# MAP_REDUCE collapse
# ---------------------------------------------------------------------------

class TestMapReduceCollapse:
    def _make_agent(self, budget, collapse_fn=None, max_retries=3):
        agent = RAGAgent(
            name="mr",
            func_retrieve_knowledge=AsyncMock(return_value=""),
            max_knowledge_tokens=budget,
            overflow_strategy=OverflowStrategy.MAP_REDUCE,
            collapse_max_retries=max_retries,
        )
        mas = DummyMAS()
        agent.set_mas(mas)
        if collapse_fn:
            agent._collapse_chunk = collapse_fn
        return agent

    @pytest.mark.asyncio
    async def test_already_fits_no_llm_call(self):
        called = []

        async def never_called(chunk, req):
            called.append(chunk)
            return "summary"

        agent = self._make_agent(budget=1000, collapse_fn=never_called)
        req = make_request(agent.mas)
        result = await agent._map_reduce_collapse("short knowledge", req)
        assert result == "short knowledge"
        assert called == []

    @pytest.mark.asyncio
    async def test_single_round_converges(self):
        summaries = []

        async def summarise(chunk, req):
            s = f"S{len(summaries)}"
            summaries.append(s)
            return s

        agent = self._make_agent(budget=100, collapse_fn=summarise)
        req = make_request(agent.mas)
        result = await agent._map_reduce_collapse("word " * 500, req)
        assert approx_tokens(result) <= 100
        assert len(summaries) >= 1

    @pytest.mark.asyncio
    async def test_multi_round_converges(self):
        round_counts = [0]

        async def verbose_summary(chunk, req):
            round_counts[0] += 1
            if round_counts[0] <= 3:
                return "word " * 20
            return "tiny"

        agent = self._make_agent(budget=10, collapse_fn=verbose_summary, max_retries=5)
        req = make_request(agent.mas)
        result = await agent._map_reduce_collapse("word " * 300, req)
        assert approx_tokens(result) <= 10
        assert round_counts[0] > 1

    @pytest.mark.asyncio
    async def test_max_retries_1_converges_without_raise(self):
        """Single retry: summary fits → return, do not raise ValueError."""

        async def small_summary(chunk, req):
            return "ok"

        agent = self._make_agent(budget=100, collapse_fn=small_summary, max_retries=1)
        req = make_request(agent.mas)
        result = await agent._map_reduce_collapse("word " * 300, req)
        assert approx_tokens(result) <= 100

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self):
        async def always_large(chunk, req):
            return "word " * 100

        agent = self._make_agent(budget=5, collapse_fn=always_large, max_retries=2)
        req = make_request(agent.mas)
        with pytest.raises(ValueError, match="MAP_REDUCE failed"):
            await agent._map_reduce_collapse("word " * 200, req)

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        agent = self._make_agent(budget=50)
        req = make_request(agent.mas)
        assert await agent._map_reduce_collapse("", req) == ""

    @pytest.mark.asyncio
    async def test_all_empty_summaries_returns_empty(self):
        async def empty_summarise(chunk, req):
            return ""

        agent = self._make_agent(budget=10, collapse_fn=empty_summarise, max_retries=3)
        req = make_request(agent.mas)
        result = await agent._map_reduce_collapse("word " * 100, req)
        assert result == ""

    @pytest.mark.asyncio
    async def test_failed_chunk_dropped(self):
        call_count = [0]

        async def fake_collapse(chunk, req):
            call_count[0] += 1
            return "" if call_count[0] == 1 else "summary"

        agent = self._make_agent(budget=100, collapse_fn=fake_collapse, max_retries=3)
        req = make_request(agent.mas)
        text = "\n\n".join(["word " * 50] * 2)
        result = await agent._map_reduce_collapse(text, req)
        assert "summary" in result
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_chunks_summarized_concurrently(self):
        start_times = []
        end_times = []

        async def slow_summarise(chunk, req):
            start_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.05)
            end_times.append(asyncio.get_event_loop().time())
            return "s"

        agent = self._make_agent(budget=100, collapse_fn=slow_summarise)
        req = make_request(agent.mas)
        text = "\n\n".join(["word " * 50] * 3)
        await agent._map_reduce_collapse(text, req)
        assert len(start_times) >= 2
        assert max(start_times) < min(end_times)

    @pytest.mark.asyncio
    async def test_map_reduce_no_budget_passthrough(self):
        """MAP_REDUCE + no budget → knowledge passed unchanged."""

        async def retrieve(req):
            return "word " * 50

        agent = RAGAgent(
            name="mr",
            func_retrieve_knowledge=retrieve,
            overflow_strategy=OverflowStrategy.MAP_REDUCE,
        )
        mas = DummyMAS()
        agent.set_mas(mas)
        result = await agent._pre_process(make_request(mas))
        assert result.arguments["knowledge"] == "word " * 50

    @pytest.mark.asyncio
    async def test_pre_process_uses_map_reduce(self):
        collapse_calls = []

        async def summarise(chunk, req):
            collapse_calls.append(chunk)
            return "ok"

        async def retrieve(req):
            return "word " * 200

        agent = RAGAgent(
            name="mr",
            func_retrieve_knowledge=retrieve,
            max_knowledge_tokens=10,
            overflow_strategy=OverflowStrategy.MAP_REDUCE,
            collapse_max_retries=3,
        )
        mas = DummyMAS()
        agent.set_mas(mas)
        agent._collapse_chunk = summarise
        result = await agent._pre_process(make_request(mas))
        assert approx_tokens(result.arguments["knowledge"]) <= 10
        assert len(collapse_calls) >= 1
