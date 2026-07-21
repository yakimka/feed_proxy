# Fix Dedup-Group Initial Burst by Splitting First-Run Scope from Dedup Scope

## Overview
The `dedup_group` feature (see `docs/plans/completed/20260721-source-dedup-groups.md`) has a
first-cycle burst bug. In `feed_proxy/logic.py:parse_message_batches_from_posts`, the "first run"
guard uses `has_posts(key)` where `key = (dedup_group or source.id, receiver_type)`. For a shared
group, only the **first** source processed triggers first-run (marks its posts, sends nothing).
The group key is then non-empty, so every **subsequent** source in the same group is treated as
**not** first-run and immediately sends its entire non-overlapping backlog — observed as a 50–100
message burst in production.

**Root cause:** "first run" is a per-**source** lifecycle fact ("I have never processed this feed
before"), but it was implemented as a side effect of group-namespace **emptiness**. While a group
equaled a single source these coincided; once a group spans N sources they diverge.

**Fix:** split the two concerns into two normalized storage columns so first-run is scoped
per-source while dedup filtering is scoped per-group. Config and public behavior are unchanged;
only storage internals and the logic wiring change.

Key benefits:
- No burst: each source self-seeds silently on its own first cycle.
- Honest, readable schema (two explicit scopes, no sentinel rows / magic strings).
- Ungrouped sources behave exactly as before the feature.

## Context (from discovery)
- Files/components involved:
  - `feed_proxy/storage.py` — `PostStorage` Protocol, `MemoryPostStorage`, `SqlitePostStorage`,
    `create_sqlite_conn` (posts schema). Storage is called **only** from `logic.py`.
  - `feed_proxy/logic.py` — `parse_message_batches_from_posts` (4 storage call sites: lines 98
    `has_posts`, 105 `mark`, 111 `any_processed`, 130 `mark`); `post_identities` helper (unchanged).
    `cli/run.py:131` calls `parse_message_batches_from_posts` with an unchanged signature — no
    change there.
  - `feed_proxy/storage.py` also defines a `Stringable` Protocol used **only** by the storage
    signatures being rewritten — it becomes dead code after the refactor.
  - `feed_proxy/deps.py:61,72` — builds conn + `SqlitePostStorage`; no change needed (just passes
    the connection through).
  - `tests/test_post_storage.py` — parametrized `make_sut` for both storages.
  - `tests/test_logic.py` — `StubStorage`, `mother`/`make_post` fixtures, existing dedup tests.
- Related patterns found:
  - `is_post_processed` is defined in the Protocol + both impls + one contract test, but is
    **dead in production** (no caller outside tests). To be deleted.
  - Every existing logic/storage test seeds via `mark_posts_as_processed(key, [...])` where `key`
    is a stringified tuple. All these calls must migrate to the new signatures.
  - `cli/run.py` metrics key is unrelated to storage and must not change.
- Dependencies identified: none new. Pure stdlib sqlite3.

## Development Approach
- **Testing approach**: **Regular** (implement code first, then tests — within each task).
- Complete each task fully before moving to the next.
- Make small, focused changes.
- **Every task MUST include new/updated tests** for its code changes (success + edge cases),
  listed as separate checklist items.
- **All tests must pass before starting the next task** — except where a task provides partial
  implementation (see Task 1 note): storage unit tests pass in isolation, but the full suite goes
  green only after Task 2 wires `logic.py` to the new signatures.
- Update this plan file if scope changes during implementation.
- No data migration: the production sqlite DB will be deleted manually before deploy (no important
  data; a fresh DB is safe because every source self-seeds silently on its first cycle).

## Testing Strategy
- **Unit tests**: required for every task.
- No UI / e2e tests in this project (CLI + library only) — not applicable.
- Test command (via docker devtools): `make test` (runs `pytest --cov` + `pytest --dead-fixtures`).
- Lint/types: `make lint` (pre-commit + mypy).
- Follow conventions (`~/.claude/CLAUDE.md`): pytest, `@pytest.fixture()`, AAA, `sut`/`make_sut`,
  `ObjectMother` (`mother` fixture), `make_<name>`/`<name>` factory pairs, mock at boundaries.

## Progress Tracking
- Mark completed items with `[x]` immediately when done.
- Add newly discovered tasks with ➕ prefix.
- Document blockers with ⚠️ prefix.
- Keep plan in sync with actual work.

## Solution Overview
Two orthogonal scopes, expressed as two normalized columns on the `posts` table:

1. **Owner scope** `(source_id, receiver_type)` → drives **first-run detection** (`has_posts`).
   Per-source, so each source's first cycle is detected independently → no burst.
2. **Dedup scope** `(dedup_group, receiver_type)` → drives the **novelty filter**
   (`any_processed`). Shared across a group → cross-source dedup still works.

`receiver_type` stays part of **both** scopes so two streams (e.g. telegram + rss) of one
source/group never share a dedup namespace.

For an ungrouped source `dedup_group == source.id`, so both scopes collapse to the same
`(source.id, receiver_type)` — identical to pre-feature behavior.

Design decisions & rationale:
- Normalized columns (not opaque stringified tuples) chosen for a schema that is self-describing
  when read directly — over the sentinel-row alternative, which overloaded the posts table with a
  hidden boolean flag and a magic `__seen__` key.
- No migration code: YAGNI given the DB is disposable and there is no migration framework in the
  project. `create_sqlite_conn` just `CREATE TABLE IF NOT EXISTS` with the new columns.
- `is_post_processed` deleted rather than ported to the new signature — it is production-dead and
  only contract-tested; the refactor is the moment to drop it.

## Technical Details
- **Schema** (`create_sqlite_conn`):
  ```sql
  CREATE TABLE IF NOT EXISTS posts (
      source_id     TEXT NOT NULL,
      dedup_group   TEXT NOT NULL,
      receiver_type TEXT NOT NULL,
      post_id       TEXT NOT NULL
  );
  ```
- **`PostStorage` Protocol** (new signatures; `is_post_processed` removed):
  ```python
  async def has_posts(source_id: str, receiver_type: str) -> bool: ...
  async def any_processed(
      dedup_group: str, receiver_type: str, post_ids: list[str]
  ) -> bool: ...
  async def mark_posts_as_processed(
      source_id: str, dedup_group: str, receiver_type: str, post_ids: list[str]
  ) -> None: ...
  ```
- **`MemoryPostStorage`**: two indexes written together by `mark`:
  - `_owner: set[tuple[str, str]]` keyed `(source_id, receiver_type)` → `has_posts`.
  - `_dedup: dict[tuple[str, str], set[str]]` keyed `(dedup_group, receiver_type)` → `any_processed`.
  - `any_processed` with empty `post_ids` → `False` (no lookup).
- **`SqlitePostStorage`**:
  - `has_posts`: `SELECT 1 FROM posts WHERE source_id = ? AND receiver_type = ? LIMIT 1`.
  - `any_processed`: empty list → `False` without querying; else
    `SELECT 1 FROM posts WHERE dedup_group = ? AND receiver_type = ? AND post_id IN (<ph>) LIMIT 1`.
  - `mark_posts_as_processed`: `executemany` INSERT of
    `(source_id, dedup_group, receiver_type, post_id)` rows.
- **`logic.parse_message_batches_from_posts`**:
  ```python
  sid = source.id
  group = source.dedup_group or source.id
  recv = stream.receiver_type

  if not await post_storage.has_posts(sid, recv):  # per-source first run
      all_identities = [i for p in posts for i in post_identities(p, source.dedup_key)]
      await post_storage.mark_posts_as_processed(sid, group, recv, all_identities)
      return message_batches

  new_posts = [
      p
      for p in reversed(posts)
      if not await post_storage.any_processed(
          group, recv, post_identities(p, source.dedup_key)
      )
  ]
  ...
  await post_storage.mark_posts_as_processed(sid, group, recv, to_mark)
  ```
  `post_identities` and `Message.post_id` are unchanged.

## What Goes Where
- **Implementation Steps** (checkboxes): all schema/code/test changes in this repo.
- **Post-Completion** (no checkboxes): manual prod DB deletion + post-deploy behavior checks.

## Implementation Steps

### Task 1: Normalize `posts` schema + storage methods; delete `is_post_processed`

**Files:**
- Modify: `feed_proxy/storage.py`
- Modify: `tests/test_post_storage.py`

> Note (partial implementation): after this task, `logic.py` still calls the **old** signatures,
> so `tests/test_logic.py` will fail until Task 2. That is expected — Task 1 is verified by the
> storage unit tests passing in isolation; the full suite goes green in Task 2.

- [x] change `create_sqlite_conn` posts table to normalized columns
      `(source_id, dedup_group, receiver_type, post_id)`
- [x] update `PostStorage` Protocol to the three new signatures; **remove** `is_post_processed`
- [x] remove the now-unused `Stringable` Protocol (no other users after the signature change)
- [x] reimplement `MemoryPostStorage` with `_owner` + `_dedup` indexes; `mark` writes both;
      remove `is_post_processed`
- [x] reimplement `SqlitePostStorage` (`has_posts`, `any_processed`, `mark_posts_as_processed`)
      per Technical Details; remove `is_post_processed`
- [x] rewrite `tests/test_post_storage.py` to new signatures (parametrized `make_sut`, both
      storages); remove the `is_post_processed` contract test
- [x] write test: `has_posts` scoped to `(source_id, receiver_type)` — true only after that
      source is marked; different source_id / different receiver_type → `False`
- [x] write test: `any_processed` matches by `(dedup_group, receiver_type)` across sources —
      mark under `source_id="a"` with `dedup_group="g"`, query group `"g"` → matches
- [x] write test: `any_processed` empty `post_ids` → `False`; wrong receiver_type → `False`
- [x] write test: a single `mark_posts_as_processed(sid, group, recv, [id])` populates **both**
      indexes atomically — afterwards `has_posts(sid, recv)` is `True` **and**
      `any_processed(group, recv, [id])` is `True` (the contract first-run seeding relies on)
- [x] run storage tests - must pass before next task

### Task 2: Wire owner/dedup scopes into `parse_message_batches_from_posts`

**Files:**
- Modify: `feed_proxy/logic.py`
- Modify: `tests/test_logic.py`

- [x] compute `sid` / `group` / `recv`; first-run guard `not await has_posts(sid, recv)`
      (per-source); seed via `mark_posts_as_processed(sid, group, recv, all_identities)`
- [x] novelty filter uses `any_processed(group, recv, post_identities(post, source.dedup_key))`
- [x] final mark uses `mark_posts_as_processed(sid, group, recv, to_mark)`
- [x] update `StubStorage` (`test_unhandled_processor_exception_aborts_before_marking`) to the new
      method signatures (`has_posts(source_id, receiver_type)`,
      `any_processed(dedup_group, receiver_type, post_ids)`,
      `mark_posts_as_processed(source_id, dedup_group, receiver_type, post_ids)`); remove its
      `is_post_processed`
- [x] migrate all existing `tests/test_logic.py` seeding/assertions to the new signatures —
      replace `is_post_processed` assertions with `any_processed`. **Multi-source group tests must
      seed EACH participating source's owner scope** separately
      (`mark_posts_as_processed(sid_a, group, recv, ["seed"])` **and**
      `mark_posts_as_processed(sid_b, group, recv, ["seed"])`), otherwise the unseeded source
      silently falls into the first-run path and returns `[]` for the *wrong reason* — a broken
      `any_processed` would then pass green. In each multi-source dedup test, add a positive guard
      proving the second source took the **dedup** path, not first-run: assert
      `has_posts(sid_b, recv)` is `True` before the dedup assertion (and/or that a genuinely-new,
      non-duplicate post from source_b *does* produce a batch)
- [x] write **regression** test: two sources sharing one `dedup_group`, both on their first run
      (empty storage) → **both** return `[]` (no batches, no burst); assert all identities marked
      under the group scope
- [x] write test: after both group sources are past first-run (each owner scope seeded), a
      cross-source duplicate (same title, different guid) from the second source is filtered (`[]`),
      with the positive guard above proving it was dedup and not first-run
- [x] write test: guid edit-resend protection preserved (same guid, changed title → `[]`)
- [x] write test: distinct `dedup_group` values are not cross-filtered
- [x] write test: ungrouped source (defaults) — first run seeds silently, then dedups by guid
      exactly as before
- [x] run full suite - must pass before next task

### Task 3: Verify acceptance criteria
- [x] verify Overview requirements: no first-cycle burst (per-source first-run); cross-source
      dedup by title still works; guid edit-resend protection preserved; ungrouped sources unchanged
- [x] verify edge cases: empty `post_ids`, distinct groups isolated, cross-stream (receiver_type)
      isolation within a source/group
- [x] run full suite: `make test`
- [x] run linters/types: `make lint`
- [x] verify no unintended change to the metrics key in `cli/run.py`

### Task 4: [Final] Update documentation
- [ ] update `README.md` if the `dedup_group`/`dedup_key` / `x-dedup` section references the old
      burst caveat — replace the "initial burst" note with the new per-source first-run behavior
- [ ] update `CLAUDE.md` only if a new pattern worth recording emerged
- [ ] move this plan to `docs/plans/completed/`

## Post-Completion
*Informational — manual/external actions, no checkboxes.*

**Deploy steps (manual, by user):**
- Stop the bot, delete the production sqlite DB file, start the bot. First cycle: every source
  self-seeds silently (marks current posts, sends nothing); normal delivery resumes next cycle.

**Manual verification after deploy:**
- Confirm no burst on the first cycle after deploying a group (2nd+ sources send nothing on cycle 1).
- Confirm a duplicate article present on both grouped sources is delivered to the channel only once.
- Confirm editing a title on one source does not re-send (guid path).
