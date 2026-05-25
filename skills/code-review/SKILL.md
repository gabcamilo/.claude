---
name: code-review
description: |
  Orchestrates a comprehensive, parallelized code review pipeline with specialized subagents for architecture, security, performance, test coverage, and code quality analysis. Produces versioned markdown review reports in /.code-review/. Use this skill whenever the user asks for a code review, says "review my changes", "review this PR", "check my code", or when an agent needs to validate its own implementation. Also triggers on /code-review or /review commands. Supports scope selection (e.g., "review security and architecture only") and iterative re-reviews with conflict conciliation.
---

# Code Review Pipeline

A structured, parallelized code review system that spawns specialized reviewer subagents, fetches relevant documentation, and produces versioned review reports.

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
  +-- 0. LOAD KNOWN DEBT (always, inline, fast)
  |     +-- Read .code-review/TECH_DEBT.md → skip-list + known-debt-list
  |     +-- Scan for ADRs, in-code markers, documented deviations
  |     +-- Build reviewer context (passed to ALL reviewers)
  |
  +-- 1. GATHER changes (always)
  +-- 1.5 PRE-COMMIT VERIFICATION (parallel subagents)
  |     +-- Mandatory hooks (scoped to reviewed changes)
  |     +-- Optional hooks: checkstyle, PMD, etc. (--hook-stage manual)
  |
  +-- 2. DETECT stack & infrastructure (always)
  +-- 3. SELECT review scopes (interactive or args)
  |
  +-- 4. KNOWLEDGE wave (parallel — KB load + live docs fetch)
  |     +-- KB Loader: read relevant domains from kb/ (inline, instant)
  |     +-- DocsExplorer agent: non-Fury tech
  |     +-- FuryDocsExplorer agent: Fury infrastructure docs
  |
  +-- 5. REVIEW wave (parallel subagents, two-wave)
  |     +-- Wave 1 (KB-only): code-quality, test-coverage
  |     +-- Wave 2 (KB+docs): architecture, security, performance
  |     +-- Each receives: changes, project context, FILTERED KB/docs, DEBT CONTEXT
  |
  +-- 6. CONCILIATE (re-reviews only)
  |     +-- Full reviewer: fresh review of current state
  |     +-- Delta reviewer: what changed since last version
  |     +-- Conciliator: merge, resolve conflicts, escalate if needed
  |
  +-- 7. SYNTHESIZE & OUTPUT
        +-- Merge findings, classify severity
        +-- Write /.code-review/REVIEW-v{N}.md
        +-- Sync .code-review/TECH_DEBT.md (new entries, updated counts)
