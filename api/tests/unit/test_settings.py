from tests.conftest import make_settings


def test_openfga_defaults() -> None:
    # TEST_SETTINGS_DEFAULTS provides a non-empty OPENFGA_STORE_ID (needed so
    # every test building a real app via AppContainer.build() passes
    # ensure_startup_config's OpenFGA check) — override it back to "" here to
    # verify the field's own bare default.
    settings = make_settings(OPENFGA_STORE_ID="")
    assert settings.openfga_api_url == "http://localhost:8080"
    assert settings.openfga_store_id == ""
    assert settings.openfga_authorization_model_id == ""
    assert settings.openfga_timeout_seconds == 10.0


def test_openfga_overrides() -> None:
    settings = make_settings(
        OPENFGA_API_URL="http://openfga.internal:8080",
        OPENFGA_STORE_ID="01ABCXYZ",
        OPENFGA_AUTHORIZATION_MODEL_ID="model-456",
        OPENFGA_TIMEOUT_SECONDS="5.0",
    )
    assert settings.openfga_api_url == "http://openfga.internal:8080"
    assert settings.openfga_store_id == "01ABCXYZ"
    assert settings.openfga_authorization_model_id == "model-456"
    assert settings.openfga_timeout_seconds == 5.0
