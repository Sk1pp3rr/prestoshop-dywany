"""Moduł parsowania stron HTML dla sklepu mosquito-sklep.pl (Wymaganie W2, D5)."""

import json
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from mosquito_scraper.models import ProductVariant, ScrapedProduct

logger = logging.getLogger(__name__)


def parse_category_page(html_content: str) -> list[str]:
    """Wyodrębnia unikalne adresy URL produktów ze strony kategorii."""
    soup = BeautifulSoup(html_content, "html.parser")
    product_urls: list[str] = []

    # 1. Miniatury produktów i linki nagłówków
    for a in soup.select(
        ".product-miniature a.product-thumbnail, .product-miniature h2 a, .product-miniature h3 a"
    ):
        href = a.get("href")
        if href and href.endswith(".html") and href not in product_urls:
            product_urls.append(href)

    # 2. Rezerwowe wyszukiwanie linków produktowych z identyfikatorem liczbowym
    if not product_urls:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"/\d+-[a-zA-Z0-9-]+\.html$", href) and "/content/" not in href:
                if href not in product_urls:
                    product_urls.append(href)

    return product_urls


def parse_product_page(
    html_content: str,
    url: str,
    fallback_category: str = "Odzież damska",
    fallback_subcategory: str = "Sukienki",
) -> ScrapedProduct | None:
    """Parsuje stronę produktu i zwraca zwalidowany obiekt ScrapedProduct."""
    soup = BeautifulSoup(html_content, "html.parser")

    try:
        # 1. Pobieranie danych strukturalnych JSON-LD
        product_json: dict | None = None
        breadcrumb_items: list[str] = []

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "{}")
                schema_type = data.get("@type")
                if schema_type == "Product":
                    product_json = data
                elif schema_type == "BreadcrumbList":
                    for elem in data.get("itemListElement", []):
                        crumb_name = elem.get("name") or elem.get("item", {}).get("name")
                        if crumb_name:
                            breadcrumb_items.append(crumb_name)
            except Exception:
                continue

        # 2. Nazwa produktu
        name: str | None = None
        if product_json and product_json.get("name"):
            name = str(product_json["name"]).strip()
        if not name:
            h1 = soup.select_one("h1")
            name = h1.get_text(strip=True) if h1 else None
        if not name:
            raise ValueError(f"Nie znaleziono nazwy produktu dla URL: {url}")

        # 3. Cena brutto
        price_gross: float = 0.0
        if product_json and "offers" in product_json:
            offers = product_json["offers"]
            if isinstance(offers, dict) and "price" in offers:
                price_gross = float(offers["price"])
            elif isinstance(offers, list) and offers and "price" in offers[0]:
                price_gross = float(offers[0]["price"])

        if price_gross <= 0:
            price_selector = (
                ".current-price span[itemprop='price'], "
                ".current-price span[content], .product-price"
            )
            price_elem = soup.select_one(price_selector)
            if price_elem:
                raw_price = price_elem.get("content") or price_elem.get_text(strip=True)
                clean_price = re.sub(r"[^\d,.]", "", raw_price).replace(",", ".")
                if clean_price:
                    price_gross = float(clean_price)

        if price_gross <= 0:
            raise ValueError(f"Nieprawidłowa lub brakująca cena dla URL: {url}")

        # 4. Opis produktu
        description: str = ""
        if product_json and product_json.get("description"):
            description = str(product_json["description"]).strip()

        if not description:
            desc_div = soup.select_one(
                ".product-description, [id^='product-description-short'], #description"
            )
            if desc_div:
                description = desc_div.get_text(strip=True)

        if not description or len(description) < 5:
            description = f"{name} - elegancka i wygodna odzież damska polskiej marki Mosquito."

        # 5. Ścieżka kategorii [Kategoria główna, Podkategoria]
        category_path: list[str] = []
        if len(breadcrumb_items) >= 3:
            # Pomijamy "Strona główna" i "Produkty", bierzemy kategorię i podkategorię
            filtered_crumbs = [
                c
                for c in breadcrumb_items
                if c.lower() not in ["strona główna", "produkty", name.lower()]
            ]
            if len(filtered_crumbs) >= 2:
                category_path = [filtered_crumbs[0], filtered_crumbs[1]]
            elif len(filtered_crumbs) == 1:
                category_path = [filtered_crumbs[0], "Kolekcja ogólna"]

        if len(category_path) < 2:
            # Próba wyciągnięcia z segmentów URL
            path_parts = [p for p in urlparse(url).path.split("/") if p and p != "pl"]
            if len(path_parts) >= 2:
                cat_slug = path_parts[0].replace("-", " ").capitalize()
                category_path = [cat_slug, "Kolekcja"]
            else:
                category_path = [fallback_category, fallback_subcategory]

        # 6. Zdjęcia produktu (wysoka rozdzielczość)
        image_urls: list[str] = []
        if product_json and "offers" in product_json and "image" in product_json["offers"]:
            imgs = product_json["offers"]["image"]
            if isinstance(imgs, list):
                image_urls.extend(str(img) for img in imgs if img)
            elif isinstance(imgs, str) and imgs:
                image_urls.append(imgs)

        if not image_urls:
            main_img = product_json.get("image") if product_json else None
            if main_img:
                image_urls.append(str(main_img))

        # Rezerwa z HTML
        if not image_urls:
            for img in soup.select("ul.product-images img, .js-qv-product-images img"):
                src = img.get("data-image-large-src") or img.get("src") or img.get("data-src")
                if src and src not in image_urls:
                    image_urls.append(src)

        if not image_urls:
            raise ValueError(f"Brak zdjęć produktu dla URL: {url}")

        # 7. Warianty rozmiarowe (XS, S, M, L, XL)
        variants: list[ProductVariant] = []
        sizes: list[str] = []

        for item in soup.select(".product-variants .product-variants-item"):
            label = item.select_one(".control-label")
            label_text = label.get_text(strip=True).lower() if label else ""
            if "rozmiar" in label_text or "size" in label_text or not label_text:
                for inp in item.select("input"):
                    title = inp.get("title")
                    if title and title not in sizes:
                        sizes.append(title)
                if not sizes:
                    for opt in item.select("option"):
                        opt_text = opt.get_text(strip=True)
                        if opt_text and opt_text not in sizes:
                            sizes.append(opt_text)

        for size in sizes:
            variants.append(
                ProductVariant(
                    size=size,
                    price_gross=price_gross,
                    weight_kg=0.5,
                    stock_quantity=5,
                )
            )

        # 8. Cechy i atrybuty (Attributes)
        attributes: dict[str, str] = {"Producent": "Mosquito"}
        # Sprawdzamy czy zdefiniowano kolor
        for item in soup.select(".product-variants .product-variants-item"):
            label = item.select_one(".control-label")
            label_text = label.get_text(strip=True).lower() if label else ""
            if "kolor" in label_text or "colour" in label_text:
                colors = [inp.get("title") for inp in item.select("input") if inp.get("title")]
                if colors:
                    attributes["Kolor"] = ", ".join(colors)

        # 9. Identyfikator zewnętrzny (SKU / id z URL)
        external_id: str = ""
        if product_json and product_json.get("sku"):
            external_id = str(product_json["sku"])
        if not external_id:
            # np. z adresu .../3272-kopertowa-sukienka... -> MOS-3272
            match_id = re.search(r"/(\d+)-", url)
            if match_id:
                external_id = f"MOS-{match_id.group(1)}"
            else:
                external_id = f"MOS-{abs(hash(url)) % 1000000}"

        return ScrapedProduct(
            external_id=external_id,
            name=name,
            description=description,
            category_path=category_path,
            price_gross=price_gross,
            vat_rate=23,
            weight_kg=0.5,
            attributes=attributes,
            image_urls=image_urls,
            variants=variants,
        )

    except Exception as e:
        logger.error(f"Błąd parsowania produktu {url}: {e}")
        return None
