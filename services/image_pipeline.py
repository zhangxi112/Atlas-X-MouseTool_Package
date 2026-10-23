"""Custom cursor image processing pipeline."""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageChops, ImageDraw, ImageOps

ONNXRUNTIME_AVAILABLE = importlib.util.find_spec("onnxruntime") is not None


@dataclass(slots=True)
class CursorProject:
    """Working files for one imported custom cursor."""

    project_id: str
    display_name: str
    working_dir: Path
    original_path: Path
    bg_removed_path: Path | None = None
    preview_path: Path | None = None
    cursor_path: Path | None = None


class ImagePipeline:
    """Handles import, background removal, crop, scale, and cursor generation."""

    SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(self, storage_dir: Path, cursor_manager) -> None:
        self.logger = logging.getLogger(__name__)
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cursor_manager = cursor_manager
        self._u2net_session = None

    def import_image(self, source_path: str | Path) -> CursorProject:
        """Validate and stage an imported image into the working directory."""
        path = Path(source_path)
        if path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError("Only PNG, JPG, JPEG, and WEBP images are supported")
        if not path.exists():
            raise FileNotFoundError(path)

        project_id = uuid4().hex[:8]
        safe_name = path.stem.replace(" ", "_") or "custom_cursor"
        working_dir = self.storage_dir / f"{safe_name}_{project_id}"
        working_dir.mkdir(parents=True, exist_ok=True)
        original_path = working_dir / "original.png"

        with Image.open(path) as image:
            ImageOps.exif_transpose(image).convert("RGBA").save(original_path, format="PNG")

        self.logger.info("Imported custom cursor source: %s", path)
        return CursorProject(
            project_id=project_id,
            display_name=path.stem,
            working_dir=working_dir,
            original_path=original_path,
        )

    def remove_background(self, project: CursorProject) -> Path:
        """Run the local U2Net pipeline and save a transparent PNG."""
        if not ONNXRUNTIME_AVAILABLE:
            raise RuntimeError("onnxruntime is not installed in the current environment")

        output_path = project.working_dir / "bg_removed.png"
        with Image.open(project.original_path) as image:
            source = image.convert("RGBA")
        mask = self._get_u2net_session().predict_mask(source)
        result = self._cutout_with_mask(source, mask)
        result.save(output_path, format="PNG")
        project.bg_removed_path = output_path
        self.logger.info("Background removed for custom cursor project: %s", project.project_id)
        return output_path

    def generate_preview(
        self,
        project: CursorProject,
        scale_percent: int,
        hotspot_x: int,
        hotspot_y: int,
    ) -> Path:
        """Create a checkerboard preview showing crop, scale, and hotspot."""
        source = self._load_active_image(project)
        canvas = self._compose_cursor_canvas(source, (64, 64), scale_percent)
        canvas = canvas.resize((256, 256), Image.Resampling.NEAREST)
        preview = self._decorate_preview(canvas, hotspot_x, hotspot_y)
        preview_path = project.working_dir / "preview.png"
        preview.save(preview_path, format="PNG")
        project.preview_path = preview_path
        return preview_path

    def generate_cursor(
        self,
        project: CursorProject,
        scale_percent: int,
        hotspot_x: int,
        hotspot_y: int,
    ) -> Path:
        """Generate a Windows .cur file from the processed image."""
        source = self._load_active_image(project)
        canvas = self._compose_cursor_canvas(source, (64, 64), scale_percent)
        cursor_path = project.working_dir / f"{project.display_name}_custom.cur"
        self.cursor_manager.create_cursor_file_from_image(
            image=canvas,
            output_path=cursor_path,
            hotspot_x=max(0, min(63, hotspot_x)),
            hotspot_y=max(0, min(63, hotspot_y)),
            size=(64, 64),
        )
        project.cursor_path = cursor_path
        self.logger.info("Generated custom cursor file: %s", cursor_path)
        return cursor_path

    def _get_u2net_session(self):
        """Create and cache the local U2Net session."""
        if self._u2net_session is None:
            from services.u2net_session import U2NetSession

            self._u2net_session = U2NetSession()
        return self._u2net_session

    def _load_active_image(self, project: CursorProject) -> Image.Image:
        """Load the latest available working image for the project."""
        active_path = project.bg_removed_path or project.original_path
        with Image.open(active_path) as image:
            return image.convert("RGBA")

    def _compose_cursor_canvas(
        self,
        source: Image.Image,
        canvas_size: tuple[int, int],
        scale_percent: int,
    ) -> Image.Image:
        """Crop transparent edges, scale the subject, and center it on a canvas."""
        cropped = self._autocrop_rgba(source)
        canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        base_target = int(min(canvas_size) * 0.68)
        target_max = max(8, min(min(canvas_size) - 4, int(base_target * (scale_percent / 100))))
        scale_ratio = min(target_max / max(cropped.width, 1), target_max / max(cropped.height, 1))
        resized = cropped.resize(
            (max(1, int(cropped.width * scale_ratio)), max(1, int(cropped.height * scale_ratio))),
            Image.Resampling.LANCZOS,
        )
        offset_x = (canvas.width - resized.width) // 2
        offset_y = (canvas.height - resized.height) // 2
        canvas.alpha_composite(resized, (offset_x, offset_y))
        return canvas

    def _autocrop_rgba(self, image: Image.Image) -> Image.Image:
        """Trim transparent padding while keeping a minimum drawable area."""
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        bbox = alpha.getbbox()
        if bbox is None:
            return rgba
        return rgba.crop(bbox)

    def _decorate_preview(self, canvas: Image.Image, hotspot_x: int, hotspot_y: int) -> Image.Image:
        """Add checkerboard background and hotspot crosshair for UI preview."""
        preview = self._checkerboard_background(canvas.size)
        preview.alpha_composite(canvas)
        draw = ImageDraw.Draw(preview)
        scale_factor = preview.width / 64
        marker_x = hotspot_x * scale_factor
        marker_y = hotspot_y * scale_factor
        draw.line((marker_x - 12, marker_y, marker_x + 12, marker_y), fill=(239, 68, 68, 255), width=3)
        draw.line((marker_x, marker_y - 12, marker_x, marker_y + 12), fill=(239, 68, 68, 255), width=3)
        draw.ellipse((marker_x - 5, marker_y - 5, marker_x + 5, marker_y + 5), outline=(15, 23, 42, 255), width=2)
        return preview

    def _checkerboard_background(self, size: tuple[int, int]) -> Image.Image:
        """Create a neutral checkerboard background for transparency preview."""
        image = Image.new("RGBA", size, (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        tile = 16
        for y in range(0, size[1], tile):
            for x in range(0, size[0], tile):
                if (x // tile + y // tile) % 2 == 0:
                    draw.rectangle((x, y, x + tile, y + tile), fill=(226, 232, 240, 255))
                else:
                    draw.rectangle((x, y, x + tile, y + tile), fill=(248, 250, 252, 255))
        return image

    def _cutout_with_mask(self, image: Image.Image, mask: Image.Image) -> Image.Image:
        """Apply a single-channel mask as alpha to produce a transparent cutout."""
        result = image.convert("RGBA").copy()
        result.putalpha(ImageChops.multiply(result.getchannel("A"), mask.convert("L")))
        return result
