---
name: web-tree
description: "Use when the user runs `/web-tree <url>`. Extracts and displays a documentation website's content tree (navigation structure, topic hierarchy, and links). Command-only — not auto-triggered."
version: 1.0.0
---

# Web Tree — Documentation Site Structure Extractor

Extract and display the navigation tree of a documentation website. Given a URL, fetch the page, parse its nav/sidebar/TOC structure, and output a hierarchical content tree with links.

## Usage

```
/web-tree <url> [options]
```

### Arguments

- `<url>` (required): The webpage URL to analyze
- `--max-nodes <N>` (optional): Threshold for collapsing large trees in conversation output. Default: 50
- `--max-depth <N>` (optional): Maximum tree depth to display. No limit if omitted.
- `--save-md` (optional flag): Also save a markdown version of the tree alongside the JSON file.
- `--output-dir <path>` (optional): Directory for output files. Default: `<cwd>/web-tree-output/`
- `--filename <name>` (optional): Base filename without extension. Default: derived from URL domain+path.

## Instructions

Follow these steps precisely. Use `WebFetch` for fetching and standard file tools for output.

### Step 1 — Parse Arguments

Parse the arguments from the user's command. Extract:
- `url` (required — error if missing)
- `max_nodes` (default: 50)
- `max_depth` (default: null — no limit)
- `save_md` (default: false)
- `output_dir` (default: `<cwd>/web-tree-output/`)
- `filename` (default: derived from URL)

**Filename derivation** when `--filename` is not provided:
1. Take hostname + path from the URL
2. Remove protocol (`https://`), query params, and fragments
3. Remove trailing slashes
4. Replace `/` with `_`
5. Truncate to max 100 characters if needed
6. Examples:
   - `https://help.obsidian.md/` → `help.obsidian.md`
   - `https://developer.myscript.com/docs/interactive-ink/4.3/concepts/ink-interpretation/` → `developer.myscript.com_docs_interactive-ink_4.3_concepts_ink-interpretation`

### Step 2 — Fetch the Page

Use `WebFetch` with this prompt to extract navigation structure:

```
Extract ALL navigation elements from this page. I need:

1. The complete sidebar/navigation menu with FULL hierarchy preserved (parent-child nesting)
2. For EVERY nav item: the exact link text AND the exact href/URL (preserve relative URLs as-is)
3. The page title and a one-sentence description of what this site/section covers
4. Any breadcrumb trail showing the current page's position in the hierarchy
5. If there are collapsible/expandable sections, list ALL items including collapsed ones

Format the navigation as a nested list where indentation shows hierarchy:
- Top Level Item [url]
  - Child Item [url]
    - Grandchild [url]
  - Another Child [url]
- Another Top Level [url]

For items that are category headers with no link, write [no-link].
For items that are anchor links on the current page, include the full #anchor URL.

IMPORTANT: Include EVERY navigation item. Do not summarize or skip items. Preserve the EXACT link text and URL for each item.
```

**If the first fetch returns no recognizable nav structure**, try a second fetch with this prompt:

```
This page may have dynamic navigation. Look for ANY of these:
1. A sidebar, left nav, or table of contents
2. A hamburger menu or mobile nav
3. An in-page table of contents with links
4. Heading hierarchy (h1-h6) that could serve as a content tree

Also check: does this page reference a sitemap? If so, what is the sitemap URL?

List everything you find as a nested hierarchy with links.
```

**Sitemap fallback**: If no nav structure is found after two fetches, try fetching `<base_url>/sitemap.xml` and parse the URL list into a tree based on URL path segments.

### Step 3 — Identify Site Context

From the fetched content, determine:
- **Site name**: The name of the documentation site
- **Domain**: The hostname
- **About**: One-sentence description of the site's purpose
- **Is root page?**: Whether the URL is the root/index page or a sub-page
- **Base URL**: For resolving relative links (protocol + hostname)

### Step 4 — Build the Navigation Tree

Parse the extracted navigation into a tree data structure. For each node:

```json
{
  "title": "Item text",
  "type": "page | section | folder",
  "url": "https://absolute-url.com/path" or null,
  "children": []
}
```

**Type classification:**
- `"page"` — Links to a different page (different path, no anchor-only)
- `"section"` — Anchor link (`#something`) on the current page
- `"folder"` — Category/group header with no URL (or URL identical to a child)

**URL resolution:**
- Convert all relative URLs to absolute using the base URL
- Normalize URLs: lowercase hostname, remove trailing slashes, remove default ports
- Maintain a **visited-URLs set** to detect and skip duplicates
- Strip fragments and query params when comparing for uniqueness (but preserve them in the output URL for sections)

**Depth limiting:** If `--max-depth` is set, truncate the tree at that depth. Nodes at the max depth that would have children should be typed as `"folder"` with an empty `children` array.

**Circular reference protection:**
- Track all URLs seen; skip any URL already processed
- Self-referencing nav items (current page in its own tree) should be marked but not re-fetched
- Hard limit: extract from the navigation HTML of the fetched page(s) only — do NOT crawl the entire site

