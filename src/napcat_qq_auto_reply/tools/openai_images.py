import asyncio
import base64
import json
from pathlib import Path


def parse_image_response(payload: dict) -> bytes:
    try:
        image = payload["data"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Image API response has no data[0]") from exc
    encoded = image.get("b64_json") if isinstance(image, dict) else None
    if not encoded:
        raise ValueError("Image API response has no b64_json")
    try:
        return base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("Image API returned invalid base64") from exc


def _align(value: float) -> int:
    return max(16, round(value / 16) * 16)


def image_size_for_aspect(aspect_ratio: str) -> str:
    try:
        width_part, height_part = aspect_ratio.split(":", 1)
        ratio = int(width_part) / int(height_part)
        if ratio <= 0:
            raise ValueError
    except (ValueError, ZeroDivisionError):
        ratio = 1.0
    ratio = min(3.0, max(1 / 3.0, ratio))
    if ratio >= 1:
        width, height = _align(1024 * ratio), 1024
    else:
        width, height = 1024, _align(1024 / ratio)
    return f"{width}x{height}"


class OpenAIImageGenerator:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        *,
        timeout_seconds: float = 600,
        max_attempts: int = 3,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)
        self._gate = asyncio.Semaphore(1)

    async def __call__(
        self,
        prompt: str,
        reference_paths: list[Path],
        aspect_ratio: str,
    ) -> tuple[bytes, str]:
        import aiohttp

        operation = "edits" if reference_paths else "generations"
        endpoint = f"{self.api_url}/images/{operation}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=self.timeout_seconds)
        async with self._gate:
            last_error: Exception | None = None
            for attempt in range(self.max_attempts):
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        if reference_paths:
                            form = aiohttp.FormData()
                            form.add_field("model", self.model)
                            form.add_field("prompt", prompt)
                            form.add_field("size", image_size_for_aspect(aspect_ratio))
                            form.add_field("n", "1")
                            for path in reference_paths:
                                form.add_field(
                                    "image",
                                    path.read_bytes(),
                                    filename=path.name,
                                    content_type="application/octet-stream",
                                )
                            response_context = session.post(endpoint, headers=headers, data=form)
                        else:
                            headers["Content-Type"] = "application/json"
                            payload = {
                                "model": self.model,
                                "prompt": prompt,
                                "size": image_size_for_aspect(aspect_ratio),
                                "n": 1,
                            }
                            response_context = session.post(
                                endpoint,
                                headers=headers,
                                data=json.dumps(payload, ensure_ascii=False).encode(),
                            )
                        async with response_context as response:
                            if response.status >= 400:
                                body = (await response.text())[:300]
                                raise RuntimeError(f"Image API HTTP {response.status}: {body}")
                            response_payload = await response.json(content_type=None)
                            image = response_payload.get("data", [{}])[0]
                            if image.get("b64_json"):
                                return parse_image_response(response_payload), "image/jpeg"
                            if image.get("url"):
                                async with session.get(image["url"]) as download:
                                    download.raise_for_status()
                                    mime = download.headers.get("Content-Type", "image/jpeg").split(";", 1)[0]
                                    return await download.read(), mime
                            raise ValueError("Image API returned neither b64_json nor url")
                except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                    last_error = exc
                    if attempt + 1 < self.max_attempts:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise
            raise RuntimeError(f"Image generation failed: {last_error}")
