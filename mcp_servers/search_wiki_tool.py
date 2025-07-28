from pydantic import Field
import requests
import datetime
import time
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


def get_wikipedia_summary(query, max_retries=5):
    """
    Get a summary from Wikipedia for a given query, with retry mechanism

    Parameters:
    query - search term
    max_retries - maximum retry attempts (default 3)

    Returns:
    Success: summary string
    Failure: error message string
    """
    # User agent identification
    HEADERS = {"User-Agent": "WikiSearch/1.0 (example@domain.com)"}
    API_URL = "https://en.wikipedia.org/w/api.php"  # Changed to English Wikipedia

    for attempt in range(max_retries):
        try:
            # Retry delay (increases with attempts)
            if attempt > 0:
                time.sleep(1 + attempt)  # Retry delays: 2s, 3s, ...

            # Step 1: Search for topics
            search_params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "utf8": 1,
            }
            response = requests.get(API_URL, params=search_params,
                                    headers=HEADERS, timeout=15)
            response.raise_for_status()  # Check for HTTP errors
            data = response.json()

            # Process search results
            if "query" not in data or "search" not in data["query"] or not data["query"]["search"]:
                return f"No Wikipedia pages found related to '{query}'"

            # Take the first result
            title = data["query"]["search"][0]["title"]

            # Step 2: Get page summary
            page_params = {
                "action": "query",
                "format": "json",
                "prop": "extracts|info",
                "inprop": "url",
                "titles": title,
                "exintro": 1,
                "explaintext": 1,
                "utf8": 1,
            }
            response = requests.get(API_URL, params=page_params,
                                    headers=HEADERS, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Process page data
            pages = data.get("query", {}).get("pages", {})
            page_data = next(iter(pages.values()), None)

            if not page_data or "extract" not in page_data or not page_data["extract"]:
                return f"Page '{title}' found but no summary available"

            # Successfully retrieved summary
            summary = page_data["extract"].strip()
            url = page_data.get("fullurl", "")
            return f"{title}:\n{summary[:500]}...\n\nRead full article: {url}"

        except requests.exceptions.RequestException as e:
            error_msg = f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}"
            print(error_msg)
            if attempt == max_retries - 1:
                final_error = f"Failed to retrieve information: {str(e)}" + \
                              "\nPossible reasons: Network issue or Wikipedia service temporarily unavailable"
                return final_error

        except Exception as e:
            return f"Unexpected error while processing data: {str(e)}"

    return "Unknown error"  # Safety return (shouldn't be reached)


