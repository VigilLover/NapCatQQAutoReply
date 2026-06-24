from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]


def test_compose_uses_local_only_ports_and_expected_mounts():
    compose = (PROJECT_ROOT / "deploy/napcat/compose.yml").read_text(encoding="utf-8")
    assert "mlikiowa/napcat-docker:latest" in compose
    assert "127.0.0.1:3001:3001" in compose
    assert "127.0.0.1:6099:6099" in compose
    assert "./runtime/config:/app/napcat/config" in compose
    assert "./runtime/qq:/app/.config/QQ" in compose
    assert "../../data/generated_images:/shared/generated_images:ro" in compose
    assert "MODE" not in compose


def test_napcat_script_exposes_only_supported_actions():
    script = (PROJECT_ROOT / "scripts/napcat.sh").read_text(encoding="utf-8")
    for action in ("start", "stop", "restart", "logs", "status", "update"):
        assert action in script
    assert "docker compose" in script
    assert "render_napcat_config.py" in script


def test_napcat_runtime_directory_is_ignored():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "deploy/napcat/runtime/" in gitignore
