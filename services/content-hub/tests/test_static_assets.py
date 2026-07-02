from pathlib import Path

from app.static_assets import get_asset, get_index_html, get_root_file, preload_static


def test_preload_static(tmp_path: Path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")

    preload_static(tmp_path)

    asset = get_asset("app.js")
    assert asset is not None
    assert asset[0] == b"console.log('ok');"
    assert asset[1].endswith("javascript")

    index = get_index_html()
    assert index is not None
    assert b"<html>" in index[0]

    logo = get_root_file("logo.png")
    assert logo is not None
    assert logo[0].startswith(b"\x89PNG")
