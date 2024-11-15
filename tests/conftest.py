import pytest

from feed_proxy.test import ObjectMother

pytest_plugins = [
    "picodi.integrations._pytest",
    "picodi.integrations._pytest_asyncio",
]


@pytest.fixture()
def mother() -> ObjectMother:
    return ObjectMother()
