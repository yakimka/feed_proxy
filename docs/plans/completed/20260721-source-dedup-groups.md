# Source Dedup Groups with Configurable Uniqueness Key

## Overview
Enable linking multiple sources into a shared **dedup group** with a configurable **uniqueness key**, so that the same article published by different sites (e.g. `migijon.com` and `mioviedo.com`) — same title/content but different guid — is delivered to a channel only once.

Problem it solves: today deduplication is bound to `(source.id, receiver_type)` + `post.post_id` (guid). Two different sites have different `source.id` and different guids, so cross-source duplicates are never filtered.

Key benefits:
- Cross-source dedup within a group via a shared namespace.
- Configurable identity field (e.g. `title`) **in addition to** guid — not replacing it.
- Full backward compatibility: sources without the new fields behave exactly as before.

How it integrates: the change touches only the dedup path (`logic.parse_message_batches_from_posts` + `storage`). Metrics, receivers, fetchers, parsers are untouched.

## Context (from discovery)
- Files/components involved:
  - `feed_proxy/entities.py` — `Source` dataclass.
  - `feed_proxy/utils/text.py` — text helpers.
  - `feed_proxy/logic.py` — `parse_message_batches_from_posts` (dedup logic, currently lines 81–122; key built at line 85).
  - `feed_proxy/storage.py` — `PostStorage` protocol + `MemoryPostStorage` + `SqlitePostStorage` (table `posts(key, post_id)`).
  - `feed_proxy/test.py` — `ObjectMother.source()` (needs new kwargs for tests).
- Related patterns found:
  - Dedup key `(source.id, stream.receiver_type)` used **only** in `logic.py:85` (+ storage). `cli/run.py:63` is a **metrics** key (leave as-is → per-source metrics preserved). `handlers/__init__.py:156` is unrelated.
  - Storage stores `(str(key), post_id)` rows; `post_id` column is effectively an "identity" string column.
  - Tests: pytest, `async def test_...`, AAA, `ObjectMother` (`mother` fixture), `make_post` factory fixture (in `tests/test_logic.py`), parametrized `make_sut` for both storages (in `tests/test_post_storage.py`).
- Dependencies identified: none new. Pure-stdlib normalization.

## Development Approach
- **Testing approach**: **Regular** (implement code first, then tests — within each task).
- Complete each task fully before moving to the next.
- Make small, focused changes.
- **Every task MUST include new/updated tests** for its code changes (success + edge cases), listed as separate checklist items.
- **All tests must pass before starting the next task.**
- Update this plan file if scope changes during implementation.
- Maintain backward compatibility (default field values reproduce current behavior).

## Testing Strategy
- **Unit tests**: required for every task.
- No UI / e2e tests in this project (CLI + library only) — not applicable.
- Test command (via docker devtools): `make test` (runs `pytest --cov` + `pytest --dead-fixtures`).
- Follow existing conventions: `ObjectMother`, `make_post`, parametrized `make_sut` for storage.

## Progress Tracking
- Mark completed items with `[x]` immediately when done.
- Add newly discovered tasks with ➕ prefix.
- Document blockers with ⚠️ prefix.
- Keep plan in sync with actual work.

## Solution Overview
Two orthogonal changes to the dedup path:

1. **Shared namespace**: dedup key becomes `(source.dedup_group or source.id, stream.receiver_type)`. Grouped sources share one "already sent" namespace; ungrouped sources are unchanged.

2. **Multi-identity**: each post yields a *list* of identity strings instead of a single guid:
   - always the bare `post.post_id` (guid) — preserves "already sent this exact post" and survives in-source title edits;
   - plus, when `dedup_key != "post_id"` and the field value is non-empty, `f"{dedup_key}:{normalize_dedup_value(value)}"`.

   A post is considered **already seen if ANY of its identities is present** in storage. When a post is sent, **all** its identities are marked.

The DB schema does not change — the extra `title:<norm>` identity is just another row in the existing `posts.post_id` column. Bare guids stay unprefixed (backward compatible + no collision with a prefixed title identity).

