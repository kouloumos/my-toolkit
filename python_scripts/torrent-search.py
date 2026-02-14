#!/usr/bin/env python3

"""
Search for movies on YTS and download torrents to managed cache.
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import subprocess

try:
    import requests
except ImportError:
    print("Error: requests is not installed")
    print("Install it with: pip install requests")
    sys.exit(1)

# Import toolkit utilities for proxy and SSL configuration
try:
    from toolkit_utils import ProxyConfig, SSLConfig
except ImportError:
    # Fallback if running outside my-toolkit environment
    print("Warning: toolkit_utils not found, proxy and SSL features may not work")
    class ProxyConfig:
        enabled = False
        proxies = None
        url = None
    class SSLConfig:
        verify = False
        @staticmethod
        def disable_warnings():
            pass

# Setup proxy and SSL configuration
PROXY_CONFIG = ProxyConfig()
SSL_CONFIG = SSLConfig()


class Config:
    """Centralized configuration for torrent manager"""

    # Cache directory for torrent downloads
    CACHE_DIR = Path.home() / ".cache" / "my-toolkit" / "torrents"

    # Metadata file to track downloads
    METADATA_FILE = CACHE_DIR / "metadata.json"

    # YTS API mirrors (try in order if one is blocked)
    # Note: Your ISP may block some of these domains
    YTS_API_MIRRORS = [
        "https://yts.mx/api/v2",
        "https://yts.lt/api/v2",
        "https://yts.am/api/v2",
        "https://yts.ag/api/v2",
    ]

    # Default quality preferences (in order of preference)
    QUALITY_PREFERENCE = ["1080p", "720p", "2160p", "3D"]

    # Timeout for API requests (seconds)
    REQUEST_TIMEOUT = 10


class TorrentCache:
    """Manage torrent cache and metadata"""

    def __init__(self, config: Config):
        self.config = config
        self.config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def load_metadata(self) -> Dict:
        """Load metadata from disk"""
        if not self.config.METADATA_FILE.exists():
            return {"movies": []}

        try:
            with open(self.config.METADATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load metadata: {e}")
            return {"movies": []}

    def save_metadata(self, metadata: Dict):
        """Save metadata to disk"""
        try:
            with open(self.config.METADATA_FILE, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save metadata: {e}")

    def add_movie(self, movie_info: Dict):
        """Add a movie to the cache metadata"""
        metadata = self.load_metadata()

        # Check if movie already exists
        for movie in metadata["movies"]:
            if movie["id"] == movie_info["id"]:
                print(f"Movie already in cache: {movie['title']}")
                return

        # Add download timestamp
        movie_info["downloaded_at"] = datetime.now().isoformat()

        metadata["movies"].append(movie_info)
        self.save_metadata(metadata)

    def get_next_id(self) -> int:
        """Get next available movie ID for cache"""
        metadata = self.load_metadata()
        if not metadata["movies"]:
            return 1
        return max(movie.get("cache_id", 0) for movie in metadata["movies"]) + 1


class YTSClient:
    """Client for YTS API"""

    def __init__(self, config: Config):
        self.config = config

    def search_movies(self, query: str, limit: int = 20) -> Optional[List[Dict]]:
        """
        Search for movies on YTS (tries multiple mirrors if blocked)

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of movie dictionaries or None on error
        """
        params = {
            "query_term": query,
            "limit": limit,
            "sort_by": "seeds",  # Most seeded first
        }

        # Try each mirror until one works
        last_error = None

        # Disable SSL warnings if verification is disabled
        if not SSL_CONFIG.verify:
            SSL_CONFIG.disable_warnings()

        for mirror_url in self.config.YTS_API_MIRRORS:
            url = f"{mirror_url}/list_movies.json"

            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.config.REQUEST_TIMEOUT,
                    verify=SSL_CONFIG.verify,
                    proxies=PROXY_CONFIG.proxies
                )
                response.raise_for_status()

                # Check if we got HTML instead of JSON (ISP block page)
                content_type = response.headers.get('content-type', '')
                if 'html' in content_type.lower():
                    last_error = f"{mirror_url}: Blocked by ISP (got HTML instead of JSON)"
                    continue

                data = response.json()

                if data["status"] != "ok":
                    print(f"API Error: {data.get('status_message', 'Unknown error')}")
                    return None

                movies = data.get("data", {}).get("movies", [])
                return movies if movies else []

            except requests.Timeout:
                last_error = f"{mirror_url}: Timeout"
                continue
            except requests.RequestException as e:
                last_error = f"{mirror_url}: {e}"
                continue
            except (ValueError, KeyError) as e:
                # JSON parse error - likely an ISP block page
                last_error = f"{mirror_url}: Invalid JSON (likely blocked)"
                continue
            except Exception as e:
                last_error = f"{mirror_url}: {e}"
                continue

        # All mirrors failed
        print("Error: All YTS mirrors failed or are blocked.")
        print(f"Last error: {last_error}")
        print("\nThis usually means:")
        print("  1. Your ISP is blocking YTS domains")
        print("  2. You need to use a VPN or proxy")
        print("  3. Try setting FORCE_SSL_VERIFY=1 if you have proper SSL config")
        return None


class TorrentSearcher:
    """Search and download torrents"""

    def __init__(self, config: Config):
        self.config = config
        self.yts_client = YTSClient(config)
        self.cache = TorrentCache(config)

    def format_size(self, size_bytes: str) -> str:
        """Format file size from bytes to human-readable"""
        try:
            size = float(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size < 1024.0:
                    return f"{size:.1f}{unit}"
                size /= 1024.0
            return f"{size:.1f}PB"
        except:
            return size_bytes

    def display_results(self, movies: List[Dict]):
        """Display search results in a formatted way"""
        if not movies:
            print("No movies found.")
            return

        print(f"\nFound {len(movies)} movie(s):\n")
        print("=" * 80)

        for idx, movie in enumerate(movies, 1):
            title = movie.get("title", "Unknown")
            year = movie.get("year", "Unknown")
            rating = movie.get("rating", "N/A")
            genres = ", ".join(movie.get("genres", []))

            print(f"\n[{idx}] {title} ({year})")
            print(f"    Rating: {rating}/10 | Genres: {genres}")

            # Display available torrents
            torrents = movie.get("torrents", [])
            if torrents:
                print("    Available qualities:")
                for torrent in torrents:
                    quality = torrent.get("quality", "Unknown")
                    size = torrent.get("size", "Unknown")
                    seeds = torrent.get("seeds", 0)
                    peers = torrent.get("peers", 0)
                    print(f"      - {quality}: {size} | Seeds: {seeds} | Peers: {peers}")

        print("\n" + "=" * 80)

    def select_torrent(self, movie: Dict, quality: Optional[str] = None) -> Optional[Dict]:
        """
        Select best torrent from movie based on quality preference

        Args:
            movie: Movie dictionary from YTS
            quality: Specific quality to select, or None for automatic selection

        Returns:
            Selected torrent dictionary or None
        """
        torrents = movie.get("torrents", [])
        if not torrents:
            return None

        # If specific quality requested, try to find it
        if quality:
            for torrent in torrents:
                if torrent.get("quality", "").lower() == quality.lower():
                    return torrent
            print(f"Warning: Quality '{quality}' not found, using best available")

        # Otherwise, use quality preference order
        for preferred_quality in self.config.QUALITY_PREFERENCE:
            for torrent in torrents:
                if torrent.get("quality", "") == preferred_quality:
                    return torrent

        # Fallback: return first torrent (highest seeded)
        return torrents[0]

    def download_torrent(self, movie: Dict, torrent: Dict, watch_dir: str) -> bool:
        """
        Download torrent using download-torrent.sh

        Args:
            movie: Movie metadata
            torrent: Torrent metadata
            watch_dir: Directory to download to

        Returns:
            True if download initiated successfully
        """
        magnet_url = torrent.get("url")
        if not magnet_url:
            print("Error: No magnet URL found")
            return False

        # Get movie directory name (sanitize title)
        cache_id = self.cache.get_next_id()
        title = movie.get("title", "Unknown").replace("/", "-")
        year = movie.get("year", "")
        movie_dir_name = f"{cache_id}-{title}-{year}"
        movie_dir = Path(watch_dir) / movie_dir_name

        print(f"\nDownloading: {title} ({year}) - {torrent.get('quality', 'Unknown')}")
        print(f"Size: {torrent.get('size', 'Unknown')}")
        print(f"Seeds: {torrent.get('seeds', 0)} | Peers: {torrent.get('peers', 0)}")
        print(f"Download directory: {movie_dir}")
        print("")

        # Call download-torrent.sh
        try:
            # Check if we're in dev mode or production
            import os
            if os.environ.get("MY_TOOLKIT_DEV_MODE") == "1":
                download_script = "./shell_scripts/download-torrent.sh"
            else:
                # In production, use my-toolkit command
                download_script = "my-toolkit"
                magnet_url = ["download-torrent", "--no-subtitles", "-d", str(movie_dir), magnet_url]
                result = subprocess.run([download_script] + magnet_url[:-1] + [magnet_url[-1]])

            if os.environ.get("MY_TOOLKIT_DEV_MODE") == "1":
                result = subprocess.run([
                    download_script,
                    "--no-subtitles",  # We'll handle subtitles separately in torrent-watch
                    "-d", str(movie_dir),
                    magnet_url
                ])

            if result.returncode == 0:
                # Add to cache metadata
                movie_info = {
                    "cache_id": cache_id,
                    "id": movie.get("id"),
                    "title": title,
                    "year": year,
                    "quality": torrent.get("quality", "Unknown"),
                    "size": torrent.get("size", "Unknown"),
                    "rating": movie.get("rating", "N/A"),
                    "genres": movie.get("genres", []),
                    "directory": movie_dir_name,
                    "magnet_url": magnet_url,
                }
                self.cache.add_movie(movie_info)
                print(f"\nMovie added to cache with ID: {cache_id}")
                print(f"Use 'my-toolkit torrent-watch {cache_id}' to play")
                return True
            else:
                print("\nDownload failed!")
                return False

        except Exception as e:
            print(f"Error downloading torrent: {e}")
            return False

    def search_and_download(self, query: str, auto_download: bool = False,
                           quality: Optional[str] = None, limit: int = 20):
        """
        Search for movies and optionally download

        Args:
            query: Search query
            auto_download: Automatically download first result
            quality: Preferred quality
            limit: Maximum results to show
        """
        print(f"Searching YTS for: {query}...")
        if PROXY_CONFIG.enabled:
            print(f"Using proxy: {PROXY_CONFIG.url}")

        movies = self.yts_client.search_movies(query, limit=limit)

        if movies is None:
            return

        if not movies:
            print("No movies found.")
            return

        self.display_results(movies)

        # Auto-download first result
        if auto_download:
            movie = movies[0]
            torrent = self.select_torrent(movie, quality)
            if torrent:
                self.download_torrent(movie, torrent, str(self.config.CACHE_DIR))
            return

        # Interactive selection
        try:
            print("\nEnter movie number to download (or 'q' to quit): ", end="")
            choice = input().strip()

            if choice.lower() == 'q':
                return

            idx = int(choice) - 1
            if idx < 0 or idx >= len(movies):
                print("Invalid selection")
                return

            movie = movies[idx]

            # If multiple qualities available, ask which one
            torrents = movie.get("torrents", [])
            if len(torrents) > 1 and not quality:
                print("\nAvailable qualities:")
                for i, torrent in enumerate(torrents, 1):
                    print(f"  [{i}] {torrent.get('quality')} - {torrent.get('size')}")
                print("\nSelect quality (or press Enter for best): ", end="")
                quality_choice = input().strip()

                if quality_choice:
                    quality_idx = int(quality_choice) - 1
                    if 0 <= quality_idx < len(torrents):
                        torrent = torrents[quality_idx]
                    else:
                        torrent = self.select_torrent(movie, quality)
                else:
                    torrent = self.select_torrent(movie, quality)
            else:
                torrent = self.select_torrent(movie, quality)

            if torrent:
                self.download_torrent(movie, torrent, str(self.config.CACHE_DIR))

        except (ValueError, IndexError):
            print("Invalid input")
        except KeyboardInterrupt:
            print("\nCancelled")


def main():
    parser = argparse.ArgumentParser(
        description="Search for movies on YTS and download torrents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent-search.py "Knives Out"
  torrent-search.py -a "Matrix"
  torrent-search.py -q 720p "Inception"
  torrent-search.py --limit 10 "Star Wars"

Note: This tool uses YTS API for movie torrents only.
For TV shows, you'll need a different solution (like Jackett).
        """
    )

    parser.add_argument(
        "query",
        type=str,
        help="Movie title to search for"
    )

    parser.add_argument(
        "-a", "--auto",
        action="store_true",
        help="Automatically download first result"
    )

    parser.add_argument(
        "-q", "--quality",
        type=str,
        choices=["720p", "1080p", "2160p", "3D"],
        help="Preferred video quality"
    )

    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=20,
        help="Maximum number of results to show (default: 20)"
    )

    args = parser.parse_args()

    config = Config()
    searcher = TorrentSearcher(config)

    searcher.search_and_download(
        query=args.query,
        auto_download=args.auto,
        quality=args.quality,
        limit=args.limit
    )


if __name__ == "__main__":
    main()
