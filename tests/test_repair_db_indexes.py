from repair_db_indexes import quote_ident


def test_quote_ident_escapes_double_quotes():
    assert quote_ident('ix_price_history_product_id') == '"ix_price_history_product_id"'
    assert quote_ident('a"b') == '"a""b"'
