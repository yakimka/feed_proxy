from __future__ import annotations

import dataclasses
import importlib
import os
import pkgutil
from collections import defaultdict
from collections.abc import Callable
from enum import Enum
from functools import partial
from inspect import isclass
from typing import TYPE_CHECKING, Any, NamedTuple, TypedDict

from dacite import Config, DaciteError, from_dict

from feed_proxy.entities import Post

if TYPE_CHECKING:
    from types import ModuleType

    from feed_proxy.configuration import Configuration

__all__ = [
    "HandlerOptions",
    "HandlerType",
    "InitHandlersError",
    "get_handler_by_name",
    "get_handler_return_model_by_name",
    "get_registered_handlers",
    "register_handler",
]


class HandlerType(Enum):
    fetchers = "fetchers"
    parsers = "parsers"
    receivers = "receivers"
    modifiers = "modifiers"


@dataclasses.dataclass
class HandlerOptions:
    DESCRIPTIONS = {}  # type: dict[str, tuple[str, str]]

    @classmethod
    def _descriptions(cls) -> dict[str, tuple[str, str]]:
        return {
            field.name: cls.DESCRIPTIONS[field.name]
            for field in dataclasses.fields(cls)
            if field.name in cls.DESCRIPTIONS
        }

    @classmethod
    def field_title(cls, field_name: str) -> str:
        title = 0
        return cls._descriptions().get(field_name, ("", ""))[title]

    @classmethod
    def field_description(cls, field_name: str) -> str:
        description = 1
        return cls._descriptions().get(field_name, ("", ""))[description]

    @classmethod
    def to_json_schema(cls) -> Schema:
        schema: Schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": type(cls).__name__,
            "type": "object",
            "properties": {},
            "required": [],
        }
        for field in dataclasses.fields(cls):
            m = dataclasses.MISSING
            field_type = field.type
            extra_properties = {}
            is_enum = isclass(field.type) and issubclass(field.type, Enum)
            if is_enum:
                field_type = _get_enum_values_type(field.type)  # type: ignore[arg-type]
                extra_properties["enum"] = [
                    field.value for field in field.type  # type: ignore[union-attr]
                ]
            schema["properties"][field.name] = {
                **extra_properties,
                "type": _python_type_to_json_schema_type(field_type),
                "title": cls.field_title(field.name),
                "description": cls.field_description(field.name),
            }

            if field.default is not m:
                default = field.default.value if is_enum else field.default
                schema["properties"][field.name]["default"] = default
            elif field.default_factory is not m:
                schema["properties"][field.name]["default"] = field.default_factory()
            else:
                schema["required"].append(field.name)

        return schema


ReturnModel = type[Post]


class Handler(NamedTuple):
    name: str
    obj: Callable
    options_class: type[HandlerOptions] | None
    return_fields_schema: dict | None
    return_model: ReturnModel | None


class RawHandler(NamedTuple):
    name: str
    obj: Callable
    init_options_class: type[HandlerOptions] | None
    options_class: type[HandlerOptions] | None
    return_fields_schema: dict | None
    return_model: ReturnModel | None


HANDLERS: dict[HandlerType, dict[str, RawHandler]] = defaultdict(dict)
REGISTERED_HANDLERS: dict[HandlerType, dict[str, Handler]] = {}


def register_handler(
    *,
    type: HandlerType,
    name: str | None = None,
    init_options: type[HandlerOptions] | None = None,
    options: type[HandlerOptions] | None = None,
    return_fields_schema: dict | None = None,
    return_model: ReturnModel | None = None,
) -> Callable:
    def wrapper(func_or_class: Callable) -> Any:
        if type == HandlerType.parsers and not return_model:
            raise ValueError("Parsers must be registered with return_model")

        if not isclass(func_or_class) and init_options is not None:
            raise ValueError("init_options is not allowed for functions")

        handler_name = name or func_or_class.__name__
        HANDLERS[type][handler_name] = RawHandler(
            name=handler_name,
            obj=func_or_class,
            init_options_class=init_options,
            options_class=options,
            return_fields_schema=return_fields_schema,
            return_model=return_model,
        )

        return func_or_class

    return wrapper


def load_handlers() -> None:
    for item in HandlerType:
        package = importlib.import_module(
            f".{item.value}", package="feed_proxy.handlers"
        )
        _load_modules(package)


class InitHandlersError(Exception):
    pass


