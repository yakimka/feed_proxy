from collections.abc import Iterable
from typing import Any

from feed_proxy.entities import Message, Modifier, Source, Stream
from feed_proxy.storage import OutboxItem


class ObjectMother:
    def source(
        self,
        id: str = "guido-blog",
        fetcher_type: str = "fetch_text",
        fetcher_options: dict[str, Any] | None = None,
        parser_type: str = "rss",
        parser_options: dict[str, Any] | None = None,
        tags: Iterable[str] = (),
        streams: Iterable[Stream] | None = None,
    ) -> Source:
        if streams is None:
            streams = [self.stream()]
        return Source(
            id=id,
            fetcher_type=fetcher_type,
            fetcher_options=fetcher_options or {},
            parser_type=parser_type,
            parser_options=parser_options or {},
            tags=list(tags),
            streams=list(streams),
        )

    def stream(
        self,
        receiver_type: str = "console_printer",
        receiver_options: dict[str, Any] | None = None,
        intervals: Iterable[str] = (),
        squash: bool = True,
        message_template: str = "${title}\n${url}",
        modifiers: Iterable[Modifier] = (),
    ) -> Stream:
        return Stream(
            receiver_type=receiver_type,
            receiver_options=receiver_options or {},
            intervals=list(intervals),
            squash=squash,
            message_template=message_template,
            modifiers=list(modifiers),
        )

    def modifier(self, type: str, options: dict[str, Any]) -> Modifier:
        return Modifier(
            type=type,
            options=options,
        )

    def outbox_item(
        self,
        id: str = "event_id",
        messages: Iterable[Message] | None = None,
        stream: Stream | None = None,
    ) -> OutboxItem:
        if messages is None:
            messages = [self.message()]
        if stream is None:
            stream = self.stream()
        return OutboxItem(
            id=id,
            messages=list(messages),
            stream=stream,
        )

    def message(
        self,
        post_id: str = "post_id",
        template: str = "${title}\n${url}",
        template_kwargs: dict[str, Any] | None = None,
    ) -> Message:
        if template_kwargs is None:
            template_kwargs = {"title": "Post title", "url": "https://post.url"}
        return Message(
            post_id=post_id,
            template=template,
            template_kwargs=template_kwargs,
        )
