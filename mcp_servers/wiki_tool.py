import datetime
import time
import requests
import re
import os
import html
import logging
from typing import List, Dict, Optional, Callable, Union
from urllib.parse import urlencode
import json
from pydantic import Field
from pydantic.fields import FieldInfo
from oxygent import oxy
from openai import OpenAI


wiki_tools = oxy.FunctionHub(name="wikipedia_tools", timeout=900)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_default_value(value):
    return value.default if isinstance(value, FieldInfo) else value


# Helper function: Date conversion
def to_iso_format(dt_input: Optional[Union[str, datetime.datetime]],
                  default_time: datetime.datetime) -> str:
    """Convert input to ISO format string required by the API"""
    dt_input = get_default_value(dt_input)
    if dt_input is None:
        dt = default_time
    elif isinstance(dt_input, str):
        # Handle different date string formats
        formats = [
            "%Y-%m-%d %H:%M:%S",  # Format with time: "2020-01-01 12:00:00"
            "%Y-%m-%dT%H:%M:%S",  # ISO format without timezone: "2020-01-01T12:00:00"
            "%Y-%m-%d"  # Simple date format: "2020-01-01"
        ]
        dt = None
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(dt_input, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            raise ValueError(f"Unsupported date format: {dt_input}")
    else:
        dt = dt_input

    # Ensure the time object is in UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    # Use strftime to convert to the API required format
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def api_request(params: Dict, max_retries: int = 5, retry_delay: float = 2.0,
                language: str = "en") -> Dict:
    """
    Enhanced API request function that automatically handles title issues

    Automatic handling scenarios:
    1. When the original query returns page does not exist, automatically search for the best matching title
    2. Maintain the original network error retry mechanism

    Parameters:
    params: API request parameters
    max_retries: Maximum number of retries (only for network errors)
    retry_delay: Initial retry delay
    language: Wikipedia language version

    Returns: API response data
    """
    headers = {
        'User-Agent': 'WikipediaTool/1.0 (contact@example.com)',
        'Accept': 'application/json'
    }

    retry_count = 0
    delay = retry_delay
    original_titles = params.get('titles', '')
    title_retried = False  # Flag to mark whether title retry has been performed

    while retry_count <= max_retries:
        try:
            url = f"https://{language}.wikipedia.org/w/api.php?{urlencode(params)}"
            logger.debug(f"API request: {url}")
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            # Check if the page does not exist
            pages = data.get('query', {}).get('pages', {})
            if pages and any('missing' in page for page in pages.values()) and not title_retried:
                logger.warning(f"Page does not exist: {original_titles}, attempting to search for alternative title")

                # Search for the best alternative title
                search_params = {
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": original_titles,
                    "srlimit": 1,
                    "utf8": 1
                }
                search_url = f"https://{language}.wikipedia.org/w/api.php?{urlencode(search_params)}"
                search_response = requests.get(search_url, headers=headers, timeout=60)
                search_response.raise_for_status()
                search_data = search_response.json()

                # Get the best matching title
                if search_results := search_data.get('query', {}).get('search', []):
                    best_title = search_results[0]['title']
                    logger.info(f"Alternative title found: {best_title}")
                    params['titles'] = best_title
                    title_retried = True
                    continue  # Retry the request with the new title

            return data

        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            retry_count += 1
            if retry_count > max_retries:
                raise RuntimeError(f"API request failed after {max_retries} retries") from e

            logger.warning(f"Retrying in {delay:.1f}s (attempt {retry_count}/{max_retries})")
            time.sleep(delay)
            delay *= 1.1  # Exponential backoff


def get_wikipedia_revisions(
        page_title: str,
        start_date: Optional[Union[str, datetime.datetime]] = None,
        end_date: Optional[Union[str, datetime.datetime]] = None,
        revision_properties: List[str] = None,
        tags: Union[List[str], str, None] = None,
        user: str = None,
        exclude_user: str = None,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        language: str = "en",
        need_more: bool = True
) -> List[Dict]:
    # Handle tags parameter
    tags = get_default_value(tags)
    tag_list = ['']
    if tags:
        if isinstance(tags, str):
            tag_list = [tags]
        else:
            tag_list = tags

    # Set default date range
    start_str = to_iso_format(start_date, datetime.datetime(1991, 1, 1, tzinfo=datetime.timezone.utc))
    end_str = to_iso_format(end_date, datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc))

    # Prepare basic API parameters - ensure only rvtag parameter is included
    base_params = {
        'action': 'query',
        'prop': 'revisions',
        'titles': page_title,
        'rvlimit': 'max',
        'rvdir': 'newer',
        'format': 'json',
        'rvstart': start_str,
        'rvend': end_str
    }

    # Ensure tags property is requested
    revision_properties = get_default_value(revision_properties)
    if revision_properties:
        base_properties = revision_properties.copy()
        if 'timestamp' not in base_properties:
            base_properties += ['timestamp']
    else:
        base_properties = ['timestamp', 'user', 'comment', 'ids', 'size']

    if 'tags' not in base_properties:
        base_properties.append('tags')

    base_params['rvprop'] = '|'.join(base_properties)

    # Add user filtering
    user = get_default_value(user)
    exclude_user = get_default_value(exclude_user)
    if user:
        base_params['rvuser'] = user
    if exclude_user:
        base_params['rvexcludeuser'] = exclude_user

    # Determine filtering mode
    filter_mode = []
    if tags:
        filter_mode.append(f"tags={tags}")
    if user:
        filter_mode.append(f"user={user}")
    if exclude_user:
        filter_mode.append(f"exclude_user={exclude_user}")

    filter_str = " with filters: " + ", ".join(filter_mode) if filter_mode else ""
    logger.info(f"Querying revisions for '{page_title}' between {start_str} and {end_str}{filter_str}")

    revisions = []
    api_calls = 0
    params = base_params.copy()
    for tag in tag_list:
        has_more = True
        while has_more:
            # Execute API request
            if tag:
                params['rvtag'] = tag
            data = api_request(params, max_retries, retry_delay, language)
            api_calls += 1

            # Process API response
            pages = data.get('query', {}).get('pages', {})
            if not pages:
                raise RuntimeError("No page data found in API response")

            page = next(iter(pages.values()))

            # Check page status
            if page.get('missing') or page.get('invalid'):
                raise RuntimeError(f"Page '{page_title}' does not exist or is invalid")

            # Handle redirects
            if 'redirected' in page or 'normalized' in data.get('query', {}):
                actual_title = page.get('title', page_title)
                logger.info(f"Redirected to actual page title: {actual_title}")

            # Process revisions
            if 'revisions' in page:
                batch_revisions = page['revisions']
                batch_size = len(batch_revisions)

                if batch_size > 0:
                    first_rev_date = batch_revisions[0]['timestamp']
                    last_rev_date = batch_revisions[-1]['timestamp']
                    logger.info(
                        f"Batch #{api_calls}: Processed {batch_size} revisions ({first_rev_date} to {last_rev_date})")

                revisions.extend(batch_revisions)
            has_more = need_more
            # Check if there are more results
            if 'continue' in data and 'rvcontinue' in data['continue']:
                params['rvcontinue'] = data['continue']['rvcontinue']
                logger.info(f"More revisions available, continuing with rvcontinue={params['rvcontinue']}")
            else:
                has_more = False
                logger.info("Reached end of revision history")
    if len(tag_list) > 1:
        finished_ids = []
        new_visions = []
        for rev_ in revisions:
            if rev_['revid'] in finished_ids:
                continue
            finished_ids.append(rev_['revid'])
            new_visions.append(rev_)
        new_visions = sorted(new_visions, key=lambda x: x['timestamp'])
        revisions = new_visions
    # Final summary
    logger.info(f"Found {len(revisions)} revisions between {start_str} and {end_str}")
    logger.info(f"Completed {api_calls} API requests")
    return revisions


