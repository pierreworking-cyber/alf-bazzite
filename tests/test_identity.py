from alf import identity


def test_get_identity_bootstraps_default(monkeypatch, tmp_path):
    monkeypatch.setattr(
        identity,
        "get_data_directory",
        lambda: tmp_path / "alf",
    )

    result = identity.get_identity()

    identity_file = tmp_path / "alf" / "identity.toml"

    assert identity_file.exists()
    assert result["name"] == "ALF"
    assert result["owner"] == "Peter"
    assert result["purpose"] == "Peter's long-term computing companion"


def test_get_identity_preserves_existing_identity(monkeypatch, tmp_path):
    data_directory = tmp_path / "alf"
    data_directory.mkdir()

    identity_file = data_directory / "identity.toml"
    identity_file.write_text(
        'name = "My ALF"\n'
        'owner = "Someone Else"\n'
        'purpose = "A different companion"\n'
        'capabilities = []\n'
        'limitations = []\n'
    )

    monkeypatch.setattr(
        identity,
        "get_data_directory",
        lambda: data_directory,
    )

    result = identity.get_identity()

    assert result["name"] == "My ALF"
    assert result["owner"] == "Someone Else"
    assert result["purpose"] == "A different companion"
