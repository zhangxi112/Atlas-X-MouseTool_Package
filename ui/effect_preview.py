"""Interactive, local preview of the two desktop emphasis effects."""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from ui.pointer_effects import draw_locator, draw_ripple


class EffectPreview(QWidget):
    def __init__(self, config_provider, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.setMinimumHeight(216)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("视效试用区，单击预览点击波纹，按空格预览定位")
        self.artwork = QPixmap()
        self.hotspot = QPointF()
        self.position: QPointF | None = None
        self.effect = ""
        self.started_at = 0.0
        self.duration_ms = 1
        self.button_color = QColor("#6EB6FF")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance)

    def set_artwork(self, pixmap: QPixmap, hotspot: QPointF) -> None:
        self.artwork = pixmap
        self.hotspot = hotspot
        self.update()

    def play(self, effect: str = "locator", position: QPointF | None = None) -> None:
        self.position = position
        self.effect = effect
        config = self.config_provider()
        self.duration_ms = config.highlight.duration_ms if effect == "locator" else config.click_ripple.duration_ms
        self.started_at = time.perf_counter()
        quiet = effect == "locator" and config.highlight.style == "quiet"
        self.timer.start(self.duration_ms if quiet else 16)
        self.update()

    def _advance(self) -> None:
        if (time.perf_counter() - self.started_at) * 1000 >= self.duration_ms:
            self.effect = ""
            self.timer.stop()
        self.update()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        self.effect = ""
        super().hideEvent(event)

    def mousePressEvent(self, event) -> None:
        self.button_color = {Qt.MouseButton.RightButton: QColor("#F472B6"),
                             Qt.MouseButton.MiddleButton: QColor("#10B981")}.get(event.button(), QColor("#3B82F6"))
        self.play("ripple", event.position())
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self.play()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        center = area.center()
        config = self.config_provider()
        dark = config.appearance.theme_mode != "light"
        background = QLinearGradient(area.topLeft(), area.bottomRight())
        background.setColorAt(0, QColor("#102A2C" if dark else "#E2F0EC"))
        background.setColorAt(1, QColor("#101B25" if dark else "#F4F7F7"))
        painter.setBrush(background)
        painter.setPen(QPen(QColor("#4EB8A8" if self.hasFocus() else "#35605D" if dark else "#A5C6BD"), 1))
        painter.drawRoundedRect(area, 11, 11)
        grid = QColor(112, 175, 164, 60 if dark else 90)
        painter.setPen(QPen(grid, 1))
        for x in range(int(center.x()) % 24 + 12, self.width() - 8, 24):
            for y in range(int(center.y()) % 24 + 12, self.height() - 8, 24):
                painter.drawPoint(x, y)
        axis = QPen(grid, 1, Qt.PenStyle.DashLine)
        painter.setPen(axis)
        painter.drawLine(QPointF(16, center.y()), QPointF(area.right() - 16, center.y()))
        painter.drawLine(QPointF(center.x(), 12), QPointF(center.x(), area.bottom() - 12))
        pupil = self.position if self.position is not None else center
        glow = QRadialGradient(pupil, 80)
        glow.setColorAt(0, QColor(77, 215, 174, 45))
        glow.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(pupil, 80, 80)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(grid, 1))
        for radius in (43, 75):
            painter.drawEllipse(pupil, radius, radius)
        progress = min(1.0, (time.perf_counter() - self.started_at) * 1000 / self.duration_ms)
        if self.effect == "locator":
            draw_locator(painter, pupil, min(config.highlight.ring_size, area.height() * 0.48),
                         progress, QColor(config.pointer.trail_color), config.highlight.style)
        elif self.effect == "ripple":
            draw_ripple(painter, pupil, min(config.click_ripple.size, area.height() * 0.48), progress, self.button_color)
        if not self.artwork.isNull():
            side = min(self.artwork.width(), area.height() * 0.43)
            rect = QRectF(pupil.x() - side * self.hotspot.x(), pupil.y() - side * self.hotspot.y(), side, side)
            painter.drawPixmap(rect, self.artwork, QRectF(self.artwork.rect()))
        painter.end()
