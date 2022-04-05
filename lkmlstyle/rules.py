import re
from typing import Optional, Sequence, Union
from dataclasses import dataclass, field
from functools import partial
from lkml.tree import SyntaxNode, PairNode, BlockNode
from lkmlstyle.utils import (
    find_child_by_type,
    find_descendant_by_lineage,
    node_has_at_least_one_valid_child,
    block_has_valid_parameter,
)


@dataclass
class NodeContext:
    """State required to check for rule violations"""

    previous_node: dict[str, Optional[SyntaxNode]] = field(default_factory=dict)
    table_to_view: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class Rule:
    title: str
    code: str
    rationale: str
    select: Union[str, tuple[str, ...]]
    filters: tuple[partial[bool], ...]
    filter_on: Optional[str] = None

    def __post_init__(self):
        # If `select` arg is a string, wrap it in a tuple
        if isinstance(self.select, str):
            # Why? https://docs.python.org/3/library/dataclasses.html#frozen-instances
            object.__setattr__(self, "select", (self.select,))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}<{self.code}>"

    def selects(self, lineage: str) -> bool:
        """Given a lineage string, determine if this rule would select that node."""
        return any(lineage.endswith(selector) for selector in self.select)

    def applies_to(self, node: SyntaxNode, lineage: str) -> bool:
        """Check a node against a rule's filters for relevance."""
        # At a minimum, the node's lineage must match the selection string
        if not self.selects(lineage):
            return False

        # The rule may specify a descendant to filter on, find this node
        if self.filter_on:
            descendant = find_descendant_by_lineage(node, lineage=self.filter_on)
            if descendant is None:
                return False
            else:
                filter_node = descendant
        else:
            filter_node = node

        return all(is_filter_valid(filter_node) for is_filter_valid in self.filters)

    def followed_by(
        self, node: SyntaxNode, context: NodeContext
    ) -> tuple[bool, NodeContext]:
        """Determine if node follows the rule."""
        raise NotImplementedError

    def get_node_value(self, node: SyntaxNode) -> Optional[str]:
        """Extract a value string from a node."""
        if isinstance(node, PairNode):
            return node.value.value
        elif isinstance(node, BlockNode) and node.name:
            return node.name.value
        else:
            return None


@dataclass(frozen=True, repr=False)
class PatternMatchRule(Rule):
    regex: str
    negative: Optional[bool] = False

    def __post_init__(self):
        super().__post_init__()
        # Why? https://docs.python.org/3/library/dataclasses.html#frozen-instances
        object.__setattr__(self, "pattern", re.compile(self.regex))

    def _matches(self, string: str) -> bool:
        """Check a string against the rule's regex."""
        matched = bool(self.pattern.search(string))  # type: ignore
        return not matched if self.negative else matched

    def followed_by(
        self, node: SyntaxNode, context: NodeContext
    ) -> tuple[bool, NodeContext]:
        """Determine if node follows the rule."""
        value = self.get_node_value(node)
        if value is None:
            return True, context
        return self._matches(value), context


@dataclass(frozen=True, repr=False)
class ParameterRule(Rule):
    criteria: partial[bool]
    negative: Optional[bool] = False

    def followed_by(
        self, node: SyntaxNode, context: NodeContext
    ) -> tuple[bool, NodeContext]:
        """Determine if node follows the rule."""
        matched = self.criteria(node)
        return not matched if self.negative else matched, context


@dataclass(frozen=True, repr=False)
class OrderRule(Rule):
    alphabetical: bool = False
    is_first: bool = False
    use_key: bool = True
    order: Optional[Sequence[str]] = None

    def __post_init__(self):
        super().__post_init__()
        # Ensure the argument combination makes sense
        if (self.alphabetical + self.is_first + bool(self.order)) > 1:
            raise ValueError(
                "Only one of 'alphabetical', 'is_first', or 'order' can be defined as "
                "the sort order"
            )

    def get_node_value(self, node: SyntaxNode) -> Optional[str]:
        """Extract a value string from a node."""
        if isinstance(node, PairNode):
            return node.type.value if self.use_key else node.value.value
        elif isinstance(node, BlockNode) and node.name:
            return node.name.value
        else:
            return None

    def followed_by(
        self, node: SyntaxNode, context: NodeContext
    ) -> tuple[bool, NodeContext]:
        """Determine if node follows the rule."""
        follows = True
        prev = context.previous_node.get(self.code)

        if self.alphabetical:
            if prev:
                node_value = self.get_node_value(node)
                prev_value = self.get_node_value(prev)
                if node_value and prev_value:
                    follows = node_value > prev_value
                else:
                    raise TypeError("Value of a compared node is None")
            else:
                follows = True
        elif self.is_first:
            follows = prev is None
        elif self.order:
            if prev:
                subset = set((self.get_node_value(prev), self.get_node_value(node)))
                follows = subset in set(self.order)
            else:
                follows = self.get_node_value(node) == self.order[0]
        else:
            raise AttributeError("Alphabetical, is_first, or custom order must be set")

        return follows, context


@dataclass(frozen=True, repr=False)
class DuplicateViewRule(Rule):
    def followed_by(
        self, node: SyntaxNode, context: NodeContext
    ) -> tuple[bool, NodeContext]:
        # Selection rules ensure this shouldn't happen, but this makes mypy happy
        if not isinstance(node, BlockNode):
            return True, context

        if context.table_to_view is None:
            raise TypeError("table_to_view cannot be None")

        if node.name is None:
            raise TypeError(f"Name for view {repr(node)} is None")

        view_name: str = node.name.value
        sql_table_name_node = find_child_by_type(node, "sql_table_name")

        if sql_table_name_node is None:
            return True, context
        elif not isinstance(sql_table_name_node, PairNode):
            raise TypeError(
                "Node for sql_table_name is of unexpected type "
                f"{type(sql_table_name_node)}. Expected a PairNode"
            )
        else:
            sql_table_name = sql_table_name_node.value.value

        if sql_table_name in context.table_to_view:
            return False, context
        else:
            context.table_to_view[sql_table_name] = view_name
            return True, context


