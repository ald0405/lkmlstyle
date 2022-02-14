import re
from typing import Optional, Callable, Iterable
from dataclasses import dataclass
from functools import partial
from lkml.tree import SyntaxNode, PairNode, BlockNode, ContainerNode


@dataclass(frozen=True)
class Rule:
    title: str
    code: str
    select: str
    filters: tuple[partial[bool], ...]

    def applies_to(self, node: SyntaxNode) -> bool:
        return all(is_filter_valid(node) for is_filter_valid in self.filters)

    def followed_by(self, node: SyntaxNode) -> bool:
        raise NotImplementedError

    def get_node_value(self, node: SyntaxNode) -> Optional[str]:
        if isinstance(node, PairNode):
            return node.value.value
        elif isinstance(node, BlockNode):
            return node.name.value
        else:
            return None


@dataclass(frozen=True)
class PatternMatchRule(Rule):
    regex: str
    negative: Optional[bool] = False

    def __post_init__(self):
        # Why? https://docs.python.org/3/library/dataclasses.html#frozen-instances
        object.__setattr__(self, "pattern", re.compile(self.regex))

    def _matches(self, string: str) -> bool:
        matched = bool(self.pattern.search(string))
        return not matched if self.negative else matched

    def followed_by(self, node: SyntaxNode) -> bool:
        value = self.get_node_value(node)
        if value is None:
            return True
        return self._matches(value)


@dataclass(frozen=True)
class ParameterRule(Rule):
    criteria: partial[bool]
    negative: Optional[bool] = False

    def followed_by(self, node: SyntaxNode) -> bool:
        matched = self.criteria(node)
        return not matched if self.negative else matched


@dataclass(frozen=True)
class OrderRule(Rule):
    alphabetical: bool = False
    is_first: bool = False
    use_key: bool = True
    order: Optional[Iterable[str]] = None

    def __post_init__(self):
        if (self.alphabetical + self.is_first + bool(self.order)) > 1:
            raise AttributeError(
                "Only one of 'alphabetical', 'is_first', or 'order' can be defined as "
                "the sort order"
            )

    def get_node_value(self, node: SyntaxNode) -> Optional[str]:
        if isinstance(node, PairNode):
            return node.type.value if self.use_key else node.value.value
        elif isinstance(node, BlockNode):
            return node.name.value
        else:
            return None

    def followed_by(self, node: SyntaxNode, prev: Optional[SyntaxNode]) -> bool:
        if self.alphabetical:
            if prev:
                return self.get_node_value(node) > self.get_node_value(prev)
            else:
                return True
        elif self.is_first:
            return prev is None
        elif self.order:
            if prev:
                subset = set(self.get_node_value(prev), self.get_node_value(node))
                return subset in set(self.order)
            else:
                return self.get_node_value(node) == self.order[0]


def node_has_valid_class(node: SyntaxNode, node_type: type) -> bool:
    return isinstance(node, node_type)


def node_has_valid_type(node: SyntaxNode, value: str) -> bool:
    return node.type.value == value


def pair_has_valid_value(pair: PairNode, value: str) -> bool:
    return pair.value.value == value


def node_has_at_least_one_valid_child(node: SyntaxNode, is_valid: Callable) -> bool:
    for child in node.children:
        if isinstance(child, ContainerNode):
            if node_has_at_least_one_valid_child(child, is_valid):
                return True
        elif is_valid(child):
            return True
    return False


def block_has_valid_parameter(
    block: BlockNode,
    parameter_name: str,
    value: Optional[str] = None,
    negative: Optional[bool] = False,
) -> bool:
    # TODO: Make sure this actually works
    if not isinstance(block, BlockNode):
        return False

    def is_valid_param(node: SyntaxNode) -> bool:
        if not isinstance(node, PairNode):
            return False
        elif not node_has_valid_type(node, parameter_name):
            return False
        elif value and not pair_has_valid_value(node, value):
            return False
        else:
            return True

    valid = node_has_at_least_one_valid_child(block, is_valid_param)
    return not valid if negative else valid


