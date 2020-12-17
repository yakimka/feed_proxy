import logging
import os
from argparse import ArgumentParser

from sqlalchemy import create_engine

from feed_proxy import handlers
from feed_proxy.conf import settings
from feed_proxy.fetchers import fetch_sources
from feed_proxy.parsers import parse_posts
from feed_proxy.utils import DEFAULT_DB_URL, validate_file

parser = ArgumentParser()

group = parser.add_argument_group('Main options')
group.add_argument('sources_file',
                   type=lambda x: validate_file(parser, x),
                   help='Path to sources ini file')
group.add_argument('--db-url', default=os.getenv(f'{settings.ENV_PREFIX}DB_URL', DEFAULT_DB_URL),
                   help=f'Database URL [env var: {settings.ENV_PREFIX}DB_URL]')
group.add_argument('--proxy-bot-url', default='http://localhost:8081',
                   help='Proxy bot for upload large files URL URL [http://localhost:8081]')

group = parser.add_argument_group('Logging options')
group.add_argument('--log-level', default='info',
                   choices=('debug', 'info', 'warning', 'error', 'fatal'))

HANDLERS = [
    handlers.FilterNewSource,
    handlers.FilterProcessed,
    handlers.SendToTelegram,
]


def main():
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper())
    settings.configure(args.sources_file, PROXY_BOT_URL=args.proxy_bot_url)

    engine = create_engine(args.db_url)
    with engine.connect() as conn:
        fetched = fetch_sources()
        parsed = parse_posts(fetched)

        result = HANDLERS[0](conn)(parsed)
        for handler in HANDLERS[1:]:
            result = handler(conn)(result)


if __name__ == '__main__':
    main()
