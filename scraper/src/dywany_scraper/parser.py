import re

from bs4 import BeautifulSoup

from .models import ProductVariant, ScrapedProduct


def parse_category_page(html_content: str) -> list[str]:
    soup = BeautifulSoup(html_content, "html.parser")
    product_urls = []

    links = soup.select("a.product-name")

    for link in links:
        href = link.get("href")
        if href and href not in product_urls:
            product_urls.append(href)

    return product_urls


def parse_product_page(
    html_content: str, url: str, category: str, subcategory: str
) -> ScrapedProduct | None:
    soup = BeautifulSoup(html_content, "html.parser")

    try:
        name = soup.select_one('h1[itemprop="name"]').text.strip()

        price_elem = soup.select_one('*[itemprop="price"]')
        price_str = price_elem.get("content") or price_elem.text.strip()
        price_clean = re.sub(r"[^\d,.]", "", price_str).replace(",", ".")
        price_gross = float(price_clean)

        description = soup.select_one("div.rte").decode_contents().strip()

        image_urls = []

        # 1. Główne zdjęcie
        main_img = soup.select_one("#bigpic")
        if main_img:
            src = main_img.get("src")
            if src:
                if src.startswith("//"):
                    src = f"https:{src}"
                elif src.startswith("/"):
                    src = f"https://dywanyluszczow.eu{src}"
                image_urls.append(src)

        # 2. Zdjęcia z galerii miniaturek
        for link in soup.select('li[id^="thumbnail_"] a'):
            href = link.get("href")
            if href and href not in image_urls:
                if href.startswith("//"):
                    href = f"https:{href}"
                elif href.startswith("/"):
                    href = f"https://dywanyluszczow.eu{href}"
                image_urls.append(href)

        attributes = {}
        short_desc = soup.select_one("#short_description_content")

        if short_desc:
            # Wyszukujemy wszystkie akapity wewnątrz opisu
            for p in short_desc.find_all("p"):
                # Pobieramy tekst całego akapitu (np. "▪ wysokość runa: ok. 10 mm")
                line = p.get_text(strip=True)

                # Usuwamy ozdobny kwadracik, jeśli istnieje
                line = line.replace("▪", "").strip()

                if not line or line == "-":
                    continue

                if ":" in line:
                    key, value = line.split(":", 1)
                    # key = "wysokość runa", value = "ok. 10 mm"
                    attributes[key.strip().capitalize()] = value.strip()

        weight_kg = _calculate_weight(name, attributes)

        variants = []
        select_element = soup.select_one("select#group_4")

        if select_element:
            for option in select_element.find_all("option"):
                size_text = option.text.strip()

                variant_weight = _calculate_weight(size_text, attributes)

                # Tworzymy obiekt wariantu z modelu
                variants.append(
                    ProductVariant(
                        size=size_text,
                        price_gross=price_gross,  # Używamy ceny głównej
                        weight_kg=variant_weight,
                        stock_quantity=5,  # Wartość domyślna z models.py
                    )
                )

        # Generujemy proste ID z końcówki URLa
        external_id = url.split("/")[-1].replace(".html", "")

        return ScrapedProduct(
            external_id=external_id,
            name=name,
            description=description,
            category_path=[category, subcategory],
            price_gross=price_gross,
            vat_rate=23,
            weight_kg=weight_kg,
            attributes=attributes,
            image_urls=image_urls,
            variants=variants,
        )

    except Exception as e:
        with open("scraper_errors.log", "a", encoding="utf-8") as f:
            f.write(f"Błąd dla {url}: {str(e)}\n")
        return None


def _calculate_weight(name: str, attributes: dict[str, str]) -> float:
    weight = 1.0

    match = re.search(r"(\d+)\s*x\s*(\d+)", name.lower())
    grammage_str = attributes.get("Waga", attributes.get("Waga całkowita", "2000"))

    grammage_match = re.search(r"(\d+[.,]?\d*)", str(grammage_str).replace(" ", ""))

    if match and grammage_match:
        width_m = float(match.group(1)) / 100
        length_m = float(match.group(2)) / 100

        raw_grammage = float(grammage_match.group(1).replace(",", "."))

        if raw_grammage > 100:
            grammage_kg = raw_grammage / 1000
        else:
            grammage_kg = raw_grammage

        weight = round(width_m * length_m * grammage_kg, 2)

    return min(weight, 49.9)
