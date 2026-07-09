def test_cors_preflight(client):
    r = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_tables_created_on_startup(client):
    from sqlalchemy import inspect

    from yarag.db import engine

    assert {"users", "threads", "messages"} <= set(inspect(engine).get_table_names())