Design decisions & rationale:
- guid is **added to**, not replaced by, the title identity → renaming an article in one source (same guid) is still recognized and not re-sent.
- Prefix identity with the field name (`title:`) so a normalized title cannot collide with someone's bare guid.
- Source priority within a group is intentionally **non-deterministic** ("first fetch wins") — no barrier logic (YAGNI).
- Known accepted limitations (not fixed):
  - If a source renames an article *before* another source first publishes it under the new title, a duplicate may pass.
  - `normalize_dedup_value` only trims/collapses whitespace and case-folds. Titles differing by punctuation, trailing marks, or HTML entities won't match and will be treated as distinct — deliberate, to avoid over-normalization false-merges.
  - `dedup_key` is not validated against the post's fields: a typo (e.g. `"titel"`) makes `getattr(post, dedup_key, "")` return `""` and silently degrades to guid-only dedup with no error. Accepted as YAGNI.

## Technical Details
- `Source` gains: `dedup_group: str | None = None`, `dedup_key: str = "post_id"`.
- `normalize_dedup_value(value) -> " ".join(value.split()).casefold()` (trim + collapse whitespace + case-fold, Unicode-aware).
- `post_identities(post, dedup_key) -> list[str]`:
  - `ids = [post.post_id]`
  - if `dedup_key != "post_id"`: `raw = getattr(post, dedup_key, "") or ""`; `norm = normalize_dedup_value(raw)`; **if `norm`** (guard on the *normalized* value, not raw): append `f"{dedup_key}:{norm}"`.
  - Guarding on `norm` (not `raw`) is required: a whitespace-only title (`"   "`) is truthy but normalizes to `""`; without this guard it would produce the identity `"title:"` and collide all empty-ish titles into false duplicates.
- Storage gains `any_processed(key, post_ids: list[str]) -> bool` (empty list → `False`):
  - Memory: `bool(self._data.get(str(key), set()) & set(post_ids))`.
  - Sqlite: `SELECT 1 FROM posts WHERE key = ? AND post_id IN (<placeholders>) LIMIT 1`.
- `parse_message_batches_from_posts`:
  - `group = source.dedup_group or source.id`; `key = (group, stream.receiver_type)`.
  - first-run branch: mark `flatten(post_identities(p, source.dedup_key) for p in posts)`.
  - novelty filter: keep post if `not await storage.any_processed(key, post_identities(post, source.dedup_key))`.
  - `to_mark`: extend with all identities of each sent post (flatten), not just `post_id`.
  - `Message.post_id` stays `post.post_id` (outbox identity unchanged).
