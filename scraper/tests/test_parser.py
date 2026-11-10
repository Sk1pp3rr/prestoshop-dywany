"""Testy jednostkowe parsera HTML dla sklepu mosquito-sklep.pl (W2, D5)."""

from pathlib import Path

from mosquito_scraper.parser import parse_category_page, parse_product_page

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_category_page() -> None:
    category_file = FIXTURES_DIR / "category_page.html"
    assert category_file.exists(), "Brak pliku fixture category_page.html"

    html = category_file.read_text(encoding="utf-8")
    product_urls = parse_category_page(html)

    assert len(product_urls) > 0, "Parser nie znalazł żadnych linków do produktów"
    assert all(url.startswith("http") and url.endswith(".html") for url in product_urls)


def test_parse_product_page() -> None:
    product_file = FIXTURES_DIR / "product_page.html"
    assert product_file.exists(), "Brak pliku fixture product_page.html"

    url = "https://mosquito-sklep.pl/pl/sukienki/3272-kopertowa-sukienka-z-wiazaniem-wyprzedaz.html"
    html = product_file.read_text(encoding="utf-8")
    product = parse_product_page(html, url=url)

    assert product is not None, "Parser zwrócił None dla poprawnej strony produktu"
    assert "KOPERTOWA SUKIENKA" in product.name.upper()
    assert product.price_gross == 80.0
    assert product.vat_rate == 23
    assert product.weight_kg == 0.5
    assert len(product.category_path) >= 2
    assert len(product.image_urls) >= 1
    assert product.external_id == "MOS-3272"

    # Weryfikacja wariantów rozmiarowych
    assert len(product.variants) > 0, "Produkt powinien zawierać warianty rozmiarowe"
    sizes = [v.size for v in product.variants]
    assert "XS" in sizes or "S" in sizes
    assert all(v.price_gross == 80.0 for v in product.variants)
