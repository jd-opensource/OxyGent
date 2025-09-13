import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import Field

from oxygent.oxy import FunctionHub

logger = logging.getLogger(__name__)

# Global browser context for reuse
_browser_context = None

browser_automation_tools = FunctionHub(name="browser_automation_tools")


async def _get_browser_context():
    """Get or create a browser context for reuse."""
    global _browser_context

    if _browser_context is None:
        try:
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            _browser_context = await browser.new_context(
                user_agent="OxyGent Browser Agent 1.0",
                viewport={"width": 1280, "height": 720},
            )
        except ImportError:
            raise ImportError(
                "Playwright not installed. Please install using: pip install playwright && playwright install"
            )
        except Exception as e:
            logger.error(f"Failed to initialize browser context: {e}")
            raise

    return _browser_context


@browser_automation_tools.tool(
    "Navigate to a URL and return basic page information including title and URL"
)
async def navigate_to_url(
    url: str = Field(
        description="URL to navigate to (must include http:// or https://)"
    ),
) -> str:
    """Navigate to a URL and return page information."""
    try:
        context = await _get_browser_context()
        page = await context.new_page()

        # Navigate with timeout
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Get page information
        title = await page.title()
        current_url = page.url

        await page.close()

        result = {
            "status": "success",
            "title": title,
            "url": current_url,
            "message": f"Successfully navigated to {url}",
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_result = {
            "status": "error",
            "url": url,
            "error": str(e),
            "message": f"Failed to navigate to {url}",
        }
        logger.error(f"Navigation error: {e}")
        return json.dumps(error_result, ensure_ascii=False, indent=2)


@browser_automation_tools.tool(
    "Extract text content from a webpage using CSS selectors"
)
async def extract_page_content(
    url: str = Field(description="URL to extract content from"),
    selector: str = Field(
        description="CSS selector for content extraction", default="body"
    ),
    max_length: int = Field(
        description="Maximum length of extracted content", default=5000
    ),
) -> str:
    """Extract text content from a webpage."""
    try:
        context = await _get_browser_context()
        page = await context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Extract content based on selector
        content = await page.text_content(selector)

        await page.close()

        if content:
            # Truncate if too long
            if len(content) > max_length:
                content = content[:max_length] + "..."

            result = {
                "status": "success",
                "url": url,
                "selector": selector,
                "content": content.strip(),
                "length": len(content),
            }
        else:
            result = {
                "status": "warning",
                "url": url,
                "selector": selector,
                "content": "",
                "message": "No content found with the specified selector",
            }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_result = {
            "status": "error",
            "url": url,
            "selector": selector,
            "error": str(e),
            "message": f"Failed to extract content from {url}",
        }
        logger.error(f"Content extraction error: {e}")
        return json.dumps(error_result, ensure_ascii=False, indent=2)


@browser_automation_tools.tool(
    "Take a screenshot of a webpage and save it to specified path"
)
async def take_screenshot(
    url: str = Field(description="URL to take screenshot of"),
    output_path: str = Field(
        description="Path to save screenshot (relative to current directory)",
        default="screenshot.png",
    ),
    full_page: bool = Field(
        description="Whether to capture full page or just viewport", default=False
    ),
) -> str:
    """Take a screenshot of a webpage."""
    try:
        context = await _get_browser_context()
        page = await context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Ensure output directory exists
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Take screenshot
        await page.screenshot(path=str(output_path_obj), full_page=full_page)

        await page.close()

        result = {
            "status": "success",
            "url": url,
            "screenshot_path": str(output_path_obj),
            "full_page": full_page,
            "message": f"Screenshot saved to {output_path_obj}",
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_result = {
            "status": "error",
            "url": url,
            "output_path": output_path,
            "error": str(e),
            "message": f"Failed to take screenshot of {url}",
        }
        logger.error(f"Screenshot error: {e}")
        return json.dumps(error_result, ensure_ascii=False, indent=2)


@browser_automation_tools.tool("Get all links from a webpage with optional filtering")
async def get_page_links(
    url: str = Field(description="URL to extract links from"),
    filter_domain: bool = Field(
        description="Whether to only return links from the same domain", default=True
    ),
    max_links: int = Field(description="Maximum number of links to return", default=50),
) -> str:
    """Extract all links from a webpage."""
    try:
        context = await _get_browser_context()
        page = await context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Get all links
        links = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(link => ({
                    text: link.textContent.trim(),
                    href: link.href,
                    title: link.title || ''
                }));
            }
        """)

        await page.close()

        # Filter links if requested
        if filter_domain:
            from urllib.parse import urlparse

            base_domain = urlparse(url).netloc
            links = [
                link for link in links if urlparse(link["href"]).netloc == base_domain
            ]

        # Limit number of links
        links = links[:max_links]

        result = {
            "status": "success",
            "url": url,
            "total_links": len(links),
            "filter_domain": filter_domain,
            "links": links,
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_result = {
            "status": "error",
            "url": url,
            "error": str(e),
            "message": f"Failed to extract links from {url}",
        }
        logger.error(f"Link extraction error: {e}")
        return json.dumps(error_result, ensure_ascii=False, indent=2)


@browser_automation_tools.tool("Fill out a form on a webpage and optionally submit it")
async def fill_form(
    url: str = Field(description="URL of the page with the form"),
    form_data: str = Field(
        description="JSON string with form field data (selector: value pairs)"
    ),
    submit: bool = Field(
        description="Whether to submit the form after filling", default=False
    ),
    submit_selector: str = Field(
        description="CSS selector for submit button",
        default="input[type='submit'], button[type='submit']",
    ),
) -> str:
    """Fill out a form on a webpage."""
    try:
        context = await _get_browser_context()
        page = await context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Parse form data
        try:
            data = json.loads(form_data)
        except json.JSONDecodeError:
            raise ValueError("form_data must be valid JSON")

        filled_fields = []

        # Fill form fields
        for selector, value in data.items():
            try:
                await page.fill(selector, str(value))
                filled_fields.append(
                    {"selector": selector, "value": value, "status": "success"}
                )
            except Exception as field_error:
                filled_fields.append(
                    {
                        "selector": selector,
                        "value": value,
                        "status": "error",
                        "error": str(field_error),
                    }
                )

        result = {
            "status": "success",
            "url": url,
            "filled_fields": filled_fields,
            "submitted": False,
        }

        # Submit form if requested
        if submit:
            try:
                await page.click(submit_selector)
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                result["submitted"] = True
                result["message"] = "Form filled and submitted successfully"
            except Exception as submit_error:
                result["submit_error"] = str(submit_error)
                result["message"] = "Form filled but submission failed"
        else:
            result["message"] = "Form filled successfully (not submitted)"

        await page.close()

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_result = {
            "status": "error",
            "url": url,
            "error": str(e),
            "message": f"Failed to fill form on {url}",
        }
        logger.error(f"Form filling error: {e}")
        return json.dumps(error_result, ensure_ascii=False, indent=2)


async def cleanup_browser_context():
    """Cleanup browser context when shutting down."""
    global _browser_context
    if _browser_context:
        try:
            await _browser_context.close()
            _browser_context = None
        except Exception as e:
            logger.error(f"Error cleaning up browser context: {e}")