ALL_RULES = (
    PatternMatchRule(
        title="Name of count measure doesn't start with 'count_'",
        code="M100",
        select="measure",
        filters=(
            partial(block_has_valid_parameter, parameter_name="type", value="count"),
        ),
        regex=r"^count_",
    ),
    PatternMatchRule(
        title="Name of sum measure doesn't start with 'total_'",
        code="M101",
        select="measure",
        filters=(
            partial(block_has_valid_parameter, parameter_name="type", value="sum"),
        ),
        regex=r"^total_",
    ),
    PatternMatchRule(
        title="Name of average measure doesn't start with 'avg_'",
        code="M102",
        select="measure",
        filters=(
            partial(block_has_valid_parameter, parameter_name="type", value="average"),
        ),
        regex=r"^(?:avg|average)_",
    ),
    PatternMatchRule(
        title="Yesno dimension doesn't start with 'is_' or 'has_'",
        code="D100",
        select="dimension",
        filters=(
            partial(block_has_valid_parameter, parameter_name="type", value="yesno"),
        ),
        regex=r"^(?:is|has)_",
    ),
    PatternMatchRule(
        title="Measure references table column directly",
        code="M110",
        select="measure.sql",
        filters=tuple(),
        regex=r"\$\{TABLE\}",
        negative=True,
    ),
    PatternMatchRule(
        title="Don't include all views",
        code="V100",
        select="include",
        filters=tuple(),
        regex=r"^\*\.view",
        negative=True,
    ),
    PatternMatchRule(
        title="Unnecessary type specification for string dimension",
        code="D101",
        select="dimension.type",
        filters=tuple(),
        regex=r"^string$",
        negative=True,
    ),
    PatternMatchRule(
        title="Dimension group name ends with redundant word",
        code="D200",
        select="dimension_group",
        filters=tuple(),
        regex=r"_(?:at|date|time)$",
        negative=True,
    ),
    ParameterRule(
        title="Explore doesn't declare fields",
        code="E100",
        select="explore",
        filters=(),
        criteria=partial(block_has_valid_parameter, parameter_name="fields"),
    ),
    # This probably is not the ideal behavior, it enforces strict title case, when in
    # reality people probably still want to lowercase words like 'and', 'is', 'or', etc.
    PatternMatchRule(
        title="Label is not title-cased",
        code="G100",
        select="label",
        filters=tuple(),
        regex=r"^(?:[A-Z][^\s]*\s?)+$",
    ),
    ParameterRule(
        title="Visible dimension missing description",
        code="D110",
        select="dimension",
        filters=tuple(
            [
                partial(
                    block_has_valid_parameter,
                    parameter_name="hidden",
                    value="yes",
                    negative=True,
                )
            ],
        ),
        criteria=partial(block_has_valid_parameter, parameter_name="description"),
    ),
    ParameterRule(
        title="View must define at least one primary key dimension",
        code="V110",
        select="view",
        filters=tuple(),
        criteria=partial(
            node_has_at_least_one_valid_child,
            is_valid=partial(
                block_has_valid_parameter, parameter_name="primary_key", value="yes"
            ),
        ),
    ),
    ParameterRule(
        title="Primary key dimension not hidden",
        code="D102",
        select="dimension",
        filters=tuple(
            [
                partial(
                    block_has_valid_parameter, parameter_name="primary_key", value="yes"
                )
            ],
        ),
        criteria=partial(
            block_has_valid_parameter,
            parameter_name="hidden",
            value="yes",
            negative=True,
        ),
    ),
    ParameterRule(
        title="Count measure doesn't specify a filter",
        code="M200",
        select="measure",
        filters=tuple(
            [partial(block_has_valid_parameter, parameter_name="type", value="count")],
        ),
        criteria=partial(block_has_valid_parameter, parameter_name="filter"),
    ),
    OrderRule(
        title="Dimension not in alphabetical order",
        code="D106",
        select="dimension",
        filters=tuple(),
        alphabetical=True,
    ),
    OrderRule(
        title="Measure not in alphabetical order",
        code="M106",
        select="measure",
        filters=tuple(),
        alphabetical=True,
    ),
)

RULES_BY_CODE = {}
for rule in ALL_RULES:
    if rule.code in RULES_BY_CODE:
        raise KeyError(f"A rule with code {rule.code} already exists")
    else:
        RULES_BY_CODE[rule.code] = rule
