import hashlib
import io
from unittest.mock import Mock

import pytest

from services import u2net_session as module


def make_session(tmp_path):
    session = module.U2NetSession.__new__(module.U2NetSession)
    session.model_home = tmp_path
    session.logger = Mock()
    return session


def test_download_publishes_model_only_after_checksum_validation(tmp_path, monkeypatch):
    session = make_session(tmp_path)
    contents = b"test ONNX model bytes"
    monkeypatch.setattr(module, "U2NET_MODEL_MD5", hashlib.md5(contents).hexdigest())
    download = Mock(return_value=io.BytesIO(contents))
    monkeypatch.setattr(module, "urlopen", download)
    path = session._ensure_model_path()
    assert path.read_bytes() == contents
    download.assert_called_once_with(module.U2NET_MODEL_URL, timeout=module.MODEL_DOWNLOAD_TIMEOUT_SECONDS)
    assert not list(tmp_path.glob("*.partial"))
    download.reset_mock()
    assert session._ensure_model_path() == path
    download.assert_not_called()


@pytest.mark.parametrize("failure", ["interrupted", "checksum", "replace"])
def test_download_failure_keeps_existing_file_and_cleans_temporary_file(tmp_path, monkeypatch, failure):
    session = make_session(tmp_path)
    model = tmp_path / module.U2NET_MODEL_NAME
    model.write_bytes(b"previous model")
    contents = b"replacement model"
    monkeypatch.setattr(module, "U2NET_MODEL_MD5", hashlib.md5(contents).hexdigest())

    class InterruptedResponse(io.BytesIO):
        def read(self, size=-1):
            if self.tell():
                raise TimeoutError("connection lost")
            return super().read(size)

    response = InterruptedResponse(contents) if failure == "interrupted" else io.BytesIO(b"bad checksum" if failure == "checksum" else contents)
    monkeypatch.setattr(module, "urlopen", Mock(return_value=response))
    if failure == "replace":
        monkeypatch.setattr(module.os, "replace", Mock(side_effect=OSError("replace failed")))
    with pytest.raises((OSError, RuntimeError)):
        session._ensure_model_path()
    assert model.read_bytes() == b"previous model"
    assert not list(tmp_path.glob("*.partial"))
