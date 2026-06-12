#!/usr/bin/env python3
"""Review context manager for code-review skill.

Usage: python3 context.py [--review-dir PATH] <subcommand> [args]

Subcommands:
  current                       Get current context (full context.json)
  list [--all]                  List active (or all) review contexts
  new SOURCE [--name STR]       Create a new context
  switch [ID]                   Switch active context
  archive [ID]                  Archive a context (moves dir to .archived/)
  delete ID                     Delete a context (moves to system trash)
  get ID                        Get full context.json for a specific context
  update-iteration ID ...       Append a review iteration to a context
  versions ID                   Get the next version string (e.g. v2)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ── I/O helpers ────────────────────────────────────────────────────────────

def read_json(path: Path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def write_json_atomic(path: Path, data) -> None:
    """Write JSON atomically: write to .tmp then os.replace()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def out(data) -> None:
    print(json.dumps(data, indent=2))


def err_exit(msg: str, code: int = 1) -> None:
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(code)


# ── Registry / context helpers ─────────────────────────────────────────────

def registry_path(review_dir: Path) -> Path:
    return review_dir / "registry.json"


def context_path(review_dir: Path, ctx_id: str) -> Path:
    return review_dir / ctx_id / "context.json"


def archived_context_path(review_dir: Path, ctx_id: str) -> Path:
    return review_dir / ".archived" / ctx_id / "context.json"


def load_registry(review_dir: Path) -> dict | None:
    return read_json(registry_path(review_dir))


def save_registry(review_dir: Path, registry: dict) -> None:
    write_json_atomic(registry_path(review_dir), registry)


def load_context(review_dir: Path, ctx_id: str) -> dict | None:
    ctx = read_json(context_path(review_dir, ctx_id))
    if ctx is None:
        ctx = read_json(archived_context_path(review_dir, ctx_id))
    return ctx


def load_config(review_dir: Path) -> dict:
    cfg = read_json(review_dir / "config.json")
    return cfg if isinstance(cfg, dict) else {}


def registry_summary(ctx: dict) -> dict:
    """Return a registry summary entry (context without iterations[])."""
    return {k: v for k, v in ctx.items() if k != "iterations"}


# ── Name / ID helpers ──────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """Normalize to lowercase alphanumeric + hyphens only."""
    name = name.lower()
    name = re.sub(r"[ _]", "-", name)        # spaces/underscores → hyphens
    name = re.sub(r"[^a-z0-9-]", "", name)   # remove invalid chars
    name = re.sub(r"-+", "-", name)           # collapse consecutive hyphens
    return name.strip("-")


BRANCH_PREFIXES = [
    "feature/", "feat/", "fix/", "bugfix/", "hotfix/",
    "chore/", "refactor/", "release/", "improvement/", "task/",
]

MAIN_BRANCHES = {"main", "master", "develop", "staging", "development"}


def suggest_name_from_branch(branch: str) -> str:
    b = branch.lower()
    for prefix in BRANCH_PREFIXES:
        if b.startswith(prefix):
            b = b[len(prefix):]
            break
    return normalize_name(b)[:60]


def is_main_branch(branch: str) -> bool:
    return branch.lower().strip() in MAIN_BRANCHES or not branch.strip()


def make_unique_id(base_id: str, existing_ids: set) -> str:
    if base_id not in existing_ids:
        return base_id
    for i in range(2, 100):
        candidate = f"{base_id}-{i}"
        if candidate not in existing_ids:
            return candidate
    raise ValueError(f"Could not find unique ID for base '{base_id}'")


def today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ── Source / branch helpers ────────────────────────────────────────────────

def parse_pr_number(source: str) -> str | None:
    """Extract PR number from source string. Returns string or None."""
    url_match = re.search(r"/pull/(\d+)", source)
    if url_match:
        return url_match.group(1)
    pr_match = re.match(r"^(?:PR\s*)?#?(\d+)$", source.strip(), re.IGNORECASE)
    if pr_match:
        return pr_match.group(1)
    return None


