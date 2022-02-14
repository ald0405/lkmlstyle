import lkmlstyle


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