```

---

## Step 0: Load Known Tech Debt & Documented Deviations

Before gathering changes or doing any analysis, scan for pre-existing tech debt documentation. This context is passed to ALL reviewers so they don't waste time rediscovering known patterns.

### 0a. Read Tech Debt Registry

Check if `.code-review/TECH_DEBT.md` exists. If yes, parse all entries into three lists:

- **skip_list**: entries with `status: intentional-deviation` — reviewers must NOT flag these patterns at all. Silent skip. The team already decided.
- **known_debt**: entries with `status: open` or `status: ticket-created` — reviewers should reference these (update occurrence counts) rather than re-discovering them from scratch.
- **resolved**: entries with `status: resolved` — if the reviewed code reintroduces a resolved pattern, flag it as a regression, not as new debt.

If `.code-review/TECH_DEBT.md` doesn't exist, proceed with empty lists — the registry will be created in Step 7 if any debt is found.

### 0b. Scan for Other Documented Deviations

Search the project for additional debt/deviation documentation beyond the registry:

- **ADR files**: `docs/adr/`, `docs/decisions/`, `**/*ADR*.md` — Architecture Decision Records often document accepted deviations
- **In-code markers**: grep for `// TECH-DEBT:`, `// DEVIATION:`, `// ACCEPTED:` — lightweight inline documentation of conscious choices
- **Project markdown**: any `.md` file containing sections titled "tech debt", "accepted deviations", "known issues"

Merge findings into the skip_list and known_debt structures.

### 0c. Build Reviewer Context

Produce a structured summary for inclusion in every reviewer prompt:

```
## Known Tech Debt (from .code-review/TECH_DEBT.md and project docs)

### Silent Skip (intentional-deviation — do not mention in review)
- TD-001: @Entity on domain models (15 files) — team accepted per ADR-007

### Known Open Debt (reference existing entry, update count if changed)
- TD-002: RuntimeException wrapping in adapters (5 files)
- TD-003: Native SQL via createNativeQuery (2 files)

### Documented Deviations (from ADRs / in-code markers)
- ADR-007: JPA-on-domain accepted for pragmatic reasons (2025-11)
- // ACCEPTED: WeightConverter uses null return for unknown units
```

This step runs inline (no subagent needed) — it's just file reads and grep. Fast and cheap.

---

## Step 1: Gather Changes

Determine what to review based on the trigger:

| Trigger | How to gather |
|---|---|
| "review my changes" | `git diff --name-only` + `git diff --cached --name-only`, then `git diff` for full content |
| "review staged changes" | `git diff --staged` |
| "review PR #N" or PR URL | `gh pr diff <N>` |
| "review [file paths]" | Read specified files directly |
| "review last commit" | `git diff HEAD~1` |
| Agent-invoked with file list | Use provided file list |

Always read the full content of changed files for context, not just the diff lines.
Store the gathered changes in memory for subagent distribution.

---

## Step 1.5: Pre-Commit Verification

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

Map the Step 1 gather trigger to the correct pre-commit scoping flags:

| Step 1 trigger | Pre-commit scoping |
|---|---|
| "review staged changes" | `pre-commit run` (default — staged files only) |
| "review my changes" (local) | `pre-commit run --files $(git diff HEAD --name-only --diff-filter=d)` |
| "review PR #N" / branch diff | `pre-commit run --from-ref $(git merge-base HEAD develop) --to-ref HEAD` |
| "review last commit" | `pre-commit run --from-ref HEAD~1 --to-ref HEAD` |
| "review [file paths]" | `pre-commit run --files <file1> <file2> ...` |

`--diff-filter=d` excludes deleted files that would cause pre-commit to fail on missing files.

**CRITICAL**: NEVER use `--all-files`. The hooks must run ONLY on the reviewed changes. Older code may not comply with current rules and we do not want to force refactoring beyond the review scope.

### Subagent parallelization

Spawn all hook runners in the same turn (parallel). Each uses the `precommit-runner` agent type on `haiku` — they just execute commands and parse output.

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

# One Task per optional hook (all spawned in the same turn as above):
Task(
  subagent_type="precommit-runner",
  model="haiku",
  description="Run {hook_name} manual hook",
  prompt="
    Run optional pre-commit hook scoped to reviewed changes.
    Command: pre-commit run {hook_name} --hook-stage manual {scoping_flags}
    Capture violations with file:line.
    Parse output into structured findings: file, line, rule, message.
    Return JSON array of findings.
  "
)
```

Each subagent:
1. Runs the hook command with the correct scoping flags
2. Captures exit code (0 = pass, non-zero = violations found)
3. Parses the output into structured findings (file, line, rule, message)
4. Returns structured results

### Auto-fix handling

Some hooks (e.g., `pretty-format-java`, `end-of-file-fixer`) auto-fix files. Since we're running hooks for analysis, not to apply changes, handle this by:
1. Running the hook and capturing the output
2. If the hook modified files, capture the diff (`git diff`) to report what would change
3. Restore the original state: `git checkout -- <modified files>`

This ensures the review REPORTS violations without modifying the working tree.

### Result classification

- **Mandatory hook failures** → Blocking issues in the review. These MUST pass before merge.
- **Optional hook violations** → Warnings in the review, with guidance:
  - If the violation is valid: suggest fixing it
  - If it's a valid exception to the rule: suggest adding the appropriate suppression annotation (e.g., `@SuppressWarnings("PMD.RuleName")`) with a comment explaining why the exception is acceptable in this context

### Distribution to reviewers

Hook results are included in the relevant reviewer's prompt in Step 5:
- Checkstyle/PMD results → code-quality reviewer
- Security hook results (websec, datasec) → security reviewer
- Formatting issues → code-quality reviewer

This gives reviewers programmatic evidence to corroborate or contextualize their AI-driven findings. Reviewers should not duplicate findings already caught by hooks — instead, reference the hook result and add analysis if needed.

---

## Step 2: Detect Stack & Infrastructure

### Documentation scope rule

The documentation available to the review **must match the scope of the changes being reviewed**. Do not read docs that the reviewed code wouldn't see:

| Review trigger | Which docs to read |
|---|---|
| "review staged changes" | Committed docs + staged doc changes. Ignore unstaged docs. |
| "review my changes" / local changes | Committed docs + staged doc changes + unstaged doc changes. |
| "review PR #N" / PR branch | Only docs as they exist on the PR branch (`gh api` or `git show <branch>:<path>`). Ignore local changes not in that branch. |
| "review last commit" | Docs as of HEAD. |

Follow these rules unless the user explicitly asks to consider documentation outside the reviewed scope.

### Stack detection

Scan the project to identify technologies. Check these indicators:

1. **Build files**: `pom.xml`, `build.gradle`, `package.json`, `go.mod`, `Cargo.toml`, `requirements.txt`
2. **Config files**: `application.yml`, `docker-compose.yml`, `.fury/`, `Dockerfile`
3. **Source structure**: package names, directory layout, framework imports
4. **Project docs**: All markdown files (`**/*.md`) in the project are considered project documentation and should be analyzed for context. Pay special attention to `CLAUDE.md`, `README.md`, and `AGENTS.md` as they typically contain architecture decisions and conventions, but do not limit discovery to only these files — any `.md` file may contain relevant rules, decisions, or context.

Match findings against the stacks registry at `references/stacks-registry.json`.

**If the stack is supported**: proceed with stack-specific knowledge sources and doc endpoints.
**If the stack is NOT supported**: alert the user clearly:

> "Detected stack: [X]. This stack is not yet in the supported registry. The review will proceed with general-purpose analysis only. Stack-specific rules, documentation sources, and specialized checks will not be available. Consider adding support — see `references/stacks-registry.json`."

---

## Step 3: Select Review Scopes

Available review scopes are defined in `references/stacks-registry.json` under each stack's `reviewScopes` field. The default scopes are:

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
3. **Otherwise**: recommend scopes based on **what actually changed**, not just file count:

#### Content-aware heuristics

Classify changed files by path to determine relevant scopes:

| Changed file paths contain | Add scope |
|---|---|
| `domain/` or `port/` | `architecture` |
| `adapter/in/` (controllers, consumers) | `architecture`, `security` |
| `adapter/out/` (persistence, integration) | `architecture`, `performance` |
| `application/service/` | `architecture`, `code-quality` |
| `config/` or `infrastructure/config/` | `security` |
| `src/test/` | `test-coverage` |
| Any file with SQL, query, or repository in name | `performance` |

**Always include** `code-quality` — it applies to all code changes.

**Fallback by file count** (if heuristics don't narrow it down):
- Small changes (<5 files): `architecture` + `code-quality`
- Medium changes (5-15 files): all except `performance`
- Large changes (>15 files): all scopes

**Skip rules** (override heuristics):
- If NO test files changed AND this isn't a re-review → skip `test-coverage`
- If changes are ONLY in `domain/model/` → skip `performance` and `test-coverage`
- If changes are ONLY test files → run `test-coverage` only

The user can always override with "all" or a specific subset.

---

## Step 4: Knowledge Wave

Three knowledge sources are loaded **in parallel**: the local KB (instant) and two docs agent subagents (network). All three run simultaneously — the KB load finishes instantly while the docs agents fetch.

### 4a. KB Loader (inline — no subagent needed)

Read the `kb/_index.yaml` registry. Based on the detected stack and selected review scopes, use the `scope_mappings` to determine which KB domains to load.

For each mapped domain, read:
1. `kb/{domain}/quick-reference.md` (always — fast lookup tables)
2. `kb/{domain}/index.md` (always — overview and principles)
3. `kb/{domain}/concepts/*.md` (always — core rules)
4. `kb/{domain}/patterns/*.md` (selectively — only when changes touch relevant areas)

Store the loaded KB content keyed by domain for distribution to reviewers.

**If a KB domain directory exists but is empty or missing files**: proceed without it. KB gaps don't block the review — live docs compensate.

### 4b. DocsExplorer Agent (non-Fury technologies)

Spawn a **DocsExplorer** subagent for non-Fury technologies. Uses Context7 MCP as primary source with llms.txt and WebFetch fallbacks.

```
Task(
  subagent_type="DocsExplorer",
  model="haiku",
  description="Fetch non-Fury tech docs",
  run_in_background=true,
  prompt="
    Fetch current documentation relevant to a code review of the following changes.

    Technologies to research: {non_fury_technologies}
    Review scopes active: {selected_scopes}
    Changes summary: {changes_summary}

    Focus on: patterns, conventions, deprecations, and known pitfalls relevant to these changes.
    Return structured markdown. Keep it under 500 lines — only what's directly relevant.
  "
)
```

### 4c. FuryDocsExplorer Agent (Fury infrastructure)

Spawn a **FuryDocsExplorer** subagent if the detected stack includes Fury infrastructure. Uses `meli-docs-fury` MCP tools (`search_sdk_docs`, `search_api_docs`, `search_api_specs`).

```
Task(
  subagent_type="FuryDocsExplorer",
  model="haiku",
  description="Fetch Fury infrastructure docs",
  run_in_background=true,
  prompt="
    Fetch current Fury infrastructure documentation relevant to a code review.

    Fury services in use: {fury_services}
    Review scopes active: {selected_scopes}
    Changes summary: {changes_summary}

    Focus on: SDK conventions, configuration rules, infrastructure patterns relevant to these changes.
    Return structured markdown. Keep it under 500 lines.
  "
)
```

### 4d. Codebase Precedent Check (lightweight — Step 0 handles known debt)

Step 0 already loaded known tech debt and intentional deviations. This step handles only **NEW patterns** not yet in the registry.

Each reviewer prompt includes this instruction:

```
You have received a "Known Tech Debt" context from Step 0. For patterns 
listed there:
- intentional-deviation → SILENT SKIP (do not mention at all)
- open/ticket-created → Reference the existing TD-xxx entry, update the 
  occurrence count if you find more files, but do not re-discover it

For patterns NOT in the Known Tech Debt context:
Before classifying a finding as blocking or warning, use the Precedent 
Check Patterns listed in your scope-specific instructions to grep for 
existing occurrences in the codebase.

If the pattern IS already established:
- Add it as a NEW Tech Debt Reference (TD-xxx) — the skill will append 
  it to .code-review/TECH_DEBT.md in Step 7
- Include: rule violated (with docs citation), occurrence count, why it 
  matters, and file:line examples from the existing codebase

IMPORTANT: Finding a precedent means the violation is pre-existing tech 
debt — it does NOT mean it's acceptable. You must ALWAYS flag it as a 
TD-xxx reference. The only patterns you silently skip are those in the 
Step 0 skip_list (status=intentional-deviation in .code-review/TECH_DEBT.md).

  "Consistent with existing code" = Tech Debt Reference (TD-xxx)
  "In the intentional-deviation skip list" = Silent skip
  "Not found elsewhere" = New violation (B/W/S)

If the pattern is NOT found elsewhere — it's a new violation. Classify 
it normally (blocking/warning/suggestion).
```

### Knowledge distribution

After all three sources complete, distribute knowledge **per scope** — each reviewer gets only the KB domains and live docs sections relevant to its scope. Do NOT send all knowledge to all reviewers.

| Scope | KB Domains | Live Docs Filter | Needs Live Docs? |
|-------|-----------|-----------------|-----------------|
| architecture | java-spring, fury-infrastructure | Framework conventions, infrastructure patterns | Yes |
| code-quality | java-spring | Language idioms, framework best practices | Optional (KB usually sufficient) |
| security | security, fury-infrastructure | Current vulnerability patterns, SDK security | Yes |
| test-coverage | java-spring | Testing framework updates, new assertions | No (KB sufficient) |
| performance | java-spring, fury-infrastructure, shopify | API rate limits, caching updates, query optimization | Yes |

**KB filtering**: Use `scope_mappings` from `kb/_index.yaml` to select domains per scope. Include only the mapped domains' quick-reference, index, and concepts for that reviewer.

**Live docs filtering**: When constructing each reviewer's prompt, include only the live docs sections that match the "Live Docs Filter" column. If a reviewer's "Needs Live Docs?" is No/Optional, omit live docs entirely from its prompt — the KB is sufficient.

This prevents sending all 4 KB domains and all live docs to all 5 reviewers. Each reviewer gets a focused, smaller context.

### Two-wave reviewer start

Reviewers that don't need live docs can start **immediately after KB loads** (Step 4a), without waiting for DocsExplorer/FuryDocsExplorer to finish:

- **Wave 1** (starts after KB loads — no live docs dependency):
  - `code-quality` reviewer (KB: java-spring only)
  - `test-coverage` reviewer (KB: java-spring only)

- **Wave 2** (starts after KB + live docs both complete):
  - `architecture` reviewer (KB + live docs)
  - `security` reviewer (KB + live docs)
  - `performance` reviewer (KB + live docs)

This lets Wave 1 reviewers start 30-60s earlier on full reviews, reducing wall-clock time.

---

## Step 5: Review Wave

Spawn reviewer subagents following the two-wave pattern above. Wave 1 reviewers launch as soon as KB is ready; Wave 2 reviewers launch when live docs also arrive.

**Wave 1** — spawn these in the same turn, immediately after KB loads (do NOT wait for docs agents):

```
Task(
  subagent_type="CodeReviewer",
  model="sonnet",
  description="Review code quality",
  prompt="<reviewer-prompt for code-quality scope>"
)

Task(
  subagent_type="CodeReviewer",
  model="sonnet",
  description="Review test coverage",
  prompt="<reviewer-prompt for test-coverage scope>"
)
```

**Wave 2** — spawn these in the same turn, after docs agents complete:

```
Task(
  subagent_type="CodeReviewer",
  model="sonnet",
  description="Review architecture",
  prompt="<reviewer-prompt for architecture scope>"
)

Task(
  subagent_type="CodeReviewer",
  model="sonnet",
  description="Review security",
  prompt="<reviewer-prompt for security scope>"
)

Task(
  subagent_type="CodeReviewer",
  model="sonnet",
  description="Review performance",
  prompt="<reviewer-prompt for performance scope>"
)
```

Each reviewer subagent receives only its filtered context:

1. **The changes** (diff + full file context)
2. **Project context** (CLAUDE.md, architecture docs, detected stack info)
3. **Scope-filtered KB** (only the domains mapped to this scope in `kb/_index.yaml`)
4. **Scope-filtered live docs** (only the sections relevant to this scope — omitted entirely for Wave 1 reviewers)
5. **Its scope-specific instructions** (from `references/agents/<scope>-reviewer.md`)
6. **Previous review** (if this is a re-review, include the last REVIEW-v{N}.md)

**Reviewer prompt template** (fill in per scope):
```
You are a specialized [scope] code reviewer.

## Your Instructions
[Contents of references/agents/<scope>-reviewer.md]

## Project Context
[CLAUDE.md summary, detected stack, architecture info]

## Knowledge Base (non-volatile rules and patterns)
[KB quick-references and concepts for this scope's mapped domains.
These are curated, project-specific rules — treat them as authoritative.]

## Live Documentation (current API specifics)
[Output from DocsExplorer/FuryDocsExplorer agents.
Use for version-specific behavior, deprecations, and current best practices.]

## Pre-Commit Hook Results (programmatic checks)
[Results from Step 1.5 — only hooks relevant to this scope.
Mandatory hook failures are pre-classified as blocking.
Optional hook violations need your analysis: is the violation valid 
(suggest fix) or a valid exception (suggest suppression annotation)?
Do NOT duplicate findings already caught by hooks — reference the hook 
result and add your analysis if needed.]

## Changes to Review
[The diff and file contents]

## Previous Review (if re-review)
[Contents of last REVIEW-v{N}.md, filtered to this scope's section]

## Output Format — Intermediate Structure

Your output is an INTERMEDIATE format — Step 7 will assemble it into 
the final review template. Return your analysis in EXACTLY these 
labeled sections. Use your scope prefix ({SCOPE_PREFIX}) on all IDs.

Scope prefixes: ARCH (architecture), SEC (security), CQ (code-quality), 
TEST (test-coverage), PERF (performance).

### Findings

> **[{SCOPE_PREFIX}-B-001]** {Short title}
> - **Scope**: {scope name}
> - **File**: `{path/to/file.java:L10-L25}`
> - **Rule**: {specific rule or principle violated}
> - **Source**: {KB | Live Docs | Project Rules — where the rule comes from}
> - **Problem**: {clear description}
> - **Fix**: {concrete, actionable suggestion}
> - **Confidence**: {high | medium} — {brief justification if medium}

[Repeat for warnings ({SCOPE_PREFIX}-W-001) and suggestions 
({SCOPE_PREFIX}-S-001). Omit empty categories entirely.]

### Tech Debt

> **[{SCOPE_PREFIX}-TD-001]** {Short title}
> - **Rule violated**: {specific rule with docs citation}
> - **In reviewed changes**: `{file:line}` — {what the code does}
> - **Pre-existing in codebase**: {count} files — {example file:line}
> - **Why it matters**: {explanation}

### Cross-Scope Observations

> **[{SCOPE_PREFIX}-CS-001]** {Short title}
> - **Target scope**: {which other scope should look at this}
> - **File**: `{file:line}`
> - **Observation**: {what you noticed and why it belongs to another scope}

### Positive Findings
- {one-liner, max 2 items}

### Scope Analysis
{Your detailed analysis narrative for the Scope Reports section of the 
final review. This is where you explain your reasoning, describe the 
patterns you found, and provide context. Do NOT include Cross-Scope 
Observations here — they belong in the section above.}

If there are no issues in a category, omit that category entirely.
If everything looks good, say so plainly. Do not invent problems.

IMPORTANT — Line number verification: Before including any file:line 
reference in your output, re-read that specific line range to confirm 
the code at that location matches your description. If you're citing 
from memory, re-read the relevant section. Incorrect line numbers 
undermine the entire review's credibility.
```

---

## Step 6: Conciliation (Re-reviews Only)

This step runs only when a previous review version exists (REVIEW-v{N-1}.md).

### 6a. Parallel review pair

Spawn both reviewers in the same turn:

```
Task(
  subagent_type="CodeReviewer",
  model="sonnet",
  description="Full re-review (fresh perspective)",
  prompt="
    You are doing a FULL re-review. Run the complete review pipeline (steps 4-5) 
    with a fresh perspective, as if no previous review existed. This catches issues 
    that might have been missed or new issues introduced by fixes.
    
    {full reviewer prompt with changes, KB, docs, project context}
  "
)

Task(
  subagent_type="CodeReviewer",
  model="sonnet",
  description="Delta review (changes since v{N-1})",
  prompt="
    You are doing a DELTA review. Focus specifically on what changed since the last review:
    - What blocking issues from v{N-1} were addressed?
    - What new code was introduced since v{N-1}?
    - Are there any regressions — issues that were fine in v{N-1} but broken now?
    
    Previous review: {contents of REVIEW-v{N-1}.md}
    {delta changes, KB, docs, project context}
  "
)
```

### 6b. Conciliation

After both complete, spawn the conciliator:

```
Task(
  subagent_type="CodeReviewer",
  model="sonnet",
  description="Conciliate full vs delta review",
  prompt="
    Read and follow: references/agents/conciliator.md
    
    Full reviewer findings: {full_reviewer_output}
    Delta reviewer findings: {delta_reviewer_output}
    
    {conciliation instructions from conciliator.md}
  "
)
```

The conciliator:

1. Compares findings from the full reviewer and the delta reviewer
2. Identifies **agreements** (same finding from both — high confidence)
3. Identifies **contradictions** (one says it's fine, the other flags it)
4. For contradictions, attempts autonomous resolution by:
   - Re-reading the actual code to determine which reviewer is correct
   - Checking against the documentation fetched in the research wave
   - Applying the principle of least surprise
5. If a contradiction cannot be resolved confidently, escalate to the user with both perspectives and a recommendation
6. Produces the final merged review

---

## Step 7: Synthesize & Output

### Version detection

Check for existing reviews:
```bash
ls .code-review/REVIEW-v*.md 2>/dev/null | sort -V | tail -1
```

If previous versions exist, increment. Otherwise, start at v1.

### Section Ownership Contract

Each section of the final review has a designated source. Step 7 assembles the review by pulling from these sources — it does not reconstruct the template from memory.

| Template Section | Source | Notes |
|---|---|---|
| Metadata table | Step 1 (gather) + verdict (computed below) | Stack, scopes, source from gather; verdict based on finding severity |
| Programmatic Checks | Step 1.5 (pre-commit) | Format raw results into template structure. If hooks couldn't run, write the section with status explanation — do NOT omit |
| Summary | Synthesis (written after all findings collected) | One paragraph: what changed, areas affected, overall assessment |
| Findings (B/W/S) | Step 5 reviewers → `### Findings` sections | Merge from all scopes, renumber sequentially |
| Scope Reports | Step 5 reviewers → `### Scope Analysis` sections | Include analysis only — NOT Cross-Scope Observations |
| Tech Debt References | Step 5 reviewers → `### Tech Debt` sections + Step 0 registry | Merge, deduplicate, cross-reference registry |
| Cross-Scope Observations | Step 5 reviewers → `### Cross-Scope Observations` sections | Extract, deduplicate, assign CS-xxx IDs, format as blockquotes |
| Positive Findings | Step 5 reviewers → `### Positive Findings` sections | Collect across scopes, pick 1-3 best |
| Conciliation Notes | Step 6 (conciliator) | Only for re-reviews (v2+) |
| Review Metadata | Synthesis | Agent list, file count, doc sources |

The critical insight: **reviewer output is an intermediate format** with scope-prefixed IDs (ARCH-B-001, SEC-TD-001, etc.). Step 7 extracts labeled sections and assembles them into the template structure, renumbering IDs sequentially.

### Assemble the review file

Build the review file section by section using the template at `references/review-template.md`. For each section:

1. **Metadata table**: Fill from Step 1 gather results. Compute verdict based on finding severity (any Blocking → "request changes", only Warnings → "needs discussion", only Suggestions → "approve").

2. **Programmatic Checks**: Take Step 1.5 results and format into the template structure:
   - If hooks ran: populate the Mandatory Hooks table and Checkstyle/PMD subsections with actual results
   - If hooks couldn't run: write the section header with a status note (e.g., "Pre-commit hooks could not execute: {reason}. Manual verification recommended.")
   - **NEVER omit this section** — it is mandatory even when hooks are unavailable

3. **Summary**: Write one paragraph covering what changed, areas affected, and overall assessment. For re-reviews, include delta from previous version.

4. **Findings**: Collect all `### Findings` sections from reviewer outputs. Strip scope prefixes and renumber sequentially: B-001, B-002... W-001... S-001... regardless of which reviewer produced them. Order blocking issues by severity, then warnings, then suggestions. Format each as a blockquote per the template.

5. **Scope Reports**: Include each reviewer's `### Scope Analysis` section under a `### {Scope Name} Review` heading. Do NOT include their `### Cross-Scope Observations` here — those are extracted separately in step 7 below.

6. **Tech Debt References**: Merge `### Tech Debt` sections from all reviewers. Deduplicate (same pattern from multiple scopes = one TD entry with multiple scope citations). Cross-reference with Step 0 registry data. Renumber as TD-001, TD-002... Format as blockquotes per the template. Include registry link for each.

7. **Cross-Scope Observations**: Extract all `### Cross-Scope Observations` sections from reviewer outputs. Deduplicate (multiple reviewers flagging the same file:line = one CS entry citing all observers). Assign sequential CS-xxx IDs. Format as blockquotes per the template:
   ```
   > **[CS-001]** {title}
   > - **Scopes involved**: {list of relevant scopes}
   > - **Observed by**: {which reviewer(s) flagged this}
   > - **File**: `{file:line}`
   > - **Observation**: {what was noticed and why it crosses scope boundaries}
   ```
   If no cross-scope observations were produced, omit the section.

   **Dual-aspect issues**: Some issues are genuinely multi-faceted — e.g., 
   unbounded recursion is both a security concern (DoS vector) and a 
   performance concern. When a finding (B/W/S) and a CS observation cover 
   the *same code location* but address *different aspects*, this is 
   allowed — it is not duplication. The finding addresses the in-scope 
   aspect; the CS observation flags the out-of-scope aspect for the 
   relevant reviewer. However, if a finding and a CS observation describe 
   the *same aspect* of the same issue, remove the CS entry (the finding 
   takes precedence).

8. **Positive Findings**: Collect from all reviewer outputs, pick 1-3 best. One sentence each, no padding.

9. **Conciliation Notes**: Include only for re-reviews (v2+), populated from Step 6 output.

10. **Review Metadata**: List agents that ran, files analyzed, docs consulted, previous version path.

Ensure `.code-review/` is in `.gitignore` (add it if not present, with a comment).

### Structural Validation

Before writing the file, verify the assembled review against this checklist. If any item fails, fix it before proceeding.

Required sections (in order):
- [ ] Metadata table with all 6 fields filled (Version, Date, Stack, Scopes Reviewed, Changes Source, Verdict)
- [ ] `## Programmatic Checks` section present (even if hooks didn't run)
- [ ] `## Summary` with at least one paragraph
- [ ] `## Findings` with `### Blocking Issues`, `### Warnings`, `### Suggestions` subsections
- [ ] All findings use `> **[X-NNN]**` blockquote format with sequential numbering
- [ ] `## Scope Reports` with one `### {Name} Review` per reviewed scope
- [ ] Scope Reports do NOT contain Cross-Scope Observations (those are in the merged section only)
- [ ] `## Tech Debt References` present if any TD items found (omitted only if none)
- [ ] All TD items use `> **[TD-NNN]**` blockquote format with sequential numbering
- [ ] `## Cross-Scope Observations` present if any CS items found (omitted only if none)
- [ ] All CS items use `> **[CS-NNN]**` blockquote format with sequential numbering
- [ ] `## Positive Findings` present
- [ ] `## Review Metadata` present
- [ ] No duplicate findings (same file:line + same aspect appearing in both Findings and Scope Reports or Findings and Cross-Scope Observations). Dual-aspect overlap is allowed: a finding and CS entry may reference the same code if they address different concerns (e.g., S-001 covers security/DoS, CS-001 covers performance impact).

### Tech Debt Registry Sync

After writing the review file, sync `.code-review/TECH_DEBT.md`:

1. **New debt found**: For each TD-xxx in the review that isn't already in the registry, append a new entry using the registry format (see `.code-review/TECH_DEBT.md` header for the template). Set status to `open`, set first-detected to this review.
2. **Known debt updated**: For entries already in the registry with status `open` or `ticket-created`, update `Occurrences` count and `Last reviewed` date if the reviewer found different numbers.
3. **Resolved debt**: If the registry has entries with status `open` and the reviewer found 0 occurrences of that pattern, update status to `resolved`.
4. **Create if missing**: If `.code-review/TECH_DEBT.md` doesn't exist and any TD items were found, create the file with the standard header and the new entries.

### Summary to user

After writing the review file, present a concise summary:
- Overall verdict: **approve** / **request changes** / **needs discussion**
- Count of blocking issues, warnings, suggestions, tech debt references
- Path to the full review file
- Tech debt registry changes (new entries added, counts updated)
- If re-review: what improved since last version, what's new

---

## Extending the Skill

### Adding a New Review Scope

1. Create `references/agents/<scope-name>-reviewer.md` with the reviewer's instructions
2. Add the scope to the relevant stack(s) in `references/stacks-registry.json`
3. Map the scope to KB domains in `kb/_index.yaml` under `scope_mappings`
4. The pipeline will automatically pick it up for scope selection

A reviewer agent file should contain:
- What the scope covers and why it matters
- Specific rules and patterns to check
- Stack-specific guidance (if applicable)
- Examples of good/bad patterns
- The severity classification criteria for this scope

### Adding a New KB Domain

1. Create a directory under `kb/` (e.g., `kb/new-domain/`)
2. Add `index.md` using `kb/_templates/concept.md.template` structure — domain overview and learning path
3. Add `quick-reference.md` using `kb/_templates/quick-reference.md.template` — decision matrices and red flags
4. Add concept files in `concepts/` (<150 lines each) — one per principle or rule
5. Add pattern files in `patterns/` (<200 lines each) — one per implementation pattern
6. Register the domain in `kb/_index.yaml` under `domains`
7. Map it to review scopes under `scope_mappings`

**What belongs in KB vs. live docs:**
- **KB**: Architectural principles, coding conventions, security rules, framework patterns that change rarely. The "why" behind decisions.
- **Live docs**: Current API versions, SDK methods, deprecation notices, changelog items. The "what" that changes with releases.

### Adding a New Stack

1. Add a stack entry in `references/stacks-registry.json` with indicators, docsSources, kbDomains, and docsAgents
2. Create corresponding KB domains under `kb/`
3. If the stack needs specialized docs agents, create them in `.claude/agents/` following the DocsExplorer/FuryDocsExplorer pattern

---

## Behavioral Rules

- **Be critical, not cruel.** The goal is to catch real issues, not to demonstrate thoroughness.
- **Be specific.** Always reference exact file paths, line numbers, and rule names.
- **Be proportional.** A typo is a suggestion. An architecture violation is blocking.
- **Verify runtime impact before classifying as Blocking.** A finding is Blocking only if it causes runtime failure, data loss, security vulnerability, or breaks an existing contract. Before classifying anything as Blocking, verify: (1) the code path is actually exercised — grep for callers/injectors, (2) it's not a placeholder or in-progress interface that nothing depends on yet, (3) it produces observable harm, not just theoretical impurity. If unsure, classify as Warning with a confidence note.
- **Verify before citing.** If unsure whether a convention exists, check the docs and project files first.
- **Don't review generated code, build artifacts, or lock files.**
- **Respect the user's time.** If the code is clean, say so. Don't manufacture findings.
- **When running as part of an agent pipeline**, return structured output that the calling agent can act on. Don't prompt the user unless the conciliator explicitly escalates a conflict.
