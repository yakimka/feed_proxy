from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
import yaml

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


@dataclass
class DummyProcessorOptions(HandlerOptions):
    source_field: str


@register_handler(
    type=HandlerType.pre_send_processors,
    name="dummy_processor",
    options=DummyProcessorOptions,
)
async def dummy_processor(posts: list, *, options: DummyProcessorOptions) -> list:
    for post in posts:
        getattr(post, options.source_field, None)
    return posts


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


def test_load_configuration_with_pre_send_processors(run_sut, minimal_sources_block):
    stream = minimal_sources_block["sources"]["some-source"]["streams"][0]
    stream["pre_send_processors"] = [
        {"type": "dummy_processor", "options": {"source_field": "title"}}
    ]

    result = run_sut(minimal_sources_block)

    processors = result.sources[0].streams[0].pre_send_processors
    assert len(processors) == 1
    assert processors[0].type == "dummy_processor"
    assert processors[0].options == {"source_field": "title"}


def test_load_configuration_without_pre_send_processors_defaults_to_empty_list(
    run_sut, minimal_sources_block
):
    result = run_sut(minimal_sources_block)

    assert result.sources[0].streams[0].pre_send_processors == []


def test_load_configuration_with_unknown_pre_send_processor_type_raises(
    run_sut, minimal_sources_block
):
    stream = minimal_sources_block["sources"]["some-source"]["streams"][0]
    stream["pre_send_processors"] = [{"type": "does_not_exist", "options": {}}]

    error_msg = (
        "Handler does_not_exist of type HandlerType.pre_send_processors not found"
    )
    with pytest.raises(InitHandlersError, match=error_msg):
        run_sut(minimal_sources_block)


def test_load_configuration_with_invalid_pre_send_processor_options_raises(
    run_sut, minimal_sources_block
):
    stream = minimal_sources_block["sources"]["some-source"]["streams"][0]
    stream["pre_send_processors"] = [{"type": "dummy_processor", "options": {}}]

    error_msg = "Error while parsing pre_send_processor options for some-source"
    with pytest.raises(InitHandlersError, match=error_msg):
        run_sut(minimal_sources_block)


_LLM_PROMPT_SAMPLE_YAML = """
sources:
  some-source:
    fetcher_type: fetch_text
    fetcher_options:
      url: https://yakimka.me/rss.xml
    parser_type: rss
    streams:
      - receiver_type: console_printer
        intervals: ["*/10 * * * *"]
        message_template: "<b>{title_ua}</b>\\n\\n{description_ua}\\n\\n{url}"
        pre_send_processors:
          - type: llm_prompt
            options:
              source_field: title
              target_field: title_ua
              prompt: "Translate to Ukrainian:\\n{source}"
          - type: llm_prompt
            options:
              source_field: description
              target_field: description_ua
              prompt: "Translate to Ukrainian:\\n{source}"
"""


def test_load_configuration_with_llm_prompt_pre_send_processors(run_sut):
    config = yaml.safe_load(_LLM_PROMPT_SAMPLE_YAML)

    result = run_sut(config)

    processors = result.sources[0].streams[0].pre_send_processors
    assert [p.type for p in processors] == ["llm_prompt", "llm_prompt"]
    assert processors[0].options["target_field"] == "title_ua"
    assert processors[1].options["target_field"] == "description_ua"


def test_load_configuration_without_pre_send_processors_still_works_end_to_end(
    run_sut, minimal_sources_block
):
    result = run_sut(minimal_sources_block)

    assert result.sources[0].streams[0].pre_send_processors == []
    assert result.sources[0].streams[0].receiver_type == "console_printer"
