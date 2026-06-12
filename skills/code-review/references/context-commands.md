# Context Management Commands

The code-review skill organizes reviews into **contexts** — named workspaces that group all review iterations for a feature, fix, or topic. Each context has its own directory under `.code-review/{YYYYMMDD}_{name}/` and tracks the full iteration history.

## Directory Layout

```
.code-review/
  registry.json                              ← global index of all contexts
  config.json                                ← optional project config
  TECH_DEBT.md                               ← project-wide tech debt registry
  20260611_adds-new-things/
    context.json                             ← full iteration history
    REVIEW-v1.md
    REVIEW-v2.md
  20260601_fix-auth-bug/
    context.json
    REVIEW-v1.md
  .archived/
    20260501_old-feature/
      context.json
      REVIEW-v1.md
```

## Project Config

`.code-review/config.json` — optional. All keys default to `false`/off if absent.

```json
{
  "auto": true
}
```

- **`auto`** — when `true`, `/code-review:new` skips confirmation prompts: uses the suggested name and proceeds directly to the review. Useful for teams that prefer uninterrupted flow. Equivalent to always passing `--auto` in the pipeline.

---

## Subcommand Reference

### `/code-review:new [source] [name]`

Creates a new review context and sets it as current. The context becomes the active workspace — all subsequent reviews are saved under its directory.

**Flow (interactive — default):**
1. Determine source from the argument or the current review trigger (e.g., `PR #123`, `git diff`)
2. Infer branch from source (PR ref → `gh pr view` for headRefName; local → `git rev-parse --abbrev-ref HEAD`)
3. Derive name suggestion from branch (strips `feature/`, `fix/`, `chore/`, etc.; normalizes to lowercase + hyphens)
4. If on `main`/`master`/`develop`/detached HEAD — no suggestion, ask user to provide a name
5. Present: *"Suggested context name: `{name}`. Accept or provide a different name?"*
6. Run `context.py new {source} --name {chosen_name}`
7. Confirm: *"Context `{id}` created. Reviews will save to `.code-review/{id}/`. Continue to review?"*

**Flow (`--auto` or `config.json auto: true`):**
Steps 5 and 7 are skipped — suggested name is used directly and review starts immediately.

**Name rules:**
- Lowercase alphanumeric + hyphens only (`[a-z0-9-]+`)
- Spaces, underscores, and uppercase are normalized automatically
- If the normalized name is empty, an error is returned
- If the ID already exists on the same date, `-2`, `-3`, etc. are appended

**Examples:**
```
/code-review:new
# → infers source from context, suggests name from branch

/code-review:new adds-shopify-import
# → creates context with that name, infers source from branch/trigger

/code-review:new PR #456 payments-redesign
# → source=PR #456, name=payments-redesign
```

---

### `/code-review:list`

Lists all active review contexts (archived contexts are hidden).

**Output:**
```
Active review contexts:

  ● 20260611_adds-new-things       [current]   v2   feature/import   Adds product import pipeline…
    20260601_fix-auth-bug                       v1   fix/auth-null    Fixes null pointer in auth flow…
```

`●` marks the current context. If no active contexts exist, says so and suggests `/code-review:new`.

Reads from `registry.json` — does not load individual context.json files.

---

### `/code-review:status`

Shows full detail for the current context, including iteration history.

**Output:**
```
Current context: 20260611_adds-new-things
  Name:     adds-new-things
  Status:   active
  Branch:   feature/new-feature
  Created:  2026-06-11 10:00
  Reviews:  2 iterations (latest: v2)
  Latest:   2026-06-11 14:30 — request changes — B:3 W:2 S:1
  Summary:  Adds product import pipeline from Shopify GraphQL API
  Path:     .code-review/20260611_adds-new-things/

  Iterations:
    v1 — 2026-06-11 11:00 — request changes — PR #123 (feature/new-feature)
    v2 — 2026-06-11 14:30 — request changes — PR #123 (feature/new-feature)
         Added: ProductImportWorker, ShopifyGateway  Modified: ProductService
```

If no current context, says so and suggests `/code-review:new` or `/code-review:list`.

---

### `/code-review:switch [id]`

Sets a different context as current.

**With ID:**
```
/code-review:switch 20260601_fix-auth-bug
→ Switched to context 20260601_fix-auth-bug
```

**Without ID:**
The skill presents a select list of active contexts (current highlighted at top). User picks one.

---

### `/code-review:archive [id]`

Archives a context: hides it from the active list while preserving all files. Moves the directory to `.code-review/.archived/`.

**With ID:**
```
/code-review:archive 20260611_adds-new-things
→ Context 20260611_adds-new-things archived. Files preserved at .code-review/.archived/20260611_adds-new-things/
→ Active context is now: 20260601_fix-auth-bug
```

**Without ID:** presents a select list of active contexts.

If the archived context was current, the next most-recently-reviewed active context becomes current. If no active contexts remain, current is set to null.

---

### `/code-review:delete [id]`

Permanently moves the context directory to the system trash.

**Always confirms before deleting:**
```
This will move .code-review/20260611_adds-new-things/ to trash,
including all review files (REVIEW-v1.md, REVIEW-v2.md, context.json).
This cannot be undone easily. Confirm? (yes/no)
```

On confirmation, calls `context.py delete {id}` which:
1. Moves the directory to system trash (`/usr/bin/trash` → `osascript` fallback)
2. Removes the entry from `registry.json` (only after successful trash)

**If trash fails:** reports the error, no registry changes are made.

---

## Context ID Format

```
{YYYYMMDD}_{name}
```

- Date is the creation date in local time
- Name is lowercase alphanumeric + hyphens
- Collisions on the same date append `-2`, `-3`, etc.

**Examples:** `20260611_adds-new-things`, `20260611_fix-auth-bug`, `20260611_adds-new-things-2`

## Switching Contexts Mid-Review

If you invoke `/code-review:switch` while a review pipeline is in progress, the switch takes effect for the **next** review request. The current pipeline uses the context that was active when it started — context_id is resolved at Step 0 and held for the duration of the pipeline.
