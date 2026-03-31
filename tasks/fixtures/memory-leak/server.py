"""Simple HTTP server with a memory leak due to unbounded cache."""
import time
from typing import Any, Optional


class RequestCache:
    """A cache for storing HTTP request results.
    
    WARNING: This cache has a memory leak - it grows unbounded without eviction.
    """

    def __init__(self):
        """Initialize the cache."""
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if key in self._cache:
            value, _ = self._cache[key]
            return value
        return None

    def set(self, key: str, value: Any) -> None:
        """Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    def size(self) -> int:
        """Get the current cache size.
        
        Returns:
            Number of items in cache
        """
        return len(self._cache)


class Server:
    """A simple server that caches HTTP request results."""

    def __init__(self):
        """Initialize the server."""
        self.cache = RequestCache()
        self.request_count = 0

    def handle_request(self, url: str) -> str:
        """Handle an HTTP request and cache the result.
        
        Args:
            url: The URL to fetch (simulated)
            
        Returns:
            The simulated response
        """
        self.request_count += 1
        
        # Check cache first
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        
        # Simulate fetching the response
        response = f"Response for {url} (request #{self.request_count})"
        
        # Cache the result - MEMORY LEAK: no eviction policy!
        self.cache.set(url, response)
        
        return response

    def get_cache_size(self) -> int:
        """Get the current cache size.
        
        Returns:
            Number of items in cache
        """
        return self.cache.size()


def test_basic_caching() -> None:
    """Test that basic caching works."""
    server = Server()
    
    # First request - should fetch
    result1 = server.handle_request("https://example.com")
    assert "Response for https://example.com" in result1
    assert server.get_cache_size() == 1
    
    # Second request for same URL - should use cache
    result2 = server.handle_request("https://example.com")
    assert result1 == result2
    assert server.get_cache_size() == 1


def test_different_urls() -> None:
    """Test caching with different URLs."""
    server = Server()
    
    urls = [f"https://example.com/{i}" for i in range(5)]
    results = []
    
    for url in urls:
        results.append(server.handle_request(url))
    
    assert server.get_cache_size() == 5
    
    # All results should be unique (different URLs)
    assert len(set(results)) == 5


if __name__ == "__main__":
    test_basic_caching()
    test_different_urls()
    print("All tests passed!")
