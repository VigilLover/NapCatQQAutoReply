from pathlib import Path

from napcat_qq_auto_reply.napcat_config import (
    load_napcat_env_values,
    render_napcat_configs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        raise SystemExit(f"Missing {env_path}; copy .env.example to .env first")
    config_dir = PROJECT_ROOT / "deploy/napcat/runtime/config"
    values = load_napcat_env_values(env_path)
    onebot_path, webui_path = render_napcat_configs(values, config_dir)
    print(f"Generated {onebot_path.relative_to(PROJECT_ROOT)}")
    print(f"Generated {webui_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
