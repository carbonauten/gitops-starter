from pathlib import Path

from app.static_assets import media_type_for, resolve_asset_path, resolve_root_file


def test_resolve_asset_and_root_paths(tmp_path: Path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")

    asset = resolve_asset_path(tmp_path, "app.js")
    assert asset is not None
    assert asset.name == "app.js"
    assert media_type_for(asset).endswith("javascript")

    assert resolve_asset_path(tmp_path, "../secret") is None
    assert resolve_root_file(tmp_path, "logo.png") is not None
    assert resolve_root_file(tmp_path, "missing.txt") is None
