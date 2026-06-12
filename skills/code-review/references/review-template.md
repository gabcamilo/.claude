# Code Review Report

<!-- source: Step 1 (gather) + Step 7 (verdict computation) -->

| Field | Value |
|---|---|
| **Version** | v{VERSION} |
| **Context** | {CONTEXT_ID} |
| **Date** | {DATE} |
| **Stack** | {DETECTED_STACK} |
| **Branch** | {WORKING_BRANCH} |
| **Scopes Reviewed** | {SCOPE_LIST} |
| **Changes Source** | {SOURCE: diff / PR #N / files / commit SHA} |
| **Verdict** | {VERDICT: approve / request changes / needs discussion} |

---

<!-- source: Step 1.5 (pre-commit) — MANDATORY section, never omit -->

## Programmatic Checks

{Results from pre-commit hooks run on the reviewed changes only. If hooks could not run, write this section with a status explanation — do NOT omit it.}

### Mandatory Hooks

| Hook | Status | Details |
|------|--------|---------|
| {hook_name} | PASS / FAIL | {details if failed, blank if passed} |

{If all pass: "All mandatory hooks passed."}
{If any fail: these are Blocking issues — must be fixed before merge.}

### Optional Hooks (Code Quality)

#### Checkstyle ({N} violations on reviewed files)
{If 0: "No checkstyle violations on reviewed files."}
{For each violation:}
- `{file:line}` -- {rule}: {message}
  - Action: {fix the violation | valid exception — add suppression with justification}

#### PMD ({N} violations on reviewed files)
{If 0: "No PMD violations on reviewed files."}
{For each violation:}
- `{file:line}` -- {rule}: {message}
  - Action: {fix the violation | valid exception — add `@SuppressWarnings("PMD.{Rule}")` because {justification}}

{Omit hook subsections that don't exist in the project's .pre-commit-config.yaml.}

---

<!-- source: Step 7 (synthesis — written after all findings collected) -->

## Summary

{One paragraph: what the changes do, which areas they affect, and the overall assessment.}

{If re-review: "Compared to v{N-1}: X blocking issues resolved, Y new issues found, Z unchanged."}

---

<!-- source: Step 5 (reviewers) → merged and renumbered by Step 7 -->

## Findings

### Blocking Issues

{Issues that MUST be fixed before merge. Ordered by severity.}

> **[B-001]** {Short title}
> - **Scope**: {architecture | security | code-quality | test-coverage | performance}
> - **File**: `{path/to/file.java:L10-L25}`
> - **Rule**: {specific rule or principle violated}
> - **Problem**: {clear description of what is wrong}
> - **Fix**: {concrete, actionable suggestion}
> - **Confidence**: {high | medium} — {brief justification if medium}

{Repeat for each blocking issue. If none: "No blocking issues found."}

### Warnings

{Non-blocking concerns worth addressing. Same format as blocking issues, using [W-001] numbering.}

{If none: "No warnings."}

### Suggestions

{Optional improvements. Brief and actionable, using [S-001] numbering.}

- **[S-001]** `{file:line}` — {suggestion}

{If none: "No suggestions."}

---

<!-- source: Step 5 (reviewers) → "Scope Analysis" sections only, NO cross-scope observations -->

## Scope Reports

{One section per reviewed scope, containing the detailed analysis from each reviewer subagent.}

### {Scope Name} Review

{Full output from the scope's reviewer subagent, preserving its structure.}

---

<!-- source: Step 5 (reviewers) "Tech Debt" sections + Step 0 (registry) → merged by Step 7 -->

## Tech Debt References

{Patterns found in the reviewed changes that violate documented rules BUT already exist elsewhere in the codebase. These are not blocking the current changes — they are pre-existing technical debt. Each item is tracked in `docs/TECH_DEBT.md`.}

> **[TD-001]** {Short title}
> - **Registry**: `docs/TECH_DEBT.md#td-001` — {new | existing} ({occurrence_count} files)
> - **Rule violated**: {specific rule with official docs citation}
> - **In reviewed changes**: `{file:line}` — {what the code does}
> - **Pre-existing in codebase**: {count} files — see registry for full list
> - **Why it matters**: {explanation referencing KB or live docs}

{If none: omit this section entirely.}
{Items from the registry with status `intentional-deviation` are silently skipped — they do NOT appear here.}

---

<!-- source: Step 5 (reviewers) "Cross-Scope Observations" sections → extracted, deduplicated, renumbered by Step 7 -->

## Cross-Scope Observations

{Issues noticed by reviewers that span multiple scopes or sit in gray areas between scopes. These were flagged during individual scope reviews and synthesized here. Grouped by theme, not by originating reviewer.}

> **[CS-001]** {Short title}
> - **Scopes involved**: {architecture + security | performance + security | etc.}
> - **Observed by**: {which reviewer(s) flagged this}
> - **File**: `{file:line}`
> - **Observation**: {what was noticed and why it crosses scope boundaries}

{If none: omit this section entirely.}

---

## Positive Findings

{Things done well across all scopes. 1-3 items max, one sentence each. Do not pad this section.}

---

## Conciliation Notes (re-reviews only)

{If this is v2+, include:}
- **Resolved from v{N-1}**: {list of issue IDs that were fixed}
- **Persisting**: {list of issue IDs still present}
- **New in v{N}**: {list of new issue IDs}
- **Conflicts resolved**: {any contradictions between full and delta reviewers, and how they were resolved}
- **Escalated to user**: {any unresolved conflicts, if applicable}

---

## Review Metadata

- **Reviewer subagents**: {list of agents that ran}
- **Files analyzed**: {count} ({list or truncated list})
- **Documentation consulted**: {list of doc sources used}
- **Previous version**: {path to v{N-1} or "N/A (first review)"}
