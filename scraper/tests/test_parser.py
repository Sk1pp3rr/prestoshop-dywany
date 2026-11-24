"""Testy jednostkowe parsera HTML dla sklepu mosquito-sklep.pl (W2, D5)."""

import random
from pathlib import Path

from mosquito_scraper.parser import (
    parse_category_page,
    parse_product_page,
    resolve_main_category,
    sample_stock_quantity,
)

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


def test_parse_product_page_with_additional_desc_blocks() -> None:
    """Weryfikuje wyciąganie sekcji desc_1, desc_2, desc_3 oraz cech z .cvProductAdditionalDesc."""
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "Product",
          "name": "Sone - Marszczona sukienka mini z poduszkami i długim rękawem Brown",
          "sku": "MMM0497",
          "description": "95% poliester, 5% lycra",
          "image": "https://mosquito-sklep.pl/5046948-tm_large_default/sone.jpg",
          "offers": {"@type": "Offer", "price": "223.99"}
        }
        </script>
      </head>
      <body>
        <div class="cvProductAdditionalDesc desc_2">
          <h2>Brązowa sukienka marszczona na biodrach, z długim rękawem i poduszkami.</h2>
        </div>
        <div class="cvProductAdditionalDesc desc_1">
          <p><strong>Modelka Alicja </strong>167 cm wzrostu, 84/62/90. Ma na sobie XS.</p>
          <p><strong>Skład</strong> 95% poliester, 5% lycra.</p>
          <p><strong>Długość </strong>XS-86, S-87, M-88, L-89.</p>
          <p><strong>Fason</strong> mini, dopasowany, z długim rękawem i poduszkami.</p>
          <p><strong>Kolor</strong> brązowy.</p>
          <p>Więcej informacji o materiale <strong>znajdziesz tutaj.</strong></p>
        </div>
        <div class="cvProductAdditionalDesc desc_3">
          <p>Elastyczna, przewiewna tkanina dobrze dopasowuje się do ciała.</p>
        </div>
      </body>
    </html>
    """
    url = (
        "https://mosquito-sklep.pl/pl/sukienki/"
        "5008317-sone-marszczona-sukienka-mini-z-poduszkami-i-dlugim-rekawem-brown.html"
    )
    product = parse_product_page(
        html,
        url=url,
        fallback_category="Odzież damska",
        fallback_subcategory="Kurtki & Płaszcze",
        prefer_fallback_category=True,
    )

    assert product is not None
    assert product.external_id == "MMM0497"
    assert product.category_path == ["Okrycia wierzchnie", "Kurtki & Płaszcze"]
    assert "Modelka Alicja: 167 cm wzrostu, 84/62/90. Ma na sobie XS." in product.description
    assert "Skład: 95% poliester, 5% lycra." in product.description
    assert "Długość: XS-86, S-87, M-88, L-89." in product.description
    assert "Fason: mini, dopasowany, z długim rękawem i poduszkami." in product.description
    assert "Kolor: brązowy." in product.description
    assert "Brązowa sukienka marszczona na biodrach" in product.description
    assert "Elastyczna, przewiewna tkanina dobrze dopasowuje się do ciała" in product.description
    assert "znajdziesz tutaj" not in product.description
    assert "znajdziesz tutaj." not in product.attributes
    assert product.attributes.get("Skład") == "95% poliester, 5% lycra."
    assert product.attributes.get("Długość") == "XS-86, S-87, M-88, L-89."
    assert product.attributes.get("Fason") == "mini, dopasowany, z długim rękawem i poduszkami."
    assert product.attributes.get("Kolor") == "brązowy."
    assert "Alicja" in product.attributes.get("Modelka", "")


def test_sample_stock_quantity_inverse_cdf() -> None:
    """Weryfikuje losowanie stanów 0–10 szt. metodą odwracania dystrybuanty (5%–20% zer)."""
    rng = random.Random(42)
    samples = [sample_stock_quantity(rng=rng) for _ in range(2000)]

    assert all(0 <= qty <= 10 for qty in samples)
    zero_ratio = sum(1 for qty in samples if qty == 0) / len(samples)
    assert 0.05 <= zero_ratio <= 0.20, f"Odsetek zer poza zakresem 5%–20%: {zero_ratio:.3f}"
    assert set(samples) == set(range(11))


def test_resolve_main_category() -> None:
    """Weryfikuje mapowanie podkategorii na 5 kategorii głównych."""
    assert resolve_main_category("Odzież damska", "Sukienki na wesele") == "Sukienki"
    assert resolve_main_category("Odzież damska", "  sukienki boho ") == "Sukienki"
    assert resolve_main_category("Sukienki", "Hiszpanki") == "Sukienki"
    assert resolve_main_category("Produkty", "Kurtki & Płaszcze") == "Okrycia wierzchnie"
    assert resolve_main_category("Produkty", "Swetry damskie") == "Swetry, bluzy i bluzki"
    assert resolve_main_category("Produkty", "Spódnice") == "Spodnie, spódnice i komplety"
    assert resolve_main_category("Produkty", "Mosquito Move") == "Sport i akcesoria"


def test_parse_product_page_stock_sampling() -> None:
    """Weryfikuje, że warianty z parsera mają stany z przedziału 0–10 i ok. 5–20% wyprzedanych."""
    product_file = FIXTURES_DIR / "product_page.html"
    html = product_file.read_text(encoding="utf-8")
    url = "https://mosquito-sklep.pl/pl/sukienki/3272-kopertowa-sukienka-z-wiazaniem-wyprzedaz.html"

    rng = random.Random(123)
    products = [parse_product_page(html, url=url, rng=rng) for _ in range(200)]
    valid = [p for p in products if p is not None]
    assert len(valid) == 200

    out_of_stock_products = sum(1 for p in valid if all(v.stock_quantity == 0 for v in p.variants))
    ratio = out_of_stock_products / len(valid)
    assert 0.05 <= ratio <= 0.20, f"Odsetek produktów wyprzedanych: {ratio:.3f}"
    assert all(0 <= v.stock_quantity <= 10 for p in valid for v in p.variants)


def test_sample_stock_quantity_from_custom_yaml(tmp_path: Path) -> None:
    """Weryfikuje wczytywanie prawdopodobieństw i wag z pliku konfiguracyjnego YAML."""
    cfg_file = tmp_path / "custom_stock.yaml"
    cfg_file.write_text(
        "out_of_stock_prob: 0.25\nin_stock_weights:\n  2: 1.0\n  8: 3.0\n",
        encoding="utf-8",
    )
    rng = random.Random(7)
    samples = [sample_stock_quantity(rng=rng, config_path=cfg_file) for _ in range(1000)]

    assert set(samples) == {0, 2, 8}
    zero_ratio = sum(1 for s in samples if s == 0) / len(samples)
    assert 0.20 <= zero_ratio <= 0.30
