# WordPress REST API Parser

## Overview
- Add a new **parser** `wordpress` that turns a WordPress REST API (`wp/v2`) posts JSON response into `list[WordpressPost]`.
- Problem it solves: lets the feed proxy ingest posts from any WordPress site exposing the standard REST API, without writing a new fetcher.
- Integration: reuses the existing generic `fetch_text` fetcher (stateless GET). A source is configured with a static URL like `https://<site>/wp-json/wp/v2/posts?per_page=100&orderby=date&order=desc`; `fetch_text` returns the JSON text, and the new `wordpress` parser parses it. Existing dedup (storage + dedup groups) removes already-seen posts by `post_id`, so no incremental `after` / pagination logic is needed.

## Context (from discovery)
- Files/components involved:
  - Create: `feed_proxy/handlers/parsers/wordpress.py`
  - Create: `tests/handlers/parsers/test_wordpress.py`
- Related patterns found:
  - `feed_proxy/handlers/parsers/reddit_json.py` — JSON parser via `json.loads`, `@register_handler(type=HandlerType.parsers, return_model=...)`, async signature `async def fn(text, *, options=None)`.
  - `feed_proxy/handlers/parsers/rss.py` — `FeedPost(Post)` dataclass with `description`/`extras` and `template_kwargs()`; uses `make_hash_tags` from `feed_proxy.utils.text`.
  - `tests/handlers/parsers/test_rss.py` — test conventions: `@pytest.fixture()` factory `make_<name>`, inline sample-data helper functions, AAA, direct assertions on parser output.
- Dependencies identified:
  - `feed_proxy.entities.Post` (base class), `feed_proxy.handlers` (`HandlerOptions`, `HandlerType`, `register_handler`), `feed_proxy.utils.text.make_hash_tags`, stdlib `json` + `html`.
  - Handlers auto-register via package scan (`load_handlers`), so no manual registry wiring needed.
  - `pytest-asyncio` with `asyncio_mode = "auto"` — async parser is tested directly with `await`.

## Development Approach
- **testing approach**: Regular (code first, then tests) — matches the tiny, well-understood scope; each task still ends with tests that must pass.
- Complete each task fully before moving to the next.
- Make small, focused changes.
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task (success + error/edge scenarios).
- **CRITICAL: all tests must pass before starting next task.**
- **CRITICAL: update this plan file when scope changes during implementation.**
- Run tests after each change; maintain backward compatibility.

## Testing Strategy
- **unit tests**: required for every task. Placed in `tests/handlers/parsers/test_wordpress.py` alongside `test_rss.py`.
- **e2e tests**: project has no UI-based e2e suite — not applicable.
- Test data: inline helper (Object Mother) producing a realistic WP `/wp/v2/posts` JSON array (list at top level, each item with `id`, `title.rendered`, `link`, `excerpt.rendered`, `content.rendered`).
- The parser is async; tests exercise it directly via `await wordpress(text)` (`asyncio_mode = "auto"`, so `async def test_...` needs no marker). Import `wordpress` and `WordpressPost` from the new module (no sync `_handler` split, unlike `rss.py`).
- Cases to cover: full field mapping, `post_id == str(id)`, `html.unescape` applied to title, empty array `[]` → `[]`, **non-list error payload → `[]`** (WP returns a JSON object like `{"code": "rest_invalid_param", ...}` on errors), `template_kwargs()` base output + `extras` merge/override.

## Progress Tracking
- Mark completed items with `[x]` immediately when done.
- Add newly discovered tasks with ➕ prefix; document blockers with ⚠️ prefix.
- Keep plan in sync with actual work.

## Solution Overview
- Mirror `reddit_json.py` structure: a dataclass model + an async parser registered as a handler.
- New model `WordpressPost(Post)` because WP needs a `content` field that `FeedPost` does not have; defining a dedicated model is cleaner than abusing `extras` (same choice `reddit_json` made with `RedditPost`).
- Tags are intentionally dropped: WP `categories`/`tags` are numeric ID arrays, not names; resolving names would require extra HTTP calls that a parser cannot make. `source_tags` are applied statically from config (`parse_posts` sets `post.source_tags = source.tags`).

## Technical Details
- **Model `WordpressPost(Post)`** (`@dataclasses.dataclass()`):
  - Fields: `post_id: str`, `title: str`, `url: str`, `source_tags: tuple | list`, `description: str = ""` (from `excerpt.rendered`), `content: str = ""` (from `content.rendered`), `extras: dict[str, str] = field(default_factory=dict)`.
  - `__str__` → `self.title`.
  - `template_kwargs()` → base dict `{post_id, title, url, source_tags="; ".join(source_tags), source_hash_tags=" ".join(make_hash_tags(source_tags)), description, content}` merged with `extras` (`{**base, **self.extras}`).
