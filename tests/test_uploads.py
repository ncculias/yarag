import pytest


@pytest.fixture(autouse=True)
def fake_s3(monkeypatch):
    from yarag import uploads

    class _FakeS3:
        def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
            return f"https://fake.r2/{Params['Key']}"

        def get_paginator(self, name):
            class _P:
                def paginate(self, **kw):
                    return [
                        {
                            "Contents": [
                                {
                                    "Key": "bills/33717.md",
                                    "Size": 1234,
                                    "LastModified": __import__("datetime").datetime(2026, 7, 8),
                                }
                            ]
                        }
                    ]

            return _P()

    monkeypatch.setattr(uploads, "s3_client", _FakeS3())


def _req(content_type="application/pdf", size=1024):
    return {"content_type": content_type, "file_name": "test.pdf", "size_bytes": size}


def test_upload_requires_auth(client):
    assert client.post("/api/v1/uploads", json=_req()).status_code == 401


def test_upload_success(client, auth_headers):
    r = client.post("/api/v1/uploads", json=_req(), headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["upload_url"].startswith("https://fake.r2/")


def test_upload_docx_allowed(client, auth_headers):
    ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert client.post("/api/v1/uploads", json=_req(ct), headers=auth_headers).status_code == 201


def test_upload_too_large(client, auth_headers):
    r = client.post("/api/v1/uploads", json=_req(size=5 * 1024 * 1024), headers=auth_headers)
    assert r.status_code == 400
    assert "4MB" in r.json()["detail"]


def test_upload_bad_type(client, auth_headers):
    r = client.post("/api/v1/uploads", json=_req("video/mp4"), headers=auth_headers)
    assert r.status_code == 400


def test_list_documents(client, auth_headers):
    r = client.get("/api/v1/documents", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()[0]["name"] == "bills/33717.md"
