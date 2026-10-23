"""Windows cursor management service."""

from __future__ import annotations

import ctypes
import io
import logging
import math
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from core.builtin_themes import BUILTIN_THEMES, BuiltinThemeDefinition, ThemePalette
from core.constants import ROOT_DIR
from core.models import CursorTheme
from services.runtime_paths import user_data_dir

IMAGE_CURSOR = 2
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
SPI_SETCURSORS = 0x0057
WIN32_CURSOR_API_AVAILABLE = hasattr(ctypes, "windll")

if WIN32_CURSOR_API_AVAILABLE:
    USER32 = ctypes.windll.user32
    USER32.LoadImageW.restype = ctypes.c_void_p
    USER32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    USER32.SetSystemCursor.restype = ctypes.c_bool
    USER32.SetSystemCursor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    USER32.SystemParametersInfoW.restype = ctypes.c_bool
    USER32.SystemParametersInfoW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
else:
    USER32 = None


@dataclass(frozen=True, slots=True)
class CursorThemeAsset:
    theme: BuiltinThemeDefinition
    preview_path: Path
    cursor_path: Path


class CursorManager:
    APPLY_CURSOR_IDS = (32512, 32650, 32651, 32649)

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.bundled_dir = ROOT_DIR / "assets" / "builtin_cursors"
        self.builtin_dir = cache_dir if cache_dir is not None else user_data_dir() / "builtin_cursors"
        self._theme_assets: dict[str, CursorThemeAsset] = {}
        self._scaled_cursor_paths: dict[tuple[str, int, str], Path] = {}
        self._animated_frames: dict[tuple[str, int, str], list[Path]] = {}

    def list_builtin_themes(self) -> list[CursorThemeAsset]:
        self._ensure_builtin_assets()
        return [self._theme_assets[theme.theme_id] for theme in BUILTIN_THEMES]

    def get_builtin_theme_asset(self, theme_id: str) -> CursorThemeAsset | None:
        self._ensure_builtin_assets()
        return self._theme_assets.get(theme_id)

    def get_preview_image(self, theme_id: str, palette_override: dict[str, str] | None = None, scale_percent: int = 100) -> Image.Image | None:
        asset = self.get_builtin_theme_asset(theme_id)
        if asset is None:
            return None
        return self._decorate_preview(self._render_theme_image(asset.theme, phase=0.0, scale_percent=scale_percent, palette_override=palette_override))

    def get_builtin_cursor_path(self, theme_id: str, size_percent: int = 100, palette_override: dict[str, str] | None = None) -> Path | None:
        self._ensure_builtin_assets()
        asset = self.get_builtin_theme_asset(theme_id)
        if asset is None:
            return None
        palette_key = self._palette_signature(asset.theme, palette_override)
        key = (theme_id, size_percent, palette_key)
        cached = self._scaled_cursor_paths.get(key)
        if cached is not None:
            return cached

        if size_percent == 100 and palette_override is None:
            self._scaled_cursor_paths[key] = asset.cursor_path
            return asset.cursor_path

        scaled_dir = self.builtin_dir / "scaled"
        scaled_dir.mkdir(parents=True, exist_ok=True)
        cursor_path = scaled_dir / f"{theme_id}_{size_percent}_{palette_key}.cur"
        if not cursor_path.exists():
            image = self._render_theme_image(asset.theme, phase=0.0, scale_percent=size_percent, palette_override=palette_override)
            cursor_size = self._cursor_dimensions_for_percent(size_percent)
            hotspot_x, hotspot_y = self._scaled_hotspot(asset.theme.hotspot_x, asset.theme.hotspot_y, cursor_size)
            self.create_cursor_file_from_image(image, cursor_path, hotspot_x, hotspot_y, size=(cursor_size, cursor_size))
        self._scaled_cursor_paths[key] = cursor_path
        return cursor_path

    def get_animated_theme_frame_paths(self, theme_id: str, size_percent: int = 100, palette_override: dict[str, str] | None = None) -> list[Path]:
        self._ensure_builtin_assets()
        asset = self.get_builtin_theme_asset(theme_id)
        if asset is None:
            return []
        palette_key = self._palette_signature(asset.theme, palette_override)
        key = (theme_id, size_percent, palette_key)
        cached = self._animated_frames.get(key)
        if cached is not None:
            return cached

        frames_dir = self.builtin_dir / "animated" / f"{theme_id}_{size_percent}_{palette_key}"
        frames_dir.mkdir(parents=True, exist_ok=True)
        frame_paths: list[Path] = []
        for frame_index in range(6):
            phase = frame_index / 6
            cursor_path = frames_dir / f"frame_{frame_index}.cur"
            if not cursor_path.exists():
                image = self._render_theme_image(asset.theme, phase=phase, scale_percent=size_percent, palette_override=palette_override)
                cursor_size = self._cursor_dimensions_for_percent(size_percent)
                hotspot_x, hotspot_y = self._scaled_hotspot(asset.theme.hotspot_x, asset.theme.hotspot_y, cursor_size)
                self.create_cursor_file_from_image(image, cursor_path, hotspot_x, hotspot_y, size=(cursor_size, cursor_size))
            frame_paths.append(cursor_path)
        self._animated_frames[key] = frame_paths
        return frame_paths

    def apply_theme(self, theme: CursorTheme, size_percent: int = 100, palette_override: dict[str, str] | None = None) -> bool:
        if theme.source == "system" or theme.theme_id == "system_default":
            return self.restore_system_default()
        if theme.source == "builtin":
            return self.apply_builtin_theme(theme.theme_id, size_percent=size_percent, palette_override=palette_override)
        if theme.source == "custom" and theme.cursor_path:
            return self.apply_cursor_file(theme.cursor_path)
        self.logger.warning("Unsupported cursor theme payload: %s", theme)
        return False

    def apply_builtin_theme(self, theme_id: str, size_percent: int = 100, palette_override: dict[str, str] | None = None) -> bool:
        cursor_path = self.get_builtin_cursor_path(theme_id, size_percent=size_percent, palette_override=palette_override)
        if cursor_path is None:
            self.logger.error("Unknown built-in theme: %s", theme_id)
            return False
        return self.apply_cursor_file(cursor_path)

    def apply_cursor_file(self, cursor_path: str | Path) -> bool:
        if not WIN32_CURSOR_API_AVAILABLE or USER32 is None:
            self.logger.warning("Windows user32 cursor API is unavailable")
            return False
        path = Path(cursor_path)
        if not path.exists():
            self.logger.error("Cursor file does not exist: %s", path)
            return False
        try:
            for cursor_id in self.APPLY_CURSOR_IDS:
                handle = USER32.LoadImageW(None, str(path), IMAGE_CURSOR, 0, 0, LR_LOADFROMFILE)
                if not handle:
                    raise ctypes.WinError(ctypes.get_last_error())
                if not USER32.SetSystemCursor(handle, cursor_id):
                    raise ctypes.WinError(ctypes.get_last_error())
            self.logger.debug("Applied cursor file to system roles: %s", path)
            return True
        except Exception as exc:
            self.logger.exception("Failed to apply cursor file: %s", exc)
            return False

    def restore_system_default(self) -> bool:
        if not WIN32_CURSOR_API_AVAILABLE or USER32 is None:
            self.logger.warning("Windows user32 cursor API is unavailable")
            return False
        try:
            if not USER32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            self.logger.info("Restored Windows default cursor scheme")
            return True
        except Exception as exc:
            self.logger.exception("Failed to restore Windows default cursors: %s", exc)
            return False

    def create_cursor_file_from_image(self, image: Image.Image, output_path: str | Path, hotspot_x: int, hotspot_y: int, size: tuple[int, int] = (64, 64)) -> Path:
        normalized = image.convert("RGBA").resize(size, Image.LANCZOS)
        cur_bytes = self._build_cur_bytes(normalized, hotspot_x, hotspot_y)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(cur_bytes)
        return path

    def _cursor_dimensions_for_percent(self, size_percent: int) -> int:
        return min(256, max(16, int(round(64 * (size_percent / 100)))))

    def _scaled_hotspot(self, hotspot_x: int, hotspot_y: int, cursor_size: int) -> tuple[int, int]:
        scale = cursor_size / 64
        return (min(cursor_size - 1, int(round(hotspot_x * scale))), min(cursor_size - 1, int(round(hotspot_y * scale))))

    def _ensure_builtin_assets(self) -> None:
        if self._theme_assets:
            return
        for theme in BUILTIN_THEMES:
            preview_path = self.bundled_dir / f"{theme.theme_id}.png"
            cursor_path = self.bundled_dir / f"{theme.theme_id}.cur"
            if not preview_path.exists():
                preview_path = self.builtin_dir / preview_path.name
            if not cursor_path.exists():
                cursor_path = self.builtin_dir / cursor_path.name
            image = None
            if not preview_path.exists() or not cursor_path.exists():
                self.builtin_dir.mkdir(parents=True, exist_ok=True)
                image = self._render_theme_image(theme)
            if not preview_path.exists():
                self._decorate_preview(image).save(preview_path, format="PNG")
            if not cursor_path.exists():
                self.create_cursor_file_from_image(image, cursor_path, theme.hotspot_x, theme.hotspot_y)
            self._theme_assets[theme.theme_id] = CursorThemeAsset(theme=theme, preview_path=preview_path, cursor_path=cursor_path)

    def _render_theme_image(self, theme: BuiltinThemeDefinition, phase: float = 0.0, scale_percent: int = 100, palette_override: dict[str, str] | None = None) -> Image.Image:
        renderers = {
            "classic_arrow": self._render_classic_arrow,
            "round_dot": self._render_round_dot,
            "crosshair": self._render_crosshair,
            "lightning": self._render_lightning,
            "highlight_arrow": self._render_highlight_arrow,
            "neon_arrow": self._render_neon_arrow,
            "comet_arrow": self._render_comet_arrow,
            "diamond_pointer": self._render_diamond_pointer,
            "hollow_ring": self._render_hollow_ring,
            "pinpoint": self._render_pinpoint,
        }
        renderer = renderers.get(theme.theme_id)
        if renderer is None:
            raise ValueError(f"No renderer registered for theme {theme.theme_id}")
        palette = self._resolve_palette(theme, palette_override)
        return self._rescale_subject(renderer(palette, phase), scale_percent)

    def _render_classic_arrow(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        pulse = 0.85 + (0.15 * math.sin(phase * math.tau))
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glow).polygon([(16, 10), (16, 108), (44, 80), (64, 122), (86, 112), (68, 72), (112, 72)], fill=self._with_alpha(palette["glow"], int(90 * pulse)))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(8)))
        draw = ImageDraw.Draw(image)
        points = [(18, 10), (18, 104), (44, 78), (62, 120), (82, 111), (65, 72), (109, 71)]
        draw.polygon(points, fill=palette["primary"], outline=palette["secondary"])
        draw.line(points + [points[0]], fill=palette["secondary"], width=4)
        return image

    def _render_round_dot(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        pulse = 0.86 + (0.18 * math.sin(phase * math.tau))
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        inset = int(18 - 4 * pulse)
        ImageDraw.Draw(glow).ellipse((inset, inset, 128 - inset, 128 - inset), fill=self._with_alpha(palette["glow"], int(150 * pulse)))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
        draw = ImageDraw.Draw(image)
        draw.ellipse((28, 28, 100, 100), fill=palette["primary"], outline=palette["secondary"], width=5)
        inner_size = int(44 + 6 * pulse)
        offset = (128 - inner_size) // 2
        draw.ellipse((offset, offset, 128 - offset, 128 - offset), fill=palette["accent"])
        return image

    def _render_crosshair(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        pulse = 0.84 + (0.16 * math.sin(phase * math.tau))
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((16, 16, 112, 112), outline=self._with_alpha(palette["glow"], int(180 * pulse)), width=8 + int(4 * pulse))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
        draw = ImageDraw.Draw(image)
        draw.ellipse((24, 24, 104, 104), outline=palette["secondary"], width=6)
        draw.line((64, 10, 64, 118), fill=palette["primary"], width=8)
        draw.line((10, 64, 118, 64), fill=palette["primary"], width=8)
        draw.ellipse((50, 50, 78, 78), fill=palette["accent"], outline=palette["secondary"], width=4)
        return image

    def _render_lightning(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        pulse = 0.82 + (0.18 * math.sin(phase * math.tau))
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glow).polygon([(54, 8), (26, 68), (52, 68), (36, 120), (102, 48), (70, 48), (88, 8)], fill=self._with_alpha(palette["glow"], int(160 * pulse)))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(8)))
        draw = ImageDraw.Draw(image)
        points = [(54, 6), (26, 66), (52, 66), (36, 122), (102, 46), (70, 46), (88, 6)]
        draw.polygon(points, fill=palette["primary"], outline=palette["secondary"])
        draw.line(points + [points[0]], fill=palette["secondary"], width=4)
        draw.line((46, 52, 82, 52), fill=palette["accent"], width=4)
        return image

    def _render_highlight_arrow(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = self._render_classic_arrow(palette, phase)
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((6, 6, 122, 122), outline=self._with_alpha(palette["glow"], 220), width=6)
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2)))
        ImageDraw.Draw(image).ellipse((10, 10, 118, 118), outline=palette["accent"], width=4)
        return image

    def _render_neon_arrow(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = self._render_classic_arrow(palette, phase)
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glow).polygon([(18, 10), (18, 104), (44, 78), (62, 120), (82, 111), (65, 72), (109, 71)], outline=self._with_alpha(palette["glow"], 220), width=8)
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
        ImageDraw.Draw(image).line([(22, 14), (40, 46)], fill=palette["accent"], width=3)
        return image

    def _render_comet_arrow(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = self._render_classic_arrow(palette, phase)
        tail = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tail)
        draw.polygon([(18, 18), (4, 34), (6, 48), (26, 36)], fill=self._with_alpha(palette["glow"], 130))
        draw.polygon([(22, 34), (4, 54), (8, 68), (30, 52)], fill=self._with_alpha(palette["accent"], 110))
        image.alpha_composite(tail.filter(ImageFilter.GaussianBlur(5)))
        return image

    def _render_diamond_pointer(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glow).polygon([(64, 8), (112, 56), (64, 104), (16, 56)], fill=self._with_alpha(palette["glow"], 120))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
        draw = ImageDraw.Draw(image)
        draw.polygon([(64, 12), (108, 56), (64, 100), (20, 56)], fill=palette["primary"], outline=palette["secondary"])
        draw.line([(64, 12), (108, 56), (64, 100), (20, 56), (64, 12)], fill=palette["secondary"], width=4)
        draw.ellipse((52, 44, 76, 68), fill=palette["accent"])
        return image

    def _render_hollow_ring(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        pulse = 0.9 + (0.1 * math.sin(phase * math.tau))
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((20, 20, 108, 108), outline=self._with_alpha(palette["glow"], int(140 * pulse)), width=16)
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(8)))
        draw = ImageDraw.Draw(image)
        draw.ellipse((26, 26, 102, 102), outline=palette["primary"], width=8)
        draw.ellipse((54, 54, 74, 74), fill=palette["accent"])
        return image

    def _render_pinpoint(self, palette: dict[str, tuple[int, int, int, int]], phase: float) -> Image.Image:
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glow).polygon([(64, 6), (102, 54), (80, 118), (48, 118), (26, 54)], fill=self._with_alpha(palette["glow"], 120))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
        draw = ImageDraw.Draw(image)
        draw.polygon([(64, 10), (98, 54), (78, 114), (50, 114), (30, 54)], fill=palette["primary"], outline=palette["secondary"])
        draw.line([(64, 10), (98, 54), (78, 114), (50, 114), (30, 54), (64, 10)], fill=palette["secondary"], width=4)
        draw.ellipse((52, 42, 76, 66), fill=palette["accent"])
        draw.rectangle((60, 98, 68, 124), fill=palette["secondary"])
        return image

    def _resolve_palette(self, theme: BuiltinThemeDefinition, override: dict[str, str] | None) -> dict[str, tuple[int, int, int, int]]:
        source = theme.palette.to_dict()
        if override:
            for key in ("primary", "secondary", "accent", "glow"):
                if override.get(key):
                    source[key] = override[key]
        return {key: self._hex_to_rgba(value) for key, value in source.items()}

    def _palette_signature(self, theme: BuiltinThemeDefinition, override: dict[str, str] | None) -> str:
        palette = theme.palette.to_dict()
        if override:
            palette.update({k: v for k, v in override.items() if v})
        return "_".join(palette[key].replace("#", "") for key in ("primary", "secondary", "accent", "glow"))

    def _decorate_preview(self, image: Image.Image) -> Image.Image:
        checker = Image.new("RGBA", image.size, (255, 255, 255, 255))
        draw = ImageDraw.Draw(checker)
        tile = 16
        for y in range(0, image.height, tile):
            for x in range(0, image.width, tile):
                fill = (226, 232, 240, 255) if (x // tile + y // tile) % 2 == 0 else (248, 250, 252, 255)
                draw.rectangle((x, y, x + tile, y + tile), fill=fill)
        checker.alpha_composite(image)
        return checker

    def _rescale_subject(self, image: Image.Image, scale_percent: int) -> Image.Image:
        if scale_percent == 100:
            return image
        rgba = image.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        if bbox is None:
            return rgba
        subject = rgba.crop(bbox)
        scale = max(0.5, min(7.0, scale_percent / 100))
        resized = subject.resize((max(1, int(subject.width * scale)), max(1, int(subject.height * scale))), Image.Resampling.LANCZOS)
        max_w, max_h = rgba.width, rgba.height
        if resized.width > max_w or resized.height > max_h:
            fitted = min(max_w / resized.width, max_h / resized.height)
            resized = resized.resize((max(1, int(resized.width * fitted)), max(1, int(resized.height * fitted))), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        canvas.alpha_composite(resized, ((canvas.width - resized.width) // 2, (canvas.height - resized.height) // 2))
        return canvas

    def _hex_to_rgba(self, value: str) -> tuple[int, int, int, int]:
        hex_value = value.strip().lstrip("#")
        if len(hex_value) != 6:
            return (255, 255, 255, 255)
        return (int(hex_value[0:2], 16), int(hex_value[2:4], 16), int(hex_value[4:6], 16), 255)

    def _with_alpha(self, color: tuple[int, int, int, int], alpha: int) -> tuple[int, int, int, int]:
        return (color[0], color[1], color[2], max(0, min(255, alpha)))

    def _build_cur_bytes(self, image: Image.Image, hotspot_x: int, hotspot_y: int) -> bytes:
        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")
        png_bytes = png_buffer.getvalue()
        width = 0 if image.width >= 256 else image.width
        height = 0 if image.height >= 256 else image.height
        header = struct.pack("<HHH", 0, 2, 1)
        entry = struct.pack("<BBBBHHII", width, height, 0, 0, hotspot_x, hotspot_y, len(png_bytes), 22)
        return header + entry + png_bytes

