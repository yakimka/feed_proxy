from datetime import datetime
from typing import List, Union

from sqlalchemy import (Column, DateTime, Integer, MetaData, String, Table, UniqueConstraint, and_,
                        exists)
from sqlalchemy.engine import Connection

from feed_proxy.schema import Source, Post

convention = {  # pragma: no cover
    'all_column_names': lambda constraint, table: '_'.join([
        column.name for column in constraint.columns.values()
    ]),
    'ix': 'ix__%(table_name)s__%(all_column_names)s',
    'uq': 'uq__%(table_name)s__%(all_column_names)s',
    'ck': 'ck__%(table_name)s__%(constraint_name)s',
    'fk': 'fk__%(table_name)s__%(all_column_names)s__%(referred_table_name)s',
    'pk': 'pk__%(table_name)s'
}
metadata = MetaData(naming_convention=convention)

processed_table = Table(
    'feed_proxy_processed',
    metadata,

    Column('id', Integer, primary_key=True),
    Column('source_name', String, nullable=False),
    Column('post_id', String, nullable=False),
    Column('created', DateTime, default=datetime.now, nullable=False),

    UniqueConstraint('source_name', 'post_id', ),
)


def is_new_source(conn: Connection, source: Source):
    query = processed_table.select().where(processed_table.c.source_name == source.name)
    query_e = exists(query)

    return not conn.execute(query_e.select()).scalar()


def create_processed(conn: Connection, posts: Union[Post, List[Post]]):
    if isinstance(posts, Post):
        posts = [posts]
    return conn.execute(processed_table.insert(), [
        {'source_name': post.source.name, 'post_id': post.id} for post in posts
    ])


def is_post_processed(conn: Connection, post: Post):
    query = processed_table.select().where(and_(
        processed_table.c.source_name == post.source.name,
        processed_table.c.post_id == post.id,
    ))
    query_e = exists(query)

    return conn.execute(query_e.select()).scalar()
