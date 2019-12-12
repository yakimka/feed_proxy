import time

from feed_proxy import db
from feed_proxy.utils import class_logger


class Proxy:
    def __init__(self, config_storage):
        self.logger = class_logger(__name__, self.__class__.__name__)

        self.messages_stored = config_storage.messages_stored
        self.sources_settings = config_storage.sources
        self.messages = []

    def run(self):
        self.download_posts()
        self.collect_messages()
        self.send_messages()

    def download_posts(self):
        self.logger.info('Posts download started')
        for source_settings in self.sources_settings.values():
            source_settings.parser.parse()
        self.logger.info('Posts download ended')

    def collect_messages(self):
        self.logger.info('Collect messages started')
        messages = []
        for source_settings, receiver_id in self._receivers():
            self.logger.info(f'Collect messages for "{source_settings.name}" started')
            created = self._process_entries_if_source_is_new(source_settings, receiver_id)
            if created:
                self.logger.info(f'"{source_settings.name}" is new. Skip')
                continue

            messages_from_source = []
            for post in source_settings.parser.posts:
                # if some of the posts is already processed - go to next receiver
                if db.is_post_processed_for_receiver(source_settings.name, post.id, receiver_id):
                    self.logger.info(f'"{post.title}" already processed. Skip "{source_settings.name}"')
                    break

                message_text = self.get_message_text(source_settings, post)
                messages_from_source.append((source_settings.name, receiver_id, message_text,
                                 post, source_settings.get_send_kwargs()))

            self.logger.info(f'Collected {len(messages_from_source)} messages from "{source_settings.name}"')
            messages.extend(messages_from_source)

        # older messages first
        messages.reverse()
        self.logger.info(f'Collected {len(messages)} messages')
        self.messages = messages

    def _receivers(self):
        for source_settings in self.sources_settings.values():
            for receiver_id in source_settings.receivers:
                yield source_settings, receiver_id

    def _process_entries_if_source_is_new(self, source_settings, receiver_id):
        created = 0
        new_for_receiver = db.is_source_new_for_receiver(source_settings.name, receiver_id)
        if new_for_receiver:
            # reversed for create older posts first
            for post in reversed(source_settings.parser.posts[:self.messages_stored]):
                created = db.create_processed_entry(source_settings.name, post.id, receiver_id)

        return created

    @classmethod
    def get_message_text(cls, source_settings, post):
        post_item = source_settings.post_template.format(**post.to_dict())
        tags_to_string = source_settings.sender_class.tags_to_string
        add_parsed_tags = source_settings.add_parsed_tags

        return source_settings.layout_template.format(
            message=post_item,
            source_tags=tags_to_string(source_settings.tags),
            post_tags=tags_to_string(post.tags) if add_parsed_tags else ''
        )

    def send_messages(self):
        for source_name, receiver, message, post, send_kwargs in self.messages:
            # send method
            source_settings = self.sources_settings[source_name]
            sender = source_settings.sender_class(receiver, message, post.attachments,
                                                  **send_kwargs)
            self.logger.info(f'Sending message from "{source_name}" to "{receiver}"')
            sender.send()
            db.create_processed_entry(source_settings.name, post.id, receiver)
            time.sleep(0.15)
