import pytest

from alf import memory


@pytest.fixture
def database(tmp_path, monkeypatch):
    database = tmp_path / "alf.db"
    monkeypatch.setattr(memory, "DATABASE", database)
    return database