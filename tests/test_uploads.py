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
    monkeypatch.setattr(uploads.cloudflare, "list_item_status", lambda: {}, raising=False)
    monkeypatch.setattr(uploads.cloudflare, "retrieve_text", lambda q, k: "", raising=False)


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


def test_safe_filename_never_produces_double_dots(client, auth_headers):
    adversarial = ["report.", "x.", "f" * 72 + ".", "...", ". . .", "a..b..c..pdf", "報告.", "..", "。..pdf"]
    for name in adversarial:
        r = client.post(
            "/api/v1/uploads",
            json={"content_type": "application/pdf", "file_name": name, "size_bytes": 100},
            headers=auth_headers,
        )
        key = r.json()["key"]
        assert ".." not in key, f"{name!r} -> {key!r}"
        assert key.endswith(".pdf"), f"{name!r} -> {key!r}"
        dl = client.get("/api/v1/documents/download", params={"key": key}, headers=auth_headers)
        assert dl.status_code == 200, f"{name!r} -> {key!r}"


def test_content_is_empty_detects_metadata_only():
    from yarag.uploads import _content_is_empty

    metadata_only = (
        "# 0871b1f0-TARG.pdf\n## Metadata\n- PDFFormatVersion=1.7\n"
        "- Author=someone\n\n\n## Contents\n### Page 1"
    )
    assert _content_is_empty(metadata_only) is True


def test_content_is_empty_false_when_body_present():
    from yarag.uploads import _content_is_empty

    real = (
        "# 遠雄.pdf\n## Metadata\n- PDFFormatVersion=1.7\n\n\n"
        "## Contents\n### Page 1\n物品出入區申請表 申請人姓名 所屬部門單位 主管簽核意見 申請日期 用途說明欄"
    )
    assert _content_is_empty(real) is False


def _patch_status(monkeypatch, status_map, text=""):
    from yarag import uploads

    monkeypatch.setattr(uploads.cloudflare, "list_item_status", lambda: status_map)
    monkeypatch.setattr(uploads.cloudflare, "retrieve_text", lambda q, k: text)


def test_documents_status_ready_for_markdown(client, auth_headers, monkeypatch):
    _patch_status(monkeypatch, {"bills/33717.md": {"status": "completed", "checksum": "c1", "error": None}})
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "ready"


def test_documents_status_indexing_when_absent(client, auth_headers, monkeypatch):
    _patch_status(monkeypatch, {})  # key 不在 items
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "indexing"


def test_documents_status_failed_on_error(client, auth_headers, monkeypatch):
    _patch_status(monkeypatch, {"bills/33717.md": {"status": "completed", "checksum": "c1", "error": "boom"}})
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "failed"


def test_documents_status_indexing_when_cloudflare_down(client, auth_headers, monkeypatch):
    from yarag import uploads

    def boom():
        raise RuntimeError("cf down")

    monkeypatch.setattr(uploads.cloudflare, "list_item_status", boom)
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "indexing"  # 安全退預設，列表仍回


def test_documents_status_empty_for_pdf_without_text(client, auth_headers, monkeypatch):
    from yarag import uploads

    class _P:
        def paginate(self, **kw):
            import datetime

            key = "2026/07/15/aa11bb22-scan.pdf"
            entry = {"Key": key, "Size": 9, "LastModified": datetime.datetime(2026, 7, 15)}
            return [{"Contents": [entry]}]

    monkeypatch.setattr(uploads.s3_client, "get_paginator", lambda name: _P())
    _patch_status(
        monkeypatch,
        {"2026/07/15/aa11bb22-scan.pdf": {"status": "completed", "checksum": "cX", "error": None}},
        text="# scan.pdf\n## Metadata\n- x\n\n\n## Contents\n### Page 1",
    )
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "empty"


