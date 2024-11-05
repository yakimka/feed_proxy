import dataclasses
import logging
import operator
from enum import Enum

from feed_proxy.entities import Post
from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler

logger = logging.getLogger(__name__)


class OperatorType(str, Enum):
    EQUAL = "="
    NOT_EQUAL = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"


class ComparisonValueType(str, Enum):
    STRING = "string"
    INTEGER = "integer"


@dataclasses.dataclass
class ComparisonOptions(HandlerOptions):
    DESCRIPTIONS = {
        "field": ("Field", "Field name for comparison"),
        "field_type": ("Field type", ""),
        "operator": ("Operator", "Comparison operator"),
        "value": ("Value", "Comparison value"),
    }

    field: str
    operator: OperatorType
    value: str
    field_type: ComparisonValueType = ComparisonValueType.STRING


@register_handler(
    type=HandlerType.modifiers.value,
    options=ComparisonOptions,
)
async def compare_and_filter(
    posts: list[Post], *, options: ComparisonOptions
) -> list[Post]:
    value: str | int
    if options.field_type == ComparisonValueType.STRING.value:
        value = options.value
    elif options.field_type == ComparisonValueType.INTEGER.value:
        value = int(options.value)
    else:
        raise ValueError(f"Unknown field type: {options.field_type}")

    operator_map = {
        OperatorType.EQUAL.value: operator.eq,
        OperatorType.NOT_EQUAL.value: operator.ne,
        OperatorType.GREATER_THAN.value: operator.gt,
        OperatorType.LESS_THAN.value: operator.lt,
    }
    operator_func = operator_map[options.operator]
    return [
        post for post in posts if operator_func(getattr(post, options.field), value)
    ]
