"""Moduł pobierania i przetwarzania zdjęć produktów (Wymaganie W2)."""

import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def process_image(
    image_bytes: bytes,
    target_path: Path,
    max_side_px: int = 1600,
    min_side_px: int = 800,
    max_file_size_kb: int = 300,
) -> bool:
    """Skaluje i kompresuje zdjęcie do wymiarów 800-1600 px oraz rozmiaru <= 300 KB."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Konwersja do RGB w przypadku RGBA lub palety P
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            width, height = img.size
            longest_side = max(width, height)

            # Skalowanie w dół, jeśli dłuższy bok > 1600 px
            if longest_side > max_side_px:
                scale_ratio = max_side_px / longest_side
                new_width = int(width * scale_ratio)
                new_height = int(height * scale_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            elif longest_side < min_side_px and longest_side > 0:
                # Skalowanie w górę, jeśli miniatura < 800 px
                scale_ratio = min_side_px / longest_side
                new_width = int(width * scale_ratio)
                new_height = int(height * scale_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Iteracyjna kompresja, aby plik nie przekroczył 300 KB
            quality = 88
            target_path.parent.mkdir(parents=True, exist_ok=True)

            while quality >= 30:
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality, optimize=True)
                size_kb = buffer.tell() / 1024

                if size_kb <= max_file_size_kb or quality == 30:
                    with open(target_path, "wb") as f:
                        f.write(buffer.getvalue())
                    return True

                quality -= 5

            return False
    except Exception as e:
        logger.error(f"Błąd przetwarzania zdjęcia dla {target_path}: {e}")
        return False
