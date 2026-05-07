from app.schemas import CompanyIdentity
from app.tools.entity_resolution import enrich_identity


def test_enrich_identity_preserves_raw_input_and_aliases() -> None:
    identity = CompanyIdentity(
        name="NVIDIA Corporation",
        url="https://www.nvidia.com",
        description="GPU company",
        ticker="NVDA",
        company_type="public",
    )

    enriched, warnings = enrich_identity(identity, "Nvidia")

    assert enriched.raw_input == "Nvidia"
    assert "Nvidia" in enriched.aliases
    assert "NVIDIA Corporation" in enriched.aliases
    assert warnings == []


def test_enrich_identity_maps_kfc_to_public_parent() -> None:
    identity = CompanyIdentity(
        name="KFC",
        url="https://global.kfc.com",
        description="Chicken restaurant brand",
        company_type="unknown",
    )

    enriched, warnings = enrich_identity(identity, "KFC")

    assert enriched.name == "Yum! Brands"
    assert enriched.raw_input == "KFC"
    assert enriched.trade_name == "KFC"
    assert enriched.parent_company == "Yum! Brands, Inc."
    assert enriched.ticker == "YUM"
    assert enriched.exchange == "NYSE"
    assert enriched.is_investable_entity is True
    assert any("parent/investable entity" in warning for warning in warnings)


def test_enrich_identity_flags_twitter_as_private_not_public_equity() -> None:
    identity = CompanyIdentity(
        name="Twitter",
        url="https://x.com",
        description="Social media company",
        company_type="unknown",
    )

    enriched, warnings = enrich_identity(identity, "Twitter")

    assert enriched.name == "X"
    assert enriched.company_type == "private"
    assert enriched.is_investable_entity is False
    assert enriched.ticker is None
    assert any("not currently a public investable equity" in warning for warning in warnings)
