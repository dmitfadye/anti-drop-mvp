"""Liveness is distinct from durable-service readiness."""
import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from main import app


def test_readiness_fails_closed_without_storage_configuration(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get('/api/health').status_code == 200
    response = client.get('/api/ready')
    assert response.status_code == 503
    assert response.json()['error_code'] == 'DATABASE_UNAVAILABLE'
    assert response.json()['request_id'] == response.headers['X-Request-ID']


def test_readiness_unavailable_postgres_does_not_leak_connection(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://unavailable:private_test_marker@127.0.0.1:1/unavailable')
    response = TestClient(app, raise_server_exceptions=False).get('/api/ready')
    assert response.status_code == 503
    assert 'private_test_marker' not in response.text
    assert 'postgresql+psycopg' not in response.text


def test_readiness_checks_migrated_real_postgres(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL required: readiness needs actual PostgreSQL')
    assert make_url(url).database.startswith('antidrop_test')
    monkeypatch.setenv('DATABASE_URL', url)
    command.upgrade(Config('alembic.ini'), 'head')
    response = TestClient(app, raise_server_exceptions=False).get('/api/ready')
    assert response.status_code == 200, response.text
    assert response.json() == {'status': 'ready', 'database': 'postgresql', 'demo_mode': True}
