import asyncio
from pathlib import Path

from feed_proxy.configuration import Modifier, Source, load_configuration
from feed_proxy.entities import Post
from feed_proxy.handlers import HandlerType, get_handler_by_name


async def fetch_text(source: Source) -> str:
    fetcher = get_handler_by_name(
        type=HandlerType.fetchers.value,
        name=source.fetcher_type,
        options=source.fetcher_options,
    )
    return await fetcher()


async def parse_posts(source: Source, text: str) -> list[Post]:
    parser = get_handler_by_name(
        name=source.parser_type,
        type=HandlerType.parsers.value,
        options=source.parser_options,
    )
    return await parser(text)


async def apply_modifiers_to_posts(
    modifiers: list[Modifier], posts: list[Post]
) -> list[Post]:
    for modifier in modifiers:
        modifier_func = get_handler_by_name(
            name=modifier.type,
            type=HandlerType.modifiers.value,
            options=modifier.options,
        )
        posts = await modifier_func(posts)
    return posts


async def fetch_posts_from_source(source: Source) -> list[Post]:
    text = await fetch_text(source)
    posts = await parse_posts(source, text)
    for stream in source.streams:
        return await apply_modifiers_to_posts(stream.modifiers, posts)


if __name__ == "__main__":
    path = Path(__file__).parent.parent / "config"
    sources = load_configuration(path)

    async def main():
        res = await fetch_posts_from_source(sources[0])
        print(res)

    asyncio.run(main())
