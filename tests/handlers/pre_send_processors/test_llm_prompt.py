import json
import sqlite3
import time

import httpx
import pytest

from feed_proxy.handlers.pre_send_processors import llm_prompt as llm_prompt_module
from feed_proxy.handlers.pre_send_processors.llm_prompt import llm_prompt
from feed_proxy.storage import (
    MemoryLlmCacheStorage,
    SqliteLlmCacheStorage,
    create_sqlite_conn,
)


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    monkeypatch.setattr(llm_prompt_module, "_client", None)
    monkeypatch.setattr(llm_prompt_module, "_last_cache_purge", 0.0)
    # the default storage, unless a test asks for the sqlite one
    memory_cache = MemoryLlmCacheStorage()
    monkeypatch.setattr(
        llm_prompt_module, "get_llm_cache_storage", lambda: memory_cache
    )
    monkeypatch.delenv("LLM_CACHE_TTL_DAYS", raising=False)


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "feed_proxy.db")


@pytest.fixture()
def make_cache(db_path, monkeypatch):
    """Cache in the sqlite file; calling it again works like a restart."""

    def _make_cache() -> SqliteLlmCacheStorage:
        cache = SqliteLlmCacheStorage(create_sqlite_conn(db_path))
        monkeypatch.setattr(llm_prompt_module, "get_llm_cache_storage", lambda: cache)
        monkeypatch.setattr(llm_prompt_module, "_last_cache_purge", 0.0)
        return cache

    return _make_cache


@pytest.fixture()
def cache(make_cache):
    return make_cache()


