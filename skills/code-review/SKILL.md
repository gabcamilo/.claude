---
name: code-review
description: |
  Orchestrates a comprehensive, parallelized code review pipeline with specialized subagents for architecture, security, performance, test coverage, and code quality analysis. Produces versioned markdown review reports in /.code-review/. Use this skill whenever the user asks for a code review, says "review my changes", "review this PR", "check my code", or when an agent needs to validate its own implementation. Also triggers on /code-review or /review commands. Supports scope selection (e.g., "review security and architecture only") and iterative re-reviews with conflict conciliation. Supports context management via /code-review:new, :list, :status, :switch, :archive, :delete to organize reviews by feature or topic.
---

# Code Review Pipeline

A structured, parallelized code review system that spawns specialized reviewer subagents, fetches relevant documentation, and produces versioned review reports — all organized into named review contexts.

## Subcommands

When a named subcommand is invoked, execute it and return immediately — do NOT run the review pipeline.

| Command | Action |
|---------|--------|
| `/code-review` or natural language | Run the full review pipeline |
| `/code-review:new [source] [name]` | Create a new review context |
| `/code-review:list` | List active review contexts |
| `/code-review:status` | Show current context details |
| `/code-review:switch [id]` | Switch the active context |
| `/code-review:archive [id]` | Archive a context (moves to `.archived/`) |
| `/code-review:delete id` | Delete a context (moves to system trash) |

For full subcommand behavior, examples, and the directory layout diagram, read `references/context-commands.md`.

---

## Data Model

Reviews are organized into contexts. All context data lives in `.code-review/` in the user's project root.

**`.code-review/registry.json`** — global index: `current` (active context id or null) + `contexts[]` (one summary entry per context). Registry entries and `context.json` share the same top-level fields; registry entries omit `iterations[]`.

**`.code-review/{id}/context.json`** — full context: same top-level fields as the registry entry, plus `iterations[]` (one entry per completed review: version, date, source, branch, verdict, scope_delta).

**`.code-review/{id}/REVIEW-v{N}.md`** — review report (same format as before, now under the context subdirectory)

**`.code-review/TECH_DEBT.md`** — project-scoped tech debt registry (shared across all contexts)

**`.code-review/config.json`** — optional project config (`auto: true` to skip prompts)

Context ids follow `{YYYYMMDD}_{name}` (e.g., `20260611_adds-new-things`). SKILL_ROOT = `~/.claude/skills/code-review` for default installations.

---

## Scripts Reference

Scripts live at `{SKILL_ROOT}/scripts/`. Always use `python3`. Always pass `--review-dir .code-review`.

| Purpose | Command |
|---------|---------|
| Load current context | `python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review current` |
| Create new context | `python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review new "{source}" --name "{name}"` |
| Get next version | `python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review versions {id}` |
| Record completed review | `python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review update-iteration {id} --version {v} --verdict "{verdict}" --source "{src}" --branch "{branch}" --scope "{scope}" [--scope-delta '{json}']` |
| Switch context | `python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review switch {id}` |
| List active contexts | `python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review list` |
| Fetch PR branches | `python3 {SKILL_ROOT}/scripts/fetch_pr.py "{pr_ref}" --json-output` |

---

## Two-Source Knowledge Model

This skill uses two complementary knowledge sources:

- **Knowledge Base (KB)** — Local, instant, zero-network. Curated principles, conventions, and patterns that rarely change. Located in `kb/` within the skill directory. Loaded directly into reviewer prompts.
- **Live Docs** — Fetched at review time via existing agents (DocsExplorer, FuryDocsExplorer). Covers volatile information: current API versions, deprecation notices, SDK changes.

Reviewers receive both: KB gives them principled grounding, live docs give them accuracy on current specifics.

## Task Dispatch Pattern

This skill spawns subagents using a structured `Task()` syntax. Each `Task()` maps directly to an Agent tool call — translate the parameters literally into the tool invocation. The `model` parameter controls which Claude model runs the subagent.