- `is_post_processed` is intentionally **retained** in the `PostStorage` Protocol even though production code stops calling it after Task 5 — it stays under contract test in `tests/test_post_storage.py`. (Noted so a reviewer doesn't flag it as dead code.)

## What Goes Where
- **Implementation Steps** (checkboxes): all code + tests below live in this repo.
- **Post-Completion** (no checkboxes): production `sources.prod.yaml` wiring + observed behavior after deploy.

## Implementation Steps

### Task 1: Add `dedup_group` / `dedup_key` fields to `Source`

**Files:**
- Modify: `feed_proxy/entities.py`
- Modify: `feed_proxy/test.py`
- Modify: `tests/test_configuration_loader.py`

- [x] add `dedup_group: str | None = None` and `dedup_key: str = "post_id"` to `Source` (kw_only dataclass) with defaults
- [x] extend `ObjectMother.source(...)` with `dedup_group: str | None = None` and `dedup_key: str = "post_id"` kwargs, pass through to `Source`
- [x] write test: config loader parses a source with `dedup_group` + `dedup_key` set (dacite `from_dict`)
- [x] write test: config loader defaults — source without the fields gets `dedup_group is None` and `dedup_key == "post_id"`
- [x] run tests - must pass before next task

### Task 2: Add `normalize_dedup_value` helper

**Files:**
- Modify: `feed_proxy/utils/text.py`
- Create: `tests/utils/__init__.py`
- Create: `tests/utils/test_text.py`

- [x] add `def normalize_dedup_value(value: str) -> str: return " ".join(value.split()).casefold()`
- [x] write test: collapses internal whitespace and trims leading/trailing
- [x] write test: case-folds (incl. a Unicode/Cyrillic example)
- [x] write test: empty / whitespace-only string → empty string
- [x] run tests - must pass before next task

### Task 3: Add `post_identities` helper to logic

**Files:**
- Modify: `feed_proxy/logic.py`
- Modify: `tests/test_logic.py`

- [x] add `post_identities(post: Post, dedup_key: str) -> list[str]` per Technical Details (uses `normalize_dedup_value`, guards on the **normalized** value)
- [x] write test: default `dedup_key="post_id"` → `[post.post_id]` only
- [x] write test: `dedup_key="title"` → `[post.post_id, "title:<normalized title>"]`
- [x] write test: `dedup_key="title"` with empty title (`""`) → `[post.post_id]` only
- [x] write test: `dedup_key="title"` with whitespace-only title (`"   "`) → `[post.post_id]` only (no `"title:"` identity)
- [x] run tests - must pass before next task

### Task 4: Add `any_processed` batch method to storage

**Files:**
- Modify: `feed_proxy/storage.py`
- Modify: `tests/test_post_storage.py`

- [x] add `any_processed(self, key, post_ids: list[str]) -> bool` to `PostStorage` Protocol
- [x] implement in `MemoryPostStorage` (set intersection; empty list → `False`)
- [x] implement in `SqlitePostStorage` (`... post_id IN (<placeholders>) LIMIT 1`; empty list → `False` without querying)
- [x] write test (parametrized `make_sut`, both storages): matches when ANY id present
- [x] write test: empty `post_ids` → `False`; different key does not match
- [x] run tests - must pass before next task

### Task 5: Wire group namespace + multi-identity into `parse_message_batches_from_posts`

**Files:**
- Modify: `feed_proxy/logic.py`
- Modify: `tests/test_logic.py`

- [x] compute `group = source.dedup_group or source.id`; `key = (group, stream.receiver_type)`
- [x] first-run branch: mark flattened identities of all posts (via `post_identities`)
- [x] novelty filter: use `await post_storage.any_processed(key, post_identities(post, source.dedup_key))`
- [x] `to_mark`: collect all identities of each sent post (flatten)
- [x] update `StubStorage` in `tests/test_logic.py` (`test_unhandled_processor_exception_aborts_before_marking`, ~line 149) to implement `any_processed` — the novelty filter now calls it *before* the pre-send processor runs, so without this the existing test raises `AttributeError` instead of `RuntimeError`
- [x] write test (a): two sources sharing `dedup_group`, same title / different guid, non-first-run → second is skipped (no batch)
- [x] write test (b): same guid + changed title → skipped (edit-resend protection preserved)
- [x] write test (c): different `dedup_group` values → no cross-filtering
- [x] write test (d): first run of a group → nothing sent, but all identities marked (assert via `any_processed`)
- [x] write test: backward-compat — source with defaults still dedups by guid exactly as before (existing tests still green)
- [x] run tests - must pass before next task

### Task 6: Verify acceptance criteria
- [x] verify Overview requirements: cross-source dedup by title works; guid still protects against edit re-send; ungrouped sources unchanged
- [x] verify edge cases: empty title, first-run marking, empty `post_ids`, distinct groups isolated
- [x] run full suite: `make test`
- [x] run linters/types: `make lint` (pre-commit + mypy)
- [x] verify no unintended change to metrics key in `cli/run.py`

### Task 7: [Final] Update documentation
- [x] document `dedup_group` / `dedup_key` in `README.md` with the `x-dedup` anchor example (below)
- [x] update `CLAUDE.md` only if a new pattern worth recording emerged (no project `CLAUDE.md` exists; no new pattern warranted creating one)
- [x] move this plan to `docs/plans/completed/`

## Post-Completion
*Informational — manual/external actions, no checkboxes.*

**Production wiring** (`sources.prod.yaml`, done by user when ready):
```yaml
x-dedup:
  asturias: &asturias-dedup
    dedup_group: "asturias-news"
    dedup_key: "title"

sources:
  mi-gijon:
    <<: [*rss-feed, *asturias-dedup]
    fetcher_options: { url: "https://migijon.com/feed/" }
    # ...streams...
  mi-oviedo:
    <<: [*rss-feed, *asturias-dedup]
    fetcher_options: { url: "https://mioviedo.com/feed/" }
    # ...streams...
```

**Migration note (initial burst on the first cycle — accepted):** attaching `dedup_group` creates a fresh, empty group key. The first-run guard (`logic.py:86`) protects only the **first** grouped source processed in that cycle — it marks its current posts as processed **without sending**. But the group key is now non-empty, so every **subsequent** source in the same group sees `has_posts(group_key) == True` (not a first run) and immediately sends all of its posts that do **not** overlap the first source's identities. So expect a one-time initial burst from the 2nd+ sources on first deploy of a group, not a silent no-op. This is accepted behavior. (Overlapping/duplicate articles are still correctly deduped — the burst is only the genuinely non-overlapping tail of each additional feed.)

**Manual verification after deploy:**
- Confirm a duplicate article present on both `migijon.com` and `mioviedo.com` is delivered to the channel only once.
- Confirm editing a title on one source does not re-send (guid path).