def search_keyword_in_comments(
        page_title: str,
        keyword: str,
        tags: Union[List[str], str, None] = None,
        start_date: Optional[Union[str, datetime.datetime]] = None,
        end_date: Optional[Union[str, datetime.datetime]] = None,
        language: str = "en"
) -> list:
    """
    Get Wikipedia edits where a revision comment contains the specified keyword

    Parameters:
        page_title: Page title (e.g., "Australian Aboriginal flag")
        keyword: Search keyword (e.g., "vandalism")
        start_date: Start date (e.g., "2017-01-01")
        end_date: End date (e.g., "2019-01-31")
        language: Language code (default "en")

    Returns:
        List of edits containing the keyword in their revision comments
    """
    # Retrieve edit history (automatically handles redirects and date range)
    revisions = get_wikipedia_revisions(
        page_title=page_title,
        start_date=start_date,
        tags=tags,
        end_date=end_date,
        language=language,
        revision_properties=['timestamp', 'user', 'comment', 'ids', 'size']  # Request only comment field for efficiency
    )

    # Convert keyword to lowercase for case-insensitive matching
    keyword_lower = keyword.lower()

    # Collect edits containing the keyword
    matching_edits = []
    for edit in revisions:
        comment = edit.get('comment', '')
        # Process only string-type comments
        if isinstance(comment, str) and keyword_lower in comment.lower():
            matching_edits.append(edit)
    return matching_edits


