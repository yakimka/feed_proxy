import datetime
import logging
import os

import peewee as pw

from feed_proxy.config import BASE_DIR


logger = logging.getLogger(__name__)

database = pw.SqliteDatabase(os.path.join(BASE_DIR, 'feed_proxy.db'))


class Processed(pw.Model):
    source_name = pw.CharField(max_length=256)
    post_id = pw.CharField(max_length=256)
    receiver_id = pw.CharField(max_length=32)
    time = pw.DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = database
        order_by = ['-time']
        indexes = (
            # create a unique on source_name/post_id/receiver_id
            (('source_name', 'post_id', 'receiver_id'), True),
        )


MODELS = [Processed]


def init():
    if not database.get_tables():
        logger.info('No tables, creating')
        _create_tables()


def _create_tables():
    with database:
        database.create_tables(MODELS)


def is_source_new(source_name):
    return Processed.select().where(Processed.source_name == source_name).count() == 0


def is_source_new_for_receiver(source_name, receiver_id):
    return Processed.select().where(Processed.source_name == source_name,
                                    Processed.receiver_id == receiver_id).count() == 0


def is_post_processed_for_receiver(source_name, post_id, receiver_id):
    return Processed.select().where(Processed.source_name == source_name,
                                    Processed.post_id == post_id,
                                    Processed.receiver_id == receiver_id).count() > 0


def create_processed_entry(source_name, post_id, receiver_id):
    return Processed.create(source_name=source_name, post_id=post_id, receiver_id=receiver_id)
