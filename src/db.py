import peewee

_db = peewee.SqliteDatabase('feed_proxy.db')
_db_created = False


class Sended(peewee.Model):
    url = peewee.CharField(max_length=2048)
    post_id = peewee.CharField(max_length=256)
    message_type = peewee.DateField()
    message_id = peewee.DateField()
    created = peewee.DateTimeField()

    class Meta:
        database = _db


def _init():
    if not _db.get_tables():
        _db_created = True
        _create_tables()


def _create_tables():
    with _db:
        _db.create_tables([Sended])


_init()
