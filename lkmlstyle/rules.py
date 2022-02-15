import re
import typing
from typing import Optional, Callable, Iterable, Union
from dataclasses import dataclass
from functools import partial
from lkml.tree import SyntaxNode, PairNode, BlockNode, ContainerNode, ListNode


TypedNode = Union[BlockNode, PairNode, ListNode]


@dataclass(frozen=True)
class Rule:
    title: str
    code: str
    rationale: str
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


def node_has_valid_type(node: TypedNode, value: str) -> bool:
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

    def is_valid_param(node: TypedNode) -> bool:
        # Only consider nodes that define a type attribute
        if not isinstance(node, typing.get_args(TypedNode)):
            return False
        if not node_has_valid_type(node, parameter_name):
            return False

        if value:
            # Can only test value for PairNodes
            if not isinstance(node, PairNode):
                return False
            if not pair_has_valid_value(node, value):
                return False

        return True

    valid = node_has_at_least_one_valid_child(block, is_valid_param)
    return not valid if negative else valid


# Rules define the criteria for the passing state
# For example, a node will pass if it a) doesn't meet the `select` and `filters`
# or it does, but also passes the regex, criteria, order, etc. of the rule
ALL_RULES = (
    PatternMatchRule(
        title="Name of count measure doesn't start with 'count_'",
        code="M100",
        rationale=(
            "You should explicitly state the aggregation type in the dimension name "
            "because it makes it easier for other developers and Explore users to "
            "understand how the measure is calculated."
        ),
        select="measure",
        filters=(
            partial(block_has_valid_parameter, parameter_name="type", value="count"),
        ),
        regex=r"^count_",
    ),
    PatternMatchRule(
        title="Name of sum measure doesn't start with 'total_'",
        code="M101",
        rationale=(
            "You should explicitly state the aggregation type in the dimension name "
            "because it makes it easier for other developers and Explore users to "
            "understand how the measure is calculated."
        ),
        select="measure",
        filters=(
            partial(block_has_valid_parameter, parameter_name="type", value="sum"),
        ),
        regex=r"^total_",
    ),
    PatternMatchRule(
        title="Name of average measure doesn't start with 'avg_'",
        code="M102",
        rationale=(
            "You should explicitly state the aggregation type in the dimension name "
            "because it makes it easier for other developers and Explore users to "
            "understand how the measure is calculated."
        ),
        select="measure",
        filters=(
            partial(block_has_valid_parameter, parameter_name="type", value="average"),
        ),
        regex=r"^(?:avg|average)_",
    ),
    PatternMatchRule(
        title="Yesno dimension doesn't start with 'is_' or 'has_'",
        code="D100",
        rationale=(
            "Wording the name of a **yesno** dimension as a question makes it clear to "
            "the user what a yes or no value represents."
        ),
        select="dimension",
        filters=(
            partial(block_has_valid_parameter, parameter_name="type", value="yesno"),
        ),
        regex=r"^(?:is|has)_",
    ),
    PatternMatchRule(
        title="Measure references table column directly",
        code="M110",
        rationale=(
            "Measures should not directly reference table columns, but should instead "
            "reference dimensions that reference table columns. This way, the "
            "dimension can be a layer of abstraction and single source of truth for "
            "**all** measures that reference it."
        ),
        select="measure.sql",
        filters=tuple(),
        regex=r"\$\{TABLE\}",
        negative=True,
    ),
    PatternMatchRule(
        title="Don't include all views",
        code="V100",
        rationale=("???"),
        select="include",
        filters=tuple(),
        regex=r"^\*\.view",
        negative=True,
    ),
    PatternMatchRule(
        title="Redundant type specification for string dimension",
        code="D300",
        rationale=(
            "By default, Looker defines dimensions with **type: string**. "
            "Explicitly stating a string-typed dimension is redundant, the **type** "
            "parameter can be removed."
        ),
        select="dimension.type",
        filters=tuple(),
        regex=r"^string$",
        negative=True,
    ),
    PatternMatchRule(
        title="Dimension group name ends with redundant word",
        code="D200",
        rationale=(
            "When Looker creates the underlying dimensions, Looker appends the name of "
            "the timeframe to the dimension group name. "
            "For example, for a dimension group called **order_date**, Looker will "
            "create dimensions with redundant names:\n"
            " * order_date_date\n"
            " * order_date_month\n"
            " * order_date_year\n"
            " * ...\n"
            "\nInstead, use **order** as the dimension group name, which becomes "
            "**order_date**, **order_month**, etc."
        ),
        select="dimension_group",
        filters=tuple(),
        regex=r"_(?:at|date|time)$",
        negative=True,
    ),
    ParameterRule(
        title="Explore doesn't declare fields",
        code="E100",
        rationale=(
            "When fields are explicitly defined, LookML developers can easily identify "
            "the fields included in the Explore without having to reference the view "
            "file or loading the Explore page.\n\n"
            "This is especially helpful when the Explore includes multiple joins and a "
            "subset of fields from each joined model."
        ),
        select="explore",
        filters=tuple(),
        criteria=partial(block_has_valid_parameter, parameter_name="fields"),
    ),
    ParameterRule(
        title="Visible dimension missing description",
        code="D301",
        rationale=(
            "Dimensions that are visible in the Explore page should have a description "
            "so users understand how and why to use them, along with any caveats."
        ),
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
        title="Visible measure missing description",
        code="M112",
        rationale=(
            "Measures that are visible in the Explore page should have a description "
            "so users understand how and why to use them, along with any caveats."
        ),
        select="measure",
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
        rationale=(
            "Views must define a primary key so that any Explores that reference them "
            "can take advantage of symmetric aggregates and join them properly to "
            "views."
        ),
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
        code="D302",
        rationale=(
            "Primary keys are not typically used directly in Explores because users "
            "are more interested in aggregates like measures, which reduce the grain "
            "beyond the grain of the primary key. Thus, these dimensions should be "
            "hidden."
        ),
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
        ),
    ),
    ParameterRule(
        title="Count measure doesn't specify a filter",
        code="LAMS:F3",
        rationale=(
            "By default, Looker will implement any non-filtered & non-distinct count "
            'field as a **COUNT(*)**. Filtering such "plain" counts on '
            "**PK IS NOT NULL** ensures correct counts in all of the following uses of "
            "the field:\n"
            " * Counting only that table\n"
            " * Counting that table when joined on as a **one-to-one** or "
            "**one-to-zero** table\n"
            " * Counting that table with symmetric aggregates when joined on as a "
            "**many_to_one** table, and counting that table in explores with join "
            "paths.\n\n"
            '**Note:** The LookML filter syntax for "is not null" varies depending on '
            "the type of the field. For strings, use **-NULL**. For numbers, use "
            "**NOT NULL**."
        ),
        select="measure",
        filters=tuple(
            [partial(block_has_valid_parameter, parameter_name="type", value="count")],
        ),
        criteria=partial(block_has_valid_parameter, parameter_name="filters"),
    ),
    OrderRule(
        title="Dimension not in alphabetical order",
        code="D106",
        rationale=(
            "Sort dimensions alphabetically to make it easier to find a dimension "
            "while scrolling through a view file."
        ),
        select="dimension",
        filters=tuple(),
        alphabetical=True,
    ),
    OrderRule(
        title="Measure not in alphabetical order",
        code="M106",
        rationale=(
            "Sort measures alphabetically to make it easier to find a measure "
            "while scrolling through a view file."
        ),
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
