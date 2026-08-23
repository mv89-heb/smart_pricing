from smartpricing.db_setup import _first_col


def test_first_col_selects_first_existing_candidate():
    assert _first_col({"email", "name"}, "username", "email", "name") == "email"
