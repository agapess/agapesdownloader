import os
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_PASSWORD', 'testpass123')
os.environ['TESTING'] = '1'


@pytest.fixture
def app(tmp_path):
    from app import app as flask_app
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'DOWNLOAD_FOLDER': str(tmp_path),
    })
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as sess:
        sess['admin'] = True
    return client
