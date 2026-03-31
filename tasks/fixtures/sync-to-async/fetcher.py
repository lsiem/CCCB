"""Synchronous HTTP fetcher using urllib.request.

This module provides blocking HTTP fetching that needs to be refactored
to async/await for better concurrent performance.
"""
import time
import urllib.request
import urllib.error
from typing import Optional, dict as DictType


class FetchError(Exception):
    """Raised when a fetch operation fails."""
    pass


def fetch_url(url: str, timeout: int = 5) -> str:
    """Fetch content from a URL synchronously.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        Response content as string
        
    Raises:
        FetchError: If the fetch fails
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except urllib.error.URLError as e:
        raise FetchError(f"Failed to fetch {url}: {e}")
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP error {e.code} for {url}")
    except Exception as e:
        raise FetchError(f"Unexpected error fetching {url}: {e}")


def fetch_multiple(urls: list[str], timeout: int = 5) -> dict[str, Optional[str]]:
    """Fetch content from multiple URLs sequentially (blocking).
    
    This function fetches URLs one at a time, blocking for each request.
    For better concurrency, this should be refactored to use async.
    
    Args:
        urls: List of URLs to fetch
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary mapping URLs to content (None if fetch failed)
    """
    results: dict[str, Optional[str]] = {}
    
    for url in urls:
        try:
            results[url] = fetch_url(url, timeout)
        except FetchError:
            results[url] = None
    
    return results


def fetch_with_retry(
    url: str,
    max_retries: int = 3,
    timeout: int = 5,
    backoff: float = 1.0
) -> str:
    """Fetch content from a URL with automatic retry logic.
    
    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        backoff: Backoff multiplier for retry delays
        
    Returns:
        Response content as string
        
    Raises:
        FetchError: If all retry attempts fail
    """
    last_error: Optional[FetchError] = None
    
    for attempt in range(max_retries):
        try:
            return fetch_url(url, timeout)
        except FetchError as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = backoff ** attempt
                time.sleep(wait_time)
    
    if last_error:
        raise FetchError(f"Failed to fetch {url} after {max_retries} attempts: {last_error}")
    
    raise FetchError(f"Failed to fetch {url}")


def fetch_batch(
    urls: list[str],
    timeout: int = 5
) -> dict[str, Optional[str]]:
    """Fetch a batch of URLs with error handling.
    
    Args:
        urls: List of URLs to fetch
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary mapping URLs to content (None if fetch failed)
    """
    return fetch_multiple(urls, timeout)


if __name__ == "__main__":
    # Example usage
    urls = [
        "https://httpbin.org/delay/1",
        "https://httpbin.org/uuid",
    ]
    
    try:
        results = fetch_multiple(urls)
        for url, content in results.items():
            if content:
                print(f"Fetched {url}: {len(content)} bytes")
            else:
                print(f"Failed to fetch {url}")
    except Exception as e:
        print(f"Error: {e}")
