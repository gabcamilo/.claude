#!/usr/bin/env python3
"""Fetch PR branch info and pull branches locally for code-review skill.

Always run this before any PR review to ensure local branch refs are available
for pre-commit scoping and accurate diff generation.

Usage:
  python3 fetch_pr.py <PR_REF> [--json-output] [--repo OWNER/REPO]

PR_REF accepts:
  - Full GitHub URL: https://github.com/org/repo/pull/123
  - PR number:       123
  - Hash-prefixed:   #123

Output (JSON):
  {success, pr_number, pr_title, base_ref, head_ref, state, fetch_result}
"""

import argparse
import json
import re
import subprocess
import sys


def parse_pr_number(pr_ref: str) -> int | None:
    """Extract integer PR number from URL, #N, or plain integer."""
    pr_ref = pr_ref.strip()

    url_match = re.search(r"/pull/(\d+)", pr_ref)
    if url_match:
        return int(url_match.group(1))

    num_match = re.match(r"^(?:PR\s*)?#?(\d+)$", pr_ref, re.IGNORECASE)
    if num_match:
        return int(num_match.group(1))

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch PR branches from remote for code review",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("pr_ref", help="PR number, #N, or full GitHub URL")
    parser.add_argument("--json-output", action="store_true",
                        help="Output JSON (default behavior, flag is for explicitness)")
    parser.add_argument("--repo", default=None,
                        help="OWNER/REPO for cross-repo PRs (passed as -R to gh)")
    args = parser.parse_args()

    pr_number = parse_pr_number(args.pr_ref)
    if pr_number is None:
        result = {
            "success": False,
            "error": "invalid_ref",
            "message": f"Could not parse a PR number from: {args.pr_ref!r}",
            "pr_ref_given": args.pr_ref,
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # ── Get PR info from gh ────────────────────────────────────────────────
    gh_cmd = [
        "gh", "pr", "view", str(pr_number),
        "--json", "number,title,baseRefName,headRefName,state",
    ]
    if args.repo:
        gh_cmd += ["-R", args.repo]

    gh_result = subprocess.run(gh_cmd, capture_output=True, text=True)

    if gh_result.returncode != 0:
        stderr = gh_result.stderr.strip()
        error_type = "gh_auth_error" if "auth" in stderr.lower() else "gh_not_found"
        result = {
            "success": False,
            "error": error_type,
            "message": stderr or gh_result.stdout.strip(),
            "pr_ref_given": args.pr_ref,
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    try:
        pr_info = json.loads(gh_result.stdout)
    except json.JSONDecodeError as exc:
        result = {
            "success": False,
            "error": "json_parse_error",
            "message": f"Could not parse gh output: {exc}",
            "pr_ref_given": args.pr_ref,
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    base_ref = pr_info["baseRefName"]
    head_ref = pr_info["headRefName"]

    # ── Fetch both branches ────────────────────────────────────────────────
    fetch_result = subprocess.run(
        ["git", "fetch", "origin", base_ref, head_ref],
        capture_output=True, text=True,
    )

    result = {
        "success": True,
        "pr_number": pr_info["number"],
        "pr_title": pr_info["title"],
        "base_ref": base_ref,
        "head_ref": head_ref,
        "state": pr_info["state"],
        "fetch_result": {
            "exit_code": fetch_result.returncode,
            "stdout": fetch_result.stdout,
            "stderr": fetch_result.stderr.strip(),
        },
    }

    # fetch failure is non-fatal: return success=true with error details so
    # the orchestrator can decide whether to proceed with gh pr diff instead.
    if fetch_result.returncode != 0:
        result["fetch_warning"] = (
            f"git fetch returned exit code {fetch_result.returncode}. "
            "Pre-commit hooks may not be scopeable to PR branches. "
            "Falling back to 'gh pr diff' for the diff itself."
        )

    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
