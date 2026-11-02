# scraper/tests/test_parser.py
import pytest
from pathlib import Path
from src.dywany_scraper.parser import parse_category_page, parse_product_page, _calculate_weight

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def test_calculate_weight_logic():
    """Testuje matematykę wyliczania wagi z m2 (wymóg W2)."""
    
    # Przypadek 1: Dywan 120x170 (1.2m x 1.7m = 2.04 m2), waga 2500 g/m2 (2.5 kg/m2)
    # Oczekiwana waga: 2.04 * 2.5 = 5.1 kg
    attrs_1 = {"Waga całkowita": "2500 g/m2"}
    assert _calculate_weight("Dywan Shaggy 120x170 szary", attrs_1) == 5.1
    
    # Przypadek 2: Dywan 200x300 (2.0m x 3.0m = 6.0 m2), waga 1800 g/m2 (1.8 kg/m2)
    # Oczekiwana waga: 6.0 * 1.8 = 10.8 kg
    attrs_2 = {"Waga": "1800g/m2"}
    assert _calculate_weight("Dywan Klasyczny 200 x 300", attrs_2) == 10.8
    
    # Przypadek 3: Limit wagi max 50 kg (zabezpieczenie wymogu)
    # 5m x 5m = 25m2 * 3kg = 75 kg (powinno zostać przycięte do 49.9)
    attrs_3 = {"Waga całkowita": "3000 g/m2"}
    assert _calculate_weight("Ogromny Dywan 500x500", attrs_3) == 49.9

def test_parse_category_page_extracts_links():
    """Sprawdza czy parser prawidłowo znajduje linki do produktów na liście."""
    html_path = FIXTURES_DIR / "category_page.html"
    if not html_path.exists():
        pytest.skip("Brak pliku category_page.html - pobierz go najpierw!")
        
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    links = parse_category_page(html)
    
    assert isinstance(links, list)
    assert len(links) > 0, "Parser nie znalazł żadnych linków do produktów na stronie kategorii"
    # Sprawdzamy czy link wygląda sensownie
    assert "http" in links[0] or "/" in links[0]

def test_parse_product_page_extracts_all_required_data():
    """Sprawdza czy parser poprawnie buduje model zwalidowanego Produktu."""
    html_path = FIXTURES_DIR / "product_page.html"
    if not html_path.exists():
        pytest.skip("Brak pliku product_page.html - pobierz go najpierw!")
        
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    product = parse_product_page(
        html_content=html, 
        url="https://dywanyluszczow.eu/testowy-dywan",
        category="Dywany", 
        subcategory="Nowoczesne"
    )
    
    assert product is not None, "Parser zwrócił None (zobacz scraper_errors.log po szczegóły)"
    
    assert len(product.name) > 0
    assert product.price_gross > 0
    assert product.vat_rate == 23
    assert len(product.image_urls) > 0, "Nie znaleziono żadnych zdjęć produktu"
    assert product.weight_kg > 0
    assert len(product.description) > 10
    assert isinstance(product.attributes, dict)
    assert len(product.category_path) == 2