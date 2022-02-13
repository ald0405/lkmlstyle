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

    assert lkmlstyle.check(fails)
    assert not lkmlstyle.check(passes)