### Step 5 — Determine Scope

- If the URL is the root/homepage → `scope: "full"`, `current_page: null`
- If the URL is a sub-page → `scope: "partial"`, `current_page: "<the URL>"`, and mark the matching node in the tree with `← current page` in the markdown output

### Step 6 — Count Total Nodes

Count every node in the tree (all types, all depths). Store as `total_nodes`.

### Step 7 — Save JSON Output

Create the output directory if it doesn't exist. Determine the output file path: `<output_dir>/<filename>.json`.

**If the file does NOT exist**, create it:

```json
{
  "site": "<site name>",
  "url": "<original URL>",
  "about": "<one-sentence description>",
  "scope": "full | partial",
  "current_page": null | "<url>",
  "total_nodes": <count>,
  "created_at": "<ISO 8601 timestamp>",
  "updated_at": "<ISO 8601 timestamp>",
  "tree": [ ... ]
}
```

**If the file ALREADY exists**, perform a **merge**:

1. Load the existing JSON
2. Match nodes by URL (for `page`/`section` types) or by title + position (for `folder` types)
3. Merge strategy:
   - Nodes in both → keep newer version (update title if changed, preserve URL)
   - Nodes only in new extraction → add to tree
   - Nodes only in existing file → keep them (may be from a different page's nav)
4. Update `about`, `total_nodes`, and set `updated_at` to current timestamp
5. Inform the user that the file was merged, showing counts: nodes added / updated / kept

**Also create/update the changelog file** at `<output_dir>/<filename>.changelog.json`:

On **first creation**, write:
```json
[
  {
    "timestamp": "<ISO 8601>",
    "action": "created",
    "source_url": "<the URL fetched>",
    "nodes_added": <total>,
    "nodes_updated": 0,
    "nodes_removed": 0,
    "diff": [
      { "type": "added", "path": "<breadcrumb path>", "node": { "title": "...", "type": "...", "url": "..." } }
    ]
  }
]
```

On **merge**, append an entry:
```json
{
  "timestamp": "<ISO 8601>",
  "action": "merged",
  "source_url": "<the URL fetched>",
  "nodes_added": <count>,
  "nodes_updated": <count>,
  "nodes_removed": <count>,
  "diff": [
    { "type": "added", "path": "Section > New Page", "node": { ... } },
    { "type": "updated", "path": "Section > Changed Page", "before": { ... }, "after": { ... } },
    { "type": "removed", "path": "Section > Old Page", "node": { ... } }
  ]
}
```

The `path` field uses breadcrumb-style notation: `"Parent > Child > Grandchild"`.

### Step 8 — Save Markdown (if --save-md)

If `--save-md` is set, save the **full tree** (not collapsed) as `<output_dir>/<filename>.md`:

```markdown
# <Site Name>

**URL:** <url>
**About:** <description>
**Scope:** <full | partial>
**Total pages:** <count>

## Content Tree

- Getting started [folder]
  - Installation [page] https://...
  - Quick start [page] https://...
- API Reference [folder]
  - Authentication [section] #auth
```

This file always contains the complete tree regardless of `--max-nodes`.

### Step 9 — Display in Conversation

**If total_nodes ≤ max_nodes** (small tree), display the full tree:

```markdown
## Site: <Name>
**URL:** <url>
**About:** <description>
**Scope:** Full site | Section: "<section name>"

### Content Tree
- Getting started [folder]
  - Installation [page] https://...
  - Quick start [page] https://...
- API Reference [folder] ← current page
  - Authentication [section] #auth
  - Endpoints [section] #endpoints

> Saved to `<path>.json`
```

**If total_nodes > max_nodes** (large tree), show top-level with counts:

```markdown
## Site: <Name>
**URL:** <url>
**Scope:** Full site (<total> pages)

### Content Tree (top-level)
1. Getting started [folder] (6 pages)
2. User interface [folder] (12 pages)
3. API Reference [folder] (47 pages)
4. Plugins [folder] (62 pages)

> Saved to `<path>.json` (full tree)

Which sections would you like me to expand?
```

If `--max-depth` was used, mention it: `"Tree limited to depth <N>."`

Always mention the saved file paths at the end.

### Edge Cases

1. **No nav found**: Fall back to in-page heading hierarchy (h1-h6). If that also fails, suggest trying the homepage URL or `<domain>/sitemap.xml`.
2. **SPA / JS-rendered nav**: The sitemap.xml fallback (Step 2) handles this.
3. **Multiple nav elements on page**: Pick the richest one (most items, deepest nesting).
4. **Non-documentation sites**: Attempt extraction but note in the output that the site may not have structured navigation.
5. **Very long trees from sitemap**: Group by URL path segments to create a folder hierarchy.

### Output Files Summary

Each run produces:
```
<output-dir>/
  ├── <filename>.json              (always — full tree + metadata)
  ├── <filename>.md                (only if --save-md)
  └── <filename>.changelog.json    (always — append-only history)
```