# Rules define the criteria for the passing state
# For example, a node will pass if it a) doesn't meet the `select` and `filters`
# or it does, but also passes the regex, criteria, order, etc. of the rule
ALL_RULES = (
    PatternMatchRule(
        title="Dimension name not in snake case",
        code="D101",
        rationale=(
            "Dimension names should match the conventional format, which is "
            "snake case—words in lowercase, separated by underscores. "
            "For example, **order_id** instead of **orderId** or **OrderID**."
        ),
        select=("dimension", "dimension_group"),
        filters=tuple(),
        regex=r"^[_a-z0-9]+$",
    ),
    PatternMatchRule(
        title="Measure name not in snake case",
        code="M103",
        rationale=(
            "Measure names should match the conventional format, which is "
            "snake case—words in lowercase, separated by underscores. "
            "For example, **count_orders** instead of **OrderCount**."
        ),
        select="measure",
        filters=tuple(),
        regex=r"^[_a-z0-9]+$",
    ),
    PatternMatchRule(
        title="View name not in snake case",
        code="V100",
        rationale=(
            "View names should match the conventional format, which is "
            "snake case—words in lowercase, separated by underscores. "
            "For example, **all_orders** instead of **allOrders** or **AllOrders**."
        ),
        select="view",
        filters=tuple(),
        regex=r"^[_a-z0-9]+$",
    ),
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
        title="Redundant type specification for join",
        code="J100",
        rationale=(
            "By default, Looker defines joins with **type: left_outer**. "
            "Explicitly stating a left outer join is redundant, the **type** "
            "parameter can be removed."
        ),
        select="join.type",
        filters=tuple(),
        regex=r"^left_outer$",
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
        select=("dimension", "dimension_group"),
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
        title="View missing view label",
        code="V111",
        rationale=(
            "Views should define a view label to provide "
            "a user-friendly name for the view in Explores. "
            "Looker generates title-cased names for views based on the view name in "
            "LookML, but these names aren't always useful for users in Explores. "
            "For example, an auto-generated view name **Prod Sessions L3d** "
            "(generated from view: prod_sessions_l3d) is not as succinct or "
            "informational as **Web Sessions**."
        ),
        select="view",
        filters=tuple(),
        criteria=partial(
            node_has_at_least_one_valid_child,
            is_valid=partial(block_has_valid_parameter, parameter_name="view_label"),
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
            "while scrolling through a view file.\n\nA dimension or dimension group "
            "violates this rule if it is not alphabetically sorted with respect to "
            "the previous dimension or dimension group."
        ),
        select=("dimension", "dimension_group"),
        filters=tuple(),
        alphabetical=True,
    ),
    OrderRule(
        title="Measure not in alphabetical order",
        code="M106",
        rationale=(
            "Sort measures alphabetically to make it easier to find a measure "
            "while scrolling through a view file.\n\nA measure "
            "violates this rule if it is not alphabetically sorted with respect to "
            "the previous measure."
        ),
        select="measure",
        filters=tuple(),
        alphabetical=True,
    ),
    OrderRule(
        title="Primary key dimension not the first dimension in this view",
        code="D107",
        rationale=(
            "The primary key should be listed first in a view so developers quickly "
            "understand the grain of the view and what a single record represents."
        ),
        select="dimension",
        filters=tuple(
            [
                partial(
                    block_has_valid_parameter, parameter_name="primary_key", value="yes"
                )
            ]
        ),
        is_first=True,
    ),
    PatternMatchRule(
        title='Dimension label includes redundant "Yes/No"',
        code="D303",
        rationale=(
            'For **yesno** dimensions, Looker adds "Yes/No" to the end of the '
            "dimension's label by default, so there's no need to include it in the "
            "label."
        ),
        select="dimension.label",
        filters=tuple(),
        regex=r"(?i)Yes/No",
        negative=True,
    ),
    DuplicateViewRule(
        title="View uses the same table as another view",
        code="V112",
        rationale=(
            "Views should not have the same **sql_table_name** because two views with "
            "the same table name are effectively the same view. Instead, consolidate "
            "these views into a single view."
        ),
        select="view",
        filters=tuple(),
    ),
    PatternMatchRule(
        title="Name of persistent derived table view doesn't start with 'pdt_'",
        code="V113",
        rationale=(
            "Views that define persistent derived tables should be prefixed "
            "to make it easy to identify views based on PDTs."
        ),
        select="view",
        regex=r"^pdt_",
        filter_on="derived_table",
        filters=tuple(
            [
                lambda x: block_has_valid_parameter(
                    x, parameter_name="datagroup_trigger"
                )
                or block_has_valid_parameter(x, parameter_name="sql_trigger_value")
                or block_has_valid_parameter(x, parameter_name="interval_trigger")
                or block_has_valid_parameter(x, parameter_name="persist_for")
                or block_has_valid_parameter(
                    x, parameter_name="materialized_view", value="yes"
                )
            ]
        ),
    ),
)

RULES_BY_CODE = {}
for rule in ALL_RULES:
    if rule.code in RULES_BY_CODE:
        raise KeyError(f"A rule with code {rule.code} already exists")
    else:
        RULES_BY_CODE[rule.code] = rule
