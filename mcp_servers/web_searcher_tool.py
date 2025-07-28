import asyncio
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, stop_after_attempt, wait_exponential
import time

from mcp_servers.web_fetech_tool import WebFetcherTool
from mcp_servers.google_search import (
    GoogleSearchEngine,
    WebSearchEngine,
    SearchItem
)

import logging
logger = logging.getLogger(__name__)


_WEB_SEARCHER_DESCRIPTION = """Search the web for real-time information about any topic.
This tool returns comprehensive search results with relevant information, URLs, titles, and descriptions.
If the primary search engine fails, it automatically falls back to alternative engines."""

class SearchResult(BaseModel):
    """Represents a single search result returned by a search engine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    position: int = Field(description="Position in search results")
    url: str = Field(description="URL of the search result")
    title: str = Field(default="", description="Title of the search result")
    description: str = Field(
        default="", description="Description or snippet of the search result"
    )
    source: str = Field(description="The search engine that provided this result")
    raw_content: Optional[str] = Field(
        default=None, description="Raw content from the search result page if available"
    )

    def __str__(self) -> str:
        """String representation of a search result."""
        return f"{self.title} ({self.url})"


class SearchMetadata(BaseModel):
    """Metadata about the search operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_results: int = Field(description="Total number of results found")
    language: str = Field(description="Language code used for the search")
    country: str = Field(description="Country code used for the search")


class SearchResponse:
    """Structured response from the web search tool, inheriting ToolResult."""
    def __init__(self, query=Field(description="The search query that was executed"),
                       results=Field(default_factory=list, description="List of search results"),
                       metadata=Field(default=None, description="Metadata about the search"),
                       error = None):
        self.query = query
        self.results = results
        self.metadata = metadata
        self.error = error
    @model_validator(mode="after")
    def populate_output(self) -> "SearchResponse":

        if self.error:
            return self

        """Populate output or error fields based on search results."""
        result_text = [f"Search results for '{self.query}':"]

        for i, result in enumerate(self.results, 1):
            # Add title with position number
            title = result.title.strip() or "No title"
            result_text.append(f"\n{i}. {title}")

            # Add URL with proper indentation
            result_text.append(f"   URL: {result.url}")

            # Add description if available
            if result.description.strip():
                result_text.append(f"   Description: {result.description}")

            # Add content preview if available
            if result.raw_content:
                content_preview = result.raw_content.replace("\n", " ").strip()
                result_text.append(f"   Content: {content_preview}")

        # Add metadata at the bottom if available
        if self.metadata:
            result_text.extend(
                [
                    f"\nMetadata:",
                    f"- Total results: {self.metadata.total_results}",
                    f"- Language: {self.metadata.language}",
                    f"- Country: {self.metadata.country}",
                ]
            )

        self.output = "\n".join(result_text)
        return self

