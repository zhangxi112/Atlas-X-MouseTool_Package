"""Minimal local U2Net session used for background removal."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import onnxruntime as ort
from PIL import Image

U2NET_MODEL_NAME = "u2net.onnx"
U2NET_MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"
U2NET_MODEL_MD5 = "60024c5c889badc19c04ad937298a77b"
MODEL_DOWNLOAD_TIMEOUT_SECONDS = 30


class U2NetSession:
    """Small ONNX-backed U2Net wrapper for local background removal."""

    def __init__(self, model_home: Path | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.model_home = model_home or self._resolve_model_home()
        self.model_home.mkdir(parents=True, exist_ok=True)
        self.model_path = self._ensure_model_path()
        session_options = ort.SessionOptions()
        self.inner_session = ort.InferenceSession(
            str(self.model_path),
            sess_options=session_options,
            providers=self._preferred_providers(),
        )

    def predict_mask(self, image: Image.Image) -> Image.Image:
        """Run U2Net inference and return a resized single-channel mask."""
        outputs = self.inner_session.run(None, self._normalize(image))
        prediction = outputs[0][:, 0, :, :]
        max_value = float(np.max(prediction))
        min_value = float(np.min(prediction))
        denominator = max(max_value - min_value, 1e-6)
        prediction = (prediction - min_value) / denominator
        prediction = np.squeeze(prediction)
        mask = Image.fromarray((prediction.clip(0, 1) * 255).astype("uint8"), mode="L")
        return mask.resize(image.size, Image.Resampling.LANCZOS)

    def _normalize(self, image: Image.Image) -> dict[str, np.ndarray]:
        """Prepare RGB tensor exactly as the original U2Net pipeline expects."""
        rgb = image.convert("RGB").resize((320, 320), Image.Resampling.LANCZOS)
        array = np.asarray(rgb, dtype=np.float32)
        array = array / max(float(np.max(array)), 1e-6)

        normalized = np.zeros((array.shape[0], array.shape[1], 3), dtype=np.float32)
        normalized[:, :, 0] = (array[:, :, 0] - 0.485) / 0.229
        normalized[:, :, 1] = (array[:, :, 1] - 0.456) / 0.224
        normalized[:, :, 2] = (array[:, :, 2] - 0.406) / 0.225
        normalized = normalized.transpose((2, 0, 1))

        return {
            self.inner_session.get_inputs()[0].name: np.expand_dims(normalized, 0).astype(np.float32)
        }

    def _preferred_providers(self) -> list[str]:
        """Prefer GPU when available, otherwise keep CPU-only inference stable."""
        available = ort.get_available_providers()
        device = ort.get_device()
        if device.startswith("GPU") and "CUDAExecutionProvider" in available:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if device.startswith("GPU") and "ROCMExecutionProvider" in available:
            return ["ROCMExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def _resolve_model_home(self) -> Path:
        """Match rembg's default model cache location so existing downloads are reused."""
        configured = os.getenv("U2NET_HOME")
        if configured:
            return Path(configured).expanduser()
        xdg_home = os.getenv("XDG_DATA_HOME")
        if xdg_home:
            return Path(xdg_home).expanduser() / ".u2net"
        return Path.home() / ".u2net"

    def _ensure_model_path(self) -> Path:
        """Reuse an existing model file or download it once with checksum validation."""
        model_path = self.model_home / U2NET_MODEL_NAME
        if model_path.exists() and self._md5(model_path) == U2NET_MODEL_MD5:
            return model_path

        self.logger.info("Downloading U2Net model to %s", model_path)
        temporary_path = None
        try:
            with urlopen(U2NET_MODEL_URL, timeout=MODEL_DOWNLOAD_TIMEOUT_SECONDS) as response:
                with tempfile.NamedTemporaryFile(dir=self.model_home, prefix="u2net-", suffix=".partial", delete=False) as target:
                    temporary_path = Path(target.name)
                    while chunk := response.read(1024 * 1024):
                        target.write(chunk)
                    target.flush()
                    os.fsync(target.fileno())
            if self._md5(temporary_path) != U2NET_MODEL_MD5:
                raise RuntimeError("Downloaded U2Net model checksum mismatch")
            os.replace(temporary_path, model_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return model_path

    def _md5(self, path: Path) -> str:
        """Return the md5 checksum for the given file."""
        digest = hashlib.md5()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
