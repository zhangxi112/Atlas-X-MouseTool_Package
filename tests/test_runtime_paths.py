import os

from core.constants import APP_ID
from services import runtime_paths


def test_unwritable_appdata_falls_back_to_localappdata(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(blocked))
    expected = runtime_paths.Path(os.environ["LOCALAPPDATA"]) / APP_ID
    assert runtime_paths.user_data_dir() == expected


def test_existing_readonly_directory_is_not_accepted(tmp_path, monkeypatch):
    first = runtime_paths.Path(os.environ["APPDATA"]) / APP_ID
    first.mkdir(parents=True)
    original = runtime_paths.tempfile.TemporaryFile

    def probe(*args, **kwargs):
        if kwargs.get("dir") == first:
            raise PermissionError("read-only directory")
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime_paths.tempfile, "TemporaryFile", probe)
    assert runtime_paths.user_data_dir() == runtime_paths.Path(os.environ["LOCALAPPDATA"]) / APP_ID


def test_missing_appdata_uses_home_instead_of_install_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("APPDATA")
    monkeypatch.delenv("LOCALAPPDATA")
    monkeypatch.setattr(runtime_paths.Path, "home", lambda: tmp_path)
    assert runtime_paths.user_data_dir() == tmp_path / f".{APP_ID}"
