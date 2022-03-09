import lkmlstyle


def test_measure_name_contains_count():
    fails = "measure: users { type: count }"
    passes = "measure: count_users { type: count }"
    assert lkmlstyle.check(fails, select=("M100",))
    assert not lkmlstyle.check(passes, select=("M100",))


def test_measure_name_contains_sum():
    fails = "measure: sale_price { type: sum }"
    passes = "measure: total_sale_price { type: sum }"
    assert lkmlstyle.check(fails, select=("M101",))
    assert not lkmlstyle.check(passes, select=("M101",))


def test_measure_name_contains_avg():
    fails = "measure: sale_price { type: average }"
    passes = "measure: avg_sale_price { type: average }"
    assert lkmlstyle.check(fails, select=("M102",))
    assert not lkmlstyle.check(passes, select=("M102",))


def test_yesno_name_is_question():
    fails = "dimension: partner { type: yesno }"
    passes = "dimension: is_partner { type: yesno }"
    assert lkmlstyle.check(fails, select=("D100",))
    assert not lkmlstyle.check(passes, select=("D100",))


def test_dimension_group_timeframes():
    fails = """
    dimension_group: created_at {
        type: time
        timeframes: [
        time,
        date,
        week,
        month,
        raw
        ]
        sql: ${TABLE}.created_at ;;
    }
    """

    passes = """
    dimension_group: created {
        type: time
        timeframes: [
        time,
        date,
        week,
        month,
        raw
        ]
        sql: ${TABLE}.created_at ;;
    }
    """

    assert lkmlstyle.check(fails, select=("D200",))
    assert not lkmlstyle.check(passes, select=("D200",))


def test_measures_only_reference_dimensions():
    fails = """
    measure: total_transaction_amount {
        type: sum
        sql: ${TABLE}."TRANSACTION.AMOUNT" ;;
        value_format_name: usd
    }
    """

    passes = """
    measure: total_transaction_amount {
        type: sum
        sql: ${transaction_amount} ;;
        value_format_name: usd
    }
    """

    assert lkmlstyle.check(fails, select=("M110",))
    assert not lkmlstyle.check(passes, select=("M110",))


def test_wildcard_includes():
    fails = 'include: "*.view"'
    passes = 'include: "schema_name.*.view"'
    assert lkmlstyle.check(fails, select=("V100",))
    assert not lkmlstyle.check(passes, select=("V100",))
    assert not lkmlstyle.check("include: view_name.view", select=("V100",))


def test_redundant_dimension_type():
    fails = "dimension: order_id { type: string }"
    all_passes = ["dimension: order_id { }", "dimension: order_id { type: number }"]
    assert lkmlstyle.check(fails, select=("D300",))
    for passes in all_passes:
        assert not lkmlstyle.check(passes, select=("D300",))


def test_explore_must_declare_fields():
    fails = 'explore: orders { label: "Company Orders" }'
    passes = "explore: orders { fields: [ALL_FIELDS*] }"
    assert lkmlstyle.check(fails, select=("E100",))
    assert not lkmlstyle.check(passes, select=("E100",))


def test_visible_dimensions_without_descriptions():
    all_fails = [
        """dimension: order_id {
            type: number
        }""",
        """dimension: order_id {
            hidden: no
        }""",
    ]
    all_passes = [
        """dimension: order_id {
            hidden: yes
            type: number
        }""",
        """dimension: order_id {
            hidden: no
            description: "Unique identifier for each order"
        }""",
        """dimension: order_id {
            description: "Unique identifier for each order"
        }""",
    ]
    for fails in all_fails:
        assert lkmlstyle.check(fails, select=("D301",))
    for passes in all_passes:
        assert not lkmlstyle.check(passes, select=("D301",))


def test_view_defines_at_least_one_primary_key():
    all_fails = (
        """
        view: orders {
            sql_table_name: `analytics.orders` ;;
            dimension: order_id {
                type: number
            }
        }
        """,
        """
        view: orders {
            sql_table_name: `analytics.orders` ;;
            dimension: order_id {
                primary_key: no
                type: number
            }
        }
        """,
    )
    passes = """
    view: orders {
        sql_table_name: `analytics.orders` ;;
        dimension: order_id {
            primary_key: yes
            type: number
        }
    }
    """
    for fails in all_fails:
        assert lkmlstyle.check(fails, select=("V110",))
    assert not lkmlstyle.check(passes, select=("V110",))


def test_primary_key_dimension_hidden():
    all_fails = (
        """
        dimension: order_id {
            primary_key: yes
        }
        """,
        """
        dimension: order_id {
            primary_key: yes
            hidden: no
        }
        """,
    )
    passes = """
    dimension: order_id {
        primary_key: yes
        hidden: yes
    }
    """
    for fails in all_fails:
        assert lkmlstyle.check(fails, select=("D302",))
    assert not lkmlstyle.check(passes, select=("D302",))


def test_count_measures_should_specify_a_filter():
    passes = """
    measure: count {
		type: count
		filters: {
			field: pk1_user_id
			value: "NOT NULL"
		}
	}
    """
    fails = """
    measure: count {
		type: count
	}
    """
    assert lkmlstyle.check(fails, select=("LAMS:F3",))
    assert not lkmlstyle.check(passes, select=("LAMS:F3",))


def test_dimensions_alphabetical():
    passes = """
    dimension: abc {}
    dimension: abd {}
    dimension_group: bcd {}
    dimension: xyz {}
    """
    fails = """
    dimension: abc {}
    dimension_group: xyz {}
    dimension: abd {}
    dimension: bcd {}
    """
    assert lkmlstyle.check(fails, select=("D106",))
    assert not lkmlstyle.check(passes, select=("D106",))


def test_measure_alphabetical():
    passes = """
    measure: abc {}
    measure: abd {}
    measure: bcd {}
    measure: xyz {}
    """
    fails = """
    measure: abc {}
    measure: xyz {}
    measure: abd {}
    measure: bcd {}
    """
    assert lkmlstyle.check(fails, select=("M106",))
    assert not lkmlstyle.check(passes, select=("M106",))
