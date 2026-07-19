def test_extract_single_id():
    from yarag.bills import extract_bill_ids

    assert extract_bill_ids("議案34619的內容是什麼") == ["34619"]


def test_extract_multiple_ids_dedup_and_order():
    from yarag.bills import extract_bill_ids

    assert extract_bill_ids("比較 34619 和 33835，還有 34619") == ["34619", "33835"]


def test_extract_none_when_no_number():
    from yarag.bills import extract_bill_ids

    assert extract_bill_ids("校園霸凌相關議案有哪些") == []


def test_extract_ignores_too_short_or_long():
    from yarag.bills import extract_bill_ids

    assert extract_bill_ids("有 12 間教室與 1234567 號") == []


def test_fetch_bill_returns_content(monkeypatch):
    from yarag import bills

    class _S3:
        def get_object(self, Bucket, Key):
            assert Key == "bills/34619.md"
            return {"Body": type("B", (), {"read": lambda self: "議案內容".encode()})()}

    monkeypatch.setattr(bills, "s3_client", _S3())
    assert bills.fetch_bill("34619") == "議案內容"


def test_fetch_bill_returns_none_when_missing(monkeypatch):
    from yarag import bills

    class _S3:
        def get_object(self, Bucket, Key):
            raise RuntimeError("NoSuchKey")

    monkeypatch.setattr(bills, "s3_client", _S3())
    assert bills.fetch_bill("99999") is None