def get_visual_editor_revisions(
        page_title: str,
        editor_tag: str = "visualeditor",
        start_date: datetime.datetime = None,
        end_date: datetime.datetime = None,
        max_retries: int = 5,
        retry_delay: float = 2.0
) -> int:
    """
    Count visual editor revisions for a Wikipedia page within a specified time range

    Parameters:
    page_title: Wikipedia page title (e.g. "Penguin")
    editor_tag: Tag to identify visual editor revisions
    start_date: Start of time range (default: earliest possible)
    end_date: End of time range (default: current UTC time)
    max_retries: Maximum API request retries
    retry_delay: Initial retry delay in seconds

    Returns: Count of revisions matching criteria
    """
    # Set default date ranges
    start_dt = start_date or datetime.datetime(2001, 1, 1)  # Wikipedia launch date
    end_dt = end_date or datetime.datetime.utcnow()

    # Prepare base API parameters
    base_params = {
        'action': 'query',
        'prop': 'revisions',
        'titles': page_title,
        'rvprop': 'timestamp|tags',
        'rvlimit': 'max',  # API max is 500 per request
        'rvdir': 'newer',
        'format': 'json',
        'rvstart': start_dt.isoformat() + 'Z',
        'rvend': end_dt.isoformat() + 'Z'
    }

    # Set user agent
    headers = {
        'User-Agent': 'RevisionCounter/1.0 (contact@example.com)',
        'Accept': 'application/json'
    }

    revision_count = 0
    total_revisions_processed = 0
    api_calls = 0
    has_more = True
    params = base_params.copy()

    # 根据标签参数调整日志信息
    if editor_tag:
        logger.info(
            f"Querying '{editor_tag}' revisions for '{page_title}' between {params['rvstart']} and {params['rvend']}")
    else:
        logger.info(f"Querying ALL revisions for '{page_title}' between {params['rvstart']} and {params['rvend']}")

    while has_more:
        retry_count = 0
        delay = retry_delay
        data = None

        while retry_count <= max_retries:
            try:
                api_calls += 1
                url = f"https://en.wikipedia.org/w/api.php?{urlencode(params)}"
                logger.debug(f"API request #{api_calls}: {url}")
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                break  # Exit retry loop on success

            except requests.exceptions.RequestException as e:
                retry_count += 1
                if retry_count > max_retries:
                    raise RuntimeError(f"API request failed after {max_retries} retries") from e

                logger.warning(f"Retrying in {delay:.1f}s (attempt {retry_count}/{max_retries})")
                time.sleep(delay)
                delay *= 1.1  # Exponential backoff

        # Handle API errors
        if 'error' in data:
            raise RuntimeError(f"API error: {data['error']['info']}")

        # Ensure valid response structure
        pages = data.get('query', {}).get('pages', {})
        if not pages:
            raise RuntimeError("No page data found in API response")

        # Process all pages (handle normalization)
        for page_id, page in pages.items():
            # Handle redirects or missing pages
            if page_id == '-1' or 'missing' in page:
                raise RuntimeError(f"Page '{page_title}' does not exist")

            # Handle normalized title
            if 'redirected' in page or 'normalized' in data.get('query', {}):
                actual_title = page.get('title', page_title)
                logger.info(f"Redirected to actual page title: {actual_title}")

            # Process revisions
            if 'revisions' in page:
                batch_revisions = page['revisions']
                batch_size = len(batch_revisions)
                total_revisions_processed += batch_size

                # Check if we've reached the end of the requested date range
                if editor_tag:  # 过滤特定标签
                    if batch_revisions:
                        first_rev_date = batch_revisions[0]['timestamp']
                        last_rev_date = batch_revisions[-1]['timestamp']
                        logger.info(f"Batch #{api_calls}: Processing {batch_size} revisions "
                                    f"({first_rev_date} to {last_rev_date})")

                # Count visual editor tags in this batch
                for revision in batch_revisions:
                    if editor_tag in revision.get('tags', []):
                        revision_count += 1
            else:
                logger.info(f"No revisions found in batch #{api_calls}")

        logger.info(
            f"After batch #{api_calls}: {revision_count} VE edits found (total: {total_revisions_processed} revs)")

        # Check continuation - stop if no more results
        if 'continue' in data and 'rvcontinue' in data['continue']:
            params['rvcontinue'] = data['continue']['rvcontinue']
            logger.info(f"More revisions available, continuing with rvcontinue={params['rvcontinue']}")
        else:
            has_more = False
            logger.info("Reached end of revision history")

    logger.info(f"Completed {api_calls} API requests")
    logger.info(f"Found {revision_count} {editor_tag} editor revisions between "
                f"{start_dt.strftime('%Y-%m-%d')} and {end_dt.strftime('%Y-%m-%d')}")
    return revision_count


from oxygent import oxy
wiki = oxy.FunctionHub(name="wikipedia_tool", timeout=900)
_WIKI_REVISIONS_DESCRIPTION = """Fetches all Wikipedia page revisions for a specified entity within a given month/year, returning revision URLs, timestamps, and revision IDs."""
_WIKI_SUMMARY_DESCRIPTION = """Retrieves a formatted Wikipedia summary (title, excerpt, and link) for any search query. Returns error messages for failed lookups."""


@wiki.tool(description=_WIKI_SUMMARY_DESCRIPTION)
def get_wikipedia_summary_api(
    query: str = Field(description="The research query to explore."),
):
    return get_wikipedia_summary(query)


if __name__ == "__main__":
    get_wikipedia_summary(" Space Mountain roller coaster at Magic Kingdom")