**Model assignments** (optimized for cost/quality tradeoff):
| Role | Model | Rationale |
|------|-------|-----------|
| Pre-commit runners | `haiku` | Command execution + output parsing |
| DocsExplorer | `haiku` | Doc fetching + summarization |
| FuryDocsExplorer | `haiku` | Doc fetching + summarization |
| Scope drift analyzer | `haiku` | Lightweight semantic comparison |
| Wave 1 reviewers (code-quality, test-coverage) | `sonnet` | Structured analysis with clear rubrics |
| Wave 2 reviewers (architecture, security, performance) | `sonnet` | Structured analysis requiring docs context |
| Re-review agents (full, delta, conciliator) | `sonnet` | Comparative analysis |

When you see a `Task()` block, call the Agent tool with these exact parameters:
- `prompt` → Agent `prompt` parameter
- `model` → Agent `model` parameter
- `subagent_type` → Agent `subagent_type` parameter (if present)
- `description` → Agent `description` parameter
- `run_in_background` → Agent `run_in_background` parameter (if present)

## Pipeline Overview

```
Trigger (user / agent / command)
  |
  +-- 0. CONTEXT BOOTSTRAP (always, inline)
  |     +-- python context.py current → load or prompt to create context
  |     +-- context_id passed to ALL subsequent steps
  |
  +-- 0.5 DRIFT DETECTION (when existing context loaded + new review triggered)
  |     +-- Phase 1 inline: PR number diff, branch diff
  |     +-- Phase 2 sub-agent (haiku): scope drift — only when Phase 1 detects something
  |     +-- If drift → AskUserQuestion (6 options)
  |
  +-- 1. LOAD KNOWN DEBT (always, inline, fast)
  |     +-- Read .code-review/TECH_DEBT.md → skip-list + known-debt-list
  |     +-- Scan for ADRs, in-code markers, documented deviations
  |     +-- Build reviewer context (passed to ALL reviewers)
  |
  +-- 2. GATHER changes (always)
  |     +-- PR trigger: ALWAYS run fetch_pr.py first to fetch remote branches
  |
  +-- 2.5 PRE-COMMIT VERIFICATION (parallel subagents)
  |     +-- Mandatory hooks (scoped to reviewed changes)
  |     +-- Optional hooks: checkstyle, PMD, etc. (--hook-stage manual)
  |
  +-- 3. DETECT stack & infrastructure (always)
  +-- 4. SELECT review scopes (interactive or args)
  |
  +-- 5. KNOWLEDGE wave (parallel — KB load + live docs fetch)
  |     +-- KB Loader: read relevant domains from kb/ (inline, instant)
  |     +-- DocsExplorer agent: non-Fury tech
  |     +-- FuryDocsExplorer agent: Fury infrastructure docs
  |
  +-- 6. REVIEW wave (parallel subagents, two-wave)
  |     +-- Wave 1 (KB-only): code-quality, test-coverage
  |     +-- Wave 2 (KB+docs): architecture, security, performance
  |     +-- Each receives: changes, project context, FILTERED KB/docs, DEBT CONTEXT
  |
  +-- 7. CONCILIATE (re-reviews only)
  |     +-- Full reviewer: fresh review of current state
  |     +-- Delta reviewer: what changed since last version
  |     +-- Conciliator: merge, resolve conflicts, escalate if needed
  |
  +-- 8. SYNTHESIZE & OUTPUT
        +-- Write .code-review/{context_id}/REVIEW-v{N}.md
        +-- Compute scope_delta (inline — file path analysis)
        +-- python context.py update-iteration ... (ALWAYS run after writing)
        +-- Sync .code-review/TECH_DEBT.md (new entries, updated counts)
```

---

## Step 0: Context Bootstrap

**ALWAYS run this step before any review pipeline execution. No exceptions.**

Run:
```bash
python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review current
```

**Case A: `found == false` (no registry or no current set)**

"No active review context. A new one will be created for this review."

1. Get current branch: `git rev-parse --abbrev-ref HEAD`
2. If branch is a feature/fix branch: suggest name by stripping the prefix (`feature/`, `fix/`, `feat/`, `chore/`, `hotfix/`, `refactor/`) and normalizing to lowercase + hyphens
3. If branch is `main`/`master`/`develop`/`staging` or detached HEAD: no suggestion — ask the user to provide a name
4. Check `config.json` for `auto: true`:
   - **auto = true**: use the suggestion directly, skip user prompt
   - **auto = false** (default): present two options — accept the suggestion or enter a custom name
