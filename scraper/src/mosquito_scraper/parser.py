"""Moduł parsowania stron HTML dla sklepu mosquito-sklep.pl (Wymaganie W2, D5)."""

import json
import logging
import re

from bs4 import BeautifulSoup

from mosquito_scraper.models import ProductVariant, ScrapedProduct

logger = logging.getLogger(__name__)


def parse_category_page(html_content: str) -> list[str]:
    """Wyodrębnia unikalne adresy URL produktów ze strony kategorii."""
    soup = BeautifulSoup(html_content, "html.parser")
    product_urls: list[str] = []

    # 1. Lista produktów z głównej siatki PrestaShop (#js-product-list)
    for pm in soup.select("#js-product-list .product-miniature"):
        a = pm.select_one('a[href$=".html"]')
        href = a.get("href") if a else None
        if (
            href
            and href.endswith(".html")
            and "test" not in href.lower()
            and href not in product_urls
        ):
            product_urls.append(href)

    # 2. Miniatury produktów i linki nagłówków (fallback dla uproszczonych szablonów)
    if not product_urls:
        fallback_selector = (
            ".product-miniature a.product-thumbnail, "
            ".product-miniature h2 a, .product-miniature h3 a"
        )
        for a in soup.select(fallback_selector):
            href = a.get("href")
            if (
                href
                and href.endswith(".html")
                and "test" not in href.lower()
                and href not in product_urls
            ):
                product_urls.append(href)

    # 3. Rezerwowe wyszukiwanie linków produktowych z identyfikatorem liczbowym
    if not product_urls:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"/\d+-[a-zA-Z0-9-]+\.html$", href) and "/content/" not in href:
                if "test" not in href.lower() and href not in product_urls:
                    product_urls.append(href)

    return product_urls


SUBCATEGORY_MAIN_CATEGORY_MAP: dict[str, str] = {
    "sukienki na wesele": "Sukienki",
    "kurtki & płaszcze": "Okrycia wierzchnie",
    "marynarki": "Okrycia wierzchnie",
    "bezrękawniki": "Okrycia wierzchnie",
    "kamizelki": "Okrycia wierzchnie",
    "swetry damskie": "Swetry, bluzy i bluzki",
    "bluzy damskie": "Swetry, bluzy i bluzki",
    "koszule": "Swetry, bluzy i bluzki",
    "bluzki & topy": "Swetry, bluzy i bluzki",
    "koszulki": "Swetry, bluzy i bluzki",
    "topy damskie": "Swetry, bluzy i bluzki",
    "spodnie": "Spodnie, spódnice i komplety",
    "spodnie dresowe": "Spodnie, spódnice i komplety",
    "spódnice": "Spodnie, spódnice i komplety",
    "szorty damskie": "Spodnie, spódnice i komplety",
    "komplety damskie": "Spodnie, spódnice i komplety",
    "kombinezony": "Spodnie, spódnice i komplety",
    "mosquito move": "Sport i akcesoria",
    "legginsy damskie": "Sport i akcesoria",
    "czapki i szaliki damskie": "Sport i akcesoria",
    "basic": "Sport i akcesoria",
}


def resolve_main_category(main_cat: str, sub_cat: str) -> str:
    """Przypisuje podkategorię do jednej z 5 głównych kategorii asortymentowych."""
    sub_norm = sub_cat.strip().lower()
    if sub_norm in SUBCATEGORY_MAIN_CATEGORY_MAP:
        return SUBCATEGORY_MAIN_CATEGORY_MAP[sub_norm]
    if "sukienk" in sub_norm:
        return "Sukienki"
    return main_cat


def parse_category_menu(html_content: str) -> list[tuple[str, str, str]]:
    """Wyodrębnia pary (kategoria_główna, podkategoria, url) z mega-menu sklepu."""
    soup = BeautifulSoup(html_content, "html.parser")
    results: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()

    # Mapowanie nazw zakładek menu na czytelne kategorie główne
    tab_mapping = {
        "Sukienki": "Sukienki",
        "Dresy": "Dresy",
        "Dziecko": "Dziecko",
        "Produkty": "Odzież damska",
    }
    skip_subcats = {
        "sukienki",
        "dresy",
        "nowości ilovemilk",
        "bestseller ilovemilk",
        "wyprzedaż ilovemilk",
        "mężczyźni",
        "ubranka dla psów",
    }

    for tab in soup.select(".cbp-hrmenu-tab"):
        top_a = tab.select_one(":scope > a")
        top_name = top_a.get_text(strip=True) if top_a else ""
        if top_name not in tab_mapping:
            continue

        main_cat = tab_mapping[top_name]
        for a in tab.select(".cbp-category-link-w a"):
            sub_name = a.get_text(strip=True)
            href = a.get("href", "").strip()
            if not sub_name or not href or "/pl/" not in href:
                continue
            if sub_name.lower() in skip_subcats:
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)
            resolved_main = resolve_main_category(main_cat, sub_name)
            results.append((resolved_main, sub_name, href))

    return results


