from __future__ import annotations

from app.config import Settings, parse_bool


def test_parse_bool_understands_common_values():
    assert parse_bool("true") is True
    assert parse_bool("1") is True
    assert parse_bool("false") is False
    assert parse_bool("0") is False


def test_settings_from_env_defaults_ssl_verification_to_false(monkeypatch):
    monkeypatch.delenv("HTTP_VERIFY_SSL", raising=False)
    monkeypatch.delenv("HTTP_CA_BUNDLE_PATH", raising=False)

    settings = Settings.from_env()

    assert settings.http_verify_ssl is False
    assert settings.http_ca_bundle_path is None


def test_settings_from_env_reads_tls_configuration(monkeypatch):
    monkeypatch.setenv("HTTP_VERIFY_SSL", "false")
    monkeypatch.setenv("HTTP_CA_BUNDLE_PATH", " /certs/root.pem ")

    settings = Settings.from_env()

    assert settings.http_verify_ssl is False
    assert settings.http_ca_bundle_path == "/certs/root.pem"
