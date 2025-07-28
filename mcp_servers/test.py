import time
import os
import requests
from typing import List, Dict, Optional, Union
from pydantic import Field
from oxygent import oxy
from pydantic.fields import FieldInfo


def get_default_value(value):
    return value.default if isinstance(value, FieldInfo) else value


def find_matching_milestone(
        repo: str,
        version_str: str,
        exact_match: bool = False
) -> Optional[int]:
    """
    Find a milestone ID matching a version string

    Args:
        repo: Repository in owner/repo format
        version_str: Version string to match (e.g., "2.3.2")
        exact_match: Require exact match of the version string

    Returns:
        Milestone if found, otherwise None
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv('GITHUB_TOKEN')
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base_url = f"https://api.github.com/repos/{repo}/milestones"
    params = {"state": "all", "per_page": 100, "page": 1}
    version_str = version_str.lower().strip()

    try:
        while True:
            response = requests.get(base_url, headers=headers, params=params)

            # Handle rate limits
            if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                reset_seconds = max(0, reset_time - time.time() + 10)  # Buffer
                time.sleep(reset_seconds)
                continue  # Retry after sleeping

            response.raise_for_status()
            milestones = response.json()

            if not milestones:
                break  # No more pages

            for milestone in milestones:
                title = milestone["title"].lower().strip()

                # Optimized matching logic
                exact_candidates = (version_str, f"v{version_str}", f"version {version_str}")

                if exact_match and title == version_str:
                    return milestone["title"]

                if not exact_match and any(title == cand for cand in exact_candidates):
                    return milestone["title"]

                # Context-aware substring matching
                if (not exact_match and
                        version_str in title and
                        (f"{version_str} " in title or
                         f" {version_str}" in title or
                         title.endswith(version_str))):
                    return milestone["title"]

            # Check for next page
            if 'next' not in response.links:
                break
            params["page"] += 1

        return None

    except requests.RequestException as e:
        raise Exception(f"Milestone lookup failed: {str(e)}")


def get_github_issues(
        repo: str = "scipy/scipy",
        milestone: Optional[str] = None,
        milestone_id: Optional[int] = None,
        state: str = "closed",
        issue_type: str = "issue",
        title_ends_with: Optional[str] = None,
        title_contains: Optional[str] = None,
        labels: Optional[Union[str, List[str]]] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0
) -> List[Dict]:
    """
    Retrieve GitHub issues/PRs with advanced filtering

    Args:
        repo: Repository in owner/repo format
        milestone: Milestone title
        milestone_id: Milestone ID (precise alternative to title)
        state: Issue state (open/closed/all)
        issue_type: Issue type (issue/pr)
        title_ends_with: Filter titles ending with this string
        title_contains: Filter titles containing this string
        labels: Label(s) to filter by (single or list)
        max_retries: Maximum API retry attempts
        retry_delay: Seconds between retries

    Returns:
        List of issue/PR dictionaries
    """
    token = os.getenv('GITHUB_TOKEN')
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Construct query parameters
    query_terms = [f"repo:{repo}", f"state:{state}", f"type:{issue_type}"]

    # Prioritize milestone ID if provided
    if milestone_id:
        query_terms.append(f"milestone:{milestone_id}")
    elif milestone:
        query_terms.append(f'milestone:"{milestone}"')

    # Handle labels
    if labels:
        if isinstance(labels, list):
            for label in labels:
                query_terms.append(f'label:"{label}"')
        else:
            query_terms.append(f'label:"{labels}"')

    all_items = []
    page = 1
    per_page = 100
    has_more = True

    while has_more and page <= 10:  # GitHub returns max 1000 items
        params = {
            "q": " ".join(query_terms),
            "per_page": per_page,
            "page": page
        }
        params = {'q': 'repo:numpy/numpy state:closed type:issue milestone:"113"', 'per_page': 100, 'page': 1}
        params = {'q': 'repo:numpy/numpy state:closed type:issue milestone:"1.25.0 release"', 'per_page': 100, 'page': 1}
        params = {'q': 'repo:numpy/numpy state:closed type:issue milestone:"1.25.0 release"', 'per_page': 100,
                  'page': 1}
        url = "https://api.github.com/search/issues"
        retries = 0
        items_page = []

        while retries <= max_retries:
            try:
                response = requests.get(url, headers=headers, params=params)

                # Handle rate limiting
                if response.status_code == 403:
                    reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                    sleep_time = max(reset_time - time.time(), 0) + 5
                    print(f"Rate limit reached, sleeping {sleep_time:.1f} seconds")
                    time.sleep(sleep_time)
                    continue

                response.raise_for_status()
                data = response.json()
                items_page = data.get("items", [])
                break

            except (requests.RequestException, KeyError) as e:
                retries += 1
                if retries > max_retries:
                    raise Exception(f"API request failed: {str(e)}")
                time.sleep(retry_delay)

        # Apply local title filters
        if title_ends_with:
            items_page = [item for item in items_page
                          if item["title"].strip().endswith(title_ends_with)]

        if title_contains:
            items_page = [item for item in items_page
                          if title_contains.lower() in item["title"].lower()]

        all_items.extend(items_page)

        # Check if more results exist
        if len(items_page) < per_page:
            has_more = False
        else:
            page += 1
            time.sleep(0.5)  # Avoid overwhelming API

    return all_items


def get_merged_pr_count(
        repo: str,
        year: int,
        token: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0
) -> int:
    """
    Get the number of merged Pull Requests in a GitHub repository for a specified year

    Args:
        repo: Repository name in format "owner/repo"
        year: Year to count merged PRs
        token: GitHub personal access token for authentication
        max_retries: Maximum API retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Number of merged PRs in specified year
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Construct precise date range
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    # 修复2：正确构造查询参数数组（不要直接使用长字符串）
    query_terms = [
        f"repo:{repo}",
        "type:pr",
        "is:merged",
        f"merged:{start_date}..{end_date}"
    ]
    query = " ".join(query_terms)

    total_count = 0
    page = 1
    retry_count = 0
    per_page = 100  # Max items per page

    while True:
        try:
            response = requests.get(
                "https://api.github.com/search/issues",
                headers=headers,
                params={"q": query, "per_page": per_page, "page": page}
            )

            # Handle rate limiting
            if response.status_code == 403:
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                sleep_time = max(reset_time - time.time(), 0) + 5
                print(f"Rate limit reached, waiting {sleep_time:.0f} seconds")
                time.sleep(sleep_time)
                continue

            response.raise_for_status()
            data = response.json()

            # First page contains total_count which we can return directly
            if page == 1:
                total_count = data["total_count"]

                # GitHub returns max 1000 items via pagination
                if total_count <= 1000:
                    return total_count

            current_items = data.get("items", [])
            if not current_items:
                break

            # For counts over 1000, we actually count items
            total_count += len(current_items)

            page += 1
            retry_count = 0  # Reset retry counter

            # Stop if we've reached max items (GitHub API limit)
            if len(current_items) < per_page or page > 10:
                break

        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count <= max_retries:
                print(f"Request failed: {e}. Retrying in {retry_delay} seconds ({retry_count}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"Max retries exceeded: {e}")
                break
        except KeyError:
            raise Exception("API returned unexpected response format")

    return total_count


# Create FunctionHub for API integration
github_tools = oxy.FunctionHub(name="github_api_tools", timeout=900)


# @github_tools.tool(description="Retrieve GitHub issues and PRs with filtering capabilities")
def get_github_issues_api(
        repo: str = Field(..., description="Repository name in owner/repo format"),
        milestone: Optional[str] = Field(None, description="Milestone name (check exact repository naming)"),
        milestone_id: Optional[int] = Field(None, description="Milestone ID (more reliable than name)"),
        state: str = Field("all", description="State of items",
                           enum=["open", "closed", "all"]),
        issue_type: str = Field("issue", description="Type of items to retrieve",
                                enum=["issue", "pr"]),
        title_ends_with: Optional[str] = Field(None, description="Filter titles ending with specific text"),
        title_contains: Optional[str] = Field(None, description="Filter titles containing specific text"),
        labels: Optional[Union[str, List[str]]] = Field(None,
                                                        description="Label(s) to filter by (multiple treated as OR)"),
) -> List[Dict]:
    """
    Enhanced GitHub issue/PR search tool with comprehensive filtering options

    Note: For milestone filtering, use milestone_id for precise matching
    when possible. The title_contains filter performs local filtering after
    fetching results from GitHub.
    """
    return get_github_issues(
        repo=repo,
        milestone=get_default_value(milestone),
        milestone_id=get_default_value(milestone_id),
        state=get_default_value(state),
        issue_type=get_default_value(issue_type),
        title_ends_with=get_default_value(title_ends_with),
        title_contains=get_default_value(title_contains),
        labels=get_default_value(labels),
        max_retries=3,
        retry_delay=2.0
    )


def get_milestone(
        repo: str = Field(..., description="Repository name in owner/repo format"),
        version_str: str = Field(..., description="Version string to match"),
        exact_match: bool = Field(False, description="Require exact version match"),
) -> Optional[int]:
    """
    Find a milestone ID matching a version string

    Returns milestone ID if found, or None if no match exists

    Examples:
        get_milestone("numpy/numpy", "1.25.0") → may return ID for "v1.25.0"
    """
    return find_matching_milestone(repo, version_str, get_default_value(exact_match))


# @github_tools.tool(description="Get count of merged pull requests for a specific year")
def get_merged_pr_count_api(
        repo: str = Field(..., description="Repository name in format owner/repo"),
        year: int = Field(..., description="Year to count merged PRs", ge=2008, le=2100),
) -> int:
    """
    Returns the number of merged pull requests in a GitHub repository during a specific year

    Note: Due to GitHub API limitations, results beyond 1000 items may be incomplete
    """
    return get_merged_pr_count(
        repo=repo,
        year=year,
        max_retries=3,
        retry_delay=5.0
    )


if __name__ == "__main__":
    # Get GitHub token from environment (recommended for higher rate limits)
    from dotenv import load_dotenv
    from pathlib import Path  # python3 only

    env_path = Path('../examples/gaia/') / '.env'
    load_dotenv(dotenv_path=env_path, verbose=True)


    # # Example 1: Find NumPy issues for v1.25 milestone with specific titles
    numpy_milestone = get_milestone("numpy/numpy", "1.25.0")
    issues = get_github_issues_api(
        repo="numpy/numpy",
        milestone=numpy_milestone,
        title_contains="BUG",  # Local filter after API call
    )
    print(f"NumPy milestone issues: {len(issues)} results")

    # Example 2: Find pandas PRs with multiple label options
    pandas_prs = get_github_issues_api(
        repo="pandas-dev/pandas",
        milestone="2.3.1",
        # issue_type="pr",
        labels=["Bug"],  # OR relationship
        title_ends_with="`",
    )
    print(f"pandas PRs: {len(pandas_prs)} results")

    # Example 3: Find Matplotlib items containing performance text
    mpl_items = get_github_issues_api(
        repo="matplotlib/matplotlib",
        milestone="v3.7.0",
        title_contains="pyplot",  # Flexible title filter
    )
    print(f"Matplotlib items: {len(mpl_items)} results")

    torch_prs_count = get_merged_pr_count_api(
        repo="pytorch/pytorch",
        year=2022
    )
    print(f"- PyTorch merged PRs in 2022: {torch_prs_count}")
