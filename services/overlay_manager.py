"""Mouse-find, motion-trail, and click-ripple overlay manager."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPainterPath, QPen, QRadialGradient, QRegion, QScreen
from PySide6.QtWidgets import QApplication, QWidget

from ui.pointer_effects import draw_locator, draw_ripple


@dataclass(slots=True)
class RippleState:
    center: QPoint
    started_at: float
    duration_ms: int
    size: int
    color: QColor


@dataclass(slots=True)
class TrailState:
    points: list[QPoint]
    started_at: float
    duration_ms: int
    size: int
    color: QColor
    style: str


class EffectOverlay(QWidget):
    """Transparent top-level window used for pointer emphasis animations."""

    def __init__(self, screen_geometry: QRect) -> None:
        super().__init__(None)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setGeometry(screen_geometry)
        self._find_center = QPoint(0, 0)
        self._find_duration_ms = 1500
        self._find_ring_size = 220
        self._find_started_at = 0.0
        self._find_active = False
        self._find_style = 'focus'
        self._find_color = QColor('#5EEAD4')
        self._previous_region = QRegion()
        self._ripples: list[RippleState] = []
        self._trails: list[TrailState] = []
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance)
        self._follow_pointer = False
        self._follow_pointer_pos = QPoint(0, 0)
        self._follow_pointer_size = 0
        self._follow_pointer_color = QColor(34, 211, 238)

    def start_find_effect(self, global_cursor_pos: QPoint, duration_ms: int, ring_size: int, style: str, color: QColor) -> None:
        self._find_style = style
        self._find_color = color
        self._find_duration_ms = duration_ms
        self._find_ring_size = ring_size
        self._find_center = global_cursor_pos - self.geometry().topLeft()
        self._find_started_at = time.perf_counter()
        self._find_active = True
        self._ensure_running()

    def add_click_ripple(self, global_cursor_pos: QPoint, duration_ms: int, size: int, color: QColor) -> None:
        self._ripples = self._ripples[-23:]
        self._ripples.append(RippleState(global_cursor_pos - self.geometry().topLeft(), time.perf_counter(), duration_ms, size, color))
        self._ensure_running()

    def add_motion_trail(self, global_points: list[QPoint], duration_ms: int, size: int, color: QColor, style: str, replace: bool = False) -> None:
        if not global_points:
            return
        local_points = [point - self.geometry().topLeft() for point in global_points]
        state = TrailState(local_points, time.perf_counter(), duration_ms, size, color, style)
        if replace:
            self._trails = [state]
        else:
            self._trails = self._trails[-11:]
            self._trails.append(state)
        self._ensure_running()

    def set_follow_pointer(self, global_cursor_pos: QPoint, size: int, color: QColor) -> None:
        position = global_cursor_pos - self.geometry().topLeft()
        if self._follow_pointer and (position, size, color) == (self._follow_pointer_pos, self._follow_pointer_size, self._follow_pointer_color):
            return
        self._follow_pointer = True
        self._follow_pointer_pos = position
        self._follow_pointer_size = size
        self._follow_pointer_color = color
        self._ensure_running()

    def clear_follow_pointer(self) -> None:
        if self._follow_pointer:
            self._follow_pointer = False
            self._present()

    def reset(self) -> None:
        self._find_active = self._follow_pointer = False
        self._ripples.clear()
        self._trails.clear()
        self._timer.stop()
        self._previous_region = QRegion()
        self.hide()

    @staticmethod
    def _around(point: QPoint, extent: float) -> QRect:
        radius = int(extent) + 4
        return QRect(point.x() - radius, point.y() - radius, 2 * radius + 1, 2 * radius + 1)

    def _effect_region(self) -> QRegion:
        region = QRegion()
        if self._find_active:
            region |= self._around(self._find_center, self._find_ring_size * 1.1)
        for ripple in self._ripples:
            region |= self._around(ripple.center, ripple.size)
        for trail in self._trails:
            bounds = QRect(trail.points[0], trail.points[0])
            for point in trail.points[1:]:
                bounds = bounds.united(QRect(point, point))
            margin = int(max(30, trail.size * 0.45))
            region |= bounds.adjusted(-margin, -margin, margin, margin)
        if self._follow_pointer:
            region |= self._around(self._follow_pointer_pos, self._follow_pointer_size)
        return region.intersected(self.rect())

    def _present(self) -> None:
        region = self._effect_region()
        dirty = self._previous_region.united(region)
        self._previous_region = region
        if not dirty.isEmpty():
            self.update(dirty)
        if not (self._ripples or self._trails or self._find_active):
            self._timer.stop()
            if not self._follow_pointer:
                self.hide()
        elif self._find_active and self._find_style == "quiet" and not (self._ripples or self._trails):
            remaining = self._find_duration_ms - (time.perf_counter() - self._find_started_at) * 1000
            self._timer.start(max(1, int(remaining) + 1))
        elif not self._timer.isActive() or self._timer.interval() != 16:
            self._timer.start(16)

    def _ensure_running(self) -> None:
        if not self.isVisible():
            self.show()
            self.raise_()
        self._present()

    def _advance(self) -> None:
        now = time.perf_counter()
        if self._find_active and (now - self._find_started_at) * 1000 >= self._find_duration_ms:
            self._find_active = False
        self._ripples = [ripple for ripple in self._ripples if (now - ripple.started_at) * 1000 < ripple.duration_ms]
        self._trails = [trail for trail in self._trails if (now - trail.started_at) * 1000 < trail.duration_ms]
        self._present()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(event.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for trail in self._trails:
            self._paint_motion_trail(painter, trail)
        if self._find_active:
            self._paint_find_effect(painter)
        if self._follow_pointer:
            self._paint_follow_pointer(painter)
        for ripple in self._ripples:
            self._paint_click_ripple(painter, ripple)
        painter.end()

    def _paint_find_effect(self, painter: QPainter) -> None:
        progress = min(1.0, max(0.0, ((time.perf_counter() - self._find_started_at) * 1000) / self._find_duration_ms))
        draw_locator(painter, self._find_center, self._find_ring_size, progress, self._find_color, self._find_style)

    def _paint_follow_pointer(self, painter: QPainter) -> None:
        size = max(120, self._follow_pointer_size)
        tip_x = self._follow_pointer_pos.x()
        tip_y = self._follow_pointer_pos.y()
        path = QPainterPath()
        path.moveTo(tip_x, tip_y)
        path.lineTo(tip_x + size * 0.20, tip_y + size * 0.62)
        path.lineTo(tip_x + size * 0.33, tip_y + size * 0.48)
        path.lineTo(tip_x + size * 0.47, tip_y + size * 0.90)
        path.lineTo(tip_x + size * 0.63, tip_y + size * 0.82)
        path.lineTo(tip_x + size * 0.49, tip_y + size * 0.41)
        path.lineTo(tip_x + size * 0.84, tip_y + size * 0.41)
        path.closeSubpath()

        glow_pen = QPen(QColor(self._follow_pointer_color.red(), self._follow_pointer_color.green(), self._follow_pointer_color.blue(), 110), max(10, int(size * 0.045)))
        glow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(glow_pen)
        painter.setBrush(QColor(self._follow_pointer_color.red(), self._follow_pointer_color.green(), self._follow_pointer_color.blue(), 55))
        painter.drawPath(path)

        painter.setPen(QPen(QColor(15, 23, 42, 220), max(4, int(size * 0.016))))
        painter.setBrush(QColor(248, 250, 252, 230))
        painter.drawPath(path)

        ring_radius = max(18, int(size * 0.12))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 190), max(3, int(size * 0.01))))
        painter.drawEllipse(self._follow_pointer_pos, ring_radius, ring_radius)
        painter.setPen(QPen(QColor(self._follow_pointer_color.red(), self._follow_pointer_color.green(), self._follow_pointer_color.blue(), 220), max(6, int(size * 0.014))))
        painter.drawEllipse(self._follow_pointer_pos, int(ring_radius * 1.45), int(ring_radius * 1.45))

    def _paint_motion_trail(self, painter: QPainter, trail: TrailState) -> None:
        if not trail.points:
            return
        progress = min(1.0, max(0.0, ((time.perf_counter() - trail.started_at) * 1000) / trail.duration_ms))
        fade = 1.0 - progress
        if trail.style == "dash":
            self._paint_dash_trail(painter, trail, fade)
        elif trail.style == "comet":
            self._paint_comet_trail(painter, trail, fade)
        elif trail.style == "spark":
            self._paint_spark_trail(painter, trail, fade)
        elif trail.style == "ring":
            self._paint_ring_trail(painter, trail, fade)
        else:
            self._paint_glow_trail(painter, trail, fade)

    def _path_for_points(self, points: list[QPoint]) -> QPainterPath:
        path = QPainterPath(points[0])
        for previous, current in zip(points, points[1:]):
            path.quadTo(previous, (previous + current) * 0.5)
        path.lineTo(points[-1])
        return path

    def _paint_glow_trail(self, painter: QPainter, trail: TrailState, fade: float) -> None:
        if len(trail.points) >= 2:
            pen = QPen(QColor(trail.color.red(), trail.color.green(), trail.color.blue(), int(150 * fade)), max(4, int(trail.size * 0.08)))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._path_for_points(trail.points))
        for index, point in enumerate(trail.points):
            point_fade = fade * ((index + 1) / len(trail.points))
            radius = max(6, int((trail.size * 0.1) + (trail.size * 0.16 * point_fade)))
            gradient = QRadialGradient(point, radius * 1.6)
            gradient.setColorAt(0.0, QColor(trail.color.red(), trail.color.green(), trail.color.blue(), int(120 * point_fade)))
            gradient.setColorAt(0.65, QColor(248, 250, 252, int(90 * point_fade)))
            gradient.setColorAt(1.0, QColor(trail.color.red(), trail.color.green(), trail.color.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(point, int(radius * 1.6), int(radius * 1.6))
        self._paint_trail_endpoint(painter, trail, fade)

    def _paint_dash_trail(self, painter: QPainter, trail: TrailState, fade: float) -> None:
        if len(trail.points) >= 2:
            pen = QPen(QColor(trail.color.red(), trail.color.green(), trail.color.blue(), int(210 * fade)), max(3, int(trail.size * 0.06)))
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._path_for_points(trail.points))
        self._paint_trail_endpoint(painter, trail, fade)

    def _paint_comet_trail(self, painter: QPainter, trail: TrailState, fade: float) -> None:
        for index, point in enumerate(trail.points):
            local_fade = fade * ((index + 1) / len(trail.points))
            radius = max(4, int(trail.size * (0.06 + 0.02 * index)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(trail.color.red(), trail.color.green(), trail.color.blue(), int(110 * local_fade)))
            painter.drawEllipse(point, radius, radius)
        self._paint_trail_endpoint(painter, trail, fade)

    def _paint_spark_trail(self, painter: QPainter, trail: TrailState, fade: float) -> None:
        for index, point in enumerate(trail.points):
            local_fade = fade * ((index + 1) / len(trail.points))
            pen = QPen(QColor(trail.color.red(), trail.color.green(), trail.color.blue(), int(210 * local_fade)), 2)
            painter.setPen(pen)
            painter.drawLine(point.x() - 8, point.y(), point.x() + 8, point.y())
            painter.drawLine(point.x(), point.y() - 8, point.x(), point.y() + 8)
            painter.setBrush(QColor(248, 250, 252, int(120 * local_fade)))
            painter.drawEllipse(point, 3, 3)
        self._paint_trail_endpoint(painter, trail, fade)

    def _paint_ring_trail(self, painter: QPainter, trail: TrailState, fade: float) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index, point in enumerate(trail.points):
            local_fade = fade * ((index + 1) / len(trail.points))
            radius = max(6, int(trail.size * (0.08 + 0.02 * index)))
            painter.setPen(QPen(QColor(trail.color.red(), trail.color.green(), trail.color.blue(), int(180 * local_fade)), 2))
            painter.drawEllipse(point, radius, radius)
        self._paint_trail_endpoint(painter, trail, fade)

    def _paint_trail_endpoint(self, painter: QPainter, trail: TrailState, fade: float) -> None:
        end_point = trail.points[-1]
        end_radius = max(12, int(trail.size * 0.22))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, int(210 * fade)), 3))
        painter.drawEllipse(end_point, end_radius, end_radius)
        painter.setPen(QPen(QColor(trail.color.red(), trail.color.green(), trail.color.blue(), int(220 * fade)), 5))
        painter.drawEllipse(end_point, int(end_radius * 1.5), int(end_radius * 1.5))

    def _paint_click_ripple(self, painter: QPainter, ripple: RippleState) -> None:
        progress = min(1.0, max(0.0, ((time.perf_counter() - ripple.started_at) * 1000) / ripple.duration_ms))
        draw_ripple(painter, ripple.center, ripple.size, progress, ripple.color)


class OverlayManager:
    CLICK_COLORS = {
        "left": QColor(59, 130, 246),
        "right": QColor(244, 114, 182),
        "middle": QColor(16, 185, 129),
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.app: QApplication | None = None
        self.config_provider: Any = None
        self.overlays: dict[QScreen, EffectOverlay] = {}
        self.effects_suspended = False
        self.pointer_timer = QTimer()
        self.pointer_timer.setInterval(16)
        self.pointer_timer.timeout.connect(self._update_follow_pointer)
        self.follow_pointer_enabled = False
        self.follow_pointer_size_percent = 100

    def attach_application(self, app: QApplication, config_provider) -> None:
        if self.app is not app:
            if self.app is not None:
                self.app.screenRemoved.disconnect(self._screen_removed)
            app.screenRemoved.connect(self._screen_removed)
        self.app = app
        self.config_provider = config_provider

    def set_effects_suspended(self, suspended: bool) -> None:
        self.effects_suspended = suspended
        if suspended:
            self.pointer_timer.stop()
            for overlay in self.overlays.values():
                overlay.reset()
        elif self.follow_pointer_enabled:
            self.set_follow_pointer_mode(True, self.follow_pointer_size_percent)

    def set_follow_pointer_mode(self, enabled: bool, size_percent: int) -> None:
        self.follow_pointer_enabled = enabled
        self.follow_pointer_size_percent = size_percent
        if enabled and not self.effects_suspended:
            if not self.pointer_timer.isActive():
                self.pointer_timer.start()
            self._update_follow_pointer()
            return
        self.pointer_timer.stop()
        for overlay in self.overlays.values():
            overlay.clear_follow_pointer()

    def trigger_find_mouse(self) -> None:
        if self.app is None or self.config_provider is None:
            self.logger.warning("OverlayManager is not attached to a QApplication")
            return
        config = self.config_provider()
        settings = config.highlight
        if self.effects_suspended or not settings.enabled:
            return
        cursor_pos = QCursor.pos()
        screen = self._resolve_screen(cursor_pos)
        if screen is None:
            return
        self._get_overlay(screen).start_find_effect(cursor_pos, settings.duration_ms, settings.ring_size,
                                                  settings.style, QColor(config.pointer.trail_color))

    def trigger_motion_trail(self, global_points: list[QPoint], replace: bool = False) -> None:
        if self.app is None or self.config_provider is None or not global_points:
            return
        config = self.config_provider()
        if self.effects_suspended or not config.pointer.shake_to_find_enabled:
            return
        screen = self._resolve_screen(global_points[-1])
        if screen is None:
            return
        color = QColor(config.pointer.trail_color)
        style = config.pointer.trail_style or "glow"
        size = max(60, config.highlight.ring_size)
        bounds = QRect(global_points[0], global_points[0])
        for point in global_points[1:]:
            bounds = bounds.united(QRect(point, point))
        margin = int(max(30, size * 0.45))
        bounds.adjust(-margin, -margin, margin, margin)
        screens = self.app.screens() if config.highlight.multi_monitor else [screen]
        for target in screens:
            if target.geometry().intersects(bounds):
                self._get_overlay(target).add_motion_trail(global_points, max(380, min(1200, config.highlight.duration_ms)),
                                                           size, color, style, replace=replace)

    def trigger_click_ripple(self, global_cursor_pos: QPoint | None = None, button: str = "left") -> None:
        if self.app is None or self.config_provider is None:
            return
        config = self.config_provider()
        settings = config.click_ripple
        if self.effects_suspended or not settings.enabled:
            return
        cursor_pos = global_cursor_pos if global_cursor_pos is not None else QCursor.pos()
        screen = self._resolve_screen(cursor_pos)
        if screen is None:
            return
        color = self.CLICK_COLORS.get(button, self.CLICK_COLORS["left"])
        self._get_overlay(screen).add_click_ripple(cursor_pos, settings.duration_ms, settings.size, color)

    def shutdown(self) -> None:
        self.pointer_timer.stop()
        if self.app is not None:
            self.app.screenRemoved.disconnect(self._screen_removed)
        for screen in list(self.overlays):
            self._screen_removed(screen)
        self.app = None

    def _screen_removed(self, screen: QScreen) -> None:
        overlay = self.overlays.pop(screen, None)
        if overlay is not None:
            overlay.reset()
            overlay.close()
            overlay.deleteLater()

    def _update_follow_pointer(self) -> None:
        if self.app is None or self.config_provider is None or not self.follow_pointer_enabled or self.effects_suspended:
            return
        cursor_pos = QCursor.pos()
        screen = self._resolve_screen(cursor_pos)
        if screen is None:
            return
        screen_geometry = screen.geometry()
        max_size = int(min(screen_geometry.width(), screen_geometry.height()) * 0.6)
        visual_size = min(max_size, max(180, int(self.follow_pointer_size_percent * 0.7)))
        color = QColor(self.config_provider().pointer.trail_color)
        for other_screen, overlay in self.overlays.items():
            if other_screen != screen:
                overlay.clear_follow_pointer()
        self._get_overlay(screen).set_follow_pointer(cursor_pos, visual_size, color)

    def _resolve_screen(self, cursor_pos: QPoint):
        if self.app is None:
            return None
        config = self.config_provider()
        if not config.highlight.multi_monitor:
            return self.app.primaryScreen()
        return QGuiApplication.screenAt(cursor_pos) or self.app.primaryScreen()

    def _get_overlay(self, screen: QScreen) -> EffectOverlay:
        geometry = screen.geometry()
        overlay = self.overlays.get(screen)
        if overlay is None:
            overlay = EffectOverlay(geometry)
            overlay.setScreen(screen)
            overlay.setGeometry(geometry)
            self.overlays[screen] = overlay
        elif overlay.geometry() != geometry:
            overlay.reset()
            overlay.setGeometry(geometry)
        return overlay
