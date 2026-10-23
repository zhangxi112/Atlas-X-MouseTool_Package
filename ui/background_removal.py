"""Run model loading and image inference outside the Qt GUI thread."""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread

from services.image_pipeline import CursorProject, ImagePipeline


class BackgroundRemovalTask(QThread):
    def __init__(self, pipeline: ImagePipeline, project: CursorProject, parent=None) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.project = project
        self.error: str | None = None

    def run(self) -> None:
        try:
            self.pipeline.remove_background(self.project)
        except Exception as exc:
            logging.getLogger(__name__).exception("Background removal failed")
            self.error = str(exc) or type(exc).__name__
