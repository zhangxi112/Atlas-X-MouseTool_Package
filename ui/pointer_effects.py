"""Pointer effect geometry shared by the desktop overlay and the studio preview."""

from __future__ import annotations

from math import cos, radians, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient


LOCATOR_STYLES = (("focus", "聚焦准星"), ("sonar", "声呐波环"), ("quiet", "静态标记"))


def tint(color: QColor, alpha: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(min(1.0, max(0.0, alpha)))
    return result


def _ring_bounds(radius: float) -> QRectF:
    return QRectF(-radius, -radius, radius * 2, radius * 2)


def draw_locator(painter: QPainter, center: QPointF, size: float, progress: float, color: QColor, style: str) -> None:
    """Draw around the hotspot, leaving the target itself visible."""
    painter.save()
    painter.translate(center)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    fade = min(1.0, (1.0 - progress) * 4)
    ink = QColor("#10202C")
    if style == "quiet":
        radius = max(10.0, size * 0.19)
        for line_color, width in ((ink, 5.0), (color, 2.5)):
            painter.setPen(QPen(line_color, width))
            for quadrant in range(4):
                painter.drawArc(_ring_bounds(radius), (quadrant * 90 + 14) * 16, 62 * 16)
    elif style == "sonar":
        for delay in (0.0, 0.24):
            phase = (progress - delay) / (1 - delay)
            if phase < 0:
                continue
            radius = size * (0.12 + 0.84 * (1 - (1 - phase) ** 2))
            for line_color, width in ((ink, 4.5), (color, 2.2)):
                painter.setPen(QPen(tint(line_color, (1 - phase) * 0.94), width))
                painter.drawEllipse(_ring_bounds(radius))
    else:
        # Four inward-moving brackets make the destination clear on a busy desktop.
        radius = size * (0.19 + 0.62 * (1 - progress) ** 3)
        halo = QRadialGradient(QPointF(), radius * 1.3)
        halo.setColorAt(0, Qt.GlobalColor.transparent)
        halo.setColorAt(0.72, tint(color, 0.12 * fade))
        halo.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(_ring_bounds(radius * 1.3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for line_color, width in ((ink, 5.0), (color, 2.4)):
            painter.setPen(QPen(tint(line_color, fade), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for quadrant in range(4):
                painter.drawArc(_ring_bounds(radius), (quadrant * 90 + 22) * 16, 46 * 16)
        painter.setPen(QPen(tint(QColor("#F9FEFF"), fade), 1.5))
        for angle in (0, 90, 180, 270):
            ux, uy = cos(radians(angle)), sin(radians(angle))
            painter.drawLine(QPointF(ux * radius * 0.62, uy * radius * 0.62), QPointF(ux * radius, uy * radius))
    painter.restore()


def draw_ripple(painter: QPainter, center: QPointF, size: float, progress: float, color: QColor) -> None:
    painter.save()
    painter.translate(center)
    fade = (1 - progress) ** 1.25
    radius = size * (0.09 + 0.88 * (1 - (1 - progress) ** 2))
    light = QRadialGradient(QPointF(), radius)
    light.setColorAt(0, Qt.GlobalColor.transparent)
    light.setColorAt(0.77, tint(color, 0.04 * fade))
    light.setColorAt(1, tint(color, 0.27 * fade))
    painter.setBrush(light)
    painter.setPen(QPen(tint(QColor("#12202A"), 0.72 * fade), 4))
    painter.drawEllipse(_ring_bounds(radius))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(tint(color, 0.96 * fade), 2.2))
    painter.drawEllipse(_ring_bounds(radius))
    painter.setPen(QPen(tint(QColor("#F6FDFF"), 0.82 * fade), 1.6))
    for quadrant in range(4):
        painter.drawArc(_ring_bounds(radius * 0.78), int((quadrant * 90 + 28 * progress) * 16), 30 * 16)
    painter.restore()
