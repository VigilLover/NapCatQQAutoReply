from pathlib import Path

import pytest

from napcat_qq_auto_reply.tools.attachments import AttachmentStore
from napcat_qq_auto_reply.tools.image_generation import ImageGenerationService


@pytest.mark.asyncio
async def test_inbound_image_uses_opaque_id_and_resolves_locally(tmp_path: Path):
    async def downloader(url):
        assert url == "https://example.invalid/input.png"
        return b"input-bytes", "image/png"

    store = AttachmentStore(tmp_path / "inbound", downloader=downloader)
    attachment_id = await store.cache_url("https://example.invalid/input.png")

    assert "/" not in attachment_id
    assert store.resolve(attachment_id).read_bytes() == b"input-bytes"
    with pytest.raises(ValueError):
        store.resolve("../../etc/passwd")


@pytest.mark.asyncio
async def test_image_generation_returns_local_image(tmp_path: Path):
    calls = []

    async def generator(prompt, reference_paths, aspect_ratio):
        calls.append((prompt, reference_paths, aspect_ratio))
        return b"generated-jpeg", "image/jpeg"

    store = AttachmentStore(tmp_path / "inbound", downloader=None)
    ref_id = store.store_bytes(b"ref", "image/png")
    service = ImageGenerationService(
        output_dir=tmp_path / "generated",
        attachment_store=store,
        generator=generator,
    )

    image = await service.generate("画一只小狼", [ref_id], "1:1")

    assert image.path.read_bytes() == b"generated-jpeg"
    assert image.mime_type == "image/jpeg"
    assert calls[0][1] == [store.resolve(ref_id)]
