from gaming_buddy.paths import ensure_data_dirs


def test_ensure_data_dirs(tmp_path):
    base, captures = ensure_data_dirs(tmp_path / "gaming-buddy")

    assert base.is_dir()
    assert captures.is_dir()
    assert captures.parent == base