5. Run: `python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review new "{source}" --name "{chosen_name}"`
6. If not auto: confirm with user — *"Context `{id}` created. Reviews will save to `.code-review/{id}/`. Continue to review?"*
7. Store `context_id` for all downstream steps. Proceed to Step 1 (skip Step 0.5 — no prior context to drift from).

**Case C: `found == true`**

Store `context_id`, `working_branch`, `scope_summary`, `latest_version` for all downstream steps. Proceed to Step 0.5.

---

## Step 0.5: Context Drift Detection

Run ONLY when Case C (existing context was loaded) AND the trigger is a new review request (not a subcommand, not an explicit re-review continuation of the current context's latest version).

### Phase 1 — inline checks (fast, no sub-agent)

Collect these drift signals:

1. **PR drift**: the trigger includes a PR ref AND the last stored iteration has `source.type == "pr"` AND the incoming PR number differs from `source.number`
2. **Branch drift**: `git rev-parse --abbrev-ref HEAD` returns a branch that differs from the stored `working_branch`

If **no Phase 1 signals** → proceed to Step 1 silently. Do NOT spawn Phase 2.

### Phase 2 — scope drift sub-agent (only when Phase 1 detected something)

Spawn a `haiku` sub-agent in parallel with any other preparatory work:

```
Task(
  model="haiku",
  description="Analyze scope drift for context drift detection",
  prompt="
    Compare the stored review context against the incoming request and explain
    if the work being reviewed seems to belong to a different context.

    Current context scope_summary: {scope_summary}
    Stored working branch: {working_branch}
    Last reviewed source: {last_source_ref}

    Incoming request:
    - Current branch: {current_branch}
    - Source/trigger: {incoming_source}
    - Changed file paths (from diff headers or trigger): {file_path_list}

    Return JSON:
    {
      \"drifted\": true/false,
      \"explanation\": \"one or two sentences explaining what differs and why it matters\"
    }

    Set drifted=true only when there is obvious mismatch — e.g. stored scope is about
    payments but changed files are entirely in shopify/ with no overlap.
    Partial overlap or iterative additions to the same feature = drifted=false.
    If scope_summary is empty, return drifted=false.
  "
)
```

### Presenting drift to the user

When any drift signal exists, use `AskUserQuestion` with the following structure. Include the Phase 2 explanation if available, or describe the Phase 1 signal(s) if the sub-agent was not needed:

```
The incoming review request differs from the current context "{context_name}":
  {list the specific signals, e.g.:}
  - Branch: you are on `fix/bug-fix` but context `{context_name}` was reviewed on `feature/new-feature`
  - PR: incoming is PR #456, context was last reviewed against PR #123
  - Scope: {Phase 2 explanation if available}

How would you like to proceed?
```

Options:
1. YES, continue — add this to the existing context scope
2. YES, but checkout `{working_branch}` from local first, then continue
3. YES, but fetch and checkout `{working_branch}` from remote first, then continue
4. NO, switch to a different review context
5. NO, create a new review context for this request
6. Let me explain / discuss this…

**Option 1**: Set `drift_acknowledged = true`. Proceed with current context. The new source/branch will be recorded by `update-iteration` in Step 8.

**Option 2**: Run `git checkout {working_branch}`. Proceed.

**Option 3**: Run `git fetch origin {working_branch} && git checkout {working_branch}`. Proceed.

**Option 4**: Run `context.py list`. Present the list. User picks an id. Run `context.py switch {id}`. Reload the new context. Re-run Step 0.5 against the new context.

**Option 5**: Run Step 0 Case A flow (auto-create). Proceed to Step 1.

**Option 6**: Enter free-form discussion. Halt the pipeline until the user clarifies intent.

---

## Step 1: Load Known Tech Debt & Documented Deviations

Before gathering changes or doing any analysis, scan for pre-existing tech debt documentation. This context is passed to ALL reviewers so they don't waste time rediscovering known patterns.

### 1a. Read Tech Debt Registry

Check if `.code-review/TECH_DEBT.md` exists (project-scoped — shared across all contexts). If yes, parse all entries into three lists:

- **skip_list**: entries with `status: intentional-deviation` — reviewers must NOT flag these patterns at all. Silent skip.
- **known_debt**: entries with `status: open` or `status: ticket-created` — reviewers should reference these (update occurrence counts) rather than re-discovering them.
- **resolved**: entries with `status: resolved` — if the reviewed code reintroduces a resolved pattern, flag it as a regression.

If `.code-review/TECH_DEBT.md` doesn't exist, proceed with empty lists.

### 1b. Scan for Other Documented Deviations

Search the project for additional debt/deviation documentation:

- **ADR files**: `docs/adr/`, `docs/decisions/`, `**/*ADR*.md`
- **In-code markers**: grep for `// TECH-DEBT:`, `// DEVIATION:`, `// ACCEPTED:`
- **Project markdown**: any `.md` file containing sections titled "tech debt", "accepted deviations", "known issues"

Merge findings into the skip_list and known_debt structures.

### 1c. Build Reviewer Context

Produce a structured summary for inclusion in every reviewer prompt:

```
## Known Tech Debt (from .code-review/TECH_DEBT.md and project docs)

### Silent Skip (intentional-deviation — do not mention in review)
- TD-001: @Entity on domain models (15 files) — team accepted per ADR-007

### Known Open Debt (reference existing entry, update count if changed)
- TD-002: RuntimeException wrapping in adapters (5 files)

### Documented Deviations (from ADRs / in-code markers)
- ADR-007: JPA-on-domain accepted for pragmatic reasons (2025-11)
```

This step runs inline — just file reads and grep. Fast and cheap.

---

## Step 2: Gather Changes

Determine what to review based on the trigger:

| Trigger | How to gather |
|---|---|
| "review my changes" | `git diff --name-only` + `git diff --cached --name-only`, then `git diff` for full content |
| "review staged changes" | `git diff --staged` |
| "review PR #N" or PR URL | **FIRST** run `fetch_pr.py` (see below), then `gh pr diff <N>` |
| "review [file paths]" | Read specified files directly |
| "review last commit" | `git diff HEAD~1` |
| Agent-invoked with file list | Use provided file list |

**PR reviews — mandatory pre-fetch**: ALWAYS run `fetch_pr.py` before `gh pr diff` for any PR trigger:

```bash
python3 {SKILL_ROOT}/scripts/fetch_pr.py "{pr_ref}" --json-output
```

- On `success: false` → halt and report the error to the user. Do NOT proceed with a partial branch state.
- On `success: true` with `fetch_result.exit_code != 0` → warn the user, then proceed using `gh pr diff` for the diff. Note that pre-commit scoping to PR branches may be limited.
- Use `base_ref` and `head_ref` from the output for all branch-relative operations and pre-commit scoping in Step 2.5.

Always read the full content of changed files for context, not just the diff lines.

---

## Step 2.5: Pre-Commit Verification

Run the project's pre-commit hooks scoped to the reviewed changes. This provides programmatic validation that complements the AI-driven review. Hooks run in parallel subagents.

### Prerequisites

Check if `pre-commit` is installed: `which pre-commit`. If not installed, skip this step and add a note to the review: "Pre-commit not available — programmatic checks skipped."

Check if `.pre-commit-config.yaml` exists in the project root. If not, skip this step.

### Discover hooks from config

Read `.pre-commit-config.yaml` to discover:
- **Mandatory hooks**: hooks with `stages: [pre-commit]` or no `stages` field (default)
- **Optional hooks**: hooks with `stages: [manual]`

Do not hardcode hook IDs — adapt to whatever the project configures.

### Scoping logic

Map the Step 2 gather trigger to the correct pre-commit scoping flags:

| Step 2 trigger | Pre-commit scoping |
|---|---|
| "review staged changes" | `pre-commit run` (default — staged files only) |
| "review my changes" (local) | `pre-commit run --files $(git diff HEAD --name-only --diff-filter=d)` |
| "review PR #N" / branch diff | `pre-commit run --from-ref $(git merge-base HEAD {base_ref}) --to-ref {head_ref}` (use refs from fetch_pr.py output) |
| "review last commit" | `pre-commit run --from-ref HEAD~1 --to-ref HEAD` |
| "review [file paths]" | `pre-commit run --files <file1> <file2> ...` |

`--diff-filter=d` excludes deleted files that would cause pre-commit to fail on missing files.

**CRITICAL**: NEVER use `--all-files`.

### Subagent parallelization

Spawn all hook runners in the same turn (parallel). Each uses the `precommit-runner` agent type on `haiku`:

```
Task(
  subagent_type="precommit-runner",
  model="haiku",
  description="Run mandatory pre-commit hooks",
  prompt="
    Run mandatory pre-commit hooks scoped to reviewed changes.
    Command: pre-commit run {scoping_flags}
    Capture exit code + output per hook.
    Parse output into structured findings: file, line, rule, message.
    Return JSON array of findings.
  "
)
```

Each subagent: runs the hook command, captures exit code, parses output into structured findings, returns results.

### Auto-fix handling

Some hooks auto-fix files. Since we're running hooks for analysis only: capture the output, if the hook modified files capture the diff (`git diff`), then restore: `git checkout -- <modified files>`.

### Result classification

- **Mandatory hook failures** → Blocking issues in the review.
- **Optional hook violations** → Warnings with guidance (fix or add suppression annotation with justification).

### Distribution to reviewers

Hook results go to the relevant reviewer in Step 6: Checkstyle/PMD → code-quality; security hooks → security; formatting → code-quality. Reviewers should not duplicate findings already caught by hooks — reference the hook result and add analysis if needed.

---

## Step 3: Detect Stack & Infrastructure

### Documentation scope rule

Documentation available to the review must match the scope of the changes being reviewed:

| Review trigger | Which docs to read |
|---|---|
| "review staged changes" | Committed docs + staged doc changes. Ignore unstaged docs. |
| "review my changes" / local changes | Committed docs + staged + unstaged doc changes. |
| "review PR #N" / PR branch | Only docs as they exist on the PR branch. Ignore local changes not in that branch. |
| "review last commit" | Docs as of HEAD. |

### Stack detection

Scan the project to identify technologies. Check these indicators:

1. **Build files**: `pom.xml`, `build.gradle`, `package.json`, `go.mod`, `Cargo.toml`, `requirements.txt`
2. **Config files**: `application.yml`, `docker-compose.yml`, `.fury/`, `Dockerfile`
3. **Source structure**: package names, directory layout, framework imports
4. **Project docs**: All markdown files (`**/*.md`) are project documentation. Pay special attention to `CLAUDE.md`, `README.md`, and `AGENTS.md` but do not limit discovery to these.

Match findings against the stacks registry at `references/stacks-registry.json`.

**If the stack is NOT supported**: alert the user clearly and proceed with general-purpose analysis only.

---

## Step 4: Select Review Scopes

Available review scopes are defined in `references/stacks-registry.json` under each stack's `reviewScopes` field.

| Scope | Agent Reference | What it checks |
|---|---|---|
| `architecture` | `references/agents/architecture-reviewer.md` | Architectural patterns, layer violations, dependency direction |
| `code-quality` | `references/agents/code-quality-reviewer.md` | DRY, SOLID, clean code, naming, complexity |
| `security` | `references/agents/security-reviewer.md` | OWASP top 10, secrets, injection, auth issues |
| `test-coverage` | `references/agents/test-coverage-reviewer.md` | Test existence, coverage gaps, test quality |
| `performance` | `references/agents/performance-reviewer.md` | N+1 queries, blocking calls, resource leaks, scalability |

### Scope selection logic

1. **Command args provided** (e.g., `/code-review --scope=architecture,security`): use those scopes directly.
2. **Natural language hints** (e.g., "review security"): extract mentioned scopes.
3. **Otherwise**: recommend scopes based on what actually changed:

| Changed file paths contain | Add scope |
|---|---|
| `domain/` or `port/` | `architecture` |
| `adapter/in/` (controllers, consumers) | `architecture`, `security` |
| `adapter/out/` (persistence, integration) | `architecture`, `performance` |
| `application/service/` | `architecture`, `code-quality` |
| `config/` or `infrastructure/config/` | `security` |
| `src/test/` | `test-coverage` |
| Any file with SQL, query, or repository in name | `performance` |

**Always include** `code-quality`. **Skip rules**: if no test files changed AND not a re-review → skip `test-coverage`; if only `domain/model/` changed → skip `performance` and `test-coverage`; if only test files → run `test-coverage` only.

---

## Step 5: Knowledge Wave

Three knowledge sources are loaded **in parallel**: the local KB (instant) and two docs agent subagents (network).

### 5a. KB Loader (inline — no subagent)

Read `kb/_index.yaml`. Based on detected stack and selected review scopes, use `scope_mappings` to determine which KB domains to load. For each mapped domain, read `quick-reference.md`, `index.md`, and `concepts/*.md`. Load patterns selectively when changes touch relevant areas.

**If a KB domain exists but is missing files**: proceed without it. KB gaps don't block the review.

### 5b. DocsExplorer Agent (non-Fury technologies)

```
Task(
  subagent_type="DocsExplorer",
  model="haiku",
  description="Fetch non-Fury tech docs",
  run_in_background=true,
  prompt="
    Fetch current documentation relevant to a code review of the following changes.
    Technologies: {non_fury_technologies}
    Review scopes: {selected_scopes}
    Changes summary: {changes_summary}
    Focus on: patterns, conventions, deprecations, known pitfalls.
    Return structured markdown. Under 500 lines — only directly relevant content.
  "
)
```

### 5c. FuryDocsExplorer Agent (Fury infrastructure)

```
Task(
  subagent_type="FuryDocsExplorer",
  model="haiku",
  description="Fetch Fury infrastructure docs",
  run_in_background=true,
  prompt="
    Fetch current Fury infrastructure documentation relevant to a code review.
    Fury services in use: {fury_services}
    Review scopes: {selected_scopes}
    Changes summary: {changes_summary}
    Focus on: SDK conventions, configuration rules, infrastructure patterns.
    Return structured markdown. Under 500 lines.
  "
)
```

### 5d. Codebase Precedent Check

Step 1 already loaded known tech debt. For patterns NOT in the registry, each reviewer prompt includes instructions to grep for existing occurrences before classifying a finding — see reviewer prompt template in Step 6.

### Knowledge distribution

After all three sources complete, distribute **per scope**:

| Scope | KB Domains | Needs Live Docs? |
|-------|-----------|-----------------|
| architecture | java-spring, fury-infrastructure | Yes |
| code-quality | java-spring | Optional |
| security | security, fury-infrastructure | Yes |
| test-coverage | java-spring | No |
| performance | java-spring, fury-infrastructure, shopify | Yes |

**Two-wave reviewer start**: Wave 1 reviewers (code-quality, test-coverage) start as soon as KB loads — no live docs needed. Wave 2 reviewers (architecture, security, performance) start after both KB and live docs complete.

---

## Step 6: Review Wave

Spawn reviewer subagents following the two-wave pattern.

**Wave 1** — spawn immediately after KB loads:

```
Task(subagent_type="CodeReviewer", model="sonnet", description="Review code quality",
     prompt="<reviewer-prompt for code-quality scope>")

Task(subagent_type="CodeReviewer", model="sonnet", description="Review test coverage",
     prompt="<reviewer-prompt for test-coverage scope>")
```

**Wave 2** — spawn after docs agents complete:

```
Task(subagent_type="CodeReviewer", model="sonnet", description="Review architecture",
     prompt="<reviewer-prompt for architecture scope>")

Task(subagent_type="CodeReviewer", model="sonnet", description="Review security",
     prompt="<reviewer-prompt for security scope>")

Task(subagent_type="CodeReviewer", model="sonnet", description="Review performance",
     prompt="<reviewer-prompt for performance scope>")
```

Each reviewer subagent receives only its filtered context:

1. **The changes** (diff + full file context)
2. **Project context** (CLAUDE.md, architecture docs, detected stack info)
3. **Scope-filtered KB** (only the domains mapped to this scope in `kb/_index.yaml`)
4. **Scope-filtered live docs** (only sections relevant to this scope — omitted entirely for Wave 1)
5. **Its scope-specific instructions** (from `references/agents/<scope>-reviewer.md`)
6. **Previous review** (if re-review, include the last REVIEW-v{N}.md)

**Reviewer prompt template** (fill in per scope):
```
You are a specialized [scope] code reviewer.

## Your Instructions
[Contents of references/agents/<scope>-reviewer.md]

## Project Context
[CLAUDE.md summary, detected stack, architecture info]

## Knowledge Base (non-volatile rules and patterns)
[KB quick-references and concepts for this scope's mapped domains.]

## Live Documentation (current API specifics)
[Output from DocsExplorer/FuryDocsExplorer agents — omitted for Wave 1 reviewers.]

## Pre-Commit Hook Results (programmatic checks)
[Results from Step 2.5 — only hooks relevant to this scope.
Do NOT duplicate findings already caught by hooks — reference and add analysis.]

## Known Tech Debt Context
[From Step 1: skip_list, known_debt, documented deviations]

## Changes to Review
[The diff and file contents]

## Previous Review (if re-review)
[Contents of last REVIEW-v{N}.md, filtered to this scope's section]

## Output Format — Intermediate Structure
[scope-prefixed findings: ARCH-B-001, SEC-W-001, CQ-S-001, etc.
Sections: ### Findings, ### Tech Debt, ### Cross-Scope Observations, ### Positive Findings, ### Scope Analysis]
```

For the full output format specification, see the reviewer agent files in `references/agents/`.

---

## Step 7: Conciliation (Re-reviews Only)

This step runs only when a previous review version exists (REVIEW-v{N-1}.md in the current context directory).

### 7a. Parallel review pair

```
Task(subagent_type="CodeReviewer", model="sonnet", description="Full re-review (fresh perspective)",
     prompt="Run the complete review pipeline with a fresh perspective, as if no previous review existed.
     {full reviewer prompt with changes, KB, docs, project context}")

Task(subagent_type="CodeReviewer", model="sonnet", description="Delta review (changes since v{N-1})",
     prompt="Focus on what changed since the last review:
     - What blocking issues from v{N-1} were addressed?
     - What new code was introduced? Any regressions?
     Previous review: {contents of REVIEW-v{N-1}.md}
     {delta changes, KB, docs, project context}")
```

### 7b. Conciliation

After both complete:

```
Task(subagent_type="CodeReviewer", model="sonnet", description="Conciliate full vs delta review",
     prompt="Read and follow: references/agents/conciliator.md
     Full reviewer findings: {full_reviewer_output}
     Delta reviewer findings: {delta_reviewer_output}")
```

The conciliator compares findings, resolves contradictions, tracks issue lifecycle vs v{N-1}, and escalates unresolvable conflicts to the user.

---

## Step 8: Synthesize & Output

### Version detection

```bash
python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review versions {context_id}
```

Returns `v1`, `v2`, etc. The output file path is: `.code-review/{context_id}/REVIEW-v{N}.md`

Before writing, verify the file does not already exist — do not overwrite silently.

### Section Ownership Contract

| Template Section | Source |
|---|---|
| Metadata table | Step 2 (gather) + verdict (computed); includes Context + Branch fields |
| Programmatic Checks | Step 2.5 (pre-commit) — MANDATORY, never omit |
| Summary | Synthesis (written after all findings collected) |
| Findings (B/W/S) | Step 6 reviewers → merged and renumbered by Step 8 |
| Scope Reports | Step 6 reviewers → `### Scope Analysis` sections |
| Tech Debt References | Step 6 reviewers → `### Tech Debt` sections + Step 1 registry |
| Cross-Scope Observations | Step 6 reviewers → `### Cross-Scope Observations` sections |
| Positive Findings | Step 6 reviewers → top 1-3 items |
| Conciliation Notes | Step 7 (conciliator) — re-reviews only |
| Review Metadata | Synthesis |

### Assemble the review file

Build section by section using the template at `references/review-template.md`. Key points:

- **Metadata table**: fill Context (context_id) and Branch (current working branch) in addition to the original fields. Compute verdict: any Blocking → "request changes", only Warnings → "needs discussion", only Suggestions → "approve".
- **Programmatic Checks**: populate from Step 2.5. If hooks couldn't run, write the section with a status note — NEVER omit this section.
- **Findings**: merge all `### Findings` from reviewer outputs. Strip scope prefixes, renumber sequentially: B-001, B-002… W-001… S-001…
- **Scope Reports**: each reviewer's `### Scope Analysis` — do NOT include Cross-Scope Observations here.
- **Tech Debt References**: merge `### Tech Debt` sections, deduplicate, renumber TD-001…, reference `.code-review/TECH_DEBT.md`.
- **Cross-Scope Observations**: extract from `### Cross-Scope Observations`, deduplicate, assign CS-xxx IDs.

### Scope Delta Analysis (inline, before writing the file)

Derive the scope delta from the diff to store in context metadata:

1. From the Step 2 gather, get the list of changed files with their git status (A=added, M=modified, D=deleted)
2. For each non-test, non-config file: extract class/feature name (filename without extension or path)
3. Exclude: test files (`src/test/`, `*Test.java`, `*Spec.java`), config files (`*.yml`, `*.xml`, `*.json`, `*.md`)
4. Build: `added`, `modified`, `removed` lists + one-sentence `summary`
5. If only test/config files changed: `summary = "Only test and configuration files modified"`

### Structural Validation

Before writing the file, verify:

- [ ] Metadata table: all 8 fields filled (Version, Context, Date, Stack, Branch, Scopes Reviewed, Changes Source, Verdict)
- [ ] `## Programmatic Checks` present (even if hooks didn't run)
- [ ] `## Summary` with at least one paragraph
- [ ] `## Findings` with blocking/warnings/suggestions subsections
- [ ] All findings use `> **[X-NNN]**` blockquote format with sequential numbering
- [ ] `## Scope Reports` with one `### {Name} Review` per scope
- [ ] Scope Reports do NOT contain Cross-Scope Observations
- [ ] `## Tech Debt References` present if any TD items found
- [ ] `## Positive Findings` present
- [ ] `## Review Metadata` present
- [ ] Output path is `.code-review/{context_id}/REVIEW-v{N}.md` (not root `.code-review/`)
- [ ] No silent overwrites — file must not already exist

### Context Update — ALWAYS run after writing the review file

```bash
python3 {SKILL_ROOT}/scripts/context.py --review-dir .code-review update-iteration {context_id} \
  --version {N} \
  --verdict "{verdict}" \
  --source "{source_ref}" \
  --branch "{working_branch}" \
  --scope "{scope_summary}" \
  --scope-delta '{scope_delta_json}'
```

If this command fails: report the error to the user but do NOT re-run the review. The review file is already written. Suggest running the update manually.

### Tech Debt Registry Sync

After writing the review file, sync `.code-review/TECH_DEBT.md` (project-scoped):

1. **New debt found**: append a new entry for each TD-xxx not already in the registry
2. **Known debt updated**: update `Occurrences` count and `Last reviewed` date for existing entries
3. **Resolved debt**: if 0 occurrences found for a previously open entry, update status to `resolved`
4. **Create if missing**: create the file with the standard header if it doesn't exist and TD items were found

Ensure `.code-review/` is in `.gitignore`.

### Summary to user

- Overall verdict: **approve** / **request changes** / **needs discussion**
- Count of blocking issues, warnings, suggestions, tech debt references
- Path to the full review: `.code-review/{context_id}/REVIEW-v{N}.md`
- Tech debt registry changes
- If re-review: what improved since last version, what's new

---

## Extending the Skill

### Adding a New Review Scope

1. Create `references/agents/<scope-name>-reviewer.md`
2. Add the scope to the relevant stack(s) in `references/stacks-registry.json`
3. Map the scope to KB domains in `kb/_index.yaml` under `scope_mappings`

### Adding a New KB Domain

1. Create `kb/{domain}/` with `index.md`, `quick-reference.md`, `concepts/`, `patterns/`
2. Register in `kb/_index.yaml` under `domains`
3. Map to review scopes under `scope_mappings`

### Adding a New Stack

1. Add a stack entry in `references/stacks-registry.json`
2. Create corresponding KB domains
3. If specialized docs agents are needed, create them in `.claude/agents/`

---

## Behavioral Rules

- **Be critical, not cruel.** Catch real issues, not demonstrate thoroughness.
- **Be specific.** Always reference exact file paths, line numbers, and rule names.
- **Be proportional.** A typo is a suggestion. An architecture violation is blocking.
- **Verify runtime impact before classifying as Blocking.** Confirm the code path is reachable, not a placeholder, and produces observable harm. If unsure, classify as Warning.
- **Verify before citing.** If unsure whether a convention exists, check the docs and project files first.
- **Don't review generated code, build artifacts, or lock files.**
- **Respect the user's time.** If the code is clean, say so. Don't manufacture findings.
- **When running as part of an agent pipeline**, return structured output the calling agent can act on.
- **Context-before-review checkpoint**: ALWAYS run Step 0 before starting the review pipeline. Never skip it.
- **Remote-fetch-before-PR checkpoint**: ALWAYS run `fetch_pr.py` before `gh pr diff` for any PR trigger.
- **Context-update-after-review checkpoint**: ALWAYS run `context.py update-iteration` after writing the review file.
- **Drift-check-before-review checkpoint**: ALWAYS run Step 0.5 when an existing context is loaded.
