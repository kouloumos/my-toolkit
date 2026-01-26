#!/usr/bin/env python3

"""
List all movies in the torrent cache.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict


class Config:
    """Centralized configuration for torrent manager"""

    CACHE_DIR = Path.home() / ".cache" / "my-toolkit" / "torrents"
    METADATA_FILE = CACHE_DIR / "metadata.json"


class TorrentLister:
    """List cached torrents"""

    def __init__(self, config: Config):
        self.config = config

    def load_metadata(self) -> Dict:
        """Load metadata from disk"""
        if not self.config.METADATA_FILE.exists():
            return {"movies": []}

        try:
            with open(self.config.METADATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error: Failed to load metadata: {e}")
            return {"movies": []}

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

    def get_directory_size(self, directory: Path) -> str:
        """Get total size of directory"""
        if not directory.exists():
            return "N/A"

        try:
            total_size = sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())
            return self.format_size(total_size)
        except Exception:
            return "N/A"

    def format_size(self, size_bytes: int) -> str:
        """Format file size to human-readable"""
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
        metadata = self.load_metadata()
        movies = metadata.get("movies", [])

        if not movies:
            print("No movies in cache.")
            print(f"\nUse 'my-toolkit torrent-search \"Movie Title\"' to download movies.")
            return

        print(f"\nCached Movies ({len(movies)}):\n")
        print("=" * 80)

        for movie in sorted(movies, key=lambda m: m.get("cache_id", 0)):
            cache_id = movie.get("cache_id", "?")
            title = movie.get("title", "Unknown")
            year = movie.get("year", "Unknown")
            quality = movie.get("quality", "Unknown")
            size = movie.get("size", "Unknown")
            downloaded_at = movie.get("downloaded_at", "Unknown")
            time_ago = self.format_time_ago(downloaded_at)

            print(f"\n[{cache_id}] {title} ({year})")
            print(f"    Quality: {quality} | Size: {size} | Downloaded: {time_ago}")

            if verbose:
                rating = movie.get("rating", "N/A")
                genres = ", ".join(movie.get("genres", []))
                directory = movie.get("directory", "Unknown")
                full_path = self.config.CACHE_DIR / directory

                print(f"    Rating: {rating}/10 | Genres: {genres}")
                print(f"    Location: {full_path}")

                # Check if directory still exists
                if full_path.exists():
                    actual_size = self.get_directory_size(full_path)
                    print(f"    Actual size: {actual_size}")

                    # List video files
                    video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
                    video_files = [f for f in full_path.rglob('*') if f.suffix.lower() in video_extensions]

                    if video_files:
                        print(f"    Video files: {len(video_files)}")
                        for video_file in video_files[:3]:  # Show first 3
                            print(f"      - {video_file.name}")
                        if len(video_files) > 3:
                            print(f"      ... and {len(video_files) - 3} more")
                else:
                    print(f"    ⚠ Directory not found (may have been deleted)")

        print("\n" + "=" * 80)
        print(f"\nCommands:")
        print(f"  Watch:   my-toolkit torrent-watch <id>")
        print(f"  Cleanup: my-toolkit torrent-cleanup <id>")
        print(f"  List subtitles: my-toolkit find-subtitles <path>")


def main():
    parser = argparse.ArgumentParser(
        description="List all movies in the torrent cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent-list.py
  torrent-list.py -v

The cache is stored in: ~/.cache/my-toolkit/torrents/
        """
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed information including file paths"
    )

    args = parser.parse_args()

    config = Config()
    lister = TorrentLister(config)
    lister.list_movies(verbose=args.verbose)


if __name__ == "__main__":
    main()
