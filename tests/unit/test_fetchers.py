import pytest

from feed_proxy import fetchers

pytestmark = [pytest.mark.usefixtures('example_feed_server')]


@pytest.mark.asyncio
async def test_fetch_text_for_source(source):
    res_source, status, text = await fetchers.fetch_text_for_source(source)

    assert 200 == status
    assert 'aiohttp 3.7.2 release' in text
    assert source == res_source


@pytest.mark.asyncio
async def test_fetch_text():
    res = await fetchers.fetch_sources()
    source, status, text = res[0]

    assert 200 == status
    assert 'aiohttp 3.7.2 release' in text
    assert 'aiohttp releases' == source.name


@pytest.mark.asyncio
async def test_fetch_error():
    res = await fetchers.fetch_sources()
    source, status, text = res[1]

    assert 500 == status
    assert 'Server error' == text
    assert 'server error feed' == source.name
