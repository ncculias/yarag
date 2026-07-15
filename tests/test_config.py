from yarag.config import settings


def test_settings_has_new_fields():
    assert settings.database_url == "sqlite:///test.db"
    assert settings.jwt_secret == "test-jwt-secret"
    assert settings.jwt_expires_hours == 8
    assert settings.cf_account_id == "test-account"
    assert settings.cf_ai_search_instance == "test-instance"
    assert settings.cf_api_token == "test-cf-token"
    assert "5173" in settings.cors_origins


def test_sync_token_setting_present():
    from yarag.config import settings

    assert settings.cf_sync_api_token == "test-cf-sync-token"
