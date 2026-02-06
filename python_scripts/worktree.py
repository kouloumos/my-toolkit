#!/usr/bin/env python3

"""
Manage git worktrees with a simple CLI.

Auto-detects the current repo, organizes worktrees in a dedicated
{repo}-worktrees/ directory, and supports optional per-project
configuration via .worktree.json in the repo root.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_CONFIG = {
    "copy_files": [".env"],
    "default_base": "main",
}


class WorktreeConfig:
    """Per-project configuration loaded from .worktree.json in the repo root."""

    def __init__(self, repo_path: Path):
        self.config_file = repo_path / ".worktree.json"
        self._data: Dict = {}
        self._has_file = self.config_file.exists()
        if self._has_file:
            try:
                self._data = json.loads(self.config_file.read_text())
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Could not read {self.config_file}: {e}", file=sys.stderr)

    @property
    def has_config_file(self) -> bool:
        return self._has_file

    @property
    def cleanup_command(self) -> Optional[str]:
        return self._data.get("cleanup_command")

    @property
    def setup_command(self) -> Optional[str]:
        return self._data.get("setup_command")

    @property
    def default_base(self) -> str:
        return self._data.get("default_base", DEFAULT_CONFIG["default_base"])

    @property
    def copy_files(self) -> List[str]:
        return self._data.get("copy_files", DEFAULT_CONFIG["copy_files"])


def git(*args, cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def get_git_root(path: Optional[Path] = None) -> Path:
    """Resolve the git root directory, following worktree links to the main repo."""
    result = git("rev-parse", "--show-toplevel", cwd=path)
    toplevel = Path(result.stdout.strip())

    commondir_result = git("rev-parse", "--git-common-dir", cwd=toplevel)
    commondir = Path(commondir_result.stdout.strip())
    if not commondir.is_absolute():
        commondir = (toplevel / commondir).resolve()

    if commondir.name == ".git":
        return commondir.parent
    return toplevel


def get_worktrees_dir(repo_path: Path) -> Path:
    """Return the worktrees container directory for a repo."""
    return repo_path.parent / f"{repo_path.name}-worktrees"


def parse_worktree_list(repo_path: Path) -> List[Dict]:
    """Parse git worktree list --porcelain into structured data."""
    result = git("worktree", "list", "--porcelain", cwd=repo_path)
    worktrees = []
    current: Dict = {}

    for line in result.stdout.splitlines():
        if not line.strip():
            if current:
                worktrees.append(current)
                current = {}
            continue

        if line.startswith("worktree "):
            current["path"] = line[len("worktree "):]
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            current["branch"] = ref.replace("refs/heads/", "")
        elif line == "bare":
            current["bare"] = True
        elif line == "detached":
            current["detached"] = True

    if current:
        worktrees.append(current)

    return worktrees


def get_managed_worktrees(repo_path: Path) -> List[Dict]:
    """Get only worktrees inside the -worktrees directory."""
    worktrees_dir = get_worktrees_dir(repo_path)
    all_wt = parse_worktree_list(repo_path)
    worktrees_dir_str = str(worktrees_dir)
    return [wt for wt in all_wt if wt.get("path", "").startswith(worktrees_dir_str)]


def resolve_repo(repo_arg: Optional[str]) -> Path:
    """Resolve repo path from argument or auto-detect from cwd."""
    if repo_arg:
        return get_git_root(Path(repo_arg).resolve())
    try:
        return get_git_root()
    except RuntimeError:
        print("Error: Not inside a git repository. Use --repo to specify one.", file=sys.stderr)
        sys.exit(1)


def cmd_create(args):
    """Create a new worktree."""
    repo_path = resolve_repo(args.repo)
    config = WorktreeConfig(repo_path)

    branch = args.branch
    if not branch:
        print("Error: branch name is required", file=sys.stderr)
        sys.exit(1)

    base = args.base or config.default_base

    worktrees_dir = get_worktrees_dir(repo_path)
    worktree_path = worktrees_dir / branch

    if worktree_path.exists():
        print(f"Error: Path already exists: {worktree_path}", file=sys.stderr)
        sys.exit(1)

    worktrees_dir.mkdir(parents=True, exist_ok=True)

    try:
        git("worktree", "add", "-b", branch, str(worktree_path), base, cwd=repo_path)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Copy files from main repo to worktree
    copied_files = []
    for filename in config.copy_files:
        src = repo_path / filename
        if src.exists():
            dst = worktree_path / filename
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            copied_files.append(filename)
        else:
            if not args.json:
                print(f"Warning: {filename} not found in repo, skipping", file=sys.stderr)

    if args.setup and config.setup_command:
        print(f"Running setup: {config.setup_command}")
        subprocess.run(config.setup_command, shell=True, cwd=worktree_path)

    result = {
        "path": str(worktree_path),
        "branch": branch,
        "base": base,
        "repo": str(repo_path),
        "copied_files": copied_files,
    }

    # Copy worktree path to clipboard (with timeout to avoid hanging)
    clipboard_ok = False
    for clip_cmd in [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
        try:
            subprocess.run(clip_cmd, input=str(worktree_path), text=True, capture_output=True, check=True, timeout=2)
            clipboard_ok = True
            break
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue

    if args.json:
        result["clipboard"] = clipboard_ok
        print(json.dumps(result))
    else:
        print(f"Worktree created:")
        print(f"  Path:   {worktree_path}")
        print(f"  Branch: {branch}")
        print(f"  Base:   {base}")
        if copied_files:
            print(f"  Copied: {', '.join(copied_files)}")
        if clipboard_ok:
            print(f"\n  Path copied to clipboard. Use cd <paste> to navigate.")
        if not config.has_config_file:
            print(f"\n  Tip: Run 'my-toolkit worktree init' to create a .worktree.json config")


def cmd_teardown(args):
    """Remove a worktree."""
    repo_path = resolve_repo(args.repo)

    # Resolve which worktree to remove
    if args.branch:
        worktrees_dir = get_worktrees_dir(repo_path)
        worktree_path = worktrees_dir / args.branch
        branch_name = args.branch
    elif args.path:
        worktree_path = Path(args.path).resolve()
        branch_name = None
    else:
        print("Error: --branch or --path is required", file=sys.stderr)
        sys.exit(1)

    # Look up branch name from git if we don't have it
    if not branch_name:
        all_wt = parse_worktree_list(repo_path)
        for wt in all_wt:
            if wt.get("path") == str(worktree_path):
                branch_name = wt.get("branch")
                break

    config = WorktreeConfig(repo_path)

    # Run cleanup command
    if config.cleanup_command and worktree_path.exists():
        if not args.json:
            print(f"Running cleanup: {config.cleanup_command}")
        subprocess.run(config.cleanup_command, shell=True, cwd=worktree_path)

    # Remove worktree
    try:
        git("worktree", "remove", str(worktree_path), cwd=repo_path)
    except RuntimeError as e:
        if not args.json:
            print(f"Warning: {e}", file=sys.stderr)
            print("Attempting force removal...", file=sys.stderr)
        git("worktree", "remove", "--force", str(worktree_path), cwd=repo_path)

    # Delete branch if requested
    branch_deleted = False
    if args.delete_branch and branch_name:
        try:
            git("branch", "-d", branch_name, cwd=repo_path)
            branch_deleted = True
        except RuntimeError:
            print(f"Warning: Branch '{branch_name}' not fully merged, skipping deletion", file=sys.stderr)

    result = {
        "removed": str(worktree_path),
        "branch_deleted": branch_deleted,
    }

    if args.json:
        print(json.dumps(result))
    else:
        print(f"Worktree removed: {worktree_path}")
        if branch_deleted:
            print(f"Branch deleted: {branch_name}")


def cmd_list(args):
    """List managed worktrees."""
    repo_path = resolve_repo(args.repo)
    managed = get_managed_worktrees(repo_path)

    if args.json:
        print(json.dumps({
            "repo": str(repo_path),
            "worktrees": managed,
        }))
        return

    if not managed:
        print(f"No managed worktrees for {repo_path}")
        return

    print(f"Worktrees for {repo_path.name}:\n")
    for wt in managed:
        branch = wt.get("branch", "detached")
        head = wt.get("head", "unknown")[:8]
        path = wt.get("path", "unknown")
        print(f"  {branch:30s} {head}  {path}")


def cmd_land(args):
    """Fast-forward merge a worktree branch into the base branch and optionally tear down."""
    repo_path = resolve_repo(args.repo)
    config = WorktreeConfig(repo_path)

    branch = args.branch
    if not branch:
        # Try to detect from cwd if inside a worktree
        try:
            result = git("rev-parse", "--abbrev-ref", "HEAD")
            branch = result.stdout.strip()
        except RuntimeError:
            print("Error: branch name is required (or run from inside the worktree)", file=sys.stderr)
            sys.exit(1)

    base = args.base or config.default_base

    # Verify the branch exists and has commits ahead of base
    try:
        log_result = git("log", "--oneline", f"{base}..{branch}", cwd=repo_path)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    commits = [l for l in log_result.stdout.strip().splitlines() if l]
    if not commits:
        print(f"Nothing to land: {branch} has no commits ahead of {base}")
        sys.exit(0)

    if not args.json:
        print(f"Landing {branch} onto {base} ({len(commits)} commit{'s' if len(commits) != 1 else ''}):")
        for c in commits:
            print(f"  {c}")

    # Check for uncommitted changes in the worktree
    worktrees_dir = get_worktrees_dir(repo_path)
    worktree_path = worktrees_dir / branch
    if worktree_path.exists():
        status = git("status", "--porcelain", cwd=worktree_path)
        if status.stdout.strip():
            print(f"Error: Worktree has uncommitted changes. Commit or stash them first.", file=sys.stderr)
            sys.exit(1)

    # Fast-forward merge on the main repo
    try:
        git("checkout", base, cwd=repo_path)
    except RuntimeError as e:
        print(f"Error checking out {base}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        git("merge", "--ff-only", branch, cwd=repo_path)
    except RuntimeError as e:
        print(f"Error: Cannot fast-forward. Rebase {branch} onto {base} first.", file=sys.stderr)
        # Go back to whatever branch was checked out
        git("checkout", "-", cwd=repo_path, check=False)
        sys.exit(1)

    result_data = {
        "branch": branch,
        "base": base,
        "commits": len(commits),
        "teardown": False,
    }

    if not args.json:
        print(f"\nMerged {branch} into {base} (fast-forward)")

    # Optionally teardown
    if args.teardown:
        if worktree_path.exists():
            cleanup_cmd = config.cleanup_command
            if cleanup_cmd:
                if not args.json:
                    print(f"Running cleanup: {cleanup_cmd}")
                subprocess.run(cleanup_cmd, shell=True, cwd=worktree_path)

            try:
                git("worktree", "remove", str(worktree_path), cwd=repo_path)
            except RuntimeError:
                git("worktree", "remove", "--force", str(worktree_path), cwd=repo_path)

        # Delete the branch (it's fully merged now, so -d will work)
        try:
            git("branch", "-d", branch, cwd=repo_path)
            result_data["teardown"] = True
            if not args.json:
                print(f"Removed worktree and deleted branch {branch}")
        except RuntimeError as e:
            print(f"Warning: Could not delete branch: {e}", file=sys.stderr)
    else:
        if not args.json:
            print(f"\nTip: Run 'my-toolkit worktree teardown --branch {branch} --delete-branch' to clean up")

    if args.json:
        print(json.dumps(result_data))


def cmd_init(args):
    """Create a .worktree.json config in the repo root."""
    repo_path = resolve_repo(args.repo)
    config_file = repo_path / ".worktree.json"

    if config_file.exists() and not args.force:
        print(f"Error: {config_file} already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    config_file.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")

    if args.json:
        print(json.dumps({"created": str(config_file)}))
    else:
        print(f"Created {config_file}")
        print(f"Edit it to customize copy_files, setup/cleanup commands, and default base branch.")


def main():
    parser = argparse.ArgumentParser(
        description="Manage git worktrees",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a worktree (from inside a repo)
  my-toolkit worktree create feature-x
  my-toolkit worktree create feature-x --base develop

  # Create with explicit repo
  my-toolkit worktree create feature-x --repo /path/to/repo

  # Create with JSON output (for agents)
  my-toolkit worktree create feature-x --json

  # List worktrees
  my-toolkit worktree list

  # Land a worktree branch back into main (fast-forward)
  my-toolkit worktree land feature-x
  my-toolkit worktree land feature-x --teardown

  # Teardown by branch name
  my-toolkit worktree teardown --branch feature-x --delete-branch

  # Teardown by path
  my-toolkit worktree teardown --path /path/to/repo-worktrees/feature-x

  # Initialize config for a project
  my-toolkit worktree init

Per-project configuration (.worktree.json in repo root):
  {
    "copy_files": [".env"],
    "cleanup_command": "./run.sh --clean",
    "setup_command": "./run.sh",
    "default_base": "main"
  }

By default (without .worktree.json), .env is copied to new worktrees.
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = subparsers.add_parser("create", help="Create a new worktree")
    p_create.add_argument("branch", help="Name for the new branch")
    p_create.add_argument("--base", help="Base branch (default: main, or from .worktree.json)")
    p_create.add_argument("--repo", help="Path to the git repository (default: auto-detect)")
    p_create.add_argument("--setup", action="store_true", help="Run the project's setup command after creation")
    p_create.add_argument("--json", action="store_true", help="Output JSON for scripting")

    # teardown
    p_teardown = subparsers.add_parser("teardown", help="Remove a worktree")
    p_teardown.add_argument("--branch", help="Branch name of the worktree to remove")
    p_teardown.add_argument("--path", help="Full path to the worktree to remove")
    p_teardown.add_argument("--repo", help="Path to the git repository (default: auto-detect)")
    p_teardown.add_argument("--delete-branch", action="store_true", help="Also delete the branch")
    p_teardown.add_argument("--json", action="store_true", help="Output JSON for scripting")

    # land
    p_land = subparsers.add_parser("land", help="Fast-forward merge worktree branch into base branch")
    p_land.add_argument("branch", nargs="?", help="Branch to land (default: current branch)")
    p_land.add_argument("--base", help="Target branch (default: main, or from .worktree.json)")
    p_land.add_argument("--repo", help="Path to the git repository (default: auto-detect)")
    p_land.add_argument("--teardown", action="store_true", help="Remove worktree and delete branch after landing")
    p_land.add_argument("--json", action="store_true", help="Output JSON for scripting")

    # list
    p_list = subparsers.add_parser("list", help="List managed worktrees")
    p_list.add_argument("--repo", help="Path to the git repository (default: auto-detect)")
    p_list.add_argument("--json", action="store_true", help="Output JSON for scripting")

    # init
    p_init = subparsers.add_parser("init", help="Create a .worktree.json config in the repo root")
    p_init.add_argument("--repo", help="Path to the git repository (default: auto-detect)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing config")
    p_init.add_argument("--json", action="store_true", help="Output JSON for scripting")

    args = parser.parse_args()

    commands = {
        "create": cmd_create,
        "teardown": cmd_teardown,
        "land": cmd_land,
        "list": cmd_list,
        "init": cmd_init,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
