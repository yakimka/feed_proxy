from feed_proxy.handlers.modifiers.strip_html import strip_html


async def test_strips_tags_and_joins_text_with_separator(
    make_feed_post, make_strip_html_options
):
    post = make_feed_post(description="<p>Hello</p><p>World</p>")
    options = make_strip_html_options(field="description")

    result = await strip_html([post], options=options)

    assert result[0].description == "Hello World"


async def test_decodes_html_entities(make_feed_post, make_strip_html_options):
    post = make_feed_post(description="Lorem ipsum [&#8230;]")
    options = make_strip_html_options(field="description")

    result = await strip_html([post], options=options)

    assert result[0].description == "Lorem ipsum […]"


async def test_custom_separator(make_feed_post, make_strip_html_options):
    post = make_feed_post(description="<p>Hello</p><p>World</p>")
    options = make_strip_html_options(field="description", separator="\n")

    result = await strip_html([post], options=options)

    assert result[0].description == "Hello\nWorld"


async def test_plain_text_is_left_unchanged(make_feed_post, make_strip_html_options):
    post = make_feed_post(description="Just plain text")
    options = make_strip_html_options(field="description")

    result = await strip_html([post], options=options)

    assert result[0].description == "Just plain text"


async def test_strips_tags_in_every_post_of_the_batch(
    make_feed_post, make_strip_html_options
):
    first = make_feed_post(post_id="1", description="<p>a</p>")
    second = make_feed_post(post_id="2", description="<p>b</p>")
    options = make_strip_html_options(field="description")

    result = await strip_html([first, second], options=options)

    assert [post.description for post in result] == ["a", "b"]
