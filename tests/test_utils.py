import lkml
from lkml.tree import PairNode, BlockNode
from lkmlstyle.utils import (
    block_has_valid_parameter,
    find_child_by_type,
    find_descendant_by_lineage,
)

# Strip away the DocumentNode and its container
def parse(text: str):
    return lkml.parse(text).container.items


def test_find_child_by_type_should_work():
    assert not find_child_by_type(PairNode("hidden", "yes"), "derived_table")
    assert not find_child_by_type(PairNode("hidden", "yes"), "hidden")

    nodes = parse("dimension: name { hidden: yes primary_key: yes }")

    # Child that does exist
    match = find_child_by_type(nodes[0], "hidden")
    assert match
    assert match.type == "hidden"

    # Child that doesn't exist
    match = find_child_by_type(nodes[0], "sql_table_name")
    assert not match


def test_find_descendant_by_lineage_should_work():
    assert not find_descendant_by_lineage(PairNode("hidden", "yes"), "derived_table")
    assert not find_descendant_by_lineage(PairNode("hidden", "yes"), "hidden")

    nodes = parse(
        """
        view: name {
            derived_table: {
                sql: "select * from orders ;;
                datagroup_trigger: datagroup
            }
            hidden: yes
        }
        """,
    )

    # Lineage depth of 1
    match = find_descendant_by_lineage(nodes[0], "derived_table")
    assert match
    assert isinstance(match, BlockNode)
    assert match.type == "derived_table"

    # Lineage depth > 1
    match = find_descendant_by_lineage(nodes[0], "derived_table.sql")
    assert match
    assert isinstance(match, PairNode)
    assert match.type == "sql"

    # Including the type of the view itself in the lineage
    match = find_descendant_by_lineage(nodes[0], "view.derived_table.sql")
    assert not match

    # Non-existing lineage
    match = find_descendant_by_lineage(nodes[0], "derived_table.view_label")
    assert not match


def test_block_has_valid_parameter_should_work():
    # Not a block node
    nodes = parse("hidden: yes")
    assert not block_has_valid_parameter(nodes[0], parameter_name="hidden")

    # Parameter only
    nodes = parse("dimension: { hidden: yes primary_key: yes }")
    assert block_has_valid_parameter(nodes[0], parameter_name="primary_key")
    assert not block_has_valid_parameter(nodes[0], parameter_name="view_label")

    # Parameter and value
    assert block_has_valid_parameter(
        nodes[0], parameter_name="primary_key", value="yes"
    )
    assert not block_has_valid_parameter(
        nodes[0], parameter_name="primary_key", value="no"
    )

    # Negative works
    assert block_has_valid_parameter(
        nodes[0], parameter_name="primary_key", value="no", negative=True
    )
    assert not block_has_valid_parameter(
        nodes[0], parameter_name="primary_key", value="yes", negative=True
    )

    # Paramter and value, but child is not a PairNode
    nodes = parse("dimension: name { hidden: {} }")
    assert not block_has_valid_parameter(nodes[0], parameter_name="hidden", value="yes")