def get_image_urls(image_titles: List[str], language: str = "en") -> List[str]:
    """
    Get URLs for multiple Wikipedia images

    Parameters:
    image_titles: List of image titles (e.g., ["File:Example.jpg"])
    language: Wikipedia language version

    Returns: List of image URLs
    """
    urls = []
    for title in image_titles:
        params = {
            'action': 'query',
            'titles': title,
            'prop': 'imageinfo',
            'iiprop': 'url',
            'format': 'json'
        }
        data = api_request(params, language=language)
        pages = data.get('query', {}).get('pages', {})
        for page in pages.values():
            if 'imageinfo' in page:
                urls.append(page['imageinfo'][0]['url'])
    return urls


def count_revisions(
        page_title: str,
        start_date: Optional[Union[str, datetime.datetime]] = None,
        end_date: Optional[Union[str, datetime.datetime]] = None,
        condition_function: Optional[Callable] = None,
        tags: Union[List[str], str, None] = None,
        user: str = None,
        exclude_user: str = None,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        language: str = "en"
) -> int:
    """
    Count the number of Wikipedia page revisions (optional conditional filtering)

    Parameters:
    page_title: Wikipedia page title
    start_date: Start date
    end_date: End date
    condition_function: Custom filtering function
    tags: Edit tags to filter by
    user: Filter edits by specific user
    exclude_user: Exclude edits from specific user
    max_retries: Maximum number of retries
    retry_delay: Retry delay time (seconds)
    language: Wikipedia language version

    Returns: Number of revisions
    """
    # Get basic revision information
    revisions = get_wikipedia_revisions(
        page_title=page_title,
        start_date=start_date,
        end_date=end_date,
        revision_properties=['timestamp', 'user', 'comment', 'tags', 'ids'],
        tags=tags,
        user=user,
        exclude_user=exclude_user,
        max_retries=5,
        retry_delay=2,
        language=language
    )

    # Apply filtering conditions
    if condition_function:
        revisions = [rev for rev in revisions if condition_function(rev)]

    logger.info(f"Found {len(revisions)} revisions matching the specified criteria")
    return len(revisions)


def get_page_content(
        page_title: str,
        as_of_date: Optional[Union[str, datetime.datetime]] = None,
        revision_id: Optional[int] = None,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        language: str = "en"
) -> str:
    """
    Get the content of a Wikipedia page at a specific point in time

    Parameters:
    page_title: Wikipedia page title
    as_of_date: Get page content as of this date
    revision_id: Get page content of specific revision ID
    max_retries: Maximum number of retries
    retry_delay: Retry delay time (seconds)
    language: Wikipedia language version

    Returns: String content of the page
    """
    # Set default date
    if as_of_date is None and revision_id is None:
        as_of_date = datetime.datetime.utcnow()

    # Prepare basic API parameters
    base_params = {
        'action': 'query',
        'prop': 'revisions',
        'titles': page_title,
        'rvprop': 'content|timestamp|ids',
        'rvslots': 'main',
        'format': 'json'
    }

    # Select how to get content based on parameters
    if revision_id:
        base_params['revids'] = revision_id
        logger.info(f"Fetching content of page '{page_title}' at revision ID {revision_id}")
    else:
        as_of_str = to_iso_format(as_of_date, datetime.datetime.utcnow())
        base_params['rvdir'] = 'older'
        base_params['rvstart'] = as_of_str
        base_params['rvlimit'] = 1
        logger.info(f"Fetching content of page '{page_title}' as of {as_of_str}")

    # Execute API request
    data = api_request(base_params, max_retries, retry_delay, language)

    # Process API response
    pages = data.get('query', {}).get('pages', {})
    if not pages:
        raise RuntimeError("No page data found in API response")

    page = next(iter(pages.values()))

    # Check page status
    if page.get('missing') or page.get('invalid'):
        raise RuntimeError(f"Page '{page_title}' does not exist")

    # Handle redirects
    if 'redirects' in data.get('query', {}) or 'normalized' in data.get('query', {}):
        actual_title = page.get('title', page_title)
        logger.info(f"Redirected to actual page title: {actual_title}")

    # Get revision content
    revisions = page.get('revisions', [])
    if not revisions:
        if revision_id:
            raise RuntimeError(f"Revision ID {revision_id} not found for page '{page_title}'")
        else:
            raise RuntimeError(f"No revisions found for page '{page_title}' before {as_of_date}")

    # Get page content
    content = revisions[0].get('slots', {}).get('main', {}).get('*', '')
    revision_timestamp = revisions[0].get('timestamp')
    revision_id = revisions[0].get('revid')

    logger.info(f"Successfully fetched content from revision {revision_id} at {revision_timestamp}")
    return content