def test_sync_endpoint_triggers_and_returns_job(client, auth_headers, monkeypatch):
    from yarag import uploads

    monkeypatch.setattr(uploads.cloudflare, "trigger_sync", lambda: "job-9")
    r = client.post("/api/v1/documents/sync", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["job_id"] == "job-9"


def test_sync_endpoint_requires_auth(client):
    assert client.post("/api/v1/documents/sync").status_code == 401


def test_sync_endpoint_502_on_failure(client, auth_headers, monkeypatch):
    from yarag import uploads

    def boom():
        raise RuntimeError("cf down")

    monkeypatch.setattr(uploads.cloudflare, "trigger_sync", boom)
    assert client.post("/api/v1/documents/sync", headers=auth_headers).status_code == 502


def test_documents_status_ready_for_pdf_with_text(client, auth_headers, monkeypatch):
    from yarag import uploads

    class _P:
        def paginate(self, **kw):
            import datetime
            key = "2026/07/15/aa11bb22-real.pdf"
            entry = {"Key": key, "Size": 9, "LastModified": datetime.datetime(2026, 7, 15)}
            return [{"Contents": [entry]}]

    monkeypatch.setattr(uploads.s3_client, "get_paginator", lambda name: _P())
    _patch_status(
        monkeypatch,
        {"2026/07/15/aa11bb22-real.pdf": {"status": "completed", "checksum": "cR", "error": None}},
        text="# real.pdf\n## Metadata\n- x\n\n\n## Contents\n### Page 1\n"
        "這是一份有實際文字內容的申請表單資料內容很多字足夠",
    )
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "ready"


def test_documents_status_indexing_when_content_check_fails(client, auth_headers, monkeypatch):
    from yarag import uploads

    class _P:
        def paginate(self, **kw):
            import datetime
            key = "2026/07/15/aa11bb22-x.pdf"
            entry = {"Key": key, "Size": 9, "LastModified": datetime.datetime(2026, 7, 15)}
            return [{"Contents": [entry]}]

    monkeypatch.setattr(uploads.s3_client, "get_paginator", lambda name: _P())
    monkeypatch.setattr(
        uploads.cloudflare,
        "list_item_status",
        lambda: {"2026/07/15/aa11bb22-x.pdf": {"status": "completed", "checksum": "cF", "error": None}},
    )

    def boom(q, k):
        raise RuntimeError("search down")

    monkeypatch.setattr(uploads.cloudflare, "retrieve_text", boom)
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "indexing"


def test_documents_status_indexing_for_processing(client, auth_headers, monkeypatch):
    _patch_status(monkeypatch, {"bills/33717.md": {"status": "processing", "checksum": "cP", "error": None}})
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "indexing"


def test_documents_content_check_cached(client, auth_headers, monkeypatch):
    from yarag import uploads

    class _P:
        def paginate(self, **kw):
            import datetime
            key = "2026/07/15/aa11bb22-c.pdf"
            entry = {"Key": key, "Size": 9, "LastModified": datetime.datetime(2026, 7, 15)}
            return [{"Contents": [entry]}]

    monkeypatch.setattr(uploads.s3_client, "get_paginator", lambda name: _P())
    monkeypatch.setattr(
        uploads.cloudflare,
        "list_item_status",
        lambda: {"2026/07/15/aa11bb22-c.pdf": {"status": "completed", "checksum": "cCACHE", "error": None}},
    )
    calls = {"n": 0}

    def counting(q, k):
        calls["n"] += 1
        return "# c.pdf\n## Metadata\n\n\n## Contents\n### Page 1"

    monkeypatch.setattr(uploads.cloudflare, "retrieve_text", counting)
    client.get("/api/v1/documents", headers=auth_headers)
    client.get("/api/v1/documents", headers=auth_headers)
    assert calls["n"] == 1  # 第二次命中 checksum 快取，不重打 search


def test_documents_status_indexing_when_key_not_in_search(client, auth_headers, monkeypatch):
    from yarag import uploads

    class _P:
        def paginate(self, **kw):
            import datetime
            key = "2026/07/15/aa11bb22-miss.pdf"
            entry = {"Key": key, "Size": 9, "LastModified": datetime.datetime(2026, 7, 15)}
            return [{"Contents": [entry]}]

    monkeypatch.setattr(uploads.s3_client, "get_paginator", lambda name: _P())
    monkeypatch.setattr(
        uploads.cloudflare,
        "list_item_status",
        lambda: {"2026/07/15/aa11bb22-miss.pdf": {"status": "completed", "checksum": "cMISS", "error": None}},
    )
    monkeypatch.setattr(uploads.cloudflare, "retrieve_text", lambda q, k: "")  # 搜尋未命中此檔
    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert docs[0]["index_status"] == "indexing"  # 未定，不誤判 empty
