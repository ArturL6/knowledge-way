from app.search import parse_query, query_terms


def test_sourcegraph_filter_parser():
    query = parse_query('repo:backend lang:python path:src/auth "refresh token"')
    assert (query.repo, query.language, query.path, query.text) == (
        "backend", "python", "src/auth", "refresh token"
    )


def test_query_terms_keep_code_identifiers_and_drop_question_words():
    assert query_terms("Where is get_dependant defined?") == ["get_dependant"]