def parse_product_page(
    html_content: str,
    url: str,
    fallback_category: str = "Odzież damska",
    fallback_subcategory: str = "Sukienki",
    prefer_fallback_category: bool = False,
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

        # 4. Opis produktu oraz cechy z bloków .cvProductAdditionalDesc (desc_1, desc_2, desc_3)
        extra_attributes: dict[str, str] = {}
        desc_parts: list[str] = []

        desc_1_div = soup.select_one(".cvProductAdditionalDesc.desc_1")
        if desc_1_div:
            desc_1_lines: list[str] = []
            for p_tag in desc_1_div.find_all("p"):
                full_p = re.sub(r"\s+", " ", p_tag.get_text(" ", strip=True)).strip()
                if not full_p or "znajdziesz tutaj" in full_p.lower():
                    continue
                strong_tag = p_tag.find(["strong", "b"])
                if strong_tag:
                    label_raw = (
                        re.sub(r"\s+", " ", strong_tag.get_text(" ", strip=True))
                        .strip()
                        .rstrip(":")
                    )
                    if label_raw and full_p.lower().startswith(label_raw.lower()):
                        val_raw = full_p[len(label_raw) :].lstrip(" :\xa0").strip()
                        if val_raw:
                            desc_1_lines.append(f"{label_raw}: {val_raw}")
                            if label_raw.lower().startswith("modelka"):
                                model_name = label_raw[len("modelka") :].strip()
                                extra_attributes["Modelka"] = (
                                    f"{model_name} ({val_raw})" if model_name else val_raw
                                )
                            else:
                                extra_attributes[label_raw] = val_raw
                            continue
                desc_1_lines.append(full_p)
            if desc_1_lines:
                desc_parts.append("\n".join(desc_1_lines))

        for sel in (".cvProductAdditionalDesc.desc_2", ".cvProductAdditionalDesc.desc_3"):
            block = soup.select_one(sel)
            if block:
                block_text = re.sub(r"\s+", " ", block.get_text(" ", strip=True)).strip()
                if block_text and block_text not in desc_parts:
                    desc_parts.append(block_text)

        description: str = "\n\n".join(desc_parts).strip()

        if not description and product_json and product_json.get("description"):
            description = str(product_json["description"]).strip()

        if not description:
            desc_div = soup.select_one(
                ".product-description, [id^='product-description-short'], "
                "#product-description, #description"
            )
            if desc_div:
                description = desc_div.get_text(strip=True)

        if not description or len(description) < 5:
            description = f"{name} - elegancka i wygodna odzież damska polskiej marki Mosquito."

        # 5. Ścieżka kategorii [Kategoria główna, Podkategoria]
        category_path: list[str] = []
        if prefer_fallback_category:
            category_path = [fallback_category, fallback_subcategory]
        elif len(breadcrumb_items) >= 3:
            # Pomijamy "Strona główna" i "Produkty", bierzemy kategorię i podkategorię
            filtered_crumbs = [
                c
                for c in breadcrumb_items
                if c.lower() not in ["strona główna", "produkty", name.lower()]
            ]
            if len(filtered_crumbs) >= 2:
                category_path = [filtered_crumbs[0], filtered_crumbs[1]]
            elif len(filtered_crumbs) == 1:
                category_path = [filtered_crumbs[0], fallback_subcategory]

        if len(category_path) < 2:
            category_path = [fallback_category, fallback_subcategory]
        category_path[0] = resolve_main_category(category_path[0], category_path[1])

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
        attributes.update(extra_attributes)
        # Sprawdzamy czy zdefiniowano kolor
        for item in soup.select(".product-variants .product-variants-item"):
            label = item.select_one(".control-label")
            label_text = label.get_text(strip=True).lower() if label else ""
            if "kolor" in label_text or "colour" in label_text:
                colors = [inp.get("title") for inp in item.select("input") if inp.get("title")]
                if colors:
                    attributes["Kolor"] = ", ".join(colors)
        if "Kolor" not in attributes:
            color_switch = soup.select_one(".current-feature__name strong")
            if color_switch:
                color_txt = color_switch.get_text(strip=True)
                if color_txt:
                    attributes["Kolor"] = color_txt

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
