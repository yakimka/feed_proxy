import pytest

from feed_proxy import db
from feed_proxy.db import Processed
from feed_proxy.proxies import Proxy


@pytest.fixture
def proxy(config_storage):
    """Proxy instance created from "config_storage" fixture
    """

    return Proxy(config_storage)


POSTS_COUNT = 10


@pytest.fixture
def mock_parser(request, mocker, post_factory):
    """Patch "RSSFeedParser.parse" method with function that returns
    parsed posts with "post_factory".
    Number of posts can be set with param (by default 10)
    """

    posts_count = getattr(request, 'param', POSTS_COUNT)

    def mock_parse(self):
        self.posts = [post_factory({'id': i}) for i in range(posts_count)]

    return mocker.patch('feed_proxy.parsers.RSSFeedParser.parse', mock_parse)


def test_download_posts(proxy, mock_parser):
    proxy.download_posts()
    for source_settings in proxy.sources_settings.values():
        assert len(source_settings.parser.posts) == POSTS_COUNT


@pytest.fixture(params=[
    ['-1001234567890'],
    ['-1001234567890', '-1001234567891'],
    ['-1001234567890', '-1001234567891', '-1001234567892'],
    ['-1001234567890', '-1001234567891', '-1001234567892', '-1001234567893'],
])
def config_storage_with_receivers_params(request, config_storage):
    """config_storage with different number of chats (params)
    """
    config_storage.sources['example source'].receivers = request.param
    return config_storage


class BaseProxyTest:
    source_name = 'example source'

    @pytest.fixture(autouse=True)
    def _setup(self, config_storage, mock_parser,
              mocked_tg_sender_class, mocker, monkeypatch):
        self.config_storage = config_storage
        self.source_settings = self.config_storage.sources[self.source_name]
        self.mocked_send = mocker.MagicMock()
        monkeypatch.setattr(mocked_tg_sender_class, 'send', self.mocked_send)
        self.source_settings.sender_class = mocked_tg_sender_class
        self.receivers = self.source_settings.receivers
        self.proxy = Proxy(self.config_storage)

    def create_proxy_and_run(self, messages_stored=None):
        if messages_stored:
            self.config_storage.messages_stored = messages_stored
        self.proxy = Proxy(self.config_storage)

        self.proxy.download_posts()

    def create_processed_entry_for_post(self, post_index):
        self.proxy.download_posts()
        post = self.source_settings.parser.posts[post_index]
        for receiver_id in self.receivers:
            db.create_processed_entry(self.source_name, post.id, receiver_id)

    def count_processed(self, *eq_pairs):
        return Processed.select().where(
            *[getattr(Processed, field) == value for field, value in eq_pairs]
        ).count()


class TestCollectMessages(BaseProxyTest):
    @pytest.mark.parametrize('messages_stored', [
        1, 3, 5, 7, 10, 12, 15
    ])
    @pytest.mark.parametrize('run_collect_twice', [True, False])
    def test_create_processed_entries_if_source_is_new(self, messages_stored, run_collect_twice):
        self.create_proxy_and_run(messages_stored)
        if run_collect_twice:
            self.proxy.collect_messages()

        self.check_processed_in_db()
        # no messages was collected
        assert len(self.proxy.messages) == 0

    def create_proxy_and_run(self, messages_stored=None):
        super().create_proxy_and_run(messages_stored)
        self.proxy.collect_messages()

    def check_processed_in_db(self, expected=None):
        __tracebackhide__ = True

        for receiver_id in self.source_settings.receivers:
            processed = self.count_processed(('receiver_id', receiver_id),
                                             ('source_name', self.source_name))

            if expected is None:
                expected = min([self.config_storage.messages_stored, POSTS_COUNT])

            assert processed == expected

    @pytest.mark.parametrize('new_messages_count', [
        0, 1, 2, 4, 8
    ])
    def test_posts_processed_and_unprocessed_together(self, new_messages_count):
        self.create_processed_entry_for_post(new_messages_count)

        self.proxy.collect_messages()

        assert len(self.proxy.messages) == new_messages_count * len(self.receivers)

    @pytest.mark.parametrize('mock_parser', [0], indirect=True)
    def test_no_posts(self, mock_parser):
        self.create_proxy_and_run()

        self.check_processed_in_db(0)
        # no messages was collected
        assert len(self.proxy.messages) == 0


class TestSendMessages(BaseProxyTest):
    def test_messages(self):
        self.create_processed_entry_for_post(-1)
        self.create_proxy_and_run()

        self.mocked_send.call_count = (POSTS_COUNT - 1) * len(self.receivers)
        for post, processed in self.processed_posts():
            assert processed == 1

    def create_proxy_and_run(self, messages_stored=None):
        super().create_proxy_and_run(messages_stored)
        self.proxy.collect_messages()
        self.proxy.send_messages()

    def processed_posts(self):
        for receiver_id in self.source_settings.receivers:
            for post in self.source_settings.parser.posts:
                processed = self.count_processed(('receiver_id', receiver_id),
                                                 ('source_name', self.source_name),
                                                 ('post_id', post.id))
                yield post, processed


class TestRun(BaseProxyTest):
    def test_run(self):
        self.create_processed_entry_for_post(-1)
        self.proxy.run()

        self.mocked_send.call_count = (POSTS_COUNT - 1) * len(self.receivers)


def test_get_message_text(config_storage, post):
    msg = Proxy.get_message_text(config_storage.sources['example source'], post)

    assert msg == '<a href="https://example.com/post">Some title</a>\n\n'
