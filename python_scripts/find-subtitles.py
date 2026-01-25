#!/usr/bin/env python3

"""
Find and download subtitles for video files using subliminal.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

try:
    from subliminal import (
        Video,
        download_best_subtitles,
        save_subtitles,
        scan_video,
        region,
    )
    from babelfish import Language
except ImportError:
    print("Error: subliminal is not installed")
    print("Install it with: pip install subliminal")
    sys.exit(1)


class Config:
    """Centralized configuration for subtitle finder"""

    # Default languages (ISO 639-3 codes)
    DEFAULT_LANGUAGES = ["eng"]

    # Supported video extensions
    VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}

    # Cache region for subliminal (speeds up repeated searches)
    CACHE_DIR = Path.home() / ".cache" / "subliminal"

    # Subtitle providers (subliminal supports: opensubtitles, tvsubtitles, podnapisi, etc.)
    # None means use all available providers
    PROVIDERS = None

    # Minimum subtitle score (0-100, higher = better match)
    MIN_SCORE = 0


class SubtitleFinder:
    """Find and download subtitles for video files"""

    def __init__(self, languages: List[str], download: bool = True, verbose: bool = False):
        """
        Initialize subtitle finder

        Args:
            languages: List of language codes (ISO 639-3, e.g., ['eng', 'spa'])
            download: Whether to download subtitles or just list them
            verbose: Show detailed information
        """
        self.languages = {Language(lang) for lang in languages}
        self.download = download
        self.verbose = verbose
        self.config = Config()

        # Ensure cache directory exists
        self.config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Configure cache
        region.configure(
            'dogpile.cache.dbm',
            arguments={'filename': str(self.config.CACHE_DIR / 'cachefile.dbm')}
        )

    def is_video_file(self, filepath: Path) -> bool:
        """Check if file is a supported video format"""
        return filepath.suffix.lower() in self.config.VIDEO_EXTENSIONS

    def find_subtitles(self, video_path: Path) -> bool:
        """
        Find and optionally download subtitles for a video file

        Args:
            video_path: Path to video file

        Returns:
            True if subtitles were found (and downloaded if enabled), False otherwise
        """
        if not video_path.exists():
            print(f"Error: File not found: {video_path}")
            return False

        if not self.is_video_file(video_path):
            print(f"Error: Not a supported video file: {video_path}")
            print(f"Supported extensions: {', '.join(sorted(self.config.VIDEO_EXTENSIONS))}")
            return False

        try:
            if self.verbose:
                print(f"Scanning video: {video_path.name}")

            # Scan video file to extract metadata
            video = scan_video(str(video_path))

            if self.verbose:
                print(f"Video info: {video}")
                print(f"Searching for subtitles in: {', '.join(str(lang) for lang in self.languages)}")

            # Search for best subtitles
            subtitles = download_best_subtitles(
                {video},
                self.languages,
                providers=self.config.PROVIDERS,
                min_score=self.config.MIN_SCORE
            )

            video_subtitles = subtitles.get(video, [])

            if not video_subtitles:
                print(f"No subtitles found for: {video_path.name}")
                return False

            print(f"Found {len(video_subtitles)} subtitle(s) for: {video_path.name}")

            # Display subtitle information
            for i, subtitle in enumerate(video_subtitles, 1):
                provider = subtitle.provider_name
                language = subtitle.language
                score = subtitle.score if hasattr(subtitle, 'score') else 'N/A'
                print(f"  {i}. Language: {language}, Provider: {provider}, Score: {score}")

            # Download subtitles if enabled
            if self.download:
                save_subtitles(video, video_subtitles)
                print(f"Downloaded {len(video_subtitles)} subtitle file(s) to: {video_path.parent}")

                # List downloaded files
                for subtitle in video_subtitles:
                    subtitle_path = video_path.with_suffix(f".{subtitle.language}{video_path.suffix}".replace(video_path.suffix, ".srt"))
                    if subtitle_path.exists():
                        print(f"  - {subtitle_path.name}")

            return True

        except Exception as e:
            print(f"Error processing {video_path.name}: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False

    def find_subtitles_recursive(self, directory: Path) -> dict:
        """
        Recursively find subtitles for all video files in a directory

        Args:
            directory: Directory to search

        Returns:
            Dictionary with success/failure counts
        """
        if not directory.exists():
            print(f"Error: Directory not found: {directory}")
            return {"success": 0, "failed": 0, "total": 0}

        if not directory.is_dir():
            print(f"Error: Not a directory: {directory}")
            return {"success": 0, "failed": 0, "total": 0}

        # Find all video files
        video_files = []
        for ext in self.config.VIDEO_EXTENSIONS:
            video_files.extend(directory.rglob(f"*{ext}"))

        if not video_files:
            print(f"No video files found in: {directory}")
            return {"success": 0, "failed": 0, "total": 0}

        print(f"Found {len(video_files)} video file(s) in: {directory}")
        print("")

        # Process each video file
        results = {"success": 0, "failed": 0, "total": len(video_files)}

        for video_file in video_files:
            print(f"Processing: {video_file.relative_to(directory)}")
            if self.find_subtitles(video_file):
                results["success"] += 1
            else:
                results["failed"] += 1
            print("")

        # Summary
        print("=" * 50)
        print(f"Summary: {results['success']}/{results['total']} successful")
        if results["failed"] > 0:
            print(f"Failed: {results['failed']}")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Find and download subtitles for video files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  find-subtitles.py movie.mp4
  find-subtitles.py -l eng spa movie.mkv
  find-subtitles.py -r ~/Videos
  find-subtitles.py --list-only movie.mp4

Supported languages (ISO 639-3 codes):
  eng (English), spa (Spanish), fra (French), deu (German),
  ita (Italian), por (Portuguese), rus (Russian), jpn (Japanese),
  kor (Korean), chi (Chinese), ara (Arabic), heb (Hebrew), etc.

Environment variables:
  SUBTITLE_LANGUAGES     Default languages (comma-separated, e.g., "eng,spa")
        """
    )

    parser.add_argument(
        "path",
        type=str,
        help="Video file or directory to process"
    )

    parser.add_argument(
        "-l", "--languages",
        nargs="+",
        default=None,
        help=f"Subtitle languages (ISO 639-3 codes, default: {' '.join(Config.DEFAULT_LANGUAGES)})"
    )

    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively process all video files in directory"
    )

    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list available subtitles without downloading"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed information"
    )

    args = parser.parse_args()

    # Determine languages
    import os
    languages = args.languages
    if languages is None:
        env_langs = os.environ.get("SUBTITLE_LANGUAGES")
        if env_langs:
            languages = env_langs.split(",")
        else:
            languages = Config.DEFAULT_LANGUAGES

    # Validate languages
    try:
        for lang in languages:
            Language(lang.strip())
    except Exception as e:
        print(f"Error: Invalid language code: {e}")
        print("Use ISO 639-3 codes (e.g., eng, spa, fra)")
        sys.exit(1)

    # Create subtitle finder
    finder = SubtitleFinder(
        languages=languages,
        download=not args.list_only,
        verbose=args.verbose
    )

    # Process path
    path = Path(args.path).resolve()

    if args.recursive or path.is_dir():
        results = finder.find_subtitles_recursive(path)
        success = results["success"] > 0
    else:
        success = finder.find_subtitles(path)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