class WebSearcherTool:
    """Search the web for information using various search engines."""

    name: str = "web_searcher"
    description: str = _WEB_SEARCHER_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The search query to submit to the search engine.",
            },
            "filter_year": {
                "type": "integer",
                "description": "(optional) Filter results by year (e.g., 2025).",
                "nullable": True,
            },
        },
        "required": ["query"],
    }
    output_type = 'any'

    _search_engine: dict[str, WebSearchEngine] = {
        "google": GoogleSearchEngine()
    }
    max_length: int = 20000
    # Get settings from config
    retry_delay = 10
    max_retries = 3
    # Use config values for lang and country if not specified
    lang = "en"
    country = "us"
    num_results = 5
    fetch_content = False

    content_fetcher: WebFetcherTool = WebFetcherTool()

    async def forward(
        self,
        query: str,
        filter_year: Optional[int] = None,
    ) -> SearchResponse:
        """
        Execute a Web search and return detailed search results.

        Args:
            query: The search query to submit to the search engine
        Returns:
            A structured response containing search results and metadata
        """
        search_params = {"lang": self.lang, "country": self.country}

        if filter_year is not None:
            search_params["filter_year"] = filter_year

        # Try searching with retries when all engines fail
        for retry_count in range(self.max_retries + 1):
            results = self._try_all_engines(query, self.num_results, search_params)
            if results:
                # Fetch content if requested
                if self.fetch_content:
                    results = await self._fetch_content_for_results(results)

                # Return a successful structured response
                return SearchResponse(
                    query=query,
                    results=results,
                    metadata=SearchMetadata(
                        total_results=len(results),
                        language=self.lang,
                        country=self.country,
                    ),
                )

            if retry_count < self.max_retries:
                # All engines failed, wait and retry
                res = f"All search engines failed. Waiting {self.retry_delay} seconds before retry {retry_count + 1}/{self.max_retries}..."
                logger.warning(res)
                time.sleep(self.retry_delay)
            else:
                res = f"All search engines failed after {self.max_retries} retries. Giving up."
                logger.error(res)
                # Return an error response
                return SearchResponse(
                    query=query,
                    error="All search engines failed to return results after multiple retries.",
                    results=[],
                )


    def _try_all_engines(
        self, query: str, num_results: int, search_params: Dict[str, Any]
    ) -> List[SearchResult]:
        """Try all search engines in the configured order."""
        engine_order = self._get_engine_order()
        failed_engines = []

        for engine_name in engine_order:
            engine = self._search_engine[engine_name]
            logger.info(f"🔎 Attempting search with {engine_name.capitalize()}...")
            search_items = self._perform_search_with_engine(
                engine, query, num_results, search_params
            )

            if not search_items:
                continue

            if failed_engines:
                logger.info(
                    f"Search successful with {engine_name.capitalize()} after trying: {', '.join(failed_engines)}"
                )

            # Transform search items into structured results
            return [
                SearchResult(
                    position=i + 1,
                    url=item.url,
                    title=item.title
                    or f"Result {i+1}",  # Ensure we always have a title
                    description=item.description or "",
                    source=engine_name,
                )
                for i, item in enumerate(search_items)
            ]

        if failed_engines:
            logger.error(f"All search engines failed: {', '.join(failed_engines)}")
        return []

    async def _fetch_content_for_results(
            self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """Fetch and add web content to search results."""
        if not results:
            return []

        # Create tasks for each result
        fetched_results = [await self._fetch_single_result_content(result) for result in results]

        # Explicit validation of return type
        return [
            (
                result
                if isinstance(result, SearchResult)
                else SearchResult(**result.dict())
            )
            for result in fetched_results
        ]

    async def _fetch_single_result_content(self, result: SearchResult) -> SearchResult:
        """Fetch content for a single search result."""
        if result.url:
            res = await self.content_fetcher.forward(result.url)
            content = res.text_content
            if content:
                if len(content) > self.max_length:
                    content = content[: self.max_length] + "..."
                result.raw_content = content
        return result

    def _get_engine_order(self) -> List[str]:
        """Determines the order in which to try search engines."""
        preferred = "google"
        fallbacks = []
        # Start with preferred engine, then fallbacks, then remaining engines
        engine_order = [preferred] if preferred in self._search_engine else []
        engine_order.extend(
            [
                fb
                for fb in fallbacks
                if fb in self._search_engine and fb not in engine_order
            ]
        )
        engine_order.extend([e for e in self._search_engine if e not in engine_order])

        return engine_order

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def _perform_search_with_engine(
        self,
        engine: WebSearchEngine,
        query: str,
        num_results: int,
        search_params: Dict[str, Any],
    ) -> List[SearchItem]:
        """Execute search with the given engine and parameters."""

        results = [result for result in engine.perform_search(query,
                                                              num_results=num_results,
                                                              lang=search_params.get("lang"),
                                                              country=search_params.get("country"),
                                                              filter_year=search_params.get("filter_year"),
                        )
                        ]
        return results
