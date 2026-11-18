#!/usr/bin/env python3
"""Import produktów, kategorii, wariantów, stanów i zdjęć do PrestaShop 8.2 przez Webservice API."""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

POLISH_TRANS = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def slugify(text: str, max_len: int = 128) -> str:
    """Tworzy bezpieczny slug ASCII dla pola link_rewrite w PrestaShop."""
    text = text.translate(POLISH_TRANS)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (text or "produkt")[:max_len]


def load_env(env_path: Path) -> dict[str, str]:
    """Wczytuje zmienne z pliku .env (bez zewnętrznych zależności)."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("\"'")
    return env


class PrestaShopAPI:
    """Minimalny klient PrestaShop Webservice API (JSON GET + XML POST/PUT + multipart upload)."""

    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.ssl_ctx = (
            ssl.create_default_context() if verify_ssl else ssl._create_unverified_context()
        )

    def _url(self, resource: str, params: dict[str, str] | None = None) -> str:
        query = dict(params or {})
        query["ws_key"] = self.api_key
        sep = "&" if "?" in resource else "?"
        return f"{self.base_url}/api/{resource.lstrip('/')}{sep}{urllib.parse.urlencode(query)}"

    def get_json(self, resource: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        query["output_format"] = "JSON"
        req = urllib.request.Request(self._url(resource, query), method="GET")
        with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}

    def post_xml(self, resource: str, xml_body: bytes) -> ET.Element:
        req = urllib.request.Request(
            self._url(resource),
            data=xml_body,
            method="POST",
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=30) as resp:
                return ET.fromstring(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"POST {resource} -> HTTP {exc.code}: {detail[:400]}") from exc

    def put_xml(self, resource: str, xml_body: bytes) -> ET.Element:
        req = urllib.request.Request(
            self._url(resource),
            data=xml_body,
            method="PUT",
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=30) as resp:
                return ET.fromstring(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"PUT {resource} -> HTTP {exc.code}: {detail[:400]}") from exc

    def delete(self, resource: str) -> bool:
        req = urllib.request.Request(self._url(resource), method="DELETE")
        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=30):
                return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"DELETE {resource} -> HTTP {exc.code}: {detail[:300]}") from exc

    def upload_product_image(self, product_id: int, image_bytes: bytes, filename: str) -> None:
        boundary = f"----PSBoundary{uuid.uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            self._url(f"images/products/{product_id}"),
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=30):
                return
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"POST images/products/{product_id} -> HTTP {exc.code}: {detail[:300]}"
            ) from exc


def add_lang_field(parent: ET.Element, tag: str, value: str, lang_ids: list[int]) -> None:
    el = ET.SubElement(parent, tag)
    for lid in lang_ids:
        lang_el = ET.SubElement(el, "language", {"id": str(lid)})
        lang_el.text = value


def extract_lang_name(name_field: Any) -> str:
    if isinstance(name_field, str):
        return name_field
    if isinstance(name_field, list) and name_field:
        return str(name_field[0].get("value", ""))
    return ""


def get_active_languages(api: PrestaShopAPI) -> list[int]:
    data = api.get_json("languages", {"display": "[id,active]"})
    langs = data.get("languages", [])
    ids = [int(l["id"]) for l in langs if str(l.get("active")) == "1"]
    return ids or [1]


def find_tax_rule_group_id(api: PrestaShopAPI) -> int:
    data = api.get_json("tax_rule_groups", {"display": "[id,name,active]"})
    groups = data.get("tax_rule_groups", [])
    for g in groups:
        name = str(g.get("name", "")).lower()
        if "23" in name or "pl standard" in name:
            return int(g["id"])
    return int(groups[0]["id"]) if groups else 1


def load_category_cache(api: PrestaShopAPI) -> dict[tuple[int, str], int]:
    data = api.get_json("categories", {"display": "[id,name,id_parent]"})
    cache: dict[tuple[int, str], int] = {}
    for c in data.get("categories", []):
        name = extract_lang_name(c.get("name")).strip()
        if name:
            cache[(int(c["id_parent"]), name.lower())] = int(c["id"])
    return cache


def ensure_category(
    api: PrestaShopAPI,
    cache: dict[tuple[int, str], int],
    parent_id: int,
    name: str,
    lang_ids: list[int],
) -> int:
    key = (parent_id, name.strip().lower())
    if key in cache:
        return cache[key]

    root = ET.Element("prestashop")
    cat = ET.SubElement(root, "category")
    ET.SubElement(cat, "id_parent").text = str(parent_id)
    ET.SubElement(cat, "active").text = "1"
    add_lang_field(cat, "name", name.strip(), lang_ids)
    add_lang_field(cat, "link_rewrite", slugify(name), lang_ids)

    resp = api.post_xml("categories", ET.tostring(root, encoding="utf-8"))
    new_id = int(resp.findtext("./category/id") or 0)
    cache[key] = new_id
    return new_id


def ensure_size_option_group(api: PrestaShopAPI, lang_ids: list[int]) -> int:
    data = api.get_json("product_options", {"display": "[id,name]"})
    for opt in data.get("product_options", []):
        name = extract_lang_name(opt.get("name")).strip().lower()
        if name in {"rozmiar", "size"}:
            return int(opt["id"])

    root = ET.Element("prestashop")
    po = ET.SubElement(root, "product_option")
    ET.SubElement(po, "group_type").text = "radio"
    add_lang_field(po, "name", "Rozmiar", lang_ids)
    add_lang_field(po, "public_name", "Rozmiar", lang_ids)
    resp = api.post_xml("product_options", ET.tostring(root, encoding="utf-8"))
    return int(resp.findtext("./product_option/id") or 1)


def load_size_values_cache(api: PrestaShopAPI, group_id: int) -> dict[str, int]:
    data = api.get_json(
        "product_option_values",
        {"display": "[id,id_attribute_group,name]", "filter[id_attribute_group]": str(group_id)},
    )
    cache: dict[str, int] = {}
    for v in data.get("product_option_values", []):
        name = extract_lang_name(v.get("name")).strip()
        if name:
            cache[name.upper()] = int(v["id"])
    return cache


def ensure_size_value(
    api: PrestaShopAPI,
    cache: dict[str, int],
    group_id: int,
    size_label: str,
    lang_ids: list[int],
) -> int:
    norm = size_label.strip().upper()
    if norm in cache:
        return cache[norm]

    root = ET.Element("prestashop")
    pov = ET.SubElement(root, "product_option_value")
    ET.SubElement(pov, "id_attribute_group").text = str(group_id)
    add_lang_field(pov, "name", size_label.strip(), lang_ids)
    resp = api.post_xml("product_option_values", ET.tostring(root, encoding="utf-8"))
    new_id = int(resp.findtext("./product_option_value/id") or 0)
    cache[norm] = new_id
    return new_id


def load_existing_references(api: PrestaShopAPI) -> set[str]:
    data = api.get_json("products", {"display": "[id,reference]"})
    return {
        str(p.get("reference", "")).strip()
        for p in data.get("products", [])
        if str(p.get("reference", "")).strip()
    }


def download_image(url: str) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; PrestaShopImporter/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return resp.read()
    except Exception as exc:
        print(f"    [WARN] Nie udało się pobrać zdjęcia {url}: {exc}", file=sys.stderr)
    return None


def update_stock_for_product(
    api: PrestaShopAPI, product_id: int, attr_to_qty: dict[int, int]
) -> None:
    data = api.get_json(
        "stock_availables",
        {"display": "full", "filter[id_product]": str(product_id)},
    )
    for sa in data.get("stock_availables", []):
        sa_id = int(sa["id"])
        attr_id = int(sa.get("id_product_attribute", 0))
        if attr_id in attr_to_qty:
            qty = attr_to_qty[attr_id]
        elif len(attr_to_qty) == 1 and 0 in attr_to_qty:
            qty = attr_to_qty[0]
        else:
            continue

        root = ET.Element("prestashop")
        el = ET.SubElement(root, "stock_available")
        ET.SubElement(el, "id").text = str(sa_id)
        ET.SubElement(el, "id_product").text = str(product_id)
        ET.SubElement(el, "id_product_attribute").text = str(attr_id)
        ET.SubElement(el, "id_shop").text = str(sa.get("id_shop", 1))
        ET.SubElement(el, "id_shop_group").text = str(sa.get("id_shop_group", 0))
        ET.SubElement(el, "quantity").text = str(qty)
        ET.SubElement(el, "depends_on_stock").text = "0"
        ET.SubElement(el, "out_of_stock").text = str(sa.get("out_of_stock", 2))
        api.put_xml(f"stock_availables/{sa_id}", ET.tostring(root, encoding="utf-8"))


def create_product(
    api: PrestaShopAPI,
    item: dict[str, Any],
    cat_ids: list[int],
    default_cat_id: int,
    tax_group_id: int,
    lang_ids: list[int],
    featured: bool,
) -> int:
    vat_rate = float(item.get("vat_rate", 23))
    price_gross = float(item["price_gross"])
    price_net = round(price_gross / (1.0 + vat_rate / 100.0), 6)
    variants = item.get("variants") or []

    root = ET.Element("prestashop")
    prod = ET.SubElement(root, "product")
    ET.SubElement(prod, "id_category_default").text = str(default_cat_id)
    ET.SubElement(prod, "id_tax_rules_group").text = str(tax_group_id)
    ET.SubElement(prod, "reference").text = str(item["external_id"])
    ET.SubElement(prod, "price").text = f"{price_net:.6f}"
    ET.SubElement(prod, "weight").text = f"{float(item.get('weight_kg', 0.5)):.6f}"
    ET.SubElement(prod, "active").text = "1"
    ET.SubElement(prod, "state").text = "1"
    ET.SubElement(prod, "available_for_order").text = "1"
    ET.SubElement(prod, "show_price").text = "1"
    ET.SubElement(prod, "visibility").text = "both"
    ET.SubElement(prod, "product_type").text = "combinations" if variants else "standard"

    name = str(item["name"]).strip()[:128]
    desc = str(item.get("description", "")).strip() or name
    add_lang_field(prod, "name", name, lang_ids)
    add_lang_field(prod, "description", f"<p>{desc}</p>", lang_ids)
    add_lang_field(prod, "description_short", desc[:400], lang_ids)
    add_lang_field(prod, "link_rewrite", slugify(name), lang_ids)

    assoc = ET.SubElement(prod, "associations")
    cats_el = ET.SubElement(assoc, "categories")
    all_cats = list(dict.fromkeys(([2] if featured else []) + cat_ids))
    for cid in all_cats:
        c_el = ET.SubElement(cats_el, "category")
        ET.SubElement(c_el, "id").text = str(cid)

    resp = api.post_xml("products", ET.tostring(root, encoding="utf-8"))
    return int(resp.findtext("./product/id") or 0)


def create_combination(
    api: PrestaShopAPI,
    product_id: int,
    ref: str,
    option_value_id: int,
    is_default: bool,
) -> int:
    root = ET.Element("prestashop")
    comb = ET.SubElement(root, "combination")
    ET.SubElement(comb, "id_product").text = str(product_id)
    ET.SubElement(comb, "reference").text = ref[:64]
    ET.SubElement(comb, "price").text = "0.000000"
    ET.SubElement(comb, "weight").text = "0.000000"
    ET.SubElement(comb, "minimal_quantity").text = "1"
    if is_default:
        ET.SubElement(comb, "default_on").text = "1"

    assoc = ET.SubElement(comb, "associations")
    povs = ET.SubElement(assoc, "product_option_values")
    pov = ET.SubElement(povs, "product_option_value")
    ET.SubElement(pov, "id").text = str(option_value_id)

    resp = api.post_xml("combinations", ET.tostring(root, encoding="utf-8"))
    return int(resp.findtext("./combination/id") or 0)


def clean_demo_catalog(api: PrestaShopAPI) -> None:
    """Usuwa domyślne produkty (id 1..19) i kategorie demo PrestaShop (id 3..9)."""
    demo_prods = api.get_json("products", {"display": "[id]", "filter[id]": "[1,19]"})
    deleted_prods = 0
    for p in demo_prods.get("products", []):
        pid = int(p["id"])
        if pid <= 19 and api.delete(f"products/{pid}"):
            deleted_prods += 1

    # Najpierw podkategorie (4,5,7,8), potem nadrzędne (3,6,9)
    deleted_cats = 0
    for cid in (4, 5, 7, 8, 3, 6, 9):
        if api.delete(f"categories/{cid}"):
            deleted_cats += 1

    print(f"Usunięto dane demo PrestaShop: produkty={deleted_prods}, kategorie={deleted_cats}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import produktów do PrestaShop przez API")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("scraper-results/products.json"),
        help="Ścieżka do pliku JSON ze scrapera",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maksymalna liczba produktów do zaimportowania (0 = wszystkie)",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=3,
        help="Maksymalna liczba zdjęć pobieranych dla produktu (domyślnie 3)",
    )
    parser.add_argument(
        "--featured-count",
        type=int,
        default=12,
        help="Liczba pierwszych produktów przypiętych też do Strony głównej (Polecane)",
    )
    parser.add_argument(
        "--clean-demo",
        action="store_true",
        help="Usuń domyślne produkty (id 1..19) i kategorie demo PrestaShop przed importem",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    env = load_env(repo_root / ".env")
    api_key = os.environ.get("PRESTASHOP_API_KEY") or env.get("PRESTASHOP_API_KEY", "")
    base_url = os.environ.get("PRESTASHOP_URL") or f"https://{env.get('PS_DOMAIN', 'localhost:8443')}"

    if not api_key:
        print("Błąd: brak PRESTASHOP_API_KEY w .env ani w zmiennych środowiskowych.", file=sys.stderr)
        sys.exit(1)

    input_path = args.input if args.input.is_absolute() else (repo_root / args.input)
    if not input_path.exists():
        print(f"Błąd: brak pliku {input_path}", file=sys.stderr)
        sys.exit(1)

    products = json.loads(input_path.read_text(encoding="utf-8"))
    if args.limit > 0:
        products = products[: args.limit]

    api = PrestaShopAPI(base_url=base_url, api_key=api_key, verify_ssl=False)
    if args.clean_demo:
        clean_demo_catalog(api)
    lang_ids = get_active_languages(api)
    tax_group_id = find_tax_rule_group_id(api)
    cat_cache = load_category_cache(api)
    size_group_id = ensure_size_option_group(api, lang_ids)
    size_cache = load_size_values_cache(api, size_group_id)
    existing_refs = load_existing_references(api)

    print(
        f"Start importu: {len(products)} produktów | języki={lang_ids} | "
        f"VAT_group={tax_group_id} | istniejących={len(existing_refs)}"
    )

    imported = 0
    skipped = 0
    errors = 0

    for idx, item in enumerate(products, start=1):
        ref = str(item.get("external_id", "")).strip()
        if not ref:
            continue
        if ref in existing_refs:
            skipped += 1
            continue

        try:
            cat_path = item.get("category_path") or ["Odzież damska", "Kolekcja"]
            parent_id = 2  # Strona główna
            cat_ids: list[int] = []
            for cat_name in cat_path:
                parent_id = ensure_category(api, cat_cache, parent_id, str(cat_name), lang_ids)
                cat_ids.append(parent_id)

            default_cat_id = cat_ids[-1]
            pid = create_product(
                api=api,
                item=item,
                cat_ids=cat_ids,
                default_cat_id=default_cat_id,
                tax_group_id=tax_group_id,
                lang_ids=lang_ids,
                featured=(idx <= args.featured_count),
            )

            variants = item.get("variants") or []
            attr_to_qty: dict[int, int] = {}
            if variants:
                for v_idx, v in enumerate(variants):
                    size_lbl = str(v.get("size", "One Size"))
                    opt_val_id = ensure_size_value(api, size_cache, size_group_id, size_lbl, lang_ids)
                    comb_id = create_combination(
                        api=api,
                        product_id=pid,
                        ref=f"{ref}-{size_lbl}",
                        option_value_id=opt_val_id,
                        is_default=(v_idx == 0),
                    )
                    attr_to_qty[comb_id] = int(v.get("stock_quantity", 5))
            else:
                attr_to_qty[0] = 5

            update_stock_for_product(api, pid, attr_to_qty)

            for img_idx, img_url in enumerate((item.get("image_urls") or [])[: args.max_images], start=1):
                img_bytes = download_image(img_url)
                if img_bytes:
                    api.upload_product_image(pid, img_bytes, f"{ref}_{img_idx}.jpg")

            existing_refs.add(ref)
            imported += 1
            print(f"[{idx}/{len(products)}] OK id={pid} ref={ref} ({item['name'][:45]})")
        except Exception as exc:
            errors += 1
            print(f"[{idx}/{len(products)}] ERROR ref={ref}: {exc}", file=sys.stderr)

    print(f"Zakończono import: zaimportowano={imported}, pominięto={skipped}, błędy={errors}.")


if __name__ == "__main__":
    main()