def _count_cached_answers(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
    finally:
        conn.close()


class BrokenCache:
    async def get(self, key, *, newer_than):  # noqa: U100
        raise sqlite3.OperationalError("broken")

    async def set(self, key, value, *, created_at):  # noqa: U100
        raise sqlite3.OperationalError("broken")

    async def delete_older_than(self, timestamp):  # noqa: U100
        raise sqlite3.OperationalError("broken")


async def test_happy_path(make_feed_post, make_llm_prompt_options, stub_llm):
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Заголовок"


async def test_arbitrary_prompt_not_related_to_translation(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_response("Short summary.")
    post = make_feed_post(extras={"description": "Long article text..."})
    options = make_llm_prompt_options(
        source_field="description",
        target_field="summary",
        prompt="Summarize in one sentence.\n\nText:\n{source}",
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["summary"] == "Short summary."


async def test_prompt_with_unrelated_braces_does_not_break_substitution(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_response("ok")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(
        source_field="title",
        target_field="title_ua",
        prompt='Return JSON like {"a": 1}. Text:\n{source}',
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "ok"
    assert stub_llm.prompts == ['Return JSON like {"a": 1}. Text:\nTitle']


async def test_reads_from_extras_when_chained(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_response("Опис")
    post = make_feed_post(extras={"description_clean": "Description"})
    options = make_llm_prompt_options(
        source_field="description_clean", target_field="description_ua"
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["description_ua"] == "Опис"
    assert len(stub_llm.prompts) == 1
    assert "Description" in stub_llm.prompts[0]


async def test_extras_take_precedence_over_attribute(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_response("translated")
    post = make_feed_post(title="Attribute value", extras={"title": "Extras value"})
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert "Extras value" in stub_llm.prompts[0]
    assert "Attribute value" not in stub_llm.prompts[0]


async def test_empty_source_skips_prompt(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    post = make_feed_post(title="")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert stub_llm.requests == []
    assert result[0].extras["title_ua"] == ""


async def test_request_uses_chat_completions_endpoint_with_configured_model(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    request = stub_llm.requests[0]
    assert str(request.url) == "https://llm.test/v1/chat/completions"
    assert json.loads(request.content)["model"] == "test-model"


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("<think>hmm, let me translate</think>\nЗаголовок", "Заголовок"),
        ("<think>\nmulti\nline\n</think>Заголовок", "Заголовок"),
        ("  Заголовок \n", "Заголовок"),
    ],
)
async def test_response_is_cleaned_up(
    make_feed_post, make_llm_prompt_options, stub_llm, answer, expected
):
    stub_llm.set_response(answer)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == expected


async def test_chunked_reasoning_response_keeps_only_text_chunks(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_response(
        [
            {"type": "thinking", "thinking": [{"type": "text", "text": "hmm"}]},
            {"type": "text", "text": "Міст "},
            {"type": "text", "text": "закритий."},
        ]
    )
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Міст закритий."


# Failures: the source text is used, or on_error_value if it's set.


@pytest.mark.parametrize(
    "exc", [Exception("boom"), RuntimeError("boom"), KeyError("boom")]
)
async def test_unexpected_error_falls_back_to_source_text(
    make_feed_post, make_llm_prompt_options, stub_llm, exc
):
    stub_llm.set_exception(exc)
    failing_post = make_feed_post(post_id="1", title="Title 1")
    next_post = make_feed_post(post_id="2", title="Title 2")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([failing_post, next_post], options=options)

    assert result[0].extras["title_ua"] == "Title 1"
    assert result[1].extras["title_ua"] == "Title 2"


async def test_error_uses_custom_on_error_value(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_exception(RuntimeError("boom"))
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(
        source_field="title", target_field="title_ua", on_error_value="Уупс, нешмогла"
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Уупс, нешмогла"


async def test_on_error_value_is_used_after_retries_are_exhausted(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_status(429)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(
        source_field="title", target_field="title_ua", on_error_value="N/A"
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "N/A"
    assert len(stub_llm.requests) == 5


async def test_missing_api_key_falls_back_to_source_text(
    make_feed_post, make_llm_prompt_options, monkeypatch
):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Title"


async def test_missing_api_key_uses_on_error_value(
    make_feed_post, make_llm_prompt_options, monkeypatch
):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(
        source_field="title", target_field="title_ua", on_error_value="N/A"
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "N/A"


async def test_error_response_body_is_logged(
    make_feed_post, make_llm_prompt_options, stub_llm, caplog
):
    stub_llm.set_status(400, body={"message": "top_p must be 1"})
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert "top_p must be 1" in caplog.text


# Retries


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_retries_transient_statuses_and_succeeds(
    make_feed_post, make_llm_prompt_options, stub_llm, status
):
    stub_llm.queue_status(status)
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Заголовок"
    assert len(stub_llm.requests) == 2


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectError("boom"),
        httpx.ReadTimeout("boom"),
        httpx.RemoteProtocolError("boom"),
        httpx.DecodingError("boom"),
    ],
)
async def test_retries_network_errors_and_timeouts(
    make_feed_post, make_llm_prompt_options, stub_llm, exc
):
    stub_llm.queue_exception(exc)
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Заголовок"
    assert len(stub_llm.requests) == 2


@pytest.mark.parametrize("answer", [None, "", "<think>only thinking</think>"])
async def test_retries_empty_answer_then_falls_back_to_source_text(
    make_feed_post, make_llm_prompt_options, stub_llm, answer
):
    stub_llm.set_response(answer)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Title"
    assert len(stub_llm.requests) == 5


async def test_empty_answer_can_recover_on_retry(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.queue_answer(None)
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Заголовок"
    assert len(stub_llm.requests) == 2


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404])
async def test_client_errors_are_not_retried(
    make_feed_post, make_llm_prompt_options, stub_llm, status
):
    stub_llm.set_status(status)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Title"
    assert len(stub_llm.requests) == 1
    assert stub_llm.sleeps == []


async def test_gives_up_after_max_attempts(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_status(503)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Title"
    assert len(stub_llm.requests) == 5
    assert len(stub_llm.sleeps) == 4


async def test_backoff_grows_exponentially_without_retry_after(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    for _ in range(4):
        stub_llm.queue_status(429)
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Заголовок"
    assert stub_llm.sleeps == [5.0, 10.0, 20.0, 40.0]


async def test_backoff_is_jittered(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    monkeypatch.setattr(llm_prompt_module, "_jitter", lambda: 1.5)
    stub_llm.queue_status(429)
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert stub_llm.sleeps == [7.5]


async def test_retry_after_header_is_respected(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.queue_status(429, headers={"Retry-After": "3"})
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert stub_llm.sleeps == [3.0]


async def test_retry_after_is_capped(make_feed_post, make_llm_prompt_options, stub_llm):
    stub_llm.queue_status(429, headers={"Retry-After": "3600"})
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert stub_llm.sleeps == [60.0]


async def test_gives_up_when_time_budget_is_spent(
    make_feed_post, make_llm_prompt_options, stub_llm
):
    stub_llm.set_status(429, headers={"Retry-After": "60"})
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Title"
    assert len(stub_llm.requests) == 4
    assert stub_llm.sleeps == [60.0, 60.0, 60.0]


async def test_rate_limit_pauses_requests_of_other_posts(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    stub_llm.queue_status(429, headers={"Retry-After": "10"})
    stub_llm.set_response("ok")
    posts = [make_feed_post(post_id=str(i), title=f"Title {i}") for i in range(3)]
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt(posts, options=options)

    # the third post starts while the first one waits and has to wait too
    assert stub_llm.sleeps == [10.0, 10.0]


async def test_server_overload_pauses_requests_of_other_posts(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    stub_llm.queue_status(503, headers={"Retry-After": "10"})
    stub_llm.set_response("ok")
    posts = [make_feed_post(post_id=str(i), title=f"Title {i}") for i in range(3)]
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt(posts, options=options)

    assert stub_llm.sleeps == [10.0, 10.0]


@pytest.mark.parametrize("status", [500, 502, 504])
async def test_single_server_error_does_not_pause_other_posts(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch, status
):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    stub_llm.queue_status(status)
    stub_llm.set_response("ok")
    posts = [make_feed_post(post_id=str(i), title=f"Title {i}") for i in range(3)]
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt(posts, options=options)

    assert stub_llm.sleeps == [5.0]


async def test_retry_after_is_spread_but_never_shortened(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    monkeypatch.setattr(llm_prompt_module, "_jitter", lambda: 1.2)
    stub_llm.queue_status(429, headers={"Retry-After": "10"})
    stub_llm.set_response("ok")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert stub_llm.sleeps == [12.0]


async def test_retry_after_is_not_shortened_by_low_jitter(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    monkeypatch.setattr(llm_prompt_module, "_jitter", lambda: 0.75)
    stub_llm.queue_status(429, headers={"Retry-After": "10"})
    stub_llm.set_response("ok")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert stub_llm.sleeps == [10.0]


@pytest.mark.parametrize(
    "body",
    [
        "<html>Bad gateway</html>",
        "",
        '{"error": {"message": "upstream failed"}}',
        '{"choices": []}',
        '{"choices": [{"message": null}]}',
    ],
)
async def test_retries_malformed_success_response(
    make_feed_post, make_llm_prompt_options, stub_llm, body
):
    stub_llm.queue_raw(body)
    stub_llm.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Заголовок"
    assert len(stub_llm.requests) == 2


async def test_malformed_response_body_is_logged_when_giving_up(
    make_feed_post, make_llm_prompt_options, stub_llm, caplog
):
    for _ in range(5):
        stub_llm.queue_raw("<html>Bad gateway</html>")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Title"
    assert "Bad gateway" in caplog.text


# Configuration


async def test_max_concurrency_is_configurable(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    stub_llm.set_response("ok")
    posts = [make_feed_post(post_id=str(i), title=f"Title {i}") for i in range(6)]
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt(posts, options=options)

    assert len(stub_llm.requests) == 6
    assert stub_llm.max_in_flight == 2


@pytest.mark.parametrize("value", [None, "0", "-1", "many", "inf"])
async def test_max_concurrency_defaults_to_five(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch, value
):
    if value is None:
        monkeypatch.delenv("LLM_MAX_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("LLM_MAX_CONCURRENCY", value)
    stub_llm.set_response("ok")
    posts = [make_feed_post(post_id=str(i), title=f"Title {i}") for i in range(8)]
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt(posts, options=options)

    assert stub_llm.max_in_flight == 5


async def test_temperature_is_zero_by_default(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    stub_llm.set_response("ok")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert json.loads(stub_llm.requests[0].content)["temperature"] == 0


@pytest.mark.parametrize(
    "value, expected",
    [("0.3", 0.3), ("junk", 0), ("-1", 0), ("nan", 0), ("inf", 0)],
)
async def test_temperature_is_configurable(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch, value, expected
):
    monkeypatch.setenv("LLM_TEMPERATURE", value)
    stub_llm.set_response("ok")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert json.loads(stub_llm.requests[0].content)["temperature"] == expected


@pytest.mark.parametrize(
    "value, expected",
    [(None, 90), ("15", 15), ("junk", 90), ("0", 90), ("nan", 90), ("inf", 90)],
)
async def test_client_timeout_is_configurable(
    make_feed_post, make_llm_prompt_options, monkeypatch, value, expected
):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    if value is None:
        monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    else:
        monkeypatch.setenv("LLM_TIMEOUT", value)
    created: list[dict] = []
    real_client = httpx.AsyncClient

    def spy_client(**kwargs):
        created.append(kwargs)
        return real_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"choices": [{"message": {"content": "ok"}}]}
                )
            ),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "AsyncClient", spy_client)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    assert [kwargs["timeout"] for kwargs in created] == [expected]


# Cache


async def test_answer_is_cached_between_calls(
    make_feed_post, make_llm_prompt_options, stub_llm, cache  # noqa: U100
):
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    first = await llm_prompt([make_feed_post(title="Title")], options=options)
    second = await llm_prompt([make_feed_post(title="Title")], options=options)

    assert first[0].extras["title_ua"] == "Заголовок"
    assert second[0].extras["title_ua"] == "Заголовок"
    assert len(stub_llm.requests) == 1


async def test_cached_answer_survives_a_restart(
    make_feed_post, make_llm_prompt_options, stub_llm, make_cache
):
    make_cache()
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    await llm_prompt([make_feed_post(title="Title")], options=options)
    make_cache()
    stub_llm.set_response("Другий переклад")

    result = await llm_prompt([make_feed_post(title="Title")], options=options)

    assert result[0].extras["title_ua"] == "Заголовок"
    assert len(stub_llm.requests) == 1


async def test_different_source_text_is_translated_separately(
    make_feed_post, make_llm_prompt_options, stub_llm, cache  # noqa: U100
):
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([make_feed_post(title="Title 1")], options=options)
    await llm_prompt([make_feed_post(title="Title 2")], options=options)

    assert len(stub_llm.requests) == 2


async def test_different_prompt_is_run_separately(
    make_feed_post, make_llm_prompt_options, stub_llm, cache  # noqa: U100
):
    stub_llm.set_response("answer")
    post = make_feed_post(title="Title")

    await llm_prompt(
        [post], options=make_llm_prompt_options(prompt="Translate.\n{source}")
    )
    await llm_prompt(
        [post], options=make_llm_prompt_options(prompt="Summarize.\n{source}")
    )

    assert len(stub_llm.requests) == 2


async def test_different_model_is_run_separately(
    make_feed_post,
    make_llm_prompt_options,
    stub_llm,
    cache,  # noqa: U100
    monkeypatch,
):
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    await llm_prompt([make_feed_post(title="Title")], options=options)
    monkeypatch.setenv("LLM_MODEL", "other-model")

    await llm_prompt([make_feed_post(title="Title")], options=options)

    assert len(stub_llm.requests) == 2


async def test_different_temperature_is_run_separately(
    make_feed_post,
    make_llm_prompt_options,
    stub_llm,
    cache,  # noqa: U100
    monkeypatch,
):
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    await llm_prompt([make_feed_post(title="Title")], options=options)
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")

    await llm_prompt([make_feed_post(title="Title")], options=options)

    assert len(stub_llm.requests) == 2


async def test_answer_is_cached_with_non_zero_temperature(
    make_feed_post,
    make_llm_prompt_options,
    stub_llm,
    cache,  # noqa: U100
    monkeypatch,
):
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([make_feed_post(title="Title")], options=options)
    await llm_prompt([make_feed_post(title="Title")], options=options)

    assert len(stub_llm.requests) == 1


async def test_failed_call_is_not_cached(
    make_feed_post, make_llm_prompt_options, stub_llm, cache  # noqa: U100
):
    stub_llm.set_status(400)
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    failed = await llm_prompt([make_feed_post(title="Title")], options=options)
    stub_llm.set_response("Заголовок")

    recovered = await llm_prompt([make_feed_post(title="Title")], options=options)

    assert failed[0].extras["title_ua"] == "Title"
    assert recovered[0].extras["title_ua"] == "Заголовок"


async def test_on_error_value_is_not_cached(
    make_feed_post, make_llm_prompt_options, stub_llm, cache  # noqa: U100
):
    stub_llm.set_status(400)
    options = make_llm_prompt_options(
        source_field="title", target_field="title_ua", on_error_value="N/A"
    )
    failed = await llm_prompt([make_feed_post(title="Title")], options=options)
    stub_llm.set_response("Заголовок")

    recovered = await llm_prompt([make_feed_post(title="Title")], options=options)

    assert failed[0].extras["title_ua"] == "N/A"
    assert recovered[0].extras["title_ua"] == "Заголовок"


async def test_broken_cache_does_not_break_translation(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    monkeypatch.setattr(
        llm_prompt_module, "get_llm_cache_storage", lambda: BrokenCache()
    )
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    first = await llm_prompt([make_feed_post(title="Title")], options=options)
    second = await llm_prompt([make_feed_post(title="Title")], options=options)

    assert first[0].extras["title_ua"] == "Заголовок"
    assert second[0].extras["title_ua"] == "Заголовок"
    assert len(stub_llm.requests) == 2


async def test_different_api_endpoint_is_run_separately(
    make_feed_post,
    make_llm_prompt_options,
    make_stub_llm,
    cache,  # noqa: U100
):
    first_provider = make_stub_llm(base_url="https://first.test/v1/")
    first_provider.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    await llm_prompt([make_feed_post(title="Title")], options=options)
    second_provider = make_stub_llm(base_url="https://second.test/v1/")
    second_provider.set_response("Заголовок")

    await llm_prompt([make_feed_post(title="Title")], options=options)

    assert len(first_provider.requests) == 1
    assert len(second_provider.requests) == 1


async def test_cache_that_cannot_be_resolved_fails_the_call_instead_of_being_ignored(
    make_feed_post, make_llm_prompt_options, stub_llm, monkeypatch
):
    def broken_get_llm_cache_storage():
        raise RuntimeError("misconfigured")

    monkeypatch.setattr(
        llm_prompt_module, "get_llm_cache_storage", broken_get_llm_cache_storage
    )
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(
        source_field="title", target_field="title_ua", on_error_value="N/A"
    )

    result = await llm_prompt([make_feed_post(title="Title")], options=options)

    assert result[0].extras["title_ua"] == "N/A"
    assert stub_llm.requests == []


@pytest.mark.parametrize(
    "ttl_days, expected_requests",
    [
        (None, 2),  # the default is 7 days
        ("30", 1),
        ("1", 2),
    ],
)
async def test_cache_ttl_is_configurable(
    make_feed_post,
    make_llm_prompt_options,
    stub_llm,
    cache,  # noqa: U100
    monkeypatch,
    ttl_days,
    expected_requests,
):
    if ttl_days is not None:
        monkeypatch.setenv("LLM_CACHE_TTL_DAYS", ttl_days)
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    await llm_prompt([make_feed_post(title="Title")], options=options)
    eight_days_later = time.time() + 8 * 24 * 60 * 60
    monkeypatch.setattr(llm_prompt_module, "_wall_time", lambda: eight_days_later)
    # the purge isn't due, so it's the age check on reading that decides
    monkeypatch.setattr(llm_prompt_module, "_last_cache_purge", eight_days_later)

    await llm_prompt([make_feed_post(title="Title")], options=options)

    assert len(stub_llm.requests) == expected_requests


@pytest.mark.parametrize("ttl_days", ["0", "0.01", "-1", "junk", "nan", "inf"])
async def test_invalid_cache_ttl_falls_back_to_the_default(
    make_feed_post,
    make_llm_prompt_options,
    stub_llm,
    cache,  # noqa: U100
    monkeypatch,
    ttl_days,
):
    monkeypatch.setenv("LLM_CACHE_TTL_DAYS", ttl_days)
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    await llm_prompt([make_feed_post(title="Title")], options=options)
    a_day_later = time.time() + 24 * 60 * 60
    monkeypatch.setattr(llm_prompt_module, "_wall_time", lambda: a_day_later)
    monkeypatch.setattr(llm_prompt_module, "_last_cache_purge", a_day_later)

    await llm_prompt([make_feed_post(title="Title")], options=options)

    # still inside the default 7 days
    assert len(stub_llm.requests) == 1


async def test_expired_answers_are_deleted(
    make_feed_post,
    make_llm_prompt_options,
    stub_llm,
    cache,  # noqa: U100
    db_path,
    monkeypatch,
):
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    await llm_prompt([make_feed_post(title="Title 1")], options=options)
    eight_days_later = time.time() + 8 * 24 * 60 * 60
    monkeypatch.setattr(llm_prompt_module, "_wall_time", lambda: eight_days_later)

    await llm_prompt([make_feed_post(title="Title 2")], options=options)

    assert _count_cached_answers(db_path) == 1


async def test_expired_answers_are_deleted_once_in_a_while(
    make_feed_post,
    make_llm_prompt_options,
    stub_llm,
    cache,
    db_path,
    monkeypatch,
):
    stub_llm.set_response("Заголовок")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")
    now = time.time()
    monkeypatch.setattr(llm_prompt_module, "_wall_time", lambda: now)
    await llm_prompt([make_feed_post(title="Title 1")], options=options)
    await cache.set("old", "answer", created_at=now - 8 * 24 * 60 * 60)

    await llm_prompt([make_feed_post(title="Title 2")], options=options)

    # the purge has already run for this hour, the old answer stays until the next one
    assert _count_cached_answers(db_path) == 3