def extract_infobox_content(
        page_content: str,
        infobox_type: Optional[str] = None
) -> Optional[str]:
    """
    Extract the complete infobox content from Wikipedia page content

    Parameters:
    page_content: Wikipedia page content
    infobox_type: Specific infobox type (e.g., "infobox book", "infobox dual roller coaster")

    Returns: Complete infobox Wikicode content, None if not found
    """
    # Find the start of the infobox
    if infobox_type:
        start_pattern = f"{{{{Infobox {infobox_type}"
        infobox_start = page_content.find(start_pattern)
        if infobox_start == -1:
            start_pattern = f"{{{{Infobox_{infobox_type}"
            infobox_start = page_content.find(start_pattern)
    else:
        start_pattern = "{{Infobox"
        infobox_start = page_content.find(start_pattern)
        if infobox_start == -1:
            start_pattern = "{{Infobox_"
            infobox_start = page_content.find(start_pattern)

    if infobox_start == -1:
        return None

    # Extract infobox content (handling nested braces)
    brace_count = 2  # Initial two {
    infobox_end = infobox_start + len(start_pattern)
    max_pos = min(len(page_content), infobox_start + 5000)  # Limit search range

    while infobox_end < max_pos and brace_count > 0:
        if page_content.startswith("{{", infobox_end):
            brace_count += 1
            infobox_end += 2
        elif page_content.startswith("}}", infobox_end):
            brace_count -= 1
            infobox_end += 2
            if brace_count == 0:
                break
        else:
            infobox_end += 1

    # Return the entire infobox content
    return page_content[infobox_start:infobox_end]


def extract_infobox_values_with_llm(
        page_content: str,
        keys: List[str],
        infobox_type: Optional[str] = None,
        model: str = "DeepSeek-V3",
        temperature: float = 0.2,
        max_tokens: int = 20000
) -> Dict[str, Optional[str]]:
    """
    Extract values from Wikipedia infobox content using OpenAI LLM

    Args:
        page_content: Raw Wikipedia page content
        keys: List of keys to extract from the infobox
        infobox_type: Optional infobox type (e.g., "book", "roller coaster")
        model: OpenAI model to use
        temperature: Creativity of the response
        max_tokens: Maximum tokens for the response

    Returns:
        Dictionary with extracted values for each key
    """
    # Step 1: Extract the infobox content
    infobox_content = extract_infobox_content(page_content, infobox_type)

    if not infobox_content:
        return {key: None for key in keys}

    # Step 2: Construct a clear prompt for the LLM
    keys_str = ", ".join(keys)
    system_prompt = "Extract values from Wikipedia infoboxes. " \
                    "Return simple key-value pairs and separate grouped items."

    user_prompt = f"""
    ## Task
    Extract these keys: {', '.join(keys)}

    ## Infobox Content
    {infobox_content}
"""+"""
    ## Instructions
    1. Return these in JSON:
       - "values": Single key-value pairs
       - "groups": For related items (tracks, editions) OR null
       - "content": Plain text summary

    2. Output rules:
       - Put most values directly in "values"
       - Only use "groups" for explicitly grouped items
       - Always include original units
       - Include NULL for missing keys

    3. Group example:
       "groups": {
            "Downtown": {
                "population": "52,000",
                "area": "2.3 sq mi"
            },
            "Eastside": {
                "population": "34,500",
                "area": "4.1 sq mi"
            },
            "Westend": {
                "population": "41,200",
                "area": "3.7 sq mi"
            }
        }

    4. Value example:
       "values": {
                            "name": "Albert Einstein",
                            "birth_date": "March 14, 1879",
                            "death_date": "April 18, 1955",
                            "fields": ["Physics", "Philosophy"],
                            "notable_awards": ["Nobel Prize in Physics", "Copley Medal"]
                        }

    ## Output Format
    {{
      "values": {{...}},
      "groups": {{...}} OR null,
      "content": "Text summary"
    }}
    """

    try:
        # Step 3: Call OpenAI API with formatted prompt
        client = OpenAI(
            base_url=os.getenv('DEEPSEEK_URL'),
            api_key=os.getenv('DEEPSEEK_KEY'),
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )

        # Step 4: Parse and return the JSON response
        if response.choices and response.choices[0].message.content:
            return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")

    # Return default values if extraction fails
    return {key: None for key in keys}


