"""Testy jednostkowe schematów walidacji scrapera (W2, D5)."""

import pytest
from pydantic import ValidationError

from dywany_scraper.models import ProductVariant, ScrapedProduct


def test_valid_scraped_product() -> None:
    product = ScrapedProduct(
        external_id="DYW-NOW-001",
        name="Dywan Nowoczesny MEFE 6182 szary",
        description="Bardzo wytrzymały dywan nowoczesny do salonu i sypialni z miękkim runem.",
        category_path=["Dywany", "Dywany nowoczesne"],
        price_gross=199.99,
        vat_rate=23,
        weight_kg=3.74,
        attributes={
            "Wysokość runa": "ok. 8 mm",
            "Skład": "100% Polipropylen",
            "Waga całkowita": "ok. 1,67 kg/m2",
        },
        image_urls=["https://dywanyluszczow.eu/img/p/1/2/3/12345-large_default.jpg"],
        variants=[
            ProductVariant(size="120x170 cm", price_gross=199.99, weight_kg=3.40, stock_quantity=7),
            ProductVariant(size="160x220 cm", price_gross=319.99, weight_kg=5.87, stock_quantity=4),
        ],
    )
    assert product.external_id == "DYW-NOW-001"
    assert product.vat_rate == 23
    assert len(product.variants) == 2


def test_invalid_product_missing_images_or_negative_price() -> None:
    with pytest.raises(ValidationError):
        ScrapedProduct(
            external_id="DYW-ERR-001",
            name="Dywan bez zdjęć",
            description="Opis testowy produktu o odpowiedniej długości.",
            category_path=["Dywany", "Dywany shaggy"],
            price_gross=-10.0,
            weight_kg=2.5,
            image_urls=[],
        )
