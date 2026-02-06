#!/usr/bin/env python3

"""
Quick worktree launcher with progressive prompting.

Usage:
  wt [project] [branch] [--base BASE]   Create worktree (prompts for missing args)
  wt config                             Show current configuration
  wt config add-dir <path>              Add a code directory to scan
  wt config rm-dir <path>               Remove a code directory
  wt config alias <name> <project>      Create a shortcut alias
  wt config rm-alias <name>             Remove an alias

Examples:
  wt                          # Interactive: pick project, enter branch
  wt bitcoin                  # Pick project "bitcoin", prompt for branch
  wt bitcoin feature-x        # Create worktree immediately
  wt btc feature-x            # Use alias "btc" for bitcoin
  wt --last feature-x         # Reuse last project
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


CONFIG_DIR = Path.home() / ".config" / "my-toolkit"
CONFIG_FILE = CONFIG_DIR / "wt.json"

DEFAULT_CONFIG = {
    "code_dirs": [],
    "aliases": {},
    "last_project": None,
    "last_project_path": None,
}


class Config:
    """Manage wt configuration."""

    def __init__(self):
        self._data = self._load()

    def _load(self) -> Dict:
        if CONFIG_FILE.exists():
            try:
                return {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text())}
            except (json.JSONDecodeError, OSError):
                pass
        return DEFAULT_CONFIG.copy()

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self._data, indent=2) + "\n")

    @property
    def code_dirs(self) -> List[str]:
        return self._data.get("code_dirs", [])

    @property
    def aliases(self) -> Dict[str, str]:
        return self._data.get("aliases", {})

    @property
    def last_project(self) -> Optional[str]:
        return self._data.get("last_project")

    @property
    def last_project_path(self) -> Optional[str]:
        return self._data.get("last_project_path")

    def set_last_project(self, name: str, path: str):
        self._data["last_project"] = name
        self._data["last_project_path"] = path
        self.save()

    def add_code_dir(self, path: str):
        expanded = str(Path(path).expanduser().resolve())
        if expanded not in self._data["code_dirs"]:
            self._data["code_dirs"].append(expanded)
            self.save()
            return True
        return False

    def remove_code_dir(self, path: str):
        expanded = str(Path(path).expanduser().resolve())
        if expanded in self._data["code_dirs"]:
            self._data["code_dirs"].remove(expanded)
            self.save()
            return True
        return False

    def add_alias(self, name: str, project: str):
        self._data["aliases"][name] = project
        self.save()

    def remove_alias(self, name: str):
        if name in self._data["aliases"]:
            del self._data["aliases"][name]
            self.save()
            return True
        return False


def discover_projects(config: Config) -> List[Tuple[str, str]]:
    """
    Discover git repositories from configured code directories.
    Returns list of (name, path) tuples.
    """
    projects = []
    seen_paths = set()

    for code_dir in config.code_dirs:
        code_path = Path(code_dir)
        if not code_path.exists():
            continue

        # Check immediate children for git repos
        for child in code_path.iterdir():
            if child.is_dir() and (child / ".git").exists():
                path_str = str(child)
                if path_str not in seen_paths:
                    projects.append((child.name, path_str))
                    seen_paths.add(path_str)

    # Sort by name
    projects.sort(key=lambda x: x[0].lower())
    return projects


def resolve_project(config: Config, project_arg: Optional[str]) -> Optional[Tuple[str, str]]:
    """
    Resolve a project argument to (name, path).
    Handles aliases and partial matching.
    """
    if not project_arg:
        return None

    # Check if it's an alias
    if project_arg in config.aliases:
        project_arg = config.aliases[project_arg]

    # Check if it's a direct path
    path = Path(project_arg).expanduser()
    if path.exists() and (path / ".git").exists():
        return (path.name, str(path.resolve()))

    # Search in discovered projects
    projects = discover_projects(config)

    # Exact match
    for name, proj_path in projects:
        if name == project_arg:
            return (name, proj_path)

    # Case-insensitive match
    for name, proj_path in projects:
        if name.lower() == project_arg.lower():
            return (name, proj_path)

    # Partial match (starts with)
    matches = [(n, p) for n, p in projects if n.lower().startswith(project_arg.lower())]
    if len(matches) == 1:
        return matches[0]

    # Substring match
    matches = [(n, p) for n, p in projects if project_arg.lower() in n.lower()]
    if len(matches) == 1:
        return matches[0]

    return None


def has_fzf() -> bool:
    """Check if fzf is available."""
    try:
        subprocess.run(["fzf", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def pick_with_fzf(options: List[Tuple[str, str]], prompt: str = "Select") -> Optional[Tuple[str, str]]:
    """Use fzf to pick from options. Each option is (display, value)."""
    if not options:
        return None

    # Format: "name          path" for display
    lines = []
    for name, path in options:
        # Right-pad name for alignment
        display = f"{name:30s} {path}"
        lines.append(display)

    input_text = "\n".join(lines)

    try:
        result = subprocess.run(
            ["fzf", "--prompt", f"{prompt}: ", "--height", "40%", "--reverse"],
            input=input_text,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            selected = result.stdout.strip()
            # Parse back the selection
            idx = lines.index(selected)
            return options[idx]
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        pass

    return None


def pick_with_menu(options: List[Tuple[str, str]], prompt: str = "Select") -> Optional[Tuple[str, str]]:
    """Simple numbered menu fallback when fzf is not available."""
    if not options:
        return None

    print(f"\n{prompt}:\n")
    for i, (name, path) in enumerate(options, 1):
        print(f"  {i:2d}) {name:30s} {path}")
    print()

    try:
        choice = input("Enter number (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except (ValueError, EOFError, KeyboardInterrupt):
        pass

    return None


def pick_project(config: Config) -> Optional[Tuple[str, str]]:
    """Interactive project picker."""
    projects = discover_projects(config)

    if not projects:
        print("No projects found.", file=sys.stderr)
        print("\nAdd code directories with:", file=sys.stderr)
        print("  wt config add-dir ~/code", file=sys.stderr)
        print("  wt config add-dir ~/projects", file=sys.stderr)
        return None

    # Add last project indicator
    display_projects = []
    for name, path in projects:
        if path == config.last_project_path:
            display_projects.append((f"{name} (last)", path))
        else:
            display_projects.append((name, path))

    # Move last project to top if it exists
    if config.last_project_path:
        for i, (name, path) in enumerate(display_projects):
            if path == config.last_project_path:
                display_projects.insert(0, display_projects.pop(i))
                break

    if has_fzf():
        result = pick_with_fzf(display_projects, "Select project")
    else:
        result = pick_with_menu(display_projects, "Select project")

    if result:
        # Strip "(last)" suffix if present
        name = result[0].replace(" (last)", "")
        return (name, result[1])
    return None


def prompt_branch() -> Optional[str]:
    """Prompt for branch name."""
    try:
        branch = input("Branch name: ").strip()
        return branch if branch else None
    except (EOFError, KeyboardInterrupt):
        return None


def create_worktree(project_path: str, branch: str, base: Optional[str] = None):
    """Create a worktree using my-toolkit worktree create."""
    cmd = ["my-toolkit", "worktree", "create", branch, "--repo", project_path]
    if base:
        cmd.extend(["--base", base])

    result = subprocess.run(cmd)
    return result.returncode == 0


def cmd_create(args, config: Config):
    """Handle the create workflow with progressive prompting."""

    # Resolve project
    project = None

    if args.last and config.last_project_path:
        # Use last project
        project = (config.last_project, config.last_project_path)
    elif args.project:
        # Try to resolve provided project
        project = resolve_project(config, args.project)
        if not project:
            # Maybe it's actually a branch name and we should prompt for project?
            print(f"Project '{args.project}' not found.", file=sys.stderr)

            # Show available projects
            projects = discover_projects(config)
            if projects:
                print("\nAvailable projects:", file=sys.stderr)
                for name, _ in projects[:5]:
                    print(f"  - {name}", file=sys.stderr)
                if len(projects) > 5:
                    print(f"  ... and {len(projects) - 5} more", file=sys.stderr)

            # Show configured aliases
            if config.aliases:
                print("\nConfigured aliases:", file=sys.stderr)
                for alias, target in config.aliases.items():
                    print(f"  {alias} -> {target}", file=sys.stderr)

            sys.exit(1)

    # Interactive project selection if not resolved
    if not project:
        project = pick_project(config)
        if not project:
            print("No project selected.", file=sys.stderr)
            sys.exit(1)

    project_name, project_path = project

    # Resolve branch
    branch = args.branch
    if not branch:
        print(f"\nProject: {project_name} ({project_path})\n")
        branch = prompt_branch()
        if not branch:
            print("No branch name provided.", file=sys.stderr)
            sys.exit(1)

    # Save as last project
    config.set_last_project(project_name, project_path)

    # Create the worktree
    print(f"\nCreating worktree '{branch}' in {project_name}...\n")
    success = create_worktree(project_path, branch, args.base)

    if not success:
        sys.exit(1)


def cmd_config(args, config: Config):
    """Handle config subcommands."""

    if args.config_cmd == "add-dir":
        if not args.path:
            print("Error: path required", file=sys.stderr)
            sys.exit(1)
        path = Path(args.path).expanduser().resolve()
        if not path.exists():
            print(f"Error: {path} does not exist", file=sys.stderr)
            sys.exit(1)
        if config.add_code_dir(str(path)):
            print(f"Added: {path}")
            # Show discovered projects
            projects = discover_projects(config)
            git_repos = [p for p in projects if Path(p[1]).parent == path]
            if git_repos:
                print(f"Found {len(git_repos)} git repositories:")
                for name, _ in git_repos:
                    print(f"  - {name}")
        else:
            print(f"Already configured: {path}")

    elif args.config_cmd == "rm-dir":
        if not args.path:
            print("Error: path required", file=sys.stderr)
            sys.exit(1)
        if config.remove_code_dir(args.path):
            print(f"Removed: {args.path}")
        else:
            print(f"Not found: {args.path}")

    elif args.config_cmd == "alias":
        if not args.alias_name or not args.alias_target:
            print("Error: alias name and target required", file=sys.stderr)
            print("Usage: wt config alias <name> <project>", file=sys.stderr)
            sys.exit(1)
        config.add_alias(args.alias_name, args.alias_target)
        print(f"Alias created: {args.alias_name} -> {args.alias_target}")

    elif args.config_cmd == "rm-alias":
        if not args.alias_name:
            print("Error: alias name required", file=sys.stderr)
            sys.exit(1)
        if config.remove_alias(args.alias_name):
            print(f"Alias removed: {args.alias_name}")
        else:
            print(f"Alias not found: {args.alias_name}")

    else:
        # Show current config
        print("wt configuration")
        print("=" * 40)
        print(f"\nConfig file: {CONFIG_FILE}")
        print(f"\nCode directories:")
        if config.code_dirs:
            for d in config.code_dirs:
                exists = "ok" if Path(d).exists() else "missing"
                print(f"  - {d} ({exists})")
        else:
            print("  (none configured)")
            print("  Add with: wt config add-dir ~/code")

        print(f"\nAliases:")
        if config.aliases:
            for alias, target in config.aliases.items():
                print(f"  {alias} -> {target}")
        else:
            print("  (none)")

        print(f"\nLast project: {config.last_project or '(none)'}")

        # Show discovered projects
        projects = discover_projects(config)
        print(f"\nDiscovered projects: {len(projects)}")
        if projects:
            for name, path in projects[:10]:
                print(f"  - {name:30s} {path}")
            if len(projects) > 10:
                print(f"  ... and {len(projects) - 10} more")


def cmd_list(args, config: Config):
    """List all worktrees across projects."""
    projects = discover_projects(config)

    if not projects:
        print("No projects configured. Add code directories first:")
        print("  wt config add-dir ~/code")
        return

    found_any = False
    for name, path in projects:
        # Check for worktrees directory
        worktrees_dir = Path(path).parent / f"{name}-worktrees"
        if worktrees_dir.exists():
            # Get worktrees via git
            try:
                result = subprocess.run(
                    ["git", "worktree", "list", "--porcelain"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    # Parse and filter to managed worktrees
                    worktrees = []
                    current = {}
                    for line in result.stdout.splitlines():
                        if not line.strip():
                            if current and current.get("path", "").startswith(str(worktrees_dir)):
                                worktrees.append(current)
                            current = {}
                        elif line.startswith("worktree "):
                            current["path"] = line[9:]
                        elif line.startswith("branch "):
                            current["branch"] = line[7:].replace("refs/heads/", "")

                    if current and current.get("path", "").startswith(str(worktrees_dir)):
                        worktrees.append(current)

                    if worktrees:
                        if not found_any:
                            print("Active worktrees:\n")
                        found_any = True
                        print(f"  {name}:")
                        for wt in worktrees:
                            branch = wt.get("branch", "detached")
                            print(f"    - {branch}")
            except Exception:
                pass

    if not found_any:
        print("No active worktrees found.")


def main():
    # Manual routing to handle both subcommands and implicit create
    # This allows: wt config, wt list, AND wt project branch

    if len(sys.argv) > 1 and sys.argv[1] == "config":
        # Config subcommand
        parser = argparse.ArgumentParser(prog="wt config", description="Manage wt configuration")
        parser.add_argument("config_cmd", nargs="?", choices=["add-dir", "rm-dir", "alias", "rm-alias"])
        parser.add_argument("args", nargs="*", help="Arguments for the config command")
        args = parser.parse_args(sys.argv[2:])

        # Map args to expected structure
        class ConfigArgs:
            pass
        config_args = ConfigArgs()
        config_args.config_cmd = args.config_cmd
        config_args.path = args.args[0] if args.args else None
        config_args.alias_name = args.args[0] if args.args else None
        config_args.alias_target = args.args[1] if len(args.args) > 1 else None

        cmd_config(config_args, Config())

    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        # List subcommand
        cmd_list(None, Config())

    else:
        # Create command (default)
        parser = argparse.ArgumentParser(
            prog="wt",
            description="Quick worktree launcher with progressive prompting",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  wt                          Interactive: pick project, enter branch
  wt bitcoin                  Pick project "bitcoin", prompt for branch
  wt bitcoin feature-x        Create worktree immediately
  wt btc feature-x            Use alias "btc" for bitcoin
  wt --last feature-x         Reuse last project

Configuration:
  wt config                   Show current configuration
  wt config add-dir ~/code    Add a code directory to scan
  wt config alias btc bitcoin Create a shortcut alias

List worktrees:
  wt list                     Show all active worktrees across projects
            """,
        )
        parser.add_argument("project", nargs="?", help="Project name, alias, or path")
        parser.add_argument("branch", nargs="?", help="Branch name for the worktree")
        parser.add_argument("--base", "-b", help="Base branch (default: main)")
        parser.add_argument("--last", "-l", action="store_true", help="Use last project")

        args = parser.parse_args()
        cmd_create(args, Config())


if __name__ == "__main__":
    main()
