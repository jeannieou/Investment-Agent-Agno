"""Entity-resolution helpers for preserving and validating user input."""

from __future__ import annotations

from app.schemas import CompanyIdentity, EvidenceSource


_PUBLIC_BRAND_HINTS = {
    "lv": {
        "name": "LVMH",
        "legal_name": "LVMH Moet Hennessy Louis Vuitton SE",
        "trade_name": "Louis Vuitton",
        "parent_company": "LVMH Moet Hennessy Louis Vuitton SE",
        "ticker": "MC.PA",
        "exchange": "Euronext Paris",
        "country": "France",
        "currency": "EUR",
        "url": "https://www.lvmh.com",
        "description": "Luxury goods group and parent company of Louis Vuitton.",
        "aliases": ["LV", "Louis Vuitton", "LVMH", "LVMH Moet Hennessy Louis Vuitton"],
        "note": "User input appears to refer to Louis Vuitton; the investable public parent is LVMH.",
    },
    "kfc": {
        "name": "Yum! Brands",
        "legal_name": "Yum! Brands, Inc.",
        "trade_name": "KFC",
        "parent_company": "Yum! Brands, Inc.",
        "ticker": "YUM",
        "exchange": "NYSE",
        "country": "United States",
        "currency": "USD",
        "url": "https://www.yum.com",
        "description": "Restaurant company and public parent of KFC.",
        "aliases": ["KFC", "Kentucky Fried Chicken", "Yum! Brands"],
        "note": "KFC is a brand; the investable public parent is usually Yum! Brands. Yum China is separate and should be checked for China-specific analysis.",
    },
    "google": {
        "name": "Alphabet",
        "legal_name": "Alphabet Inc.",
        "trade_name": "Google",
        "parent_company": "Alphabet Inc.",
        "ticker": "GOOGL",
        "exchange": "NASDAQ",
        "country": "United States",
        "currency": "USD",
        "url": "https://abc.xyz",
        "description": "Public parent company of Google.",
        "aliases": ["Google", "Alphabet", "GOOG", "GOOGL"],
        "note": "Google is analyzed through public parent Alphabet.",
    },
    "twitter": {
        "name": "X",
        "legal_name": "X Corp.",
        "trade_name": "Twitter",
        "parent_company": "X Holdings Corp.",
        "ticker": None,
        "exchange": None,
        "country": "United States",
        "currency": "USD",
        "url": "https://x.com",
        "description": "Social media company formerly known as Twitter; currently private.",
        "aliases": ["Twitter", "X", "X Corp."],
        "note": "Twitter was taken private and is not currently a public investable equity.",
        "company_type": "private",
        "is_investable_entity": False,
    },
}


def enrich_identity(identity: CompanyIdentity, raw_input: str) -> tuple[CompanyIdentity, list[str]]:
    """Preserve raw input and add conservative resolution metadata.

    This helper does not replace source-backed LLM/tool resolution. It guards the
    workflow against common brand/subsidiary inputs and makes uncertainty visible
    in `run_log.warnings`.
    """

    warnings: list[str] = []
    normalized = _normalize(raw_input)
    hint = _PUBLIC_BRAND_HINTS.get(normalized)

    if hint:
        identity = identity.model_copy(
            update={
                "raw_input": raw_input,
                "name": hint["name"],
                "legal_name": hint["legal_name"],
                "trade_name": hint["trade_name"],
                "parent_company": hint["parent_company"],
                "ticker": hint["ticker"],
                "exchange": hint["exchange"],
                "country": hint["country"],
                "currency": hint["currency"],
                "url": hint["url"],
                "description": hint["description"],
                "aliases": hint["aliases"],
                "company_type": hint.get("company_type", "public"),
                "is_investable_entity": hint.get("is_investable_entity", True),
                "confidence": "high",
                "resolution_note": hint["note"],
                "sources": _merge_sources(
                    identity.sources,
                    EvidenceSource(
                        title=f"{hint['name']} official site",
                        url=hint["url"],
                        publisher="Official company website",
                        snippet=hint["note"],
                    ),
                ),
            }
        )
        warnings.append(f"{raw_input}: resolved as {identity.name}. {identity.resolution_note}")
    else:
        update = {
            "raw_input": raw_input,
            "aliases": _dedupe([raw_input, *identity.aliases, identity.name]),
        }
        if not identity.resolution_note:
            update["resolution_note"] = "No brand-to-parent override was applied; identity comes from the Identity Agent."
        identity = identity.model_copy(update=update)

    warnings.extend(_identity_warnings(identity))
    return identity, warnings


def source_urls(sources: list[EvidenceSource]) -> set[str]:
    return {source.url for source in sources if source.url}


def _identity_warnings(identity: CompanyIdentity) -> list[str]:
    warnings: list[str] = []
    if identity.confidence == "low":
        warnings.append(f"{identity.raw_input}: low-confidence company identity resolution.")
    if identity.trade_name and identity.parent_company and identity.trade_name != identity.parent_company:
        warnings.append(
            f"{identity.raw_input}: analyzed through parent/investable entity {identity.parent_company}."
        )
    if not identity.is_investable_entity:
        warnings.append(f"{identity.raw_input}: resolved entity is not currently a public investable equity.")
    if identity.company_type == "public" and not identity.ticker:
        warnings.append(f"{identity.raw_input}: public company identified but ticker is missing.")
    return warnings


def _merge_sources(existing: list[EvidenceSource], source: EvidenceSource) -> list[EvidenceSource]:
    urls = source_urls(existing)
    if source.url in urls:
        return existing
    return [*existing, source]


def _dedupe(items: list[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item:
            continue
        clean = " ".join(item.split())
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("!", "").split())
