#!/usr/bin/env python3

"""
Unified torrent management: search, download, list, watch, resume, and cleanup.
"""

import argparse
import json
import sys
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

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

    # Default download directory for torrents
    DEFAULT_DOWNLOAD_DIR = Path(os.environ.get("TORRENT_DOWNLOAD_DIR", str(Path.home() / "Downloads" / "torrents")))

    # Metadata directory (index only, not storage)
    METADATA_DIR = Path.home() / ".cache" / "my-toolkit" / "torrents"

    # Metadata file to track downloads
    METADATA_FILE = METADATA_DIR / "metadata.json"

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

    # BitTorrent trackers for magnet link construction
    TRACKERS = [
        "udp://open.demonii.com:1337/announce",
        "udp://tracker.openbittorrent.com:80",
        "udp://tracker.coppersurfer.tk:6969",
        "udp://glotorrents.pw:6969/announce",
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://torrent.gresille.org:80/announce",
        "udp://p4p.arenabg.com:1337",
        "udp://tracker.leechers-paradise.org:6969",
    ]

    # Video file extensions
    VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}


class TorrentCache:
    """Manage torrent metadata index"""

    def __init__(self, config: Config):
        self.config = config
        self.config.METADATA_DIR.mkdir(parents=True, exist_ok=True)

    def load_metadata(self) -> Dict:
        """Load metadata from disk, auto-migrating old format"""
        if not self.config.METADATA_FILE.exists():
            return {"movies": []}

        try:
            with open(self.config.METADATA_FILE, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load metadata: {e}")
            return {"movies": []}

        # Auto-migrate old "directory" field to new "path" field
        migrated = False
        for movie in metadata.get("movies", []):
            if "directory" in movie and "path" not in movie:
                old_dir = movie.pop("directory")
                # Best-effort: reconstruct absolute path from old cache dir layout
                old_path = self.config.METADATA_DIR / old_dir
                if old_path.exists():
                    movie["path"] = str(old_path)
                else:
                    movie["path"] = ""
                if "status" not in movie:
                    movie["status"] = "downloaded" if movie["path"] else "downloading"
                migrated = True
            elif "directory" in movie:
                # Both exist (shouldn't happen), drop old field
                movie.pop("directory")
                migrated = True
            if "status" not in movie:
                movie["status"] = "downloaded"
                migrated = True

        if migrated:
            self.save_metadata(metadata)

        return metadata

    def save_metadata(self, metadata: Dict):
        """Save metadata to disk"""
        try:
            with open(self.config.METADATA_FILE, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save metadata: {e}")

    def add_movie(self, movie_info: Dict):
        """Add a movie to the metadata index"""
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

    def update_movie_path(self, cache_id: int, path: str):
        """Update the download path and status for a movie"""
        metadata = self.load_metadata()
        for movie in metadata.get("movies", []):
            if movie.get("cache_id") == cache_id:
                movie["path"] = path
                movie["status"] = "downloaded"
                self.save_metadata(metadata)
                return
        print(f"Warning: Movie with cache_id {cache_id} not found in metadata")

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


class TorrentManager:
    """Unified torrent management: search, list, watch, resume, cleanup"""

    def __init__(self, config: Config):
        self.config = config
        self.yts_client = YTSClient(config)
        self.cache = TorrentCache(config)

    # =========================================================================
    # Search
    # =========================================================================

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

    def _run_download(self, magnet_url: str, download_dir: Path, cache_id: int) -> bool:
        """
        Run download-torrent.sh and update cache on completion.

        Args:
            magnet_url: Magnet link to download
            download_dir: Directory to download into
            cache_id: Cache ID to update on completion

        Returns:
            True if download completed successfully
        """
        try:
            if os.environ.get("MY_TOOLKIT_DEV_MODE") == "1":
                cmd = [
                    "./shell_scripts/download-torrent.sh",
                    "--no-subtitles",
                    "-d", str(download_dir),
                    magnet_url
                ]
            else:
                cmd = [
                    "my-toolkit", "download-torrent",
                    "--no-subtitles",
                    "-d", str(download_dir),
                    magnet_url
                ]

            actual_path = ""
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            for line in process.stdout:
                line = line.rstrip("\n")
                if line.startswith("TORRENT_DOWNLOAD_PATH="):
                    actual_path = line.split("=", 1)[1]
                else:
                    print(line)

            process.wait()

            if process.returncode == 0:
                if actual_path:
                    self.cache.update_movie_path(cache_id, actual_path)
                    print(f"\nDownload completed! Path: {actual_path}")
                else:
                    # Fallback: no path detected, mark as downloaded with download_dir
                    self.cache.update_movie_path(cache_id, str(download_dir))
                    print(f"\nDownload completed!")
                print(f"Use 'my-toolkit torrent watch {cache_id}' to play")
                return True
            else:
                print(f"\nDownload exited with code {process.returncode}")
                print(f"Movie is still in cache (ID: {cache_id}, status: downloading)")
                print(f"Use 'my-toolkit torrent resume {cache_id}' to retry")
                return False

        except Exception as e:
            print(f"Error downloading torrent: {e}")
            return False

    def download_torrent(self, movie: Dict, torrent: Dict) -> bool:
        """
        Download torrent using download-torrent.sh

        Args:
            movie: Movie metadata
            torrent: Torrent metadata

        Returns:
            True if download initiated successfully
        """
        # Construct magnet link from torrent hash (more reliable than .torrent URLs)
        torrent_hash = torrent.get("hash")
        if not torrent_hash:
            print("Error: No torrent hash found")
            return False

        cache_id = self.cache.get_next_id()
        title = movie.get("title", "Unknown").replace("/", "-")
        year = movie.get("year", "")
        download_dir = self.config.DEFAULT_DOWNLOAD_DIR

        # Build magnet link from hash
        from urllib.parse import quote
        trackers = "&".join(f"tr={quote(t)}" for t in self.config.TRACKERS)
        magnet_url = f"magnet:?xt=urn:btih:{torrent_hash}&dn={quote(title)}&{trackers}"

        print(f"\nDownloading: {title} ({year}) - {torrent.get('quality', 'Unknown')}")
        print(f"Size: {torrent.get('size', 'Unknown')}")
        print(f"Seeds: {torrent.get('seeds', 0)} | Peers: {torrent.get('peers', 0)}")
        print(f"Download directory: {download_dir}")
        print("")

        # Save metadata before starting download (download is blocking and may be interrupted)
        movie_info = {
            "cache_id": cache_id,
            "id": movie.get("id"),
            "title": title,
            "year": year,
            "quality": torrent.get("quality", "Unknown"),
            "size": torrent.get("size", "Unknown"),
            "rating": movie.get("rating", "N/A"),
            "genres": movie.get("genres", []),
            "path": "",
            "status": "downloading",
            "magnet_url": magnet_url,
        }
        self.cache.add_movie(movie_info)
        print(f"Movie added to cache with ID: {cache_id}")

        return self._run_download(magnet_url, download_dir, cache_id)

    def search(self, query: str, auto_download: bool = False,
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
                self.download_torrent(movie, torrent)
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
                self.download_torrent(movie, torrent)

        except (ValueError, IndexError):
            print("Invalid input")
        except KeyboardInterrupt:
            print("\nCancelled")

    # =========================================================================
    # List
    # =========================================================================

    def format_time_ago(self, timestamp: str) -> str:
        """Format timestamp to human-readable 'time ago' format"""
        try:
            dt = datetime.fromisoformat(timestamp)
            now = datetime.now()
            delta = now - dt

            seconds = delta.total_seconds()
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f"{minutes}m ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours}h ago"
            else:
                days = int(seconds / 86400)
                return f"{days}d ago"
        except:
            return timestamp

    def get_path_size(self, path: Path) -> str:
        """Get total size of a file or directory"""
        if not path.exists():
            return "N/A"

        try:
            if path.is_file():
                return self.format_disk_size(path.stat().st_size)
            total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
            return self.format_disk_size(total_size)
        except Exception:
            return "N/A"

    def format_disk_size(self, size_bytes: int) -> str:
        """Format file size (int bytes) to human-readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}PB"

    def list_movies(self, verbose: bool = False):
        """
        List all movies in cache

        Args:
            verbose: Show detailed information
        """
        metadata = self.cache.load_metadata()
        movies = metadata.get("movies", [])

        if not movies:
            print("No movies in cache.")
            print(f"\nUse 'my-toolkit torrent search \"Movie Title\"' to download movies.")
            return

        print(f"\nCached Movies ({len(movies)}):\n")
        print("=" * 80)

        for movie in sorted(movies, key=lambda m: m.get("cache_id", 0)):
            cache_id = movie.get("cache_id", "?")
            title = movie.get("title", "Unknown")
            year = movie.get("year", "Unknown")
            quality = movie.get("quality", "Unknown")
            size = movie.get("size", "Unknown")
            status = movie.get("status", "unknown")
            downloaded_at = movie.get("downloaded_at", "Unknown")
            time_ago = self.format_time_ago(downloaded_at)

            status_label = " [DOWNLOADING]" if status == "downloading" else ""
            print(f"\n[{cache_id}] {title} ({year}){status_label}")
            print(f"    Quality: {quality} | Size: {size} | Downloaded: {time_ago}")

            if verbose:
                rating = movie.get("rating", "N/A")
                genres = ", ".join(movie.get("genres", []))
                movie_path = Path(movie.get("path", ""))

                print(f"    Rating: {rating}/10 | Genres: {genres}")
                print(f"    Location: {movie_path or 'N/A'}")

                if movie_path and movie_path.exists():
                    actual_size = self.get_path_size(movie_path)
                    print(f"    Actual size: {actual_size}")

                    # Find video files (handle both file and directory paths)
                    if movie_path.is_file():
                        if movie_path.suffix.lower() in self.config.VIDEO_EXTENSIONS:
                            print(f"    Video file: {movie_path.name}")
                    else:
                        video_files = [f for f in movie_path.rglob('*') if f.suffix.lower() in self.config.VIDEO_EXTENSIONS]
                        if video_files:
                            print(f"    Video files: {len(video_files)}")
                            for video_file in video_files[:3]:
                                print(f"      - {video_file.name}")
                            if len(video_files) > 3:
                                print(f"      ... and {len(video_files) - 3} more")
                elif movie_path:
                    print(f"    Path not found (may have been deleted)")
                elif status == "downloading":
                    print(f"    Download in progress or interrupted")

        print("\n" + "=" * 80)
        print(f"\nCommands:")
        print(f"  Watch:   my-toolkit torrent watch <id>")
        print(f"  Resume:  my-toolkit torrent resume <id>")
        print(f"  Cleanup: my-toolkit torrent cleanup <id>")
        print(f"  List subtitles: my-toolkit find-subtitles <path>")

    # =========================================================================
    # Watch
    # =========================================================================

    def find_video_files(self, directory: Path) -> List[Path]:
        """Find all video files in directory"""
        if not directory.exists():
            return []

        video_files = [
            f for f in directory.rglob('*')
            if f.is_file() and f.suffix.lower() in self.config.VIDEO_EXTENSIONS
        ]

        # Sort by size (largest first, usually the main movie)
        video_files.sort(key=lambda f: f.stat().st_size, reverse=True)
        return video_files

    def check_watch_dependencies(self) -> bool:
        """Check if required tools for watching are available"""
        missing = []

        if not shutil.which("bwrap"):
            missing.append("bubblewrap (bwrap)")

        if not shutil.which("vlc"):
            missing.append("vlc")

        if missing:
            print("Error: Missing required dependencies:")
            for tool in missing:
                print(f"  - {tool}")
            print("\nThese should be provided by the Nix environment.")
            print("If you're in development mode, make sure you ran: nix develop")
            return False

        return True

    def launch_vlc_isolated(self, video_path: Path, with_subtitles: bool = True) -> bool:
        """
        Launch VLC in an isolated bubblewrap sandbox

        Args:
            video_path: Path to video file
            with_subtitles: Whether to search for subtitles first

        Returns:
            True if launched successfully
        """
        if not video_path.exists():
            print(f"Error: Video file not found: {video_path}")
            return False

        # Optionally search for subtitles first
        if with_subtitles:
            print("Searching for subtitles...")
            try:
                if os.environ.get("MY_TOOLKIT_DEV_MODE") == "1":
                    subprocess.run([
                        "python3",
                        "./python_scripts/find-subtitles.py",
                        str(video_path)
                    ], check=False)
                else:
                    subprocess.run([
                        "my-toolkit",
                        "find-subtitles",
                        str(video_path)
                    ], check=False)
            except Exception as e:
                print(f"Warning: Subtitle search failed: {e}")
            print("")

        print(f"Launching VLC in isolated environment...")
        print(f"Playing: {video_path.name}")
        print("")

        uid = str(os.getuid())

        # Build bubblewrap command
        # This creates a minimal isolated environment for VLC
        bwrap_cmd = [
            "bwrap",
            # Start with minimal filesystem
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/sbin", "/sbin",
            "--ro-bind-try", "/nix", "/nix",  # For NixOS
            "--ro-bind-try", "/run/current-system", "/run/current-system",  # For NixOS
            # Bind video directory (read-only)
            "--ro-bind", str(video_path.parent), str(video_path.parent),
            # Minimal writable directories
            "--tmpfs", "/tmp",
            "--tmpfs", "/var",
            "--dir", f"/run/user/{uid}",
            "--dev", "/dev",
            "--proc", "/proc",
            # Unshare network (VLC doesn't need internet for local playback)
            "--unshare-net",
            # Share X11/Wayland for display
            "--ro-bind-try", "/tmp/.X11-unix", "/tmp/.X11-unix",
            "--ro-bind-try", str(Path.home() / ".Xauthority"), str(Path.home() / ".Xauthority"),
            # Share audio
            "--ro-bind-try", f"/run/user/{uid}/pulse", f"/run/user/{uid}/pulse",
            # Environment variables for display and audio
            "--setenv", "DISPLAY", os.environ.get("DISPLAY", ":0"),
            "--setenv", "PULSE_SERVER", os.environ.get("PULSE_SERVER", ""),
            # Run VLC
            "vlc",
            "--fullscreen",
            str(video_path)
        ]

        try:
            result = subprocess.run(bwrap_cmd)
            return result.returncode == 0
        except Exception as e:
            print(f"Error launching VLC: {e}")
            return False

    def watch_movie(self, cache_id: int, with_subtitles: bool = True, select_file: bool = False):
        """
        Watch a movie from cache

        Args:
            cache_id: Movie cache ID
            with_subtitles: Whether to search for subtitles first
            select_file: Manually select which video file to play
        """
        # Check dependencies
        if not self.check_watch_dependencies():
            sys.exit(1)

        # Find movie in cache
        metadata = self.cache.load_metadata()
        movie = None
        for m in metadata.get("movies", []):
            if m.get("cache_id") == cache_id:
                movie = m
                break

        if not movie:
            print(f"Error: Movie with ID {cache_id} not found in cache")
            print(f"Use 'my-toolkit torrent list' to see available movies")
            sys.exit(1)

        # Check download status
        status = movie.get("status", "downloaded")
        if status == "downloading":
            print(f"Error: Movie '{movie.get('title', 'Unknown')}' is still downloading or download was interrupted")
            print(f"Use 'my-toolkit torrent resume {cache_id}' to resume the download.")
            sys.exit(1)

        # Get movie path
        movie_path_str = movie.get("path", "")
        if not movie_path_str:
            print(f"Error: No download path recorded for this movie")
            sys.exit(1)

        movie_path = Path(movie_path_str)

        if not movie_path.exists():
            print(f"Error: Path not found: {movie_path}")
            print(f"The movie files may have been deleted.")
            sys.exit(1)

        # Handle single-file torrents (path is a file, not directory)
        if movie_path.is_file():
            if movie_path.suffix.lower() in self.config.VIDEO_EXTENSIONS:
                video_files = [movie_path]
            else:
                print(f"Error: Path is a file but not a video: {movie_path}")
                sys.exit(1)
        else:
            video_files = self.find_video_files(movie_path)

        if not video_files:
            print(f"Error: No video files found in {movie_path}")
            sys.exit(1)

        # Select video file
        video_file = None

        if len(video_files) == 1:
            video_file = video_files[0]
        elif select_file or len(video_files) > 1:
            print(f"\nFound {len(video_files)} video file(s):")
            for idx, vf in enumerate(video_files, 1):
                size = vf.stat().st_size / (1024 ** 3)  # GB
                print(f"  [{idx}] {vf.name} ({size:.2f} GB)")

            if not select_file:
                print(f"\nPlaying largest file (usually the main movie)")
                video_file = video_files[0]
            else:
                try:
                    print("\nSelect file to play (or press Enter for largest): ", end="")
                    choice = input().strip()

                    if not choice:
                        video_file = video_files[0]
                    else:
                        idx = int(choice) - 1
                        if 0 <= idx < len(video_files):
                            video_file = video_files[idx]
                        else:
                            print("Invalid selection")
                            sys.exit(1)
                except (ValueError, KeyboardInterrupt):
                    print("\nCancelled")
                    sys.exit(1)

        if not video_file:
            print("Error: No video file selected")
            sys.exit(1)

        # Launch VLC in isolated environment
        print(f"\n{'=' * 80}")
        print(f"Movie: {movie.get('title', 'Unknown')} ({movie.get('year', 'Unknown')})")
        print(f"Quality: {movie.get('quality', 'Unknown')}")
        print(f"{'=' * 80}\n")

        success = self.launch_vlc_isolated(video_file, with_subtitles=with_subtitles)

        if not success:
            print("\nPlayback failed or was interrupted")
            sys.exit(1)

    # =========================================================================
    # Resume
    # =========================================================================

    def resume_download(self, cache_id: int):
        """
        Resume an interrupted download

        Args:
            cache_id: Movie cache ID
        """
        metadata = self.cache.load_metadata()
        movie = None
        for m in metadata.get("movies", []):
            if m.get("cache_id") == cache_id:
                movie = m
                break

        if not movie:
            print(f"Error: Movie with ID {cache_id} not found in cache")
            print(f"Use 'my-toolkit torrent list' to see available movies")
            sys.exit(1)

        status = movie.get("status", "downloaded")
        if status != "downloading":
            print(f"Error: Movie '{movie.get('title', 'Unknown')}' is not in 'downloading' state (status: {status})")
            print(f"Only interrupted downloads can be resumed.")
            sys.exit(1)

        magnet_url = movie.get("magnet_url", "")
        if not magnet_url:
            print(f"Error: No magnet URL stored for this movie")
            print(f"You may need to search and download it again.")
            sys.exit(1)

        title = movie.get("title", "Unknown")
        year = movie.get("year", "")
        quality = movie.get("quality", "Unknown")
        download_dir = self.config.DEFAULT_DOWNLOAD_DIR

        print(f"Resuming download: {title} ({year}) - {quality}")
        print(f"Download directory: {download_dir}")
        print("")

        self._run_download(magnet_url, download_dir, cache_id)

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup_movie(self, cache_id: int, force: bool = False) -> bool:
        """
        Remove a movie from cache

        Args:
            cache_id: Movie cache ID
            force: Skip confirmation

        Returns:
            True if removed successfully
        """
        metadata = self.cache.load_metadata()
        movies = metadata.get("movies", [])

        # Find movie
        movie = None
        movie_idx = None
        for idx, m in enumerate(movies):
            if m.get("cache_id") == cache_id:
                movie = m
                movie_idx = idx
                break

        if not movie:
            print(f"Error: Movie with ID {cache_id} not found in cache")
            return False

        title = movie.get("title", "Unknown")
        year = movie.get("year", "Unknown")
        movie_path_str = movie.get("path", "")
        movie_path = Path(movie_path_str) if movie_path_str else None

        print(f"\nMovie to remove:")
        print(f"  [{cache_id}] {title} ({year})")
        print(f"  Quality: {movie.get('quality', 'Unknown')}")
        print(f"  Size: {movie.get('size', 'Unknown')}")

        # Check if path exists and show disk usage
        if movie_path and movie_path.exists():
            if movie_path.is_file():
                total_size = movie_path.stat().st_size
            else:
                total_size = sum(f.stat().st_size for f in movie_path.rglob('*') if f.is_file())
            size_gb = total_size / (1024 ** 3)
            print(f"  Location: {movie_path}")
            print(f"  Disk space to free: {size_gb:.2f} GB")
        elif movie_path_str:
            print(f"  Location: {movie_path_str} (not found)")

        # Confirm deletion
        if not force:
            try:
                print("\nAre you sure you want to delete this movie? [y/N]: ", end="")
                confirm = input().strip().lower()
                if confirm not in ['y', 'yes']:
                    print("Cancelled")
                    return False
            except KeyboardInterrupt:
                print("\nCancelled")
                return False

        # Remove files
        if movie_path and movie_path.exists():
            try:
                if movie_path.is_file():
                    movie_path.unlink()
                else:
                    shutil.rmtree(movie_path)
                print(f"Removed: {movie_path}")
            except Exception as e:
                print(f"Error removing {movie_path}: {e}")

        # Remove from metadata
        movies.pop(movie_idx)
        metadata["movies"] = movies
        self.cache.save_metadata(metadata)
        print(f"Removed from cache metadata")

        return True

    def cleanup_all(self, force: bool = False) -> int:
        """
        Remove all movies from cache

        Args:
            force: Skip confirmation

        Returns:
            Number of movies removed
        """
        metadata = self.cache.load_metadata()
        movies = metadata.get("movies", [])

        if not movies:
            print("Cache is already empty")
            return 0

        print(f"\nMovies in cache: {len(movies)}")

        # Calculate total size
        total_size = 0
        for movie in movies:
            movie_path_str = movie.get("path", "")
            if movie_path_str:
                movie_path = Path(movie_path_str)
                if movie_path.exists():
                    if movie_path.is_file():
                        total_size += movie_path.stat().st_size
                    else:
                        total_size += sum(f.stat().st_size for f in movie_path.rglob('*') if f.is_file())

        if total_size > 0:
            size_gb = total_size / (1024 ** 3)
            print(f"Total disk space to free: {size_gb:.2f} GB")

        # Confirm deletion
        if not force:
            try:
                print("\nAre you sure you want to delete ALL movies? [y/N]: ", end="")
                confirm = input().strip().lower()
                if confirm not in ['y', 'yes']:
                    print("Cancelled")
                    return 0
            except KeyboardInterrupt:
                print("\nCancelled")
                return 0

        # Remove all files/directories
        removed_count = 0
        for movie in movies:
            movie_path_str = movie.get("path", "")
            if movie_path_str:
                movie_path = Path(movie_path_str)
                if movie_path.exists():
                    try:
                        if movie_path.is_file():
                            movie_path.unlink()
                        else:
                            shutil.rmtree(movie_path)
                        removed_count += 1
                    except Exception as e:
                        print(f"Error removing {movie_path}: {e}")

        # Clear metadata
        metadata["movies"] = []
        self.cache.save_metadata(metadata)

        print(f"\nRemoved {removed_count} movie(s)")
        return removed_count


def main():
    parser = argparse.ArgumentParser(
        description="Torrent management: search, download, list, watch, resume, and cleanup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent search "Knives Out"
  torrent search -a "Matrix"
  torrent list -v
  torrent watch 1
  torrent resume 1
  torrent cleanup 2
  torrent cleanup --all

Note: This tool uses YTS API for movie torrents only.
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- search ---
    search_parser = subparsers.add_parser(
        "search",
        help="Search for movies on YTS and download",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent search "Knives Out"
  torrent search -a "Matrix"
  torrent search -q 720p "Inception"
  torrent search --limit 10 "Star Wars"
        """
    )
    search_parser.add_argument("query", type=str, help="Movie title to search for")
    search_parser.add_argument("-a", "--auto", action="store_true",
                               help="Automatically download first result")
    search_parser.add_argument("-q", "--quality", type=str,
                               choices=["720p", "1080p", "2160p", "3D"],
                               help="Preferred video quality")
    search_parser.add_argument("-l", "--limit", type=int, default=20,
                               help="Maximum number of results to show (default: 20)")

    # --- list ---
    list_parser = subparsers.add_parser(
        "list",
        help="List all movies in the torrent cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent list
  torrent list -v
        """
    )
    list_parser.add_argument("-v", "--verbose", action="store_true",
                             help="Show detailed information including file paths")

    # --- watch ---
    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch a movie from cache in isolated VLC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent watch 1
  torrent watch --no-subtitles 2
  torrent watch --select-file 3

Security:
  VLC runs in a bubblewrap sandbox with:
  - Network access disabled (--unshare-net)
  - Read-only access to video files
  - Isolated filesystem (minimal bindings)
  - No access to your home directory
        """
    )
    watch_parser.add_argument("cache_id", type=int,
                              help="Movie cache ID (see 'torrent list' for IDs)")
    watch_parser.add_argument("-S", "--no-subtitles", action="store_true",
                              help="Skip automatic subtitle search")
    watch_parser.add_argument("-s", "--select-file", action="store_true",
                              help="Manually select which video file to play")

    # --- resume ---
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume an interrupted torrent download",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent resume 1

Only movies with status 'downloading' can be resumed.
Use 'torrent list -v' to see movie statuses.
        """
    )
    resume_parser.add_argument("cache_id", type=int,
                               help="Movie cache ID (see 'torrent list' for IDs)")

    # --- cleanup ---
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Remove movies from cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent cleanup 1              # Remove movie with ID 1
  torrent cleanup --all          # Remove all movies
  torrent cleanup -f 2           # Force remove without confirmation
        """
    )
    cleanup_parser.add_argument("cache_id", type=int, nargs="?",
                                help="Movie cache ID to remove (see 'torrent list' for IDs)")
    cleanup_parser.add_argument("-a", "--all", action="store_true",
                                help="Remove all movies from cache")
    cleanup_parser.add_argument("-f", "--force", action="store_true",
                                help="Skip confirmation prompt")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = Config()
    manager = TorrentManager(config)

    if args.command == "search":
        manager.search(
            query=args.query,
            auto_download=args.auto,
            quality=args.quality,
            limit=args.limit
        )
    elif args.command == "list":
        manager.list_movies(verbose=args.verbose)
    elif args.command == "watch":
        manager.watch_movie(
            cache_id=args.cache_id,
            with_subtitles=not args.no_subtitles,
            select_file=args.select_file
        )
    elif args.command == "resume":
        manager.resume_download(cache_id=args.cache_id)
    elif args.command == "cleanup":
        if args.all:
            manager.cleanup_all(force=args.force)
        elif args.cache_id is not None:
            manager.cleanup_movie(args.cache_id, force=args.force)
        else:
            cleanup_parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
