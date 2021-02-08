from feed_proxy import parsers
from feed_proxy.schema import Author

parser_func = parsers.github_search_parser

GITHUB_SEARCH_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Title</title>
</head>
<body>
<div data-hydro-click="{&quot;payload&quot;:{&quot;result&quot;:{&quot;model_name&quot;
:&quot;Repository&quot;,&quot;url&quot;:&quot;https://github.com/user/project&quot;}}}"></div>
<div data-hydro-click="{}"></div>
</body>
</html>
'''


def test_parse_search_page(source, factory):
    parsed_posts = parser_func(source, GITHUB_SEARCH_PAGE)

    assert [factory.post(
        author='user',
        authors=(Author(name='user'),),
        id='https://github.com/user/project',
        url='https://github.com/user/project',
        summary='',
        title='user/project',
        source=source,
        tags=(),
        attachments=(),
        published=None,
    )] == parsed_posts
