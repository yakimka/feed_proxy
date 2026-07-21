from feed_proxy.handlers.modifiers.regex_replace import regex_replace


async def test_replaces_matched_part_of_field(
    make_feed_post, make_regex_replace_options
):
    post = make_feed_post(description="keep me<p>drop me</p>")
    options = make_regex_replace_options(field="description", pattern="<p>drop me</p>")

    result = await regex_replace([post], options=options)

    assert result[0].description == "keep me"


async def test_replacement_supports_group_refs(
    make_feed_post, make_regex_replace_options
):
    post = make_feed_post(description="Hello, World!")
    options = make_regex_replace_options(
        field="description", pattern=r"Hello, (\w+)!", replacement=r"Hi, \1."
    )

    result = await regex_replace([post], options=options)

    assert result[0].description == "Hi, World."


async def test_dotall_lets_dot_match_newlines(
    make_feed_post, make_regex_replace_options
):
    post = make_feed_post(description="keep\n<p>drop\nme</p>")
    options = make_regex_replace_options(
        field="description", pattern="<p>.*</p>", dotall=True
    )

    result = await regex_replace([post], options=options)

    assert result[0].description == "keep\n"


async def test_without_dotall_dot_does_not_match_newlines(
    make_feed_post, make_regex_replace_options
):
    post = make_feed_post(description="keep\n<p>drop\nme</p>")
    options = make_regex_replace_options(field="description", pattern="<p>.*</p>")

    result = await regex_replace([post], options=options)

    assert result[0].description == "keep\n<p>drop\nme</p>"


async def test_no_match_leaves_field_unchanged(
    make_feed_post, make_regex_replace_options
):
    post = make_feed_post(description="nothing to drop here")
    options = make_regex_replace_options(field="description", pattern="<p>drop me</p>")

    result = await regex_replace([post], options=options)

    assert result[0].description == "nothing to drop here"


async def test_none_field_value_is_treated_as_empty_string(
    make_feed_post, make_regex_replace_options
):
    post = make_feed_post(comments_url=None)
    options = make_regex_replace_options(field="comments_url", pattern="x")

    result = await regex_replace([post], options=options)

    assert result[0].comments_url == ""


async def test_replaces_matches_in_every_post_of_the_batch(
    make_feed_post, make_regex_replace_options
):
    first = make_feed_post(post_id="1", description="a<p>x</p>")
    second = make_feed_post(post_id="2", description="b<p>x</p>")
    options = make_regex_replace_options(field="description", pattern="<p>x</p>")

    result = await regex_replace([first, second], options=options)

    assert [post.description for post in result] == ["a", "b"]