def infer_branch(source: str) -> str:
    """Infer working branch from a review source string."""
    pr_num = parse_pr_number(source)
    if pr_num:
        result = subprocess.run(
            ["gh", "pr", "view", pr_num, "--json", "headRefName"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout).get("headRefName", "")
            except json.JSONDecodeError:
                pass

    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def parse_source_obj(source: str) -> dict:
    """Build a structured source object from a source string."""
    pr_num = parse_pr_number(source)
    if pr_num:
        return {"type": "pr", "ref": f"PR #{pr_num}", "number": int(pr_num)}

    s = source.lower()
    if "staged" in s:
        return {"type": "staged", "ref": source, "number": None}
    if "commit" in s:
        return {"type": "commit", "ref": source, "number": None}
    if "file" in s:
        return {"type": "files", "ref": source, "number": None}
    return {"type": "diff", "ref": source, "number": None}


# ── Trash helper ───────────────────────────────────────────────────────────

def move_to_trash(path: Path) -> tuple[bool, str]:
    """Move path to system trash. Returns (success, method_used)."""
    abs_path = str(path.absolute())

    # Try /usr/bin/trash (macOS)
    r = subprocess.run(["/usr/bin/trash", abs_path], capture_output=True, text=True)
    if r.returncode == 0:
        return True, "trash_cli"

    # Fallback: osascript (Finder)
    script = f'tell application "Finder" to delete POSIX file "{abs_path}"'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode == 0:
        return True, "osascript"

    return False, ""


# ── Subcommand implementations ─────────────────────────────────────────────

def cmd_current(review_dir: Path) -> None:
    registry = load_registry(review_dir)
    if registry is None:
        out({"found": False, "context": None, "reason": "no_registry"})
        return

    current_id = registry.get("current")
    if not current_id:
        out({"found": False, "context": None, "reason": "no_current"})
        return

    ctx_dir = review_dir / current_id
    if not ctx_dir.exists():
        out({"found": False, "context": None, "reason": "context_dir_missing", "id": current_id})
        return

    context = load_context(review_dir, current_id)
    out({"found": True, "context": context})


def cmd_list(review_dir: Path, show_all: bool) -> None:
    registry = load_registry(review_dir)
    if registry is None:
        out([])
        return

    current_id = registry.get("current")
    contexts = list(registry.get("contexts", []))

    if not show_all:
        contexts = [c for c in contexts if c.get("status") != "archived"]

    # Annotate is_current
    for c in contexts:
        c = dict(c)
        c["is_current"] = (c["id"] == current_id)

    # Re-annotate on a fresh copy (avoid mutating registry data)
    result = []
    for c in contexts:
        entry = dict(c)
        entry["is_current"] = (entry["id"] == current_id)
        result.append(entry)

    # Sort: current first, then most-recently-reviewed first
    current_entries = [c for c in result if c["is_current"]]
    other_entries = sorted(
        [c for c in result if not c["is_current"]],
        key=lambda c: c.get("last_reviewed") or c.get("created", ""),
        reverse=True,
    )
    out(current_entries + other_entries)


def cmd_new(review_dir: Path, source: str, name: str | None) -> None:
    branch = infer_branch(source)

    if name:
        name = normalize_name(name)
    else:
        if branch and not is_main_branch(branch):
            name = suggest_name_from_branch(branch)
        else:
            err_exit(
                "Cannot suggest a name from a main/develop branch or detached HEAD. "
                "Provide --name explicitly."
            )

    if not name:
        err_exit("Name is empty after normalization. Provide a valid --name.")

    registry = load_registry(review_dir) or {
        "format_version": "1.0",
        "current": None,
        "contexts": [],
    }

    existing_ids = {c["id"] for c in registry.get("contexts", [])}
    base_id = f"{today_str()}_{name}"
    ctx_id = make_unique_id(base_id, existing_ids)

    now = now_iso()
    context = {
        "id": ctx_id,
        "name": name,
        "status": "active",
        "created": now,
        "last_reviewed": None,
        "latest_version": None,
        "working_branch": branch,
        "scope_summary": "",
        "iterations": [],
    }

    # Write context.json
    write_json_atomic(review_dir / ctx_id / "context.json", context)

    # Prepend to registry (newest first) and set as current
    registry.setdefault("contexts", []).insert(0, registry_summary(context))
    registry["current"] = ctx_id
    save_registry(review_dir, registry)

    out({"id": ctx_id, "created": True, "name": name, "branch": branch, "scope_summary": ""})


def cmd_switch(review_dir: Path, ctx_id: str | None) -> None:
    registry = load_registry(review_dir)
    if registry is None:
        err_exit("No registry found. Run 'new' first.")

    if ctx_id is None:
        active = [c for c in registry.get("contexts", []) if c.get("status") != "archived"]
        current_id = registry.get("current")
        result = []
        for c in active:
            entry = dict(c)
            entry["is_current"] = (entry["id"] == current_id)
            result.append(entry)
        # Current on top
        result.sort(key=lambda c: not c["is_current"])
        out({"requires_selection": True, "contexts": result})
        return

    existing_ids = {c["id"] for c in registry.get("contexts", [])}
    if ctx_id not in existing_ids:
        err_exit(f"Context '{ctx_id}' not found in registry.")

    ctx_dir = review_dir / ctx_id
    if not ctx_dir.exists():
        err_exit(f"Context directory missing for '{ctx_id}'.")

    registry["current"] = ctx_id
    save_registry(review_dir, registry)
    out({"switched_to": ctx_id})


def cmd_archive(review_dir: Path, ctx_id: str | None) -> None:
    registry = load_registry(review_dir)
    if registry is None:
        err_exit("No registry found.")

    if ctx_id is None:
        active = [c for c in registry.get("contexts", []) if c.get("status") != "archived"]
        current_id = registry.get("current")
        result = []
        for c in active:
            entry = dict(c)
            entry["is_current"] = (entry["id"] == current_id)
            result.append(entry)
        result.sort(key=lambda c: not c["is_current"])
        out({"requires_selection": True, "contexts": result})
        return

    existing_ids = {c["id"] for c in registry.get("contexts", [])}
    if ctx_id not in existing_ids:
        err_exit(f"Context '{ctx_id}' not found.")

    # Move directory to .archived/
    ctx_dir = review_dir / ctx_id
    archived_parent = review_dir / ".archived"
    archived_dest = archived_parent / ctx_id

    archived_parent.mkdir(parents=True, exist_ok=True)
    if ctx_dir.exists():
        shutil.move(str(ctx_dir), str(archived_dest))

    # Update context.json status in the new location
    ctx_json = archived_dest / "context.json"
    if ctx_json.exists():
        with open(ctx_json) as f:
            context = json.load(f)
        context["status"] = "archived"
        write_json_atomic(ctx_json, context)

    # Update registry entry status
    current_id = registry.get("current")
    for c in registry.get("contexts", []):
        if c["id"] == ctx_id:
            c["status"] = "archived"

    # If this was current, promote the next active context
    new_current = current_id
    if current_id == ctx_id:
        active_ids = [
            c["id"] for c in registry.get("contexts", [])
            if c.get("status") != "archived" and c["id"] != ctx_id
        ]
        new_current = active_ids[0] if active_ids else None
        registry["current"] = new_current

    save_registry(review_dir, registry)
    out({"archived": ctx_id, "current": new_current})


def cmd_delete(review_dir: Path, ctx_id: str) -> None:
    registry = load_registry(review_dir)
    if registry is None:
        err_exit("No registry found.")

    # Find directory (active or archived)
    ctx_dir = review_dir / ctx_id
    if not ctx_dir.exists():
        ctx_dir = review_dir / ".archived" / ctx_id
    if not ctx_dir.exists():
        err_exit(f"Context directory for '{ctx_id}' not found on disk.")

    # Trash BEFORE modifying registry (if trash fails, registry stays intact)
    success, method = move_to_trash(ctx_dir)
    if not success:
        err_exit(f"Failed to move '{ctx_dir}' to trash. No registry changes made.")

    current_id = registry.get("current")
    registry["contexts"] = [c for c in registry.get("contexts", []) if c["id"] != ctx_id]

    new_current = current_id
    if current_id == ctx_id:
        active_ids = [c["id"] for c in registry["contexts"] if c.get("status") != "archived"]
        new_current = active_ids[0] if active_ids else None
        registry["current"] = new_current

    save_registry(review_dir, registry)
    out({"deleted": ctx_id, "trash_method": method, "new_current": new_current})


def cmd_get(review_dir: Path, ctx_id: str) -> None:
    # Check active then archived
    for ctx_json in [
        review_dir / ctx_id / "context.json",
        review_dir / ".archived" / ctx_id / "context.json",
    ]:
        if ctx_json.exists():
            with open(ctx_json) as f:
                out(json.load(f))
            return
    err_exit(f"Context '{ctx_id}' not found.")


def cmd_update_iteration(
    review_dir: Path,
    ctx_id: str,
    version: str,
    verdict: str,
    source: str,
    branch: str,
    scope: str,
    scope_delta_json: str | None,
) -> None:
    context = load_context(review_dir, ctx_id)
    if context is None:
        err_exit(f"Context '{ctx_id}' not found.")

    existing_versions = {it["version"] for it in context.get("iterations", [])}
    if version in existing_versions:
        err_exit(f"Version '{version}' already exists in context '{ctx_id}'.")

    scope_delta = {}
    if scope_delta_json:
        try:
            scope_delta = json.loads(scope_delta_json)
        except json.JSONDecodeError:
            err_exit(f"Invalid JSON for --scope-delta.")

    now = now_iso()
    iteration = {
        "version": version,
        "date": now,
        "source": parse_source_obj(source),
        "working_branch": branch,
        "scope_summary": scope,
        "verdict": verdict.lower().strip(),
        "scope_delta": scope_delta,
    }

    context.setdefault("iterations", []).append(iteration)

    # Update top-level cache fields
    context["last_reviewed"] = now
    context["latest_version"] = version
    context["working_branch"] = branch
    context["scope_summary"] = scope

    # Determine correct save path (active or archived)
    ctx_json = review_dir / ctx_id / "context.json"
    if not ctx_json.exists():
        ctx_json = review_dir / ".archived" / ctx_id / "context.json"
    write_json_atomic(ctx_json, context)

    # Sync registry
    registry = load_registry(review_dir)
    if registry:
        for c in registry.get("contexts", []):
            if c["id"] == ctx_id:
                c["last_reviewed"] = now
                c["latest_version"] = version
                c["working_branch"] = branch
                c["scope_summary"] = scope
        save_registry(review_dir, registry)

    out({"updated": ctx_id, "version": version})


def cmd_versions(review_dir: Path, ctx_id: str) -> None:
    context = load_context(review_dir, ctx_id)
    if context is None:
        err_exit(f"Context '{ctx_id}' not found.")

    max_n = 0
    for it in context.get("iterations", []):
        m = re.match(r"^v(\d+)$", it.get("version", ""))
        if m:
            max_n = max(max_n, int(m.group(1)))

    print(f"v{max_n + 1}")


# ── Entry point ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review context manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--review-dir", default=".code-review",
        help="Path to .code-review directory (default: .code-review, relative to cwd)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("current", help="Get full context.json of the current context")

    lp = sub.add_parser("list", help="List review contexts")
    lp.add_argument("--all", action="store_true", dest="show_all", help="Include archived")

    np = sub.add_parser("new", help="Create a new review context")
    np.add_argument("source", help="Review source: PR URL, 'PR #N', 'git diff', 'staged', etc.")
    np.add_argument("--name", default=None, help="Context name slug (optional — inferred from branch if omitted)")

    swp = sub.add_parser("switch", help="Switch the active context")
    swp.add_argument("id", nargs="?", default=None, help="Context ID (omit to get selection list)")

    archp = sub.add_parser("archive", help="Archive a context (moves dir to .archived/)")
    archp.add_argument("id", nargs="?", default=None, help="Context ID (omit to get selection list)")

    delp = sub.add_parser("delete", help="Delete a context (moves to system trash)")
    delp.add_argument("id", help="Context ID")

    getp = sub.add_parser("get", help="Get full context.json for any context")
    getp.add_argument("id", help="Context ID")

    uip = sub.add_parser("update-iteration", help="Record a completed review iteration")
    uip.add_argument("id", help="Context ID")
    uip.add_argument("--version", required=True, help="Version string, e.g. v1")
    uip.add_argument("--verdict", required=True, help="approve | request changes | needs discussion")
    uip.add_argument("--source", required=True, help="Source description, e.g. 'PR #123'")
    uip.add_argument("--branch", required=True, help="Working branch at review time")
    uip.add_argument("--scope", required=True, help="One-sentence scope summary")
    uip.add_argument("--scope-delta", default=None, dest="scope_delta",
                     help="JSON string: {added, modified, removed, summary}")

    vp = sub.add_parser("versions", help="Get next version string (e.g. v2)")
    vp.add_argument("id", help="Context ID")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    review_dir = Path(args.review_dir).resolve()

    dispatch = {
        "current":          lambda: cmd_current(review_dir),
        "list":             lambda: cmd_list(review_dir, args.show_all),
        "new":              lambda: cmd_new(review_dir, args.source, args.name),
        "switch":           lambda: cmd_switch(review_dir, args.id),
        "archive":          lambda: cmd_archive(review_dir, args.id),
        "delete":           lambda: cmd_delete(review_dir, args.id),
        "get":              lambda: cmd_get(review_dir, args.id),
        "update-iteration": lambda: cmd_update_iteration(
            review_dir, args.id, args.version, args.verdict,
            args.source, args.branch, args.scope, args.scope_delta,
        ),
        "versions":         lambda: cmd_versions(review_dir, args.id),
    }

    dispatch[args.command]()


if __name__ == "__main__":
    main()
