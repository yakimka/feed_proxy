# Pre-send processors + Gemini translator (MVP)

## Overview

Add a new handler entity `pre_send_processors` for enriching posts (translation, summarization,
content fetching) before sending messages. MVP scope: only the `translator` handler using Google
Gemini Flash.

**Problem solved:** there is currently no way to transform post content (e.g., translate titles to a
different language) before it lands in a Telegram message. Existing `modifiers` run too early in the
pipeline (before storage dedup), so plugging AI calls into them would re-translate every post on
every poll — wasteful and expensive.

**Integration:** new handler type registered alongside existing
fetchers/parsers/modifiers/receivers. Processors run inside `parse_message_batches_from_posts` *
*after** the `is_post_processed` filter, so AI is invoked only for genuinely new posts.

## Context (from discovery)

**Files involved:**

- `feed_proxy/entities.py` — add `PreSendProcessor` dataclass + field on `Stream`
- `feed_proxy/handlers/__init__.py` — extend `HandlerType` enum + add validation in
  `init_registered_handlers` (lines 154-179 are the modifier pattern to mirror)
- `feed_proxy/logic.py` — add `apply_pre_send_processors`, restructure
  `parse_message_batches_from_posts` to call it on new posts only with explicit ordering of
  `mark_posts_as_processed`
- `feed_proxy/handlers/parsers/rss.py` — add `description` + `extras` to `FeedPost`, fill
  description from `entry.summary/description`, update `template_kwargs`
- `feed_proxy/handlers/parsers/reddit_json.py` — add `extras` to `RedditPost`, update
  `template_kwargs`
- `feed_proxy/handlers/parsers/fotocasa.py` — add `extras` to `FotocasaItem`, update
  `template_kwargs`
- `feed_proxy/handlers/pre_send_processors/` — new package with `__init__.py` and `translator.py`
- `pyproject.toml` — add `google-genai` dependency
- `tests/` — new test files

**Patterns found (reuse):**

- `register_handler(type=HandlerType.X, options=...)` decorator
- `HandlerOptions` dataclass with `DESCRIPTIONS` dict for option metadata
- `feed_proxy/handlers/modifiers/replace.py` is the structural template for the translator
- `apply_modifiers_to_posts` (`logic.py:48-58`) is the structural twin of the new
  `apply_pre_send_processors`
- `Modifier` dataclass in `entities.py:32-35` is the structural twin of `PreSendProcessor` — both
  are `type: str` + `options: dict` and load via dacite without explicit `configuration.py`
  registration

**Dependencies identified:**

- `google-genai` (new)
- env var `GEMINI_API_KEY`

## Development Approach

- **testing approach:** Regular (code first, then tests within the same task)
- complete each task fully before moving to the next
- make small, focused changes
- every task MUST include new/updated tests for the code introduced/modified in that task
- all tests must pass before starting the next task
- update this plan file if scope changes during implementation
- maintain backward compatibility: configs without `pre_send_processors` MUST continue to work
  unchanged; existing parser output remains usable everywhere

## Testing Strategy

- unit tests required per task (see Development Approach)
- mock Gemini at the SDK boundary (the `google.genai` client call), not internal helpers
- AAA pattern, `@pytest.fixture()` with parentheses, no test classes
- SUT pattern: use `sut` / `make_sut` fixtures where appropriate
- Object Mother / `make_<name>` factory fixtures for posts
- conftest.py per directory for shared fixtures

## Progress Tracking

- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope

## Implementation Steps

### Task 1: Add `extras` to all Post dataclasses; add `description` to `FeedPost`; update
`template_kwargs` everywhere

**Files:**

- Modify: `feed_proxy/handlers/parsers/rss.py`
- Modify: `feed_proxy/handlers/parsers/reddit_json.py`
- Modify: `feed_proxy/handlers/parsers/fotocasa.py`
- Create: `tests/handlers/__init__.py` (if missing)
- Create: `tests/handlers/parsers/__init__.py`
- Create: `tests/handlers/parsers/test_rss.py` (only this one in this task — others have no behavior
  change beyond the field)

- [x] add `extras: dict[str, str] = dataclasses.field(default_factory=dict)` to `FeedPost`,
  `RedditPost`, `FotocasaItem`
