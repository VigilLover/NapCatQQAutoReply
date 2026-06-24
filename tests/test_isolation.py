from pathlib import Path


def test_source_has_no_forbidden_legacy_dependencies():
    source_root = Path(__file__).parents[1] / "src"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in source_root.rglob("*.py")
    ).lower()
    forbidden = (
        "shuiyuan_auto_reply",
        "shuiyuan.sjtu.edu.cn",
        "get_persistence_cookie",
        "reply_to_post",
        "upload_image",
    )
    assert all(item not in source for item in forbidden)
