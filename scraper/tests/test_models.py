"""Testy jednostkowe schematów walidacji scrapera (W2, D5)."""

import pytest
from pydantic import ValidationError

from mosquito_scraper.models import ProductVariant, ScrapedProduct


def test_valid_scraped_product() -> None:
    product = ScrapedProduct(
        external_id="MOS-SUK-3272",
        name="KOPERTOWA SUKIENKA Z WIĄZANIEM wyprzedaż",
        description=(
            "Idealna dla kobiety sukcesu. Klasyczna, prosta o bardzo komfortowym wygodnym kroju."
        ),
        category_path=["Sukienki", "Sukienki codzienne"],
        price_gross=80.00,
        vat_rate=23,
        weight_kg=0.5,
        attributes={
            "Producent": "Mosquito",
            "Kolor": "Zielony",
            "Skład": "95% poliester, 5% lycra",
        },
        image_urls=[
            "https://mosquito-sklep.pl/18444-tm_large_default/kopertowa-sukienka-z-wiazaniem-wyprzedaz.jpg"
        ],
        variants=[
            ProductVariant(size="XS", price_gross=80.00, weight_kg=0.5, stock_quantity=5),
            ProductVariant(size="S", price_gross=80.00, weight_kg=0.5, stock_quantity=7),
            ProductVariant(size="M", price_gross=80.00, weight_kg=0.5, stock_quantity=3),
            ProductVariant(size="L", price_gross=80.00, weight_kg=0.5, stock_quantity=4),
        ],
    )
    assert product.external_id == "MOS-SUK-3272"
    assert product.vat_rate == 23
    assert len(product.variants) == 4
    assert product.variants[0].size == "XS"


def test_invalid_product_missing_images_or_negative_price() -> None:
    with pytest.raises(ValidationError):
        ScrapedProduct(
            external_id="MOS-ERR-001",
            name="Sukienka bez zdjęć",
            description="Opis testowy produktu o odpowiedniej długości.",
            category_path=["Sukienki", "Sukienki wieczorowe"],
            price_gross=-10.0,
            weight_kg=0.5,
            image_urls=[],
        )