def find_first_edit(
        page_title: str,
        condition_function: Callable = None,
        start_date: Optional[Union[str, datetime.datetime]] = None,
        end_date: Optional[Union[str, datetime.datetime]] = None,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        language: str = "en"
) -> Optional[Dict]:
    """
    Find the first edit that meets specific criteria

    Parameters:
    page_title: Wikipedia page title
    condition_function: Edit filtering condition function
    start_date: Start date
    end_date: End date
    max_retries: Maximum number of retries
    retry_delay: Retry delay time (seconds)
    language: Wikipedia language version

    Returns: The first edit record that meets the criteria, None if not found
    """
    # Get basic revision information, sorted chronologically (oldest to newest)
    revisions = get_wikipedia_revisions(
        page_title=page_title,
        start_date=start_date,
        end_date=end_date,
        revision_properties=['timestamp', 'user', 'comment', 'tags', 'ids'],
        max_retries=5,
        retry_delay=2,
        language=language,
        need_more=True
    )

    condition_function = eval(condition_function)
    # Find the first edit that meets the criteria
    for revision in revisions:
        if type(revision['timestamp']) != str:
            revision['timestamp'] = revision['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        revision['timestamp'] = datetime.datetime.strptime(revision['timestamp'].replace('T', ' ').replace('Z', ''),
                                                           '%Y-%m-%d %H:%M:%S')
        if condition_function and condition_function(revision):
            logger.info(
                f"Found first matching edit at {revision['timestamp']} by user {revision.get('user', 'unknown')}")
            return revision

    logger.info("No matching edits found")
    return None


def get_user_page_content(
        username: str,
        as_of_date: Optional[Union[str, datetime.datetime]] = None,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        language: str = "en"
) -> str:
    """
    Get the content of a Wikipedia user page

    Parameters:
    username: Wikipedia username
    as_of_date: Get user page content as of this date
    max_retries: Maximum number of retries
    retry_delay: Retry delay time (seconds)
    language: Wikipedia language version

    Returns: User page content
    """
    return get_page_content(
        page_title=f"User:{username}",
        as_of_date=as_of_date,
        max_retries=5,
        retry_delay=2,
        language=language
    )


def get_page_properties(
        page_title: str,
        as_of_date: Optional[Union[str, datetime.datetime]] = None,
        properties: List[str] = ["info", "revisions", "images", "links", "references"],
        max_retries: int = 5,
        retry_delay: float = 2.0,
        language: str = "en"
) -> Dict:
    """
    Get multiple properties of a Wikipedia page

    Parameters:
    page_title: Wikipedia page title
    as_of_date: Get page properties as of this date
    properties: List of properties to retrieve
    max_retries: Maximum number of retries
    retry_delay: Retry delay time (seconds)
    language: Wikipedia language version

    Returns: Dictionary containing all requested properties
    """
    # Set default date
    if as_of_date is None:
        as_of_date = datetime.datetime.utcnow()

    # Prepare basic API parameters
    as_of_str = to_iso_format(as_of_date, datetime.datetime.utcnow())
    params = {
        'action': 'query',
        'titles': page_title,
        'format': 'json',
        'rvdir': 'older',
        'rvlimit': 1,
        'rvstart': as_of_str
    }

    # Add requested properties
    if "info" in properties:
        params['inprop'] = 'url|displaytitle'
    if "revisions" in properties:
        params['prop'] = 'revisions'
        params['rvprop'] = 'ids|timestamp|user|comment|size|tags'
    if "images" in properties:
        if 'prop' in params:
            params['prop'] += '|images'
        else:
            params['prop'] = 'images'
    if "links" in properties:
        if 'prop' in params:
            params['prop'] += '|links'
        else:
            params['prop'] = 'links'
        params['pllimit'] = 'max'
    if "references" in properties:
        if 'prop' in params:
            params['prop'] += '|extlinks'
        else:
            params['prop'] = 'extlinks'
        # params['ellimit'] = 'max'
        # params['prop'] = 'revisions'  # Get revision content
        # params['rvprop'] = 'content'  # Include page Wikitext content
        # # params['ellimit'] = 'max'

    # Execute API request
    data = api_request(params, max_retries, retry_delay, language)

    # Process response
    pages = data.get('query', {}).get('pages', {})
    if not pages:
        raise RuntimeError(f"No page data found for '{page_title}'")

    page = next(iter(pages.values()))

    # Return results
    result = {}
    if "info" in properties:
        result['info'] = {
            'pageid': page.get('pageid'),
            'title': page.get('title'),
            'fullurl': page.get('fullurl'),
            'displaytitle': page.get('displaytitle')
        }

    if "revisions" in properties and 'revisions' in page:
        result['revision'] = page['revisions'][0] if page['revisions'] else {}

    if "images" in properties and 'images' in page:
        result['images'] = [img['title'] for img in page.get('images', [])]

    if "links" in properties and 'links' in page:
        result['links'] = [link['title'] for link in page.get('links', [])]

    if "references" in properties and 'extlinks' in page:
        result['references'] = [ref['*'] for ref in page.get('extlinks', [])]

    if 'images' in result:
        result['images'] = get_image_urls(result['images'])
    return result


