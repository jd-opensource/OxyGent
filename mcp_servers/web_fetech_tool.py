from typing import Optional
from markitdown._base_converter import DocumentConverterResult
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.processors.pdf import PDFContentScrapingStrategy

from mcp_servers.markitdown_tool import MarkitdownConverter
import logging
logger = logging.getLogger(__name__)


_WEB_FETCHER_DESCRIPTION = """Visit a webpage at a given URL and return its text. """


async def fetch_url(url: str, converter: Optional[MarkitdownConverter] = None) -> Optional[DocumentConverterResult]:
    try:
        async with AsyncWebCrawler() as crawler:
            if '/pdf' in url or '.pdf' in url:
                result = await crawler.arun(url=url,
                                            config=CrawlerRunConfig(
                                                scraping_strategy=PDFContentScrapingStrategy(
                                                    extract_images=False,
                                                    save_images_locally=False,
                                                    batch_size=5,
                                                ),
                                                page_timeout=60000)
                                            )
            else:
                result = await crawler.arun(url=url,
                                            config=CrawlerRunConfig(
                                                page_timeout=60000)
                                            )

            if result:
                markdown = result.markdown

                res = DocumentConverterResult(
                    markdown=markdown,
                    title=f"Fetched content from {url}",
                )
                return res
            else:
                if converter:
                    res = converter.convert(result.html)
                    return res
    except Exception as e:
        logger.error(f"Error fetching URL: {url}, Error: {e}")
        return None

class WebFetcherTool:
    name = "web_fetcher"
    description = _WEB_FETCHER_DESCRIPTION
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The relative or absolute url of the webpage to visit."
            }
        },
        "required": ["url"],
        "additionalProperties": False
    }
    output_type = "any"

    converter = MarkitdownConverter(
        use_llm=False,
        timeout=30,
    )

    async def forward(self, url: str) -> Optional[DocumentConverterResult]:
        """Fetch content from a given URL."""

        # try to use asyncio to fetch the URL content
        try:
            res = await fetch_url(url, self.converter)
            if not res:
                logger.error(f"Failed to fetch content from {url}")
                res = DocumentConverterResult(
                    markdown=f"Failed to fetch content from {url}",
                    title="Error",
                )
        except Exception as e:
            logger.error(f"Error fetching content: {e}")
            res = DocumentConverterResult(
                markdown=f"Failed to fetch content: {e}",
                title="Error",
            )
        return res