- **Parser** `async def wordpress(text, *, options=None) -> list[WordpressPost]`:
  - `raw = json.loads(text)`.
  - **Guard:** if `not isinstance(raw, list)` → `logger.warning(...)` and `return []`. WP returns a JSON *object* (e.g. `{"code": "rest_invalid_param", ...}`, `rest_no_route`) on errors; iterating that dict would raise `TypeError` on `entry["id"]`. This guard also gives the module `logger` a real use.
  - Otherwise iterate over `raw` (top-level array). Mapping per entry: `post_id=str(entry["id"])`, `title=html.unescape(entry["title"]["rendered"])`, `url=entry["link"]`, `source_tags=[]`, `description=entry["excerpt"]["rendered"]`, `content=entry["content"]["rendered"]`.
  - `description`/`content` intentionally keep their HTML markup (like `rss`'s `description`); note that `excerpt.rendered` is typically wrapped in `<p>…</p>` with a trailing "read more" link — template authors of `${description}`/`${content}` should expect HTML.
  - Registered via `@register_handler(type=HandlerType.parsers, return_model=WordpressPost)`.
- Processing flow: `fetch_text` → JSON text → `wordpress` parser → `list[WordpressPost]` → modifiers/dedup/receivers (unchanged).

## What Goes Where
- **Implementation Steps** (`[ ]`): parser module, model, tests, docs.
- **Post-Completion** (no checkboxes): live smoke test against a real WP site and adding a real source entry to `sources.prod.yaml` (deployment-side).

## Implementation Steps

### Task 1: Create `WordpressPost` model, `wordpress` parser, and tests

**Files:**
- Create: `feed_proxy/handlers/parsers/wordpress.py`
- Create: `tests/handlers/parsers/test_wordpress.py`

- [x] add imports: `dataclasses`, `html`, `json`, `logging`, `typing.Any`; `from feed_proxy.entities import Post`; `from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler`; `from feed_proxy.utils.text import make_hash_tags`; create module `logger`
- [x] define `WordpressPost(Post)` dataclass with fields `post_id`, `title`, `url`, `source_tags`, `description=""`, `content=""`, `extras` (default_factory dict); add `__str__` returning `title`
- [x] implement `template_kwargs()` returning the base dict (incl. `source_hash_tags` via `make_hash_tags`, `description`, `content`) merged with `extras`
- [x] implement `async def wordpress(text, *, options=None) -> list[WordpressPost]` with `@register_handler(type=HandlerType.parsers, return_model=WordpressPost)`, `json.loads`, `isinstance(raw, list)` guard (`logger.warning` + `return []`), top-level array iteration, and field mapping (`str(id)`, `html.unescape(title.rendered)`, `link`, `excerpt.rendered`, `content.rendered`, `source_tags=[]`)
- [x] (self-check) confirm handler auto-registers — no manual registry edits required
- [x] add `@pytest.fixture()` factory `make_wordpress_post` (Object Mother with sensible defaults) mirroring `test_rss.py` style
- [x] add inline helper building a realistic WP posts JSON array (≥2 posts, with HTML entities in a title, populated `excerpt.rendered`/`content.rendered`)
- [x] write test: full field mapping success case via `await wordpress(text)` — `post_id == str(id)`, `title`, `url`, `description`, `content` correctly mapped, `source_tags == []`
- [x] write test: `title` is HTML-unescaped (e.g. `&#8217;`/`&amp;` decoded)
- [x] write test: empty JSON array `[]` → returns `[]` (edge case)
- [x] write test: non-list error payload (e.g. `{"code": "rest_invalid_param", ...}`) → returns `[]` (does not raise)
- [x] write tests for `template_kwargs()`: base output shape, `extras` adds new key, `extras` overrides base field
- [x] run tests: `make test args="tests/handlers/parsers/test_wordpress.py"` — must pass before next task

### Task 2: Verify acceptance criteria
- [ ] verify all requirements from Overview are implemented (parser registered, model fields, tag-drop, unescape, `str` post_id, non-list guard)
- [ ] verify edge cases handled (empty array, non-list error payload, extras merge/override, HTML entities)
- [ ] run full test suite: `make test`
- [ ] run dead-fixtures check (part of `make test`) and lint/type checks: `make lint`
- [ ] verify test coverage is consistent with sibling parsers

### Task 3: [Final] Update documentation
- [ ] update `README.md` / docs parser list if parsers are enumerated there (grep for `reddit_json`/`rss` in docs; skip if not listed)
- [ ] update `CLAUDE.md` only if a genuinely new pattern was discovered (unlikely — mirrors existing parser)
- [ ] move this plan to `docs/plans/completed/`

## Post-Completion
*Items requiring manual intervention or external systems — informational only*

**Manual verification:**
- Smoke test against a real endpoint, e.g. `https://mioviedo.com/wp-json/wp/v2/posts?per_page=5&orderby=date&order=desc`, and confirm parsed `WordpressPost` objects look correct.

**External system updates:**
- Add a real WordPress source to `sources.prod.yaml` using `fetcher_type: fetch_text` + `parser_type: wordpress` with the static `wp/v2/posts` URL, appropriate `source_tags`, message template referencing `${title}`/`${url}` (and optionally `${description}`/`${content}`), and stream/receiver config. This is deployment-side, not part of the code change.
