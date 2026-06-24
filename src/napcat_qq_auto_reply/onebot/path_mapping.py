from pathlib import Path, PurePosixPath


class ContainerPathMapper:
    """Map an existing file below a host root to its container file URI."""

    def __init__(self, host_root: Path | str, container_root: str):
        resolved_root = Path(host_root).expanduser().resolve(strict=True)
        if not resolved_root.is_dir():
            raise ValueError("Host image root must be a directory")
        posix_root = PurePosixPath(container_root)
        if not posix_root.is_absolute() or ".." in posix_root.parts:
            raise ValueError("Container image root must be an absolute POSIX path")
        self.host_root = resolved_root
        self.container_root = posix_root

    def to_file_uri(self, path: Path | str) -> str:
        candidate = Path(path).expanduser()
        if not candidate.exists() or not candidate.is_file():
            raise ValueError(f"Image file does not exist: {candidate}")
        resolved = candidate.resolve(strict=True)
        try:
            relative = resolved.relative_to(self.host_root)
        except ValueError as exc:
            raise ValueError("Image path is outside the configured host image root") from exc
        container_path = self.container_root.joinpath(*relative.parts)
        return container_path.as_uri()
