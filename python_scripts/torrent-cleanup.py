#!/usr/bin/env python3

"""
Cleanup torrent cache by removing movies.
"""

import argparse
import json
import sys
import shutil
from pathlib import Path
from typing import Dict, List


class Config:
    """Centralized configuration for torrent manager"""

    METADATA_DIR = Path.home() / ".cache" / "my-toolkit" / "torrents"
    METADATA_FILE = METADATA_DIR / "metadata.json"


class TorrentCleaner:
    """Cleanup torrent cache"""

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

    def save_metadata(self, metadata: Dict):
        """Save metadata to disk"""
        try:
            with open(self.config.METADATA_FILE, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save metadata: {e}")

    def remove_movie(self, cache_id: int, force: bool = False) -> bool:
        """
        Remove a movie from cache

        Args:
            cache_id: Movie cache ID
            force: Skip confirmation

        Returns:
            True if removed successfully
        """
        metadata = self.load_metadata()
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
        self.save_metadata(metadata)
        print(f"✓ Removed from cache metadata")

        return True

    def cleanup_all(self, force: bool = False) -> int:
        """
        Remove all movies from cache

        Args:
            force: Skip confirmation

        Returns:
            Number of movies removed
        """
        metadata = self.load_metadata()
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
        self.save_metadata(metadata)

        print(f"\nRemoved {removed_count} movie(s)")
        return removed_count


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup torrent cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent-cleanup.py 1              # Remove movie with ID 1
  torrent-cleanup.py --all          # Remove all movies
  torrent-cleanup.py -f 2           # Force remove without confirmation

Cleanup operations:
  - Remove movie by ID: Deletes the movie files and removes metadata
  - Remove all: Clears entire cache
        """
    )

    parser.add_argument(
        "cache_id",
        type=int,
        nargs="?",
        help="Movie cache ID to remove (see 'torrent-list' for IDs)"
    )

    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Remove all movies from cache"
    )

    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    config = Config()
    cleaner = TorrentCleaner(config)

    # Determine action
    if args.all:
        cleaner.cleanup_all(force=args.force)
    elif args.cache_id is not None:
        cleaner.remove_movie(args.cache_id, force=args.force)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
