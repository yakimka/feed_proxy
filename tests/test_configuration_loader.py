from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from feed_proxy.configuration import (
    Configuration,
    LoadConfigurationError,
    load_configuration,
)
from feed_proxy.handlers import (
    HandlerOptions,
    HandlerType,
    InitHandlersError,
    register_handler,
)

if TYPE_CHECKING:
    from feed_proxy.entities import Message


@pytest.fixture()
def run_sut():
    def _run_sut(config: dict[str, Any]) -> Configuration:
        return load_configuration(config)

    return _run_sut


@pytest.fixture()
def minimal_sources_block() -> dict[str, Any]:
    return {
        "sources": {
            "some-source": {
                "fetcher_type": "fetch_text",
                "fetcher_options": {
                    "url": "https://yakimka.me/rss.xml",
                },
                "parser_type": "rss",
                "streams": [
                    {
                        "receiver_type": "console_printer",
                        "intervals": ["*/10 * * * *"],
                        "message_template": "${title}\n${url}",
                    }
                ],
            }
        }
    }


@dataclass
class DummyReceiverClassOptions(HandlerOptions):
    name: str
    some_number: int


@dataclass
class DummyReceiverOptions(HandlerOptions):
    number: int
    another_number: int = 12


@register_handler(
    type=HandlerType.receivers,
    name="dummy_receiver",
    init_options=DummyReceiverClassOptions,
    options=DummyReceiverOptions,
)
class DummyReceiver:
    def __init__(self, options: DummyReceiverClassOptions):
        self.name = options.name
        self.some_number = options.some_number

    async def __call__(
        self, messages: list[Message], *, options: DummyReceiverOptions
    ) -> None:
        return


def test_raise_error_if_sources_block_is_not_present(run_sut):
    error_msg = "Configuration must contain filled 'sources' block"
    with pytest.raises(LoadConfigurationError, match=error_msg):
        run_sut({"some_field": {}})


def test_load_minimal_configuration(run_sut, minimal_sources_block):
    result = run_sut(minimal_sources_block)

    assert len(result.sources) == 1
    assert not result.subhandlers


def test_load_configuration_with_subhandlers(run_sut):
    configuration_with_subhandlkers = {
        "handlers": {
            "receivers": {
                "my-dummy-receiver": {
                    "type": "dummy_receiver",
                    "init_options": {
                        "name": "dummy name",
                        "some_number": 42,
                    },
                }
            }
        },
        "sources": {
            "some-source": {
                "fetcher_type": "fetch_text",
                "fetcher_options": {
                    "url": "https://yakimka.me/rss.xml",
                },
                "parser_type": "rss",
                "parser_options": {},
                "streams": [
                    {
                        "receiver_type": "my-dummy-receiver",
                        "receiver_options": {"number": 42},
                        "intervals": ["*/10 * * * *"],
                        "message_template": "${title}\n${url}",
                    }
                ],
            }
        },
    }

    result = run_sut(configuration_with_subhandlkers)

    assert len(result.sources) == 1
    assert result.sources[0].id == "some-source"
    assert len(result.sources[0].streams) == 1
    assert result.sources[0].streams[0].receiver_type == "my-dummy-receiver"


@pytest.fixture()
def configuration_for_typechecking():
    return {
        "handlers": {
            "receivers": {
                "my-dummy-receiver": {
                    "type": "dummy_receiver",
                    "init_options": {
                        "name": "dummy name",
                        "some_number": 42,
                    },
                }
            }
        },
        "sources": {
            "some-source": {
                "fetcher_type": "fetch_text",
                "fetcher_options": {
                    "url": "https://yakimka.me/rss.xml",
                },
                "parser_type": "rss",
                "streams": [
                    {
                        "receiver_type": "my-dummy-receiver",
                        "receiver_options": {"number": 42},
                        "intervals": ["*/10 * * * *"],
                        "message_template": "${title}\n${url}",
                    }
                ],
            }
        },
    }


def test_check_types_of_subhandler_kwargs(configuration_for_typechecking):
    receivers = configuration_for_typechecking["handlers"]["receivers"]
    receivers["my-dummy-receiver"]["init_options"]["some_number"] = "NEED TO BE INT"

    error_msg = (
        "Error while parsing init_options for my-dummy-receiver: "
        'wrong value type for field "some_number"'
    )
    with pytest.raises(InitHandlersError, match=error_msg):
        load_configuration(configuration_for_typechecking)


def test_check_types_of_handler_options(configuration_for_typechecking):
    streams = configuration_for_typechecking["sources"]["some-source"]["streams"]
    streams[0]["receiver_options"]["number"] = "NEED TO BE INT"

    error_msg = (
        "Error while parsing receiver options for some-source, stream index 0: "
        'wrong value type for field "number"'
    )
    with pytest.raises(InitHandlersError, match=error_msg):

        load_configuration(configuration_for_typechecking)


@pytest.mark.parametrize("value", [None, {}])
def test_required_options_need_to_be_presented(configuration_for_typechecking, value):
    streams = configuration_for_typechecking["sources"]["some-source"]["streams"]
    streams[0]["receiver_options"] = value

    with pytest.raises((LoadConfigurationError, InitHandlersError)):
        load_configuration(configuration_for_typechecking)
