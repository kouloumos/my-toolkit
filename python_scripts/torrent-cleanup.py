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

    CACHE_DIR = Path.home() / ".cache" / "my-toolkit" / "torrents"
    METADATA_FILE = CACHE_DIR / "metadata.json"


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
        directory_name = movie.get("directory", "")

        print(f"\nMovie to remove:")
        print(f"  [{cache_id}] {title} ({year})")
        print(f"  Quality: {movie.get('quality', 'Unknown')}")
        print(f"  Size: {movie.get('size', 'Unknown')}")

        # Check if directory exists
        movie_dir = self.config.CACHE_DIR / directory_name if directory_name else None
        if movie_dir and movie_dir.exists():
            # Calculate actual size
            total_size = sum(f.stat().st_size for f in movie_dir.rglob('*') if f.is_file())
            size_gb = total_size / (1024 ** 3)
            print(f"  Disk space to free: {size_gb:.2f} GB")

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

        # Remove directory
        if movie_dir and movie_dir.exists():
            try:
                shutil.rmtree(movie_dir)
                print(f"✓ Removed directory: {movie_dir}")
            except Exception as e:
                print(f"Error removing directory: {e}")
                # Continue anyway to clean metadata

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
            directory_name = movie.get("directory", "")
            if directory_name:
                movie_dir = self.config.CACHE_DIR / directory_name
                if movie_dir.exists():
                    size = sum(f.stat().st_size for f in movie_dir.rglob('*') if f.is_file())
                    total_size += size

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

        # Remove all directories
        removed_count = 0
        for movie in movies:
            directory_name = movie.get("directory", "")
            if directory_name:
                movie_dir = self.config.CACHE_DIR / directory_name
                if movie_dir.exists():
                    try:
                        shutil.rmtree(movie_dir)
                        removed_count += 1
                    except Exception as e:
                        print(f"Error removing {movie_dir}: {e}")

        # Clear metadata
        metadata["movies"] = []
        self.save_metadata(metadata)

        print(f"\n✓ Removed {removed_count} movie(s)")
        return removed_count

    def cleanup_orphans(self) -> int:
        """
        Remove directories that don't have metadata entries

        Returns:
            Number of orphaned directories removed
        """
        if not self.config.CACHE_DIR.exists():
            print("Cache directory doesn't exist")
            return 0

        metadata = self.load_metadata()
        movies = metadata.get("movies", [])

        # Get all valid directory names from metadata
        valid_dirs = {movie.get("directory") for movie in movies if movie.get("directory")}

        # Find all directories in cache
        cache_dirs = [d for d in self.config.CACHE_DIR.iterdir() if d.is_dir()]

        # Find orphans
        orphans = [d for d in cache_dirs if d.name not in valid_dirs]

        if not orphans:
            print("No orphaned directories found")
            return 0

        print(f"\nFound {len(orphans)} orphaned director(y/ies):")
        for orphan in orphans:
            size = sum(f.stat().st_size for f in orphan.rglob('*') if f.is_file())
            size_gb = size / (1024 ** 3)
            print(f"  - {orphan.name} ({size_gb:.2f} GB)")

        try:
            print("\nRemove orphaned directories? [y/N]: ", end="")
            confirm = input().strip().lower()
            if confirm not in ['y', 'yes']:
                print("Cancelled")
                return 0
        except KeyboardInterrupt:
            print("\nCancelled")
            return 0

        removed_count = 0
        for orphan in orphans:
            try:
                shutil.rmtree(orphan)
                removed_count += 1
                print(f"✓ Removed {orphan.name}")
            except Exception as e:
                print(f"Error removing {orphan.name}: {e}")

        return removed_count


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup torrent cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent-cleanup.py 1              # Remove movie with ID 1
  torrent-cleanup.py --all          # Remove all movies
  torrent-cleanup.py --orphans      # Clean up orphaned directories
  torrent-cleanup.py -f 2           # Force remove without confirmation

Cleanup operations:
  - Remove movie by ID: Deletes the movie directory and removes metadata
  - Remove all: Clears entire cache
  - Remove orphans: Cleans up directories without metadata entries
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
        "-o", "--orphans",
        action="store_true",
        help="Remove orphaned directories (directories without metadata)"
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
    elif args.orphans:
        cleaner.cleanup_orphans()
    elif args.cache_id is not None:
        cleaner.remove_movie(args.cache_id, force=args.force)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
