"""Testy jednostkowe modułu przetwarzania zdjęć (W2, D5)."""

import io
from pathlib import Path

from PIL import Image

from mosquito_scraper.image_processor import process_image


def test_process_image_resizing_and_compression(tmp_path: Path) -> None:
    # Tworzymy duży obrazek w pamięci (2000x1500 px)
    large_img = Image.new("RGB", (2000, 1500), color=(255, 100, 50))
    buffer = io.BytesIO()
    large_img.save(buffer, format="JPEG")
    image_bytes = buffer.getvalue()

    target_file = tmp_path / "test_output.jpg"
    success = process_image(image_bytes, target_file, max_side_px=1600, min_side_px=800)

    assert success is True
    assert target_file.exists()

    # Sprawdzamy wymiary po przetworzeniu
    with Image.open(target_file) as processed:
        width, height = processed.size
        assert max(width, height) <= 1600
        assert max(width, height) >= 800

    # Sprawdzamy limit wagi (<= 300 KB)
    size_kb = target_file.stat().st_size / 1024
    assert size_kb <= 300
