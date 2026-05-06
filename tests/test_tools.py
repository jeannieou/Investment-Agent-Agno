from app.agents import research_agent
from app.tools._utils import clean_text
from app.tools.exa_search import search_exa
from app.tools.sec_edgar import extract_financial_summary, fetch_sec_financial_data, resolve_cik
from app.tools.web_search import search_company_web
from app.tools.wikipedia import fetch_wikipedia_summary


class MockResponse:
    def __init__(self, payload, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


def test_clean_text_strips_html_and_caps_length() -> None:
    assert clean_text("<p>Hello   world</p>", max_chars=5) == "Hello"


def test_fetch_wikipedia_summary_returns_evidence(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None):
        return MockResponse(
            {
                "title": "Nvidia",
                "extract": "Nvidia is a technology company.",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Nvidia"}},
            }
        )

    monkeypatch.setattr("app.tools.wikipedia.requests.get", fake_get)

    sources = fetch_wikipedia_summary("Nvidia")

    assert len(sources) == 1
    assert sources[0].publisher == "Wikipedia"
    assert sources[0].url == "https://en.wikipedia.org/wiki/Nvidia"


def test_fetch_wikipedia_summary_returns_empty_on_failure(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None):
        return MockResponse({}, status_code=404)

    monkeypatch.setattr("app.tools.wikipedia.requests.get", fake_get)

    assert fetch_wikipedia_summary("UnknownCo") == []


def test_fetch_wikipedia_summary_uses_search_fallback(monkeypatch) -> None:
    def fake_get(url, params=None, headers=None, timeout=None):
        if "w/api.php" in url:
            return MockResponse(["LVMH Moet Hennessy Louis Vuitton", ["LVMH"]])
        if url.endswith("/LVMH"):
            return MockResponse(
                {
                    "title": "LVMH",
                    "extract": "LVMH is a French luxury goods conglomerate.",
                    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/LVMH"}},
                }
            )
        return MockResponse({}, status_code=404)

    monkeypatch.setattr("app.tools.wikipedia.requests.get", fake_get)

    sources = fetch_wikipedia_summary("LVMH Moet Hennessy Louis Vuitton")

    assert len(sources) == 1
    assert sources[0].title == "LVMH"


def test_fetch_wikipedia_summary_uses_generated_uppercase_candidate(monkeypatch) -> None:
    def fake_get(url, params=None, headers=None, timeout=None):
        if url.endswith("/LVMH"):
            return MockResponse(
                {
                    "title": "LVMH",
                    "extract": "LVMH is a French luxury goods conglomerate.",
                    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/LVMH"}},
                }
            )
        return MockResponse({}, status_code=404)

    monkeypatch.setattr("app.tools.wikipedia.requests.get", fake_get)

    sources = fetch_wikipedia_summary("LVMH Moet Hennessy Louis Vuitton")

    assert len(sources) == 1
    assert sources[0].url == "https://en.wikipedia.org/wiki/LVMH"


def test_resolve_cik_uses_ticker(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None):
        return MockResponse(
            {
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                "1": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
            }
        )

    monkeypatch.setattr("app.tools.sec_edgar.requests.get", fake_get)

    assert resolve_cik("Nvidia", ticker="NVDA") == "0001045810"


def test_extract_financial_summary_parses_latest_revenue_and_profit() -> None:
    summary = extract_financial_summary(
        {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {"val": 100, "end": "2023-12-31", "fy": 2023, "fp": "FY", "form": "10-K"},
                                {"val": 200, "end": "2024-12-31", "fy": 2024, "fp": "FY", "form": "10-K"},
                            ]
                        }
                    },
                    "NetIncomeLoss": {
                        "units": {
                            "USD": [
                                {"val": 50, "end": "2024-12-31", "fy": 2024, "fp": "FY", "form": "10-K"}
                            ]
                        }
                    },
                }
            }
        }
    )

    assert "200 USD" in summary
    assert "50 USD" in summary


def test_fetch_sec_financial_data_returns_evidence(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("company_tickers.json"):
            return MockResponse({"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"}})
        return MockResponse(
            {
                "entityName": "NVIDIA CORP",
                "facts": {
                    "us-gaap": {
                        "Revenues": {
                            "units": {
                                "USD": [
                                    {"val": 200, "end": "2024-12-31", "fy": 2024, "fp": "FY", "form": "10-K"}
                                ]
                            }
                        }
                    }
                },
            }
        )

    monkeypatch.setattr("app.tools.sec_edgar.requests.get", fake_get)

    sources = fetch_sec_financial_data("Nvidia", ticker="NVDA")

    assert len(sources) == 1
    assert sources[0].publisher == "SEC EDGAR"
    assert "200 USD" in sources[0].snippet


def test_search_company_web_returns_evidence(monkeypatch) -> None:
    def fake_get(url, params=None, headers=None, timeout=None):
        return MockResponse(
            {
                "Heading": "Nvidia",
                "AbstractText": "Nvidia is a technology company.",
                "AbstractURL": "https://example.com/nvidia",
                "RelatedTopics": [
                    {"Text": "Nvidia news - product update", "FirstURL": "https://example.com/news"}
                ],
            }
        )

    monkeypatch.setattr("app.tools.web_search.requests.get", fake_get)

    sources = search_company_web("Nvidia recent news")

    assert len(sources) == 2
    assert sources[0].url == "https://example.com/nvidia"


def test_search_exa_returns_evidence(monkeypatch) -> None:
    def fake_post(url, headers=None, json=None, timeout=None):
        assert headers["x-api-key"] == "test-key"
        assert json["contents"]["highlights"]["maxCharacters"] == 1000
        return MockResponse(
            {
                "results": [
                    {
                        "title": "Nvidia latest AI chip coverage",
                        "url": "https://example.com/nvidia-news",
                        "publishedDate": "2026-01-01T00:00:00.000Z",
                        "highlights": ["Nvidia announced a new AI chip for data centers."],
                    }
                ]
            }
        )

    monkeypatch.setattr("app.tools.exa_search.requests.post", fake_post)

    sources = search_exa("Nvidia recent news", api_key="test-key")

    assert len(sources) == 1
    assert sources[0].url == "https://example.com/nvidia-news"
    assert sources[0].publisher == "example.com"
    assert "AI chip" in sources[0].snippet


def test_search_exa_returns_empty_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    assert search_exa("Nvidia recent news") == []


def test_research_agent_has_stage4_tools() -> None:
    tool_names = {tool.name for tool in research_agent.tools}

    assert {
        "get_wiki_summary",
        "get_financial_data",
        "search_exa_for_company",
        "search_web_for_company",
    } <= tool_names
