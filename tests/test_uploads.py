import pytest


@pytest.fixture(autouse=True)
def fake_s3(monkeypatch):
    from yarag import uploads

    class _FakeS3:
        def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
            if ClientMethod == "get_object":
                return f"https://fake.r2/download/{Params['Key']}"
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


def test_upload_key_contains_sanitized_filename(client, auth_headers):
    r = client.post(
        "/api/v1/uploads",
        json={"content_type": "application/pdf", "file_name": "114年度 預算/說明.pdf", "size_bytes": 100},
        headers=auth_headers,
    )
    key = r.json()["key"]
    tail = key.split("/")[-1]
    assert tail.endswith("114年度 預算說明.pdf")  # 斜線被移除、空白保留單一
    assert len(tail.split("-", 1)[0]) == 8  # uuid8 前綴


def test_upload_filename_extension_corrected(client, auth_headers):
    r = client.post(
        "/api/v1/uploads",
        json={"content_type": "application/pdf", "file_name": "評估報告.docx", "size_bytes": 100},
        headers=auth_headers,
    )
    assert r.json()["key"].endswith(".pdf")


def test_documents_display_name(client, auth_headers, monkeypatch):
    from yarag import uploads

    class _P:
        def paginate(self, **kw):
            import datetime

            return [
                {
                    "Contents": [
                        {"Key": "bills/34619.md", "Size": 1, "LastModified": datetime.datetime(2026, 7, 9)},
                        {
                            "Key": "2026/07/10/a1b2c3d4-預算說明.pdf",
                            "Size": 2,
                            "LastModified": datetime.datetime(2026, 7, 10),
                        },
                    ]
                }
            ]

    monkeypatch.setattr(uploads.s3_client, "get_paginator", lambda name: _P())
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    names = {d["name"]: d["display_name"] for d in docs}
    assert names["bills/34619.md"] == "34619.md"
    assert names["2026/07/10/a1b2c3d4-預算說明.pdf"] == "預算說明.pdf"


def test_download_url(client, auth_headers):
    r = client.get(
        "/api/v1/documents/download", params={"key": "2026/07/10/a1b2c3d4-預算說明.pdf"}, headers=auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["download_url"].startswith("https://")
    assert body["expires_in"] > 0


def test_download_rejects_bad_key(client, auth_headers):
    assert (
        client.get("/api/v1/documents/download", params={"key": "../secret"}, headers=auth_headers).status_code == 400
    )


def test_download_requires_auth(client):
    assert client.get("/api/v1/documents/download", params={"key": "x.md"}).status_code == 401


def test_upload_filename_consecutive_dots_collapsed(client, auth_headers):
    r = client.post(
        "/api/v1/uploads",
        json={"content_type": "application/pdf", "file_name": "v1..final.pdf", "size_bytes": 100},
        headers=auth_headers,
    )
    key = r.json()["key"]
    assert ".." not in key
    assert key.endswith("v1.final.pdf")


def test_uploaded_dotty_filename_is_downloadable(client, auth_headers):
    r = client.post(
        "/api/v1/uploads",
        json={"content_type": "application/pdf", "file_name": "報告...v2.pdf", "size_bytes": 100},
        headers=auth_headers,
    )
    key = r.json()["key"]
    assert client.get("/api/v1/documents/download", params={"key": key}, headers=auth_headers).status_code == 200
