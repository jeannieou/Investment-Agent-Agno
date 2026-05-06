from app.config import get_settings


def test_app_imports() -> None:
    settings = get_settings()
    assert settings.llm_provider

