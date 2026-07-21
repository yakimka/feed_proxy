import pytest

from feed_proxy.handlers.pre_send_processors import llm_prompt as llm_prompt_module
from feed_proxy.handlers.pre_send_processors.llm_prompt import llm_prompt


@pytest.fixture(autouse=True)
def _reset_client_cache(monkeypatch):
    monkeypatch.setattr(llm_prompt_module, "_client", None)


async def test_happy_path(make_feed_post, make_llm_prompt_options, stub_gemini):
    stub_gemini.set_response("Заголовок")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Заголовок"


async def test_arbitrary_prompt_not_related_to_translation(
    make_feed_post, make_llm_prompt_options, stub_gemini
):
    stub_gemini.set_response("Short summary.")
    post = make_feed_post(extras={"description": "Long article text..."})
    options = make_llm_prompt_options(
        source_field="description",
        target_field="summary",
        prompt="Summarize in one sentence.\n\nText:\n{source}",
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["summary"] == "Short summary."


async def test_prompt_with_unrelated_braces_does_not_break_substitution(
    make_feed_post, make_llm_prompt_options, stub_gemini
):
    stub_gemini.set_response("ok")
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(
        source_field="title",
        target_field="title_ua",
        prompt='Return JSON like {"a": 1}. Text:\n{source}',
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "ok"
    _, kwargs = stub_gemini.aio.models.generate_content.call_args
    assert kwargs["contents"] == 'Return JSON like {"a": 1}. Text:\nTitle'


async def test_reads_from_extras_when_chained(
    make_feed_post, make_llm_prompt_options, stub_gemini
):
    stub_gemini.set_response("Опис")
    post = make_feed_post(extras={"description_clean": "Description"})
    options = make_llm_prompt_options(
        source_field="description_clean", target_field="description_ua"
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["description_ua"] == "Опис"
    stub_gemini.aio.models.generate_content.assert_awaited_once()
    _, kwargs = stub_gemini.aio.models.generate_content.call_args
    assert "Description" in kwargs["contents"]


async def test_extras_take_precedence_over_attribute(
    make_feed_post, make_llm_prompt_options, stub_gemini
):
    stub_gemini.set_response("translated")
    post = make_feed_post(title="Attribute value", extras={"title": "Extras value"})
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    await llm_prompt([post], options=options)

    _, kwargs = stub_gemini.aio.models.generate_content.call_args
    assert "Extras value" in kwargs["contents"]
    assert "Attribute value" not in kwargs["contents"]


async def test_empty_source_skips_prompt(
    make_feed_post, make_llm_prompt_options, stub_gemini
):
    post = make_feed_post(title="")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    stub_gemini.aio.models.generate_content.assert_not_awaited()
    assert result[0].extras["title_ua"] == ""


@pytest.mark.parametrize(
    "exc", [Exception("boom"), RuntimeError("boom"), KeyError("boom")]
)
async def test_error_falls_back_to_source_text_by_default(
    make_feed_post, make_llm_prompt_options, stub_gemini, exc
):
    stub_gemini.set_exception(exc)
    failing_post = make_feed_post(post_id="1", title="Title 1")
    next_post = make_feed_post(post_id="2", title="Title 2")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([failing_post, next_post], options=options)

    assert result[0].extras["title_ua"] == "Title 1"
    assert result[1].extras["title_ua"] == "Title 2"


async def test_error_uses_custom_on_error_value(
    make_feed_post, make_llm_prompt_options, stub_gemini
):
    stub_gemini.set_exception(RuntimeError("boom"))
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(
        source_field="title", target_field="title_ua", on_error_value="Уупс, нешмогла"
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Уупс, нешмогла"


async def test_empty_response_text_falls_back_to_source_text(
    make_feed_post, make_llm_prompt_options, stub_gemini
):
    stub_gemini.set_response(None)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Title"


async def test_missing_api_key_falls_back_to_source_text(
    make_feed_post, make_llm_prompt_options, monkeypatch
):
    monkeypatch.setattr(llm_prompt_module, "_client", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(source_field="title", target_field="title_ua")

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "Title"


async def test_missing_api_key_uses_custom_on_error_value(
    make_feed_post, make_llm_prompt_options, monkeypatch
):
    monkeypatch.setattr(llm_prompt_module, "_client", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    post = make_feed_post(title="Title")
    options = make_llm_prompt_options(
        source_field="title", target_field="title_ua", on_error_value="N/A"
    )

    result = await llm_prompt([post], options=options)

    assert result[0].extras["title_ua"] == "N/A"
