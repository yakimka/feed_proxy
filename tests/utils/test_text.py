import pytest

from feed_proxy.utils.text import normalize_dedup_value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Hello   World  ", "hello world"),
        ("Foo\tBar\nBaz", "foo bar baz"),
        ("ПРИВЕТ Мир", "привет мир"),
        ("Ёжик", "ёжик"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_dedup_value(value, expected):
    result = normalize_dedup_value(value)

    assert result == expected
