"""SR-17 / AC-12: ground_truth must never appear in any API response.

Walks every GET route in the app's OpenAPI schema (so new endpoints are covered
automatically) plus every write endpoint's response, against seeded data
where every post has a ground truth.
"""

import re

from tests.conftest import KARA, KOBE, as_user, make_jpeg, upload

FORBIDDEN = re.compile(r"ground[_\s-]?truth|groundtruth", re.IGNORECASE)


def _assert_clean(response):
    assert not FORBIDDEN.search(response.text), f"{response.request.method} {response.request.url} leaked it"


def _fill(path: str) -> list[str]:
    if "{key}" in path:
        return []  # binary media, checked separately
    if "{post_id}" in path:
        return [path.replace("{post_id}", str(i)) for i in range(1, 7)]
    if "{user_id}" in path:
        return [path.replace("{user_id}", str(i)) for i in (KOBE, KARA)]
    return [path]


def test_no_get_endpoint_returns_ground_truth(seeded_client, app):
    checked = 0
    for route_path, operations in app.openapi()["paths"].items():
        if "get" in operations:
            for path in _fill(route_path):
                for headers in ({}, as_user(KOBE)):
                    r = seeded_client.get(path, headers=headers)
                    assert r.status_code < 500
                    _assert_clean(r)
                    checked += 1
    assert checked >= 10


def test_openapi_schema_does_not_mention_it(seeded_client):
    _assert_clean(seeded_client.get("/openapi.json"))


def test_write_responses_do_not_return_it(seeded_client, app):
    paths = set(app.openapi()["paths"])
    _assert_clean(upload(seeded_client, KOBE, make_jpeg()))
    if "/api/v1/posts/{post_id}/vote" in paths:
        _assert_clean(seeded_client.put("/api/v1/posts/1/vote", headers=as_user(KOBE), json={"value": "AI"}))
        _assert_clean(seeded_client.delete("/api/v1/posts/1/vote", headers=as_user(KOBE)))
    if "/api/v1/posts/{post_id}/reaction" in paths:
        _assert_clean(seeded_client.put("/api/v1/posts/1/reaction", headers=as_user(KOBE), json={"kind": "heart"}))
    if "/api/v1/me/avatar" in paths:
        _assert_clean(seeded_client.put("/api/v1/me/avatar", headers=as_user(KOBE), json={"avatar_id": 4}))


def test_errors_do_not_return_it(seeded_client):
    _assert_clean(seeded_client.get("/api/v1/posts/9999"))
    _assert_clean(seeded_client.get("/api/v1/posts", params={"ground_truth": "AI"}))
