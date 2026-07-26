"""Unit tests for url_shortener.db's connection-string construction logic."""

from __future__ import annotations

from url_shortener.db import _database_url, _read_secret


def test_database_url_defaults_to_sqlite_without_postgres_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    assert _database_url() == "sqlite:///./url_shortener.db"


def test_database_url_uses_explicit_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://custom/override")
    assert _database_url() == "postgresql+psycopg://custom/override"


def test_database_url_builds_from_postgres_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "url_shortener")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "mydb")
    assert _database_url() == "postgresql+psycopg://url_shortener:secret@db-host:5433/mydb"


def test_database_url_uses_defaults_for_optional_postgres_fields(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "url_shortener")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    assert _database_url() == "postgresql+psycopg://url_shortener:@postgres:5432/url_shortener"


def test_database_url_reads_password_from_file(monkeypatch, tmp_path):
    secret_file = tmp_path / "postgres_password.txt"
    secret_file.write_text("secret-from-file\n", encoding="utf-8")

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "url_shortener")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", str(secret_file))
    monkeypatch.setenv("POSTGRES_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "mydb")
    assert _database_url() == "postgresql+psycopg://url_shortener:secret-from-file@db-host:5433/mydb"


def test_read_secret_prefers_direct_env_var_over_file(monkeypatch, tmp_path):
    secret_file = tmp_path / "x.txt"
    secret_file.write_text("from-file", encoding="utf-8")
    monkeypatch.setenv("SOME_VALUE", "direct")
    monkeypatch.setenv("SOME_VALUE_FILE", str(secret_file))
    assert _read_secret("SOME_VALUE") == "direct"