- [x] add `description: str = ""` to `FeedPost` only (description is RSS-specific; other parsers
  don't have a natural equivalent in MVP)
- [x] in `rss.py:_handler`, populate
  `description=entry.get("summary") or entry.get("description") or ""` (description may contain raw
  HTML; MVP stores it verbatim, HTML stripping is out of scope)
- [x] update `template_kwargs()` in all three dataclasses to return `{**base, **self.extras}` so
  extras override base by design
- [x] include `"description": self.description` in `FeedPost.template_kwargs` base dict
- [x] write unit tests for `FeedPost.template_kwargs()`: without extras, with extras adding new key,
  with extras overriding base field
- [x] write a unit test for `rss` parser: `description` populated from `summary`, falls back to
  `description`, defaults to `""`
- [x] run tests — must pass before next task

### Task 2: Add `PreSendProcessor` entity and `Stream.pre_send_processors` field

**Files:**

- Modify: `feed_proxy/entities.py`
- Modify: `tests/test_configuration_loader.py`

- [x] add `PreSendProcessor` dataclass mirroring `Modifier`: `type: str`,
  `options: dict[str, Any] = field(default_factory=dict)`
- [x] add `pre_send_processors: list[PreSendProcessor] = field(default_factory=list)` to `Stream`
- [x] no change needed in `configuration.py` — dacite picks the new field automatically because
  `PreSendProcessor` has the same shape as `Modifier`; verify via test, not via code inspection
- [x] reuse `run_sut` and `minimal_sources_block` fixtures from
  `tests/test_configuration_loader.py` — do not create new SUT scaffolding
- [x] write a configuration-loader test: a stream config with `pre_send_processors` list parses
  correctly into `Stream` with `PreSendProcessor` instances
- [x] write a test that a stream config WITHOUT `pre_send_processors` still parses (defaults to
  `[]`)
- [x] run tests — must pass before next task

### Task 3: Create the `pre_send_processors` package, then add `HandlerType` enum entry

**Files:**

- Create: `feed_proxy/handlers/pre_send_processors/__init__.py` (empty)
- Modify: `feed_proxy/handlers/__init__.py`

**Order matters:** `load_handlers()` (`handlers/__init__.py:97-102`) iterates `HandlerType` and
imports `feed_proxy.handlers.<value>` for each member. Adding the enum entry before the package
exists would crash at import time.

- [x] create empty `feed_proxy/handlers/pre_send_processors/__init__.py` FIRST
- [x] add `pre_send_processors = "pre_send_processors"` to the `HandlerType` enum
- [x] extend the existing `for si, stream in enumerate(source.streams):` block (
  `handlers/__init__.py:154-179`) to also iterate `stream.pre_send_processors`, build the
  `(HandlerType.pre_send_processors, processor.type)` key, append the options to
  `options_to_validate`, add to `used_handlers` — mirror the modifier loop exactly
- [x] the subsequent `for handler_type, handler_id in used_handlers:` loop (lines 187-235) is
  type-agnostic and needs no change — confirm via test
- [x] write a test: `load_handlers()` runs without error after the enum is added (i.e. the new
  package is discoverable)
- [x] write a test: a config referencing a non-existent `pre_send_processor.type` raises
  `InitHandlersError`
- [x] write a test: an invalid `options` dict for a registered processor raises
  `InitHandlersError` — follow the `DummyReceiver` pattern in
  `tests/test_configuration_loader.py:66-80`: register a dummy processor at module scope in the new
  test file via `@register_handler(type=HandlerType.pre_send_processors, ...)`
- [x] run tests — must pass before next task

### Task 4: Wire `apply_pre_send_processors` into the pipeline with explicit ordering

**Files:**

- Modify: `feed_proxy/logic.py`
- Create: `tests/test_logic.py` — `parse_message_batches_from_posts` currently has no direct test
  coverage, so this file also serves as the baseline for the unchanged paths (first-run, squash,
  no-new-posts)

**Critical invariants:**

- Processors run AFTER `is_post_processed` filtering (only on new posts)
- `mark_posts_as_processed` is called ONLY after `Message` objects are successfully constructed
- Any pre-send processor that raises uncaught aborts the batch and skips marking; the translator
  deliberately catches its own per-post errors so it never triggers this path — the invariant is
  enforced via a stub processor in tests, not via the translator

- [x] add
  `async def apply_pre_send_processors(processors: list[PreSendProcessor], posts: list[Post]) -> list[Post]` —
  sequentially apply each processor (use
  `get_handler_by_name(type=HandlerType.pre_send_processors, ...)`), mirroring
  `apply_modifiers_to_posts`
- [x] restructure `parse_message_batches_from_posts`:
    1. iterate `reversed(posts)`, skip those where `is_post_processed`, collect remaining into
       `new_posts` in the same reversed (oldest-first) order produced by the existing loop
    2. call `new_posts = await apply_pre_send_processors(stream.pre_send_processors, new_posts)`
    3. build the `messages` list from `new_posts` (`template_kwargs = post.template_kwargs()`)
    4. compute `to_mark = [post.post_id for post in new_posts]`
    5. call `await post_storage.mark_posts_as_processed(key, to_mark)` ONLY after step 3-4 succeed
- [x] preserve the existing "first run" early-return branch (
  `if not await post_storage.has_posts(key):`) — no processors run there, all post_ids are marked as
  before
- [x] preserve the existing squash logic for batches
- [x] write a unit test using a stub processor handler that records which posts it sees — assert it
  sees ONLY the un-processed posts
- [x] write a unit test: empty `pre_send_processors` list → behavior identical to pre-change (same
  `Message` produced, same posts marked)
- [x] write a unit test: a processor that writes `post.extras["x"] = "v"` → resulting
  `messages[0].template_kwargs["x"] == "v"`
- [x] write a unit test for `apply_pre_send_processors`: processors are applied in declared order,
  output of processor N is visible to processor N+1
- [x] write a unit test using a STUB processor (not the translator) that raises an unhandled
  exception → `mark_posts_as_processed` is NOT called (verify via mock/stub storage)
- [x] write a unit test: two streams on the same source with different `pre_send_processors` — the
  second stream's posts do not contain extras written by the first stream's processors (cross-stream
  isolation, relies on the `copy.deepcopy` in `parse_posts:40`)
- [x] run tests — must pass before next task

### Task 5: Add `google-genai` dependency

**Files:**

- Modify: `pyproject.toml`
- Modify: `poetry.lock` (regenerated)

- [ ] add `google-genai` to `[tool.poetry.dependencies]`
- [ ] run `poetry add google-genai` (adds to pyproject.toml AND locks)
- [ ] verify import: `poetry run python -c "import google.genai"` exits 0
- [ ] no test code; dependency-only task
- [ ] run existing test suite — must still pass before next task

### Task 6: Implement `translator` pre-send processor + its tests

**Files:**

- Create: `feed_proxy/handlers/pre_send_processors/translator.py`
- Create: `tests/handlers/pre_send_processors/__init__.py`
- Create: `tests/handlers/pre_send_processors/conftest.py`
- Create: `tests/handlers/pre_send_processors/test_translator.py`

**Pinned seams (so the test fixture and the implementation agree):**

- The Gemini client is obtained via a module-level helper `_get_client() -> genai.Client` (lazy,
  cached in a module global). Tests patch
  `feed_proxy.handlers.pre_send_processors.translator._get_client` to return a stub.
- Missing `GEMINI_API_KEY` is NOT a startup error — `_get_client()` raises only on first use; the
  per-post `try/except` catches it and writes `on_error_value`.

- [ ] define `TranslatorOptions(HandlerOptions)` with: `source_field: str`, `target_field: str`,
  `target_language: str`, `model: str = "gemini-2.0-flash"`,
  `on_error_value: str = "[translation failed]"`; include `DESCRIPTIONS` dict
- [ ] register `translator` via
  `@register_handler(type=HandlerType.pre_send_processors, options=TranslatorOptions)`
- [ ] implement `_read_field(post, name)`: returns `post.extras[name]` if present, otherwise
  `getattr(post, name, "") or ""`
- [ ] implement `_get_client()`: lazy module-level client, API key from `GEMINI_API_KEY`; raises if
  env var missing
- [ ] implement `_translate(source, language, model)`: calls Gemini Flash with the prompt
  `"Translate the following text to {language}. Output only the translation, no explanations.\n\nText:\n{source}"`;
  returns the translated string
- [ ] main function `translator(posts, *, options)`: for each post — read source; if empty, skip;
  else try `_translate`, on any exception log and use `on_error_value`; write to
  `post.extras[options.target_field]`; continue to next post
- [ ] write a parametrized test asserting the translator never re-raises for arbitrary exception
  types from `_translate` (`Exception`, `RuntimeError`, `KeyError`, etc.) — for each,
  `extras[target_field] == on_error_value` and the next post in the batch is still processed
- [ ] in `tests/handlers/pre_send_processors/conftest.py`: `make_feed_post` factory fixture with
  sensible defaults, `make_translator_options` factory fixture, `stub_gemini` fixture that patches
  `_get_client` and lets each test set the response/exception
- [ ] test happy path: source field set → `extras[target_field]` == stubbed translation
- [ ] test chain: `source_field` references a key in `extras` (set by prior step) → reads from
  extras
- [ ] test precedence: both `extras[name]` and attribute `post.<name>` are set → `_read_field`
  returns the extras value
- [ ] test empty source: source field is `""` → no Gemini call, `extras` unchanged
- [ ] test error: Gemini stub raises → `extras[target_field] == on_error_value`, log emitted, the
  NEXT post in the same batch is still processed
- [ ] test custom `on_error_value`: option override propagates
- [ ] test missing API key: with `GEMINI_API_KEY` unset, the function does not crash at import; on
  first call `extras[target_field] == on_error_value`
- [ ] run tests — must pass before next task

### Task 7: Verify acceptance criteria

- [ ] write a sample YAML inline within a test (or in `tests/fixtures/` if appropriate for this
  repo) using translator on `title` → `title_ua` and on `description` → `description_ua`; load via
  `load_configuration` + `init_registered_handlers` to confirm validation passes. Do NOT modify
  `config/sources.yaml` (production config — would activate translation in deploy)
- [ ] verify an existing config WITHOUT `pre_send_processors` still loads and runs
- [ ] run full test suite (the project test command — `make test` if present, otherwise `pytest`)
- [ ] run linters: `make lint` if present, otherwise `pre-commit run --all-files`
- [ ] mypy passes (project uses type hints + py.typed)

### Task 8: [Final] Update documentation and move plan

- [ ] update `README.md`: brief section documenting `pre_send_processors` field on Stream with the
  translator example
- [ ] move this plan to `docs/plans/completed/20260531-pre-send-processors-translator.md`

## Technical Details

**Pipeline order (after this change):**

```
fetch_text → parse_posts (modifiers still run here, on ALL posts — by design, for cheap filtering/rewrites)
           → parse_message_batches_from_posts:
               1. filter posts via is_post_processed → new_posts (preserve reversed order)
               2. apply_pre_send_processors(stream.pre_send_processors, new_posts)   ← NEW (expensive enrichment)
               3. build Message objects (template_kwargs = base + extras)
               4. mark_posts_as_processed (only after step 3 succeeds)
           → send_messages
```

Modifiers continue to be applied before dedup (filtering and cheap rewrites). Pre-send processors
run after dedup (expensive enrichment).

**Post field semantics:**

- All three concrete posts (`FeedPost`, `RedditPost`, `FotocasaItem`) get `extras: dict[str, str]` —
  enrichment results written by pre-send processors
- `FeedPost` ALSO gets `description: str = ""` (RSS-specific, set by parser from `entry.summary`/
  `entry.description`)
- `template_kwargs() = {**base_fields, **extras}` — extras override base by design (user controls
  `target_field`)

**Processor field semantics:**

- `source_field`: read order = `extras[source_field]` → `getattr(post, source_field, "")` (allows
  chaining; extras wins on collision)
- `target_field`: ALWAYS written to `extras[target_field]` (never mutates base attributes)
- On per-post error: write `on_error_value` to target_field, log, continue with next post
- On unrecoverable error (e.g., bug in processor itself): exception propagates out, batch is NOT
  marked processed, retried next poll

**Sequential processing:** posts are processed one at a time inside a single processor, and
processors run one after another. No concurrency in MVP — keeps rate-limiting simple and
observability easy.

**Cross-stream isolation:** `parse_posts:40` does `copy.deepcopy(posts)` for each stream, so
per-stream processor mutations cannot leak between streams. This invariant is locked in by a test in
Task 4.

**Chained error markers:** if a chained `source_field` points at a previously-failed extras value (
containing `on_error_value`), the next processor translates the marker as-is. The operator is
responsible for setting `on_error_value` to something safe to re-translate or for breaking the chain
manually (e.g., a guard processor).

**Example YAML:**

```yaml
streams:
  - receiver_type: telegram
    message_template: "<b>{title_ua}</b>\n\n{description_ua}\n\n{url}"
    pre_send_processors:
      - type: translator
        options:
          source_field: title
          target_field: title_ua
          target_language: uk
      - type: translator
        options:
          source_field: description
          target_field: description_ua
          target_language: uk
```

## Post-Completion

**Manual verification:**

- run the bot end-to-end with `GEMINI_API_KEY` set and a real RSS source; observe a Telegram message
  arriving with translated `title_ua` / `description_ua`
- temporarily set a bad API key → message should still arrive with the `on_error_value` marker in
  target fields

**External system updates:**

- ensure `GEMINI_API_KEY` is configured in the deployment environment before enabling
  `pre_send_processors` in production sources.yaml
- future iterations (NOT in this plan): `summarizer`, `url_content_fetcher` (with HTML→text helper),
  parallel processing, prompt overrides, alternative AI providers
