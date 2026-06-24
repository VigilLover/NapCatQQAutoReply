import mimetypes
import time
import uuid
from pathlib import Path


class AttachmentStore:
    def __init__(self, directory, downloader=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.downloader = downloader

    async def cache_url(self, url):
        if self.downloader is None:
            raise RuntimeError("No attachment downloader is configured")
        data, mime_type = await self.downloader(url)
        return self.store_bytes(data, mime_type)

    def store_bytes(self, data, mime_type):
        extension = mimetypes.guess_extension(mime_type) or ".bin"
        attachment_id = uuid.uuid4().hex
        (self.directory / f"{attachment_id}{extension}").write_bytes(data)
        return attachment_id

    def resolve(self, attachment_id):
        if not attachment_id or not attachment_id.isalnum():
            raise ValueError("Invalid attachment id")
        matches = list(self.directory.glob(f"{attachment_id}.*"))
        if len(matches) != 1:
            raise ValueError("Attachment not found")
        path = matches[0].resolve()
        if path.parent != self.directory:
            raise ValueError("Attachment path escaped cache directory")
        return path

    def cleanup(self, ttl_seconds: float = 86400) -> int:
        cutoff = time.time() - ttl_seconds
        removed = 0
        for path in self.directory.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        return removed


async def download_http_image(url: str) -> tuple[bytes, str]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            mime_type = response.headers.get("Content-Type", "image/jpeg").split(";", 1)[0]
            if not mime_type.startswith("image/"):
                raise ValueError("Attachment URL did not return an image")
            return await response.read(), mime_type
