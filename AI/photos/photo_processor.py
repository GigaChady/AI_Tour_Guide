import logging
from pathlib import Path

from photos.config import PhotoConfig
from photos.contracts import ImageStorage

logger = logging.getLogger(__name__)


class PhotoProcessor:
    def __init__(
        self,
        storage: ImageStorage,
        config: PhotoConfig | None = None,
        photo_path: str | Path | None = None,
    ):
        self.storage = storage
        self.config = config or PhotoConfig()
        self.photo_path = Path(photo_path) if photo_path else (
            Path(__file__).parent / "assets" / "default_photos"
        )

    def generate(self, image_type: str, count: int) -> str:
        mapped_type = self.config.category_mapping.get(
            image_type,
            self.config.default_image_type,
        )
        if count > 0:
            mapped_type = self.config.default_image_type

        image = self.config.image_files.get(
            mapped_type,
            self.config.image_files[self.config.default_image_type],
        )
        logger.info("Selected image %s for category %s", image, mapped_type)
        image_bytes = (self.photo_path / image).read_bytes()
        result = self.storage.upload_bytes(image, image_bytes)
        return result["image_url"]
