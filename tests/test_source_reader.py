from app.tools.source_reader import read_source_text


class MockResponse:
    def __init__(self, text: str, content_type: str = "text/html", content: bytes | None = None):
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None


def test_read_source_text_extracts_html_text(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None):
        return MockResponse("<html><script>skip()</script><body><h1>Revenue</h1><p>80.8 billion euros</p></body></html>")

    monkeypatch.setattr("app.tools.source_reader.requests.get", fake_get)

    result = read_source_text("https://example.com/key-figures")

    assert result.success is True
    assert result.content_type == "html"
    assert "80.8 billion euros" in result.text
    assert "skip" not in result.text


def test_read_source_text_returns_failure_on_request_error(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None):
        raise RuntimeError("network failed")

    monkeypatch.setattr("app.tools.source_reader.requests.get", fake_get)

    result = read_source_text("https://example.com/fail")

    assert result.success is False
    assert result.error