def extract_text_changes(
        html_diff: str,
        change_type: str = "both",  # "added", "deleted", or "both"
        max_lines: int = None  # Optional: limit maximum number of lines
) -> dict:
    """
    Extract Wikipedia diff content, with optional change type selection

    Parameters:
    html_diff: HTML formatted diff content
    change_type: Type of changes to extract ("added", "deleted", "both")
    max_lines: Optional, limit the number of returned lines

    Returns: Dictionary containing the change content
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_diff, 'html.parser')
    results = {"added": [], "deleted": []}

    for tr in soup.find_all('tr'):
        # Skip line number rows
        if tr.find('td', class_='diff-lineno'):
            continue

        # Extract deleted lines (left side)
        if del_td := tr.find('td', class_='diff-deletedline'):
            text = " ".join(del_td.stripped_strings)
            if text:  # Filter empty lines
                results["deleted"].append(text)

        # Extract added lines (right side)
        if ins_td := tr.find('td', class_='diff-addedline'):
            text = " ".join(ins_td.stripped_strings)
            if text:  # Filter empty lines
                results["added"].append(text)

    # Apply line limit
    if max_lines:
        for key in results:
            results[key] = results[key][:max_lines]

    # Return results based on requested change type
    if change_type == "added":
        return {"added": results["added"]}
    elif change_type == "deleted":
        return {"deleted": results["deleted"]}
    else:
        return results


def get_text_diff_single(
        revision_id1: int,
        revision_id2: int,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        language: str = "en"
) -> str:
    """
    Compare differences between two revisions and return plain text diff

    Parameters:
    revision_id1: Base revision ID
    revision_id2: Target revision ID
    max_retries: Maximum number of retries
    retry_delay: Retry delay time (seconds)
    language: Wikipedia language version

    Returns: Plain text diff content
    """
    params = {
        'action': 'compare',
        'fromrev': revision_id1,
        'torev': revision_id2,
        'difftype': 'unified',
        'format': 'json'
    }

    # Execute API request
    data = api_request(params, max_retries, retry_delay, language)

    # Directly access compare.* field to get HTML formatted diff
    if 'compare' not in data or '*' not in data['compare']:
        raise RuntimeError(f"API response missing diff data: {data}")

    diff_html = data['compare']['*']

    # Extract plain text diff content from <pre> tag
    pre_match = re.search(r'<pre>(.*?)</pre>', diff_html, re.DOTALL)
    if not pre_match:
        raise RuntimeError("Failed to extract diff content from HTML")

    # Get plain text content and unescape HTML entities
    diff_text = html.unescape(pre_match.group(1))

    # Normalize line breaks and clean special characters
    diff_text = re.sub(r'\r\n|\r|\n', '\n', diff_text)
    diff_text = re.sub(r'[\x00-\x08\x0b-\x1f]', '', diff_text)

    return diff_text


def get_previous_revision_chain(
        revision_id: int,
        depth: int,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        language: str = "en"
) -> list:
    """
    Get the revision chain before the specified revision ID (updated version, following latest API specifications)
    """
    revisions = []
    current_id = revision_id

    for _ in range(depth + 1):
        # Request revision information including parent version ID
        params = {
            'action': 'query',
            'prop': 'revisions',
            'revids': current_id,
            'rvprop': 'ids|user',  # Only need id
            'rvslots': 'main',
            'format': 'json'
        }

        data = api_request(params, max_retries, retry_delay, language)

        # Parse response to get parent version ID
        pages = data['query']['pages']
        page_id = next(iter(pages.keys()))
        page_data = pages[page_id]

        if 'revisions' not in page_data or not page_data['revisions']:
            break

        rev_info = page_data['revisions'][0]

        # Get ID from revision information
        if 'revid' in rev_info:
            revid = rev_info['revid']
        else:
            revid = None

        if not revid:
            break

        revisions.insert(0, {'rev_id': revid, 'editor': rev_info['user']})
        current_id = rev_info.get('parentid', None)
        if current_id is None:
            break

    if len(revisions) < depth:
        raise RuntimeError(f"Not enough parent versions found: need {depth} but only found {len(revisions)}")

    return revisions[:-1]


def get_text_diff(
        main_id,
        language: str = "en"
) -> list:
    """
    Compare differences between the specified revision and previous revisions and return plain text diff

    Parameters:
    main_id: Target revision ID

    Returns: Plain text diff content
    """
    child_ids = get_previous_revision_chain(main_id, 2)
    # Extract differences for each revision
    diffs = []
    for child in child_ids:
        diff = get_text_diff_single(
            revision_id1=child['rev_id'],  # Previous version ID
            revision_id2=main_id,
            language=language
        )
        diffs.append({f"compare with {child['rev_id']}": diff})
    return diffs


# Revision history retrieval tool
@wiki_tools.tool(description="Retrieves full revision history of a Wikipedia page with filtering capabilities")
def get_wikipedia_revisions_api(
    page_title: str = Field(description="Title of Wikipedia page", examples=["Penguin", "Space Mountain"]),
    start_date: Optional[Union[str, datetime]] = Field(
        description="Start date of search range, start_date is inclusive", default=datetime.datetime(1991,1,1, tzinfo=datetime.timezone.utc)),
    end_date: Optional[Union[str, datetime]] = Field(description="End date of search range, end_date is exclusive",
                                                  default=datetime.datetime(2023,8,1, tzinfo=datetime.timezone.utc)),
    revision_properties: List[str] = Field(description="Revision properties to include",
                                           default=["timestamp", "user", "comment", "tags", "ids", "size"]),
    tags: Optional[Union[List[str], str, None]] = Field(description="Filter by edit tags e.g. 'mw-reverted', 'mw-manual-revert'", default=None),
    user: Optional[str] = Field(description="Filter by specific editor", default=None),
    exclude_user: Optional[str] = Field(description="Exclude edits from specific user", default=None),
    language: str = Field(description="Wikipedia language edition", default="en")
):
    # 使用统一的工具函数处理所有参数
    return get_wikipedia_revisions(
        page_title=page_title,
        start_date=get_default_value(start_date),
        end_date=get_default_value(end_date),
        revision_properties=get_default_value(revision_properties),
        tags=get_default_value(tags),
        user=get_default_value(user),
        exclude_user=get_default_value(exclude_user),
        language=get_default_value(language)
    )


# Edit counter tool
@wiki_tools.tool(description="Counts number of edits matching specified criteria")
def count_revisions_api(
    page_title: str = Field(description="Title of Wikipedia page", examples=["Flag"]),
    start_date: Optional[Union[str, datetime]] = Field(description="Start date of count range, start_date is inclusive", default=None),
    end_date: Optional[Union[str, datetime]] = Field(description="End date of count range, end_date is exclusive",
                                                     default=datetime.datetime(2023,8,1, tzinfo=datetime.timezone.utc)),
    tags: Optional[Union[List[str], str, None]] = Field(description="Edit tags to count, e.g. 'mw-reverted', 'mw-manual-revert'", default=None),
    user: Optional[str] = Field(description="Only count edits from this user", default=None),
    exclude_user: Optional[str] = Field(description="Exclude edits from this user", default=None),
    language: str = Field(description="Wikipedia language edition", default="en")
):
    return count_revisions(
        page_title=page_title,
        start_date=get_default_value(start_date),
        end_date=get_default_value(end_date),
        tags=get_default_value(tags),
        user=get_default_value(user),
        exclude_user=get_default_value(exclude_user),
        max_retries=5,
        retry_delay=2,
        language=get_default_value(language)
    )


# Page content retrieval tool
@wiki_tools.tool(description="Gets Wikipedia page content at specific time point or revision")
def get_page_content_api(
    page_title: str = Field(description="Title of Wikipedia page", examples=["Diplomacy (game)"]),
    as_of_date: Optional[Union[str, datetime]] = Field(description="Get content as of this date", default=None),
    revision_id: Optional[int] = Field(description="Get content of specific revision ID", default=None),
    language: str = Field(description="Wikipedia language edition", default="en")
):
    return get_page_content(
        page_title=page_title,
        as_of_date=get_default_value(as_of_date),
        revision_id=get_default_value(revision_id),
        max_retries=5,
        retry_delay=2,
        language=get_default_value(language)
    )


# Infobox value extractor tool
@wiki_tools.tool(description="Extracts content from Wikipedia infobox templates")
def extract_infobox_values_api(
    page_content: str = Field(description="Full Wikipedia page content"),
    keys: list = Field(description="Infobox keys to extract"),
    infobox_type: Optional[str] = Field(description="Specific infobox template type", default=None)
):
    return extract_infobox_values_with_llm(
        page_content=page_content,
        keys=keys,
        infobox_type=get_default_value(infobox_type)
    )


# First edit finder tool
@wiki_tools.tool(description="Finds the first edit meeting specified criteria")
def find_first_edit_api(
    page_title: str = Field(description="Title of Wikipedia page", examples=["Mermaids"]),
    condition_function: Callable = Field(description="Condition function for filtering edits", default=None),
    start_date: Optional[Union[str, datetime]] = Field(description="Search start date, start_date is inclusive", default=None),
    end_date: Optional[Union[str, datetime]] = Field(description="Search end date, end_date is exclusive",
                                                     default=datetime.datetime(2023,8,1, tzinfo=datetime.timezone.utc)),
    language: str = Field(description="Wikipedia language edition", default="en")
):
    return find_first_edit(
        page_title=page_title,
        condition_function=condition_function,
        start_date=get_default_value(start_date),
        end_date=get_default_value(end_date),
        max_retries=5,
        retry_delay=2,
        language=get_default_value(language)
    )


# User page content tool
@wiki_tools.tool(description="Gets content of Wikipedia user page")
def get_user_page_content_api(
    username: str = Field(description="Wikipedia username", examples=["ExampleEditor"]),
    as_of_date: Optional[Union[str, datetime]] = Field(description="Get content as of this date", default=None),
    language: str = Field(description="Wikipedia language edition", default="en")
):
    return get_user_page_content(
        username=username,
        as_of_date=get_default_value(as_of_date),
        max_retries=5,
        retry_delay=2,
        language=get_default_value(language)
    )


# Page properties retrieval tool
@wiki_tools.tool(description="Gets multiple properties of a Wikipedia page")
def get_page_properties_api(
    page_title: str = Field(description="Title of Wikipedia page", examples=["West African Vodun"]),
    as_of_date: Optional[Union[str, datetime.datetime]] = Field(description="Get properties as of this date", default=None),
    properties: List[str] = Field(description="Properties to retrieve", default=["info", "revisions", "images", "links", "references"]),
    language: str = Field(description="Wikipedia language edition", default="en")
):
    return get_page_properties(
        page_title=page_title,
        as_of_date=get_default_value(as_of_date),
        properties=get_default_value(properties),
        max_retries=5,
        retry_delay=2,
        language=get_default_value(language)
    )


# Edit diff comparison tool
@wiki_tools.tool(description="Compares differences between target revision and before revisions of a Wikipedia page")
def get_text_diff_api(
    main_id: int = Field(description="Revision ID of target version"),
    language: str = Field(description="Wikipedia language edition", default="en")
):
    return get_text_diff(
        main_id=main_id,
        language=get_default_value(language)
    )


@wiki_tools.tool(description="Get revisions containing a specific keyword in their edit comments")
def search_keyword_in_comments_api(
        page_title: str = Field(description="Title of Wikipedia page", examples=["Australian Aboriginal flag"]),
        keyword: str = Field(description="Keyword to search for in edit comments", examples=["apple"]),
        tags: Optional[Union[List[str], str, None]] = Field(description="Edit tags to count, e.g. 'mw-reverted', 'mw-manual-revert'", default=None),
        start_date: str = Field(description="Start date (YYYY-MM-DD format), start_date is inclusive", examples=["1990-01-01"]),
        end_date: str = Field(description="End date (YYYY-MM-DD format), end_date is exclusive", examples=["2023-07-30"],
                              default=datetime.datetime(2023,8,1, tzinfo=datetime.timezone.utc)),
) -> list:
    """
    Get revisions for the specified page contain the given keyword
    in their edit comments during the specified date range.

    Returns:
         matching revisions
    """
    return search_keyword_in_comments(
            page_title=page_title,
            keyword=keyword,
            tags=get_default_value(tags),
            start_date=get_default_value(start_date),
            end_date=get_default_value(end_date),
            language='en'
        )


if __name__ == '__main__':
    revisions = get_wikipedia_revisions(
        page_title='Western rockhopper penguin',
        revision_properties=['size', 'comment'],
        end_date='2023-08-01',
        language='en'
    )

    l = 10
    res = []
    abs_ = 'both'
    for i in range(1, len(revisions)):
        if abs_ == 'both':
            com = abs(revisions[i]['size'] - revisions[i - 1]['size'])
        elif abs_ == '+':
            com = revisions[i]['size'] - revisions[i - 1]['size']
        else:  # '-'
            com = revisions[i - 1]['size'] - revisions[i]['size']
        res.append([com, revisions[i]])
    res = sorted(res, key=lambda x: x[0], reverse=True)
    print([i[0] for i in res[:l]])