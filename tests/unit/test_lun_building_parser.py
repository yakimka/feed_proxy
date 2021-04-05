from feed_proxy import parsers
from feed_proxy.schema import Author

parser_func = parsers.lun_building_parser

PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Title</title>
</head>
<body>
<div>
    <a href="/uk/жк-ідеаліст-київ" class="card-media">
        <img alt="Клубний будинок Ідеаліст">
    </a>
</div>
<div>
    <a href="/uk/клубний-будинок-m29-київ" class="card-media">
        <img alt="Клубний будинок M29">
    </a>
</div>
</body>
</html>
'''


def test_piter_book_parser(source, factory):
    parsed_posts = parser_func(source, PAGE)

    assert [factory.post(author='Unknown',
                         authors=(Author(name='Unknown'),),
                         id='https://lun.ua/uk/жк-ідеаліст-київ',
                         url='https://lun.ua/uk/жк-ідеаліст-київ',
                         summary='',
                         title='Клубний будинок Ідеаліст',
                         source=source,
                         tags=(),
                         attachments=(),
                         published=None, ),
            factory.post(author='Unknown',
                         authors=(Author(name='Unknown'),),
                         id='https://lun.ua/uk/клубний-будинок-m29-київ',
                         url='https://lun.ua/uk/клубний-будинок-m29-київ',
                         summary='',
                         title='Клубний будинок M29',
                         source=source,
                         tags=(),
                         attachments=(),
                         published=None, )] == parsed_posts
