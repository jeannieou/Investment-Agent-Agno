"""User-facing input limits for investment research runs."""

from __future__ import annotations


RECOMMENDED_COMPANY_LIMIT = 6
MAX_COMPANY_LIMIT = 8
DEFAULT_COMPANIES = ["Nvidia", "AMD", "Intel"]


def parse_company_names(raw: str) -> list[str]:
    return [name.strip() for name in raw.split(",") if name.strip()]


def validate_company_limit(company_names: list[str]) -> list[str]:
    if len(company_names) > MAX_COMPANY_LIMIT:
        raise ValueError(
            f"Too many companies: received {len(company_names)}. "
            f"Please enter at most {MAX_COMPANY_LIMIT} company names. "
            f"For best memo quality, use {RECOMMENDED_COMPANY_LIMIT} or fewer."
        )
    return company_names


def usage_note() -> str:
    return (
        f"Usage: enter up to {RECOMMENDED_COMPANY_LIMIT} company names for best memo quality "
        f"(hard limit: {MAX_COMPANY_LIMIT}). Example: Nvidia, AMD, Intel."
    )
