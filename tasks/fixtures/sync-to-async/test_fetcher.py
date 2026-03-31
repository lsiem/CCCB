"""Tests for the fetcher module."""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import urllib.error
from fetcher import (
    fetch_url,
    fetch_multiple,
    fetch_with_retry,
    FetchError
)


class TestFetchUrl(unittest.TestCase):
    """Tests for fetch_url function."""

    @patch('urllib.request.urlopen')
    def test_fetch_url_success(self, mock_urlopen):
        """Test successful URL fetch."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"Test content"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = fetch_url("https://example.com")
        assert result == "Test content"
        mock_urlopen.assert_called_once()

    @patch('urllib.request.urlopen')
    def test_fetch_url_http_error(self, mock_urlopen):
        """Test HTTP error handling."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, None
        )
        
        with self.assertRaises(FetchError):
            fetch_url("https://example.com")

    @patch('urllib.request.urlopen')
    def test_fetch_url_url_error(self, mock_urlopen):
        """Test URL error handling."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        with self.assertRaises(FetchError):
            fetch_url("https://example.com")

    @patch('urllib.request.urlopen')
    def test_fetch_url_timeout(self, mock_urlopen):
        """Test timeout handling."""
        mock_urlopen.side_effect = TimeoutError()
        
        with self.assertRaises(FetchError):
            fetch_url("https://example.com", timeout=1)


class TestFetchMultiple(unittest.TestCase):
    """Tests for fetch_multiple function."""

    @patch('fetcher.fetch_url')
    def test_fetch_multiple_success(self, mock_fetch):
        """Test fetching multiple URLs."""
        mock_fetch.side_effect = ["Content 1", "Content 2"]
        
        urls = ["https://example.com/1", "https://example.com/2"]
        results = fetch_multiple(urls)
        
        assert len(results) == 2
        assert results["https://example.com/1"] == "Content 1"
        assert results["https://example.com/2"] == "Content 2"

    @patch('fetcher.fetch_url')
    def test_fetch_multiple_with_error(self, mock_fetch):
        """Test fetch_multiple with some failures."""
        mock_fetch.side_effect = [
            "Content 1",
            FetchError("Failed"),
            "Content 3"
        ]
        
        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3"
        ]
        results = fetch_multiple(urls)
        
        assert results["https://example.com/1"] == "Content 1"
        assert results["https://example.com/2"] is None
        assert results["https://example.com/3"] == "Content 3"

    @patch('fetcher.fetch_url')
    def test_fetch_multiple_all_failures(self, mock_fetch):
        """Test fetch_multiple with all failures."""
        mock_fetch.side_effect = FetchError("Failed")
        
        urls = ["https://example.com/1", "https://example.com/2"]
        results = fetch_multiple(urls)
        
        assert results["https://example.com/1"] is None
        assert results["https://example.com/2"] is None


class TestFetchWithRetry(unittest.TestCase):
    """Tests for fetch_with_retry function."""

    @patch('fetcher.fetch_url')
    def test_fetch_with_retry_success(self, mock_fetch):
        """Test successful fetch on first try."""
        mock_fetch.return_value = "Content"
        
        result = fetch_with_retry("https://example.com", max_retries=3)
        assert result == "Content"
        assert mock_fetch.call_count == 1

    @patch('fetcher.fetch_url')
    @patch('time.sleep')
    def test_fetch_with_retry_eventual_success(self, mock_sleep, mock_fetch):
        """Test successful fetch after retries."""
        mock_fetch.side_effect = [
            FetchError("Failed"),
            FetchError("Failed"),
            "Content"
        ]
        
        result = fetch_with_retry("https://example.com", max_retries=3)
        assert result == "Content"
        assert mock_fetch.call_count == 3

    @patch('fetcher.fetch_url')
    def test_fetch_with_retry_exhausted(self, mock_fetch):
        """Test all retries exhausted."""
        mock_fetch.side_effect = FetchError("Failed")
        
        with self.assertRaises(FetchError):
            fetch_with_retry("https://example.com", max_retries=2)
        
        assert mock_fetch.call_count == 2


if __name__ == "__main__":
    unittest.main()
