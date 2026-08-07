from app.search import parse_query


def test_sourcegraph_filter_parser():
    query = parse_query('repo:backend lang:python path:src/auth "refresh token"')
    assert (query.repo, query.language, query.path, query.text) == (
        "backend", "python", "src/auth", "refresh token"
    )
