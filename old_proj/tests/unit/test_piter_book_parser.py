from feed_proxy import parsers
from feed_proxy.schema import Author

parser_func = parsers.piter_book_parser

PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Title</title>
</head>
<body>
<div class="products-list">
    <div class="book-block">
        <a href="/book-url">
            <span class="author">&nbsp;</span>
            <span class="title">Программируй & типизируй</span>
        </a>
    </div>
    <div class="book-block">
        <a href="/book-url2">
            <span class="author">Имя автора</span>
            <span class="title">Имя книги</span>
        </a>
    </div>
</div>
</body>
</html>
'''


def test_piter_book_parser(source, factory):
    parsed_posts = parser_func(source, PAGE)

    assert [factory.post(author='Unknown',
                         authors=(Author(name='Unknown'),),
                         id='https://www.piter.com/book-url',
                         url='https://www.piter.com/book-url',
                         summary='',
                         title='Программируй & типизируй',
                         source=source,
                         tags=(),
                         attachments=(),
                         published=None, ),
            factory.post(author='Имя автора',
                         authors=(Author(name='Имя автора'),),
                         id='https://www.piter.com/book-url2',
                         url='https://www.piter.com/book-url2',
                         summary='',
                         title='Имя книги',
                         source=source,
                         tags=(),
                         attachments=(),
                         published=None, )] == parsed_posts