def init_registered_handlers(configuration: Configuration) -> None:  # noqa: C901
    REGISTERED_HANDLERS.clear()
    load_handlers()

    def _get_handler(handler_type: HandlerType, handler_id: str) -> RawHandler:
        try:
            return HANDLERS[handler_type][handler_id]
        except KeyError:
            raise InitHandlersError(
                f"Handler {handler_id} of type {handler_type} not found"
            ) from None

    def _validate_options(
        options: dict[str, Any],
        options_class: type[HandlerOptions] | None,
        error_msg: str,
    ) -> None:
        if options_class is None:
            return
        try:
            from_dict(options_class, options, config=Config(cast=[Enum]))
        except DaciteError as e:
            raise InitHandlersError(f"{error_msg}: {e}") from None

    used_handlers = set()
    options_to_validate = []
    for source in configuration.sources:
        fetcher_key = (HandlerType.fetchers, source.fetcher_type)
        options_to_validate.append(
            (
                source.fetcher_options,
                fetcher_key,
                f"Error while parsing fetcher options for {source.id}",
            )
        )
        used_handlers.add(fetcher_key)
        parser_key = (HandlerType.parsers, source.parser_type)
        used_handlers.add(parser_key)
        options_to_validate.append(
            (
                source.parser_options,
                parser_key,
                f"Error while parsing parser options for {source.id}",
            )
        )
        for si, stream in enumerate(source.streams):
            receiver_key = (HandlerType.receivers, stream.receiver_type)
            options_to_validate.append(
                (
                    stream.receiver_options,
                    receiver_key,
                    (
                        "Error while parsing receiver options for "
                        f"{source.id}, stream index {si}"
                    ),
                )
            )
            used_handlers.add(receiver_key)
            for mi, modifier in enumerate(stream.modifiers):
                modifier_key = (HandlerType.modifiers, modifier.type)
                options_to_validate.append(
                    (
                        modifier.options,
                        modifier_key,
                        (
                            "Error while parsing modifier options for "
                            f"{source.id}, stream index {si}, modifier index {mi}"
                        ),
                    )
                )
                used_handlers.add(modifier_key)

    subhandlers_by_name = {
        (item.handler_type, item.name): item for item in configuration.subhandlers
    }

    result: dict[HandlerType, dict[str, Handler]] = {}
    options_class_by_key = {}
    for handler_type, handler_id in used_handlers:
        if subhandler := subhandlers_by_name.get((handler_type, handler_id)):
            handler = _get_handler(handler_type, subhandler.type)
            if subhandler.init_options and not handler.init_options_class:
                raise InitHandlersError(
                    f"Handler {handler_id} does not have init_options"
                )
            init_options = None
            if handler.init_options_class:
                try:
                    init_options = from_dict(
                        handler.init_options_class, subhandler.init_options
                    )
                except DaciteError as e:
                    raise InitHandlersError(
                        f"Error while parsing init_options for {handler_id}: {e}"
                    ) from None
            result.setdefault(handler_type, {})[subhandler.name] = Handler(
                subhandler.name,
                handler.obj(options=init_options),
                handler.options_class,
                handler.return_fields_schema,
                handler.return_model,
            )
            handler_key = (handler_type, subhandler.name)
            options_class_by_key[handler_key] = handler.options_class
        else:
            handler = _get_handler(handler_type, handler_id)
            func_or_class = handler.obj
            if handler.init_options_class and not isclass(func_or_class):
                raise InitHandlersError(
                    f"init_options is not allowed for function {handler_id}"
                )
            elif handler.init_options_class:
                try:
                    init_options = from_dict(handler.init_options_class, {})
                    func_or_class = func_or_class(options=init_options)
                except DaciteError:
                    raise InitHandlersError(
                        f"Please specify init_options for {handler_id} in config"
                    ) from None

            result.setdefault(handler_type, {})[handler_id] = Handler(
                handler_id,
                func_or_class,
                handler.options_class,
                handler.return_fields_schema,
                handler.return_model,
            )
            handler_key = (handler_type, handler_id)
            options_class_by_key[handler_key] = handler.options_class

    # Validate handlers options
    for options, handler_key, error_msg in options_to_validate:
        _validate_options(options, options_class_by_key[handler_key], error_msg)

    REGISTERED_HANDLERS.update(result)


def get_registered_handlers() -> dict[HandlerType, dict[str, Handler]]:
    return REGISTERED_HANDLERS


def _load_modules(package: ModuleType) -> None:
    for module_name in _parse_modules(package):
        importlib.import_module(f".{module_name}", package=package.__name__)


def _parse_modules(package: ModuleType) -> list[str]:
    assert package.__file__ is not None
    pkgpath = os.path.dirname(package.__file__)
    return [name for _, name, _ in pkgutil.iter_modules([pkgpath])]


def get_handler_by_name(
    type: HandlerType, name: str, options: dict | None = None
) -> Any:
    registered_handlers = get_registered_handlers()
    handler = dict(registered_handlers[type])[name]
    options_ = None
    if options and handler.options_class:
        options_ = handler.options_class(**options)
    return partial(handler.obj, options=options_)


def get_handler_return_model_by_name(type: HandlerType, name: str) -> ReturnModel:
    registered_handlers = get_registered_handlers()
    handler = dict(registered_handlers[type])[name]
    if handler.return_model is None:
        raise ValueError(f"Handler {name} does not have return model")
    return handler.return_model


Schema = TypedDict(
    "Schema",
    {
        "$schema": str,
        "title": str,
        "type": str,
        "properties": dict,
        "required": list,
    },
)


def _python_type_to_json_schema_type(python_type: type | str) -> str:
    types = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
    }
    python_type = python_type if isinstance(python_type, str) else python_type.__name__
    try:
        return types[python_type]
    except KeyError:
        raise ValueError(f"Unsupported type {python_type}") from None


def _get_enum_values_type(enum_class: type[Enum]) -> type:
    enums: list[Enum] = list(enum_class)
    klass = type(enums[0].value)
    is_consistent = all(isinstance(e.value, klass) for e in enums)
    if not is_consistent:
        raise ValueError(f"Enum {enum_class.__name__} has inconsistent values types")

    return klass
