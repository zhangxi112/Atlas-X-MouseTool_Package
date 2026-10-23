from pathlib import Path

from PIL import Image
import io
import pytest

from services.cursor_manager import CursorManager
from services.image_pipeline import ImagePipeline


def test_image_pipeline_import_preview_and_cursor_generation(tmp_path) -> None:
    workspace = tmp_path
    source_path = workspace / "sample.png"
    Image.new("RGBA", (80, 60), (255, 0, 0, 255)).save(source_path)

    pipeline = ImagePipeline(storage_dir=workspace / "workspace", cursor_manager=CursorManager())
    project = pipeline.import_image(source_path)
    preview_path = pipeline.generate_preview(project, scale_percent=100, hotspot_x=32, hotspot_y=32)
    cursor_path = pipeline.generate_cursor(project, scale_percent=100, hotspot_x=32, hotspot_y=32)

    assert project.original_path.exists()
    assert preview_path.exists()
    assert cursor_path.exists()


def test_import_respects_exif_orientation(tmp_path):
    source = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (30, 10), "red")
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, exif=exif)
    pipeline = ImagePipeline(tmp_path / "cursors", CursorManager())
    project = pipeline.import_image(source)
    with Image.open(project.original_path) as staged:
        assert staged.size == (10, 30)


def test_background_mask_preserves_existing_transparency(tmp_path):
    pipeline = ImagePipeline(tmp_path, CursorManager())
    image = Image.new("RGBA", (3, 1), (255, 0, 0, 255))
    image.putalpha(Image.frombytes("L", (3, 1), bytes([0, 128, 255])))
    result = pipeline._cutout_with_mask(image, Image.new("L", image.size, 128))
    assert result.getchannel("A").tobytes() == bytes([0, 64, 128])


@pytest.mark.parametrize("scale", [40, 100, 180])
def test_preview_matches_generated_cursor_geometry(tmp_path, monkeypatch, scale):
    source = tmp_path / "sample.png"
    Image.new("RGBA", (80, 60), "red").save(source)
    pipeline = ImagePipeline(tmp_path / "cursors", CursorManager())
    project = pipeline.import_image(source)
    monkeypatch.setattr(pipeline, "_decorate_preview", lambda canvas, x, y: canvas)
    preview = pipeline.generate_preview(project, scale, 32, 32)
    cursor = pipeline.generate_cursor(project, scale, 32, 32)
    with Image.open(preview) as preview_image, Image.open(io.BytesIO(cursor.read_bytes()[22:])) as cursor_image:
        assert preview_image.tobytes() == cursor_image.resize((256, 256), Image.Resampling.NEAREST).tobytes()
