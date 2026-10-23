from services.cursor_manager import CursorManager


def test_cursor_manager_generates_builtin_assets() -> None:
    manager = CursorManager()
    assets = manager.list_builtin_themes()
    assert len(assets) >= 10
    assert all(asset.preview_path.exists() for asset in assets)
    assert all(asset.cursor_path.exists() for asset in assets)


def test_cursor_manager_generates_animated_frames() -> None:
    manager = CursorManager()
    frame_paths = manager.get_animated_theme_frame_paths("classic_arrow")
    assert len(frame_paths) == 6
    assert all(path.exists() for path in frame_paths)


def test_cursor_manager_renders_palette_override_preview() -> None:
    manager = CursorManager()
    image = manager.get_preview_image("classic_arrow", palette_override={"primary": "#FF0000"}, scale_percent=140)
    assert image is not None
    assert image.size == (128, 128)


def fail_render(*args, **kwargs):
    raise AssertionError("Unexpected rerender of cached theme")


def test_bundled_assets_are_read_without_rerendering(tmp_path, monkeypatch):
    manager = CursorManager(cache_dir=tmp_path / "cache")
    monkeypatch.setattr(manager, "_render_theme_image", fail_render)
    assets = manager.list_builtin_themes()
    assert all(asset.cursor_path.is_relative_to(manager.bundled_dir) for asset in assets)
    assert not manager.builtin_dir.exists()


def test_generated_assets_use_user_cache_and_reuse_existing_frames(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    manager = CursorManager(cache_dir=cache)
    cursor = manager.get_builtin_cursor_path("classic_arrow", size_percent=150)
    frames = manager.get_animated_theme_frame_paths("classic_arrow", size_percent=150)
    assert cursor.is_relative_to(cache)
    assert all(path.is_relative_to(cache) for path in frames)
    second_manager = CursorManager(cache_dir=cache)
    monkeypatch.setattr(second_manager, "_render_theme_image", fail_render)
    assert second_manager.get_animated_theme_frame_paths("classic_arrow", size_percent=150) == frames


def test_missing_bundled_assets_are_generated_only_in_cache(tmp_path):
    manager = CursorManager(cache_dir=tmp_path / "cache")
    manager.bundled_dir = tmp_path / "missing-install-assets"
    assets = manager.list_builtin_themes()
    assert not manager.bundled_dir.exists()
    assert all(asset.preview_path.exists() and asset.cursor_path.exists() for asset in assets)
    assert all(asset.cursor_path.is_relative_to(manager.builtin_dir) for asset in assets)
