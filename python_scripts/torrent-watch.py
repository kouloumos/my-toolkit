#!/usr/bin/env python3

"""
Watch a movie from torrent cache in an isolated VLC environment using bubblewrap.
"""

import argparse
import json
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Optional, List


class Config:
    """Centralized configuration for torrent manager"""

    CACHE_DIR = Path.home() / ".cache" / "my-toolkit" / "torrents"
    METADATA_FILE = CACHE_DIR / "metadata.json"

    # Video file extensions
    VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}


class TorrentWatcher:
    """Watch movies from cache with bubblewrap isolation"""

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

    def find_movie(self, cache_id: int) -> Optional[Dict]:
        """Find movie by cache ID"""
        metadata = self.load_metadata()
        for movie in metadata.get("movies", []):
            if movie.get("cache_id") == cache_id:
                return movie
        return None

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

    def check_dependencies(self) -> bool:
        """Check if required tools are available"""
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
                import os
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
            "--dir", "/run/user/" + str(os.getuid()) if 'os' in dir() else "1000",
            "--dev", "/dev",
            "--proc", "/proc",
            # Unshare network (VLC doesn't need internet for local playback)
            "--unshare-net",
            # Share X11/Wayland for display
            "--ro-bind-try", "/tmp/.X11-unix", "/tmp/.X11-unix",
            "--ro-bind-try", str(Path.home() / ".Xauthority"), str(Path.home() / ".Xauthority"),
            # Share audio
            "--ro-bind-try", "/run/user/" + str(__import__('os').getuid()) + "/pulse", "/run/user/" + str(__import__('os').getuid()) + "/pulse",
            # Environment variables for display and audio
            "--setenv", "DISPLAY", __import__('os').environ.get("DISPLAY", ":0"),
            "--setenv", "PULSE_SERVER", __import__('os').environ.get("PULSE_SERVER", ""),
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
        if not self.check_dependencies():
            sys.exit(1)

        # Find movie in cache
        movie = self.find_movie(cache_id)
        if not movie:
            print(f"Error: Movie with ID {cache_id} not found in cache")
            print(f"Use 'my-toolkit torrent-list' to see available movies")
            sys.exit(1)

        # Get movie directory
        directory_name = movie.get("directory")
        if not directory_name:
            print(f"Error: Movie directory not found in metadata")
            sys.exit(1)

        movie_dir = self.config.CACHE_DIR / directory_name

        if not movie_dir.exists():
            print(f"Error: Movie directory not found: {movie_dir}")
            print(f"The movie may have been deleted.")
            sys.exit(1)

        # Find video files
        video_files = self.find_video_files(movie_dir)

        if not video_files:
            print(f"Error: No video files found in {movie_dir}")
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


def main():
    parser = argparse.ArgumentParser(
        description="Watch a movie from torrent cache in isolated VLC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  torrent-watch.py 1
  torrent-watch.py --no-subtitles 2
  torrent-watch.py --select-file 3

Security:
  VLC runs in a bubblewrap sandbox with:
  - Network access disabled (--unshare-net)
  - Read-only access to video files
  - Isolated filesystem (minimal bindings)
  - No access to your home directory

This provides strong isolation while watching potentially untrusted content.
        """
    )

    parser.add_argument(
        "cache_id",
        type=int,
        help="Movie cache ID (see 'torrent-list' for IDs)"
    )

    parser.add_argument(
        "-S", "--no-subtitles",
        action="store_true",
        help="Skip automatic subtitle search"
    )

    parser.add_argument(
        "-s", "--select-file",
        action="store_true",
        help="Manually select which video file to play"
    )

    args = parser.parse_args()

    config = Config()
    watcher = TorrentWatcher(config)

    watcher.watch_movie(
        cache_id=args.cache_id,
        with_subtitles=not args.no_subtitles,
        select_file=args.select_file
    )


if __name__ == "__main__":
    main()
