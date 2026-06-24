import mimetypes
import uuid
from pathlib import Path

from napcat_qq_auto_reply.onebot.models import LocalImage


class ImageGenerationService:
    def __init__(self, output_dir, attachment_store, generator):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.attachment_store = attachment_store
        self.generator = generator

    async def generate(self, prompt, reference_ids=None, aspect_ratio="1:1"):
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Image prompt cannot be empty")
        reference_paths = [
            self.attachment_store.resolve(item) for item in (reference_ids or [])
        ]
        image_bytes, mime_type = await self.generator(
            normalized_prompt, reference_paths, aspect_ratio
        )
        extension = mimetypes.guess_extension(mime_type) or ".jpg"
        output_path = self.output_dir / f"{uuid.uuid4().hex}{extension}"
        output_path.write_bytes(image_bytes)
        return LocalImage(path=output_path, mime_type=mime_type)
