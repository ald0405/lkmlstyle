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
