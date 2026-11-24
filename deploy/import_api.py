#!/usr/bin/env python3
"""Idempotentny import kategorii, produktów, cech, wariantów, stanów i zdjęć przez API PrestaShop.

Realizuje wymaganie D2 (oraz powiązane metryki W2, W3, W4, D3):
- Tworzy i aktualizuje (POST / PUT) drzewo kategorii, cechy, warianty rozmiarowe, stany i zdjęcia.
- Gwarantuje idempotencję: ponowne uruchomienie aktualizuje rekordy bez tworzenia duplikatów.
- Wyznacza deterministyczne stany magazynowe 0–10 szt. (suma produktu <= 10, 5–20% ze stanem 0).
- Pobiera paczkę zdjęć z GitHub Releases (images.zip) z bezpiecznym fallbackiem do image_urls.
- Aktualizuje górne menu (#top-menu / MOD_BLOCKTOPMENU_ITEMS) na główne kategorie sklepu.
- Raportuje liczbę utworzonych, zaktualizowanych i odrzuconych rekordów.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import http.client
import io
import json
import logging
import os
import re
import ssl
import sys
import tarfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from PIL import Image

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

DEFAULT_RELEASE_ARCHIVE_URL = (
    "https://github.com/Sk1pp3rr/prestoshop-dywany/releases/download/images-v1.0/images.zip"
)
POLISH_TRANS = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
FORBIDDEN_GENERIC_CHARS_RE = re.compile(r"[<>;=#{}]+")
WHITESPACE_RE = re.compile(r"\s+")

logger = logging.getLogger("import_api")


def slugify(text: str, max_len: int = 128) -> str:
    """Tworzy bezpieczny slug ASCII dla pola link_rewrite w PrestaShop."""
    translated = text.translate(POLISH_TRANS)
    normalized = unicodedata.normalize("NFKD", translated).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return (slug or "produkt")[:max_len]


def sanitize_catalog_text(text: str, max_len: int = 128) -> str:
    """Usuwa znaki zabronione przez Validate::isCatalogName / Validate::isGenericName."""
    cleaned = FORBIDDEN_GENERIC_CHARS_RE.sub(",", text)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip(" ,")
    return (cleaned or "-")[:max_len]


def format_description_html(raw_desc: str, fallback: str) -> tuple[str, str]:
    """Zamienia opis tekstowy na czysty HTML (<p>, <br />) oraz krótki opis (<= 400 znaków)."""
    text = raw_desc.strip() or fallback.strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [fallback.strip()]

    html_parts: list[str] = []
    for para in paragraphs:
        lines = [html.escape(line.strip()) for line in para.splitlines() if line.strip()]
        if lines:
            html_parts.append(f"<p>{'<br />'.join(lines)}</p>")
    full_html = "\n".join(html_parts) or f"<p>{html.escape(fallback)}</p>"

    plain_short = WHITESPACE_RE.sub(" ", paragraphs[-1] if len(paragraphs) > 1 else paragraphs[0])
    if len(plain_short) > 360:
        plain_short = plain_short[:357].rsplit(" ", 1)[0] + "..."
    short_html = f"<p>{html.escape(plain_short)}</p>"
    return full_html, short_html


def load_env_file(repo_root: Path) -> dict[str, str]:
    """Wczytuje zmienne środowiskowe z pliku .env bez zewnętrznych zależności."""
    env: dict[str, str] = {}
    candidates = [
        Path.cwd() / ".env",
        repo_root / ".env",
        Path(__file__).resolve().parent / ".env",
    ]
    seen: set[str] = set()
    for candidate in candidates:
        resolved = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists():
            for raw_line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                env.setdefault(key.strip(), val.strip().strip("\"'"))
    return env


def normalize_release_url(raw_url: str) -> str:
    """Zamienia URL strony tagu GitHub Releases na bezpośredni adres archiwum images.zip."""
    url = raw_url.strip()
    if not url or "OWNER/REPO" in url:
        return DEFAULT_RELEASE_ARCHIVE_URL
    tag_match = re.match(r"^(https://github\.com/[^/]+/[^/]+)/releases/tag/([^/?#]+)", url)
    if tag_match:
        base_repo, tag = tag_match.group(1), tag_match.group(2)
        return f"{base_repo}/releases/download/{tag}/images.zip"
    return url


@dataclass(frozen=True)
class PreparedRecord:
    """Wstępnie znormalizowany rekord produktu gotowy do importu."""

    index: int
    ref: str
    external_id: str
    archive_prefix: str
    is_primary_ext_id: bool
    item: dict[str, Any]


def prepare_records(products: list[dict[str, Any]]) -> tuple[list[PreparedRecord], int]:
    """Nadaje każdemu rekordowi unikalny, deterministyczny klucz reference (<= 64 znaki).

    Pierwsze wystąpienie danego external_id zachowuje czysty kod (np. MMM0492),
    a kolejne warianty kolorystyczne otrzymują deterministyczny skrót z nazwy produktu.
    Zwraca listę poprawnych rekordów oraz liczbę rekordów odrzuconych na etapie walidacji.
    """
    prepared: list[PreparedRecord] = []
    rejected_invalid = 0
    ext_occ_counts: dict[str, int] = {}
    used_refs: set[str] = set()

    for idx, item in enumerate(products, start=1):
        if not isinstance(item, dict):
            logger.error("[%d] REJECTED: rekord nie jest obiektem JSON.", idx)
            rejected_invalid += 1
            continue

        ext_id = str(item.get("external_id") or "").strip()
        name = str(item.get("name") or "").strip()
        try:
            price_gross = float(item.get("price_gross") or 0.0)
        except (TypeError, ValueError):
            price_gross = 0.0

        if not ext_id or not name or price_gross <= 0:
            logger.error(
                "[%d] REJECTED ext_id=%r name=%r: brak wymaganych pól lub błędna cena.",
                idx,
                ext_id,
                name,
            )
            rejected_invalid += 1
            continue

        occ = ext_occ_counts.get(ext_id, 0) + 1
        ext_occ_counts[ext_id] = occ
        archive_prefix = ext_id if occ == 1 else f"{ext_id}-{occ}"

        if occ == 1 and ext_id[:64] not in used_refs:
            ref = ext_id[:64]
            is_primary = True
        else:
            is_primary = False
            name_hash = hashlib.md5(name.lower().encode("utf-8")).hexdigest()[:6]
            tail_slug = slugify(name.rsplit(" ", 2)[-1], max_len=16)
            candidate = f"{ext_id[:38]}-{tail_slug}-{name_hash}"[:64]
            counter = 2
            while candidate in used_refs:
                candidate = f"{ext_id[:48]}-{name_hash}-{counter}"[:64]
                counter += 1
            ref = candidate

        used_refs.add(ref)
        prepared.append(
            PreparedRecord(
                index=idx,
                ref=ref,
                external_id=ext_id,
                archive_prefix=archive_prefix,
                is_primary_ext_id=is_primary,
                item=item,
            )
        )

    return prepared, rejected_invalid


def is_product_out_of_stock(ref: str) -> bool:
    """Deterministycznie wyznacza ok. 12% produktów ze stanem 0 (wymóg W3: 5%–20%)."""
    seed = int(hashlib.md5(ref.encode("utf-8")).hexdigest()[:8], 16) % 100
    return seed < 12


def compute_variant_stocks(ref: str, variant_labels: list[str]) -> tuple[list[int], int]:
    """Wyznacza deterministyczne stany wariantów oraz indeks domyślnego wariantu.

    Gwarantuje:
    - 0 szt. na wszystkich wariantach dla produktów wyprzedanych (~12% katalogu),
    - dla produktów dostępnych: łączna suma stanów wszystkich wariantów wynosi 3..10 szt.
      (dzięki czemu wiersz główny id_product_attribute=0 w ps_stock_available ma zawsze <= 10 szt.),
    - domyślny wariant produktu dostępnego ma co najmniej 3 szt. (pod testy E2E Playwright).
    """
    count = len(variant_labels)
    if count == 0:
        qty = (
            0
            if is_product_out_of_stock(ref)
            else (3 + int(hashlib.md5(ref.encode()).hexdigest()[:4], 16) % 8)
        )
        return [qty], 0

    if is_product_out_of_stock(ref):
        return [0] * count, 0

    digest = int(hashlib.md5(ref.encode("utf-8")).hexdigest()[:12], 16)
    if count == 1:
        total_qty = 3 + (digest % 8)  # 3..10
        return [total_qty], 0

    total_qty = 4 + (digest % 7)  # 4..10 dla wielowariantowych
    default_idx = (digest // 7) % count
    stocks = [0] * count
    base_default = min(total_qty, 3)
    stocks[default_idx] = base_default
    remaining = total_qty - base_default

    step_seed = (digest // 97) or 1
    for unit in range(remaining):
        target_idx = (default_idx + 1 + (unit + step_seed) % count) % count
        stocks[target_idx] += 1

    return stocks, default_idx


class PrestaShopAPI:
    """Wielowątkowy klient PrestaShop Webservice API z połączeniami Keep-Alive (stdlib)."""

    def __init__(
        self, base_url: str, api_key: str, verify_ssl: bool = False, timeout: int = 30
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
        self.scheme = parsed.scheme or "https"
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or (443 if self.scheme == "https" else 80)
        self.base_path = parsed.path.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.ssl_ctx = (
            ssl.create_default_context() if verify_ssl else ssl._create_unverified_context()
        )
        token = base64.b64encode(f"{api_key}:".encode("ascii")).decode("ascii")
        self.auth_header = f"Basic {token}"
        self.use_query_key = False
        self._local = threading.local()

    def _get_conn(self) -> http.client.HTTPConnection:
        conn: http.client.HTTPConnection | None = getattr(self._local, "conn", None)
        if conn is None:
            if self.scheme == "https":
                conn = http.client.HTTPSConnection(
                    self.host, self.port, timeout=self.timeout, context=self.ssl_ctx
                )
            else:
                conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
            self._local.conn = conn
        return conn

    def _reset_conn(self) -> None:
        conn: http.client.HTTPConnection | None = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
            self._local.conn = None

    def _build_path(self, resource: str, params: dict[str, str] | None = None) -> str:
        query = dict(params or {})
        if self.use_query_key:
            query["ws_key"] = self.api_key
        clean_res = resource.lstrip("/")
        path = f"{self.base_path}/api/{clean_res}"
        if query:
            sep = "&" if "?" in path else "?"
            path = f"{path}{sep}{urllib.parse.urlencode(query)}"
        return path

    def request(
        self,
        method: str,
        resource: str,
        params: dict[str, str] | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
        retries: int = 3,
    ) -> tuple[int, bytes]:
        headers: dict[str, str] = {
            "Authorization": self.auth_header,
            "Connection": "keep-alive",
        }
        if content_type:
            headers["Content-Type"] = content_type
        if body is not None:
            headers["Content-Length"] = str(len(body))

        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            path = self._build_path(resource, params)
            try:
                conn = self._get_conn()
                conn.request(method, path, body=body, headers=headers)
                resp = conn.getresponse()
                raw = resp.read()
                status = resp.status

                if status == 401 and not self.use_query_key:
                    self.use_query_key = True
                    continue

                if (
                    status in {500, 502, 503, 504}
                    and attempt < retries
                    and method in {"GET", "PUT", "DELETE", "HEAD"}
                ):
                    self._reset_conn()
                    time.sleep(0.25 * attempt)
                    continue

                return status, raw
            except (
                http.client.HTTPException,
                OSError,
                TimeoutError,
                ssl.SSLError,
            ) as exc:
                last_exc = exc
                self._reset_conn()
                if attempt < retries:
                    time.sleep(0.25 * attempt)
                    continue
                raise RuntimeError(f"{method} {resource} błąd połączenia: {exc}") from exc

        raise RuntimeError(f"{method} {resource} nieudane po {retries} próbach: {last_exc}")

    def get_json(self, resource: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        query["output_format"] = "JSON"
        status, raw = self.request("GET", resource, params=query)
        if status >= 400:
            detail = raw.decode("utf-8", errors="ignore")[:400]
            raise RuntimeError(f"GET {resource} -> HTTP {status}: {detail}")
        text = raw.decode("utf-8", errors="replace").strip()
        if not text or text == "[]":
            return {}
        data = json.loads(text)
        return data if isinstance(data, dict) else {}

    def post_xml(self, resource: str, xml_body: bytes) -> ET.Element:
        status, raw = self.request(
            "POST", resource, body=xml_body, content_type="application/xml; charset=utf-8"
        )
        if status >= 400:
            detail = raw.decode("utf-8", errors="ignore")[:400]
            raise RuntimeError(f"POST {resource} -> HTTP {status}: {detail}")
        return ET.fromstring(raw)

    def put_xml(self, resource: str, xml_body: bytes) -> ET.Element:
        status, raw = self.request(
            "PUT", resource, body=xml_body, content_type="application/xml; charset=utf-8"
        )
        if status >= 400:
            detail = raw.decode("utf-8", errors="ignore")[:400]
            raise RuntimeError(f"PUT {resource} -> HTTP {status}: {detail}")
        return ET.fromstring(raw)

    def delete(self, resource: str) -> bool:
        status, raw = self.request("DELETE", resource)
        if status == 404:
            return False
        if status >= 400:
            detail = raw.decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"DELETE {resource} -> HTTP {status}: {detail}")
        return True

    def upload_product_image(self, product_id: int, image_bytes: bytes, filename: str) -> None:
        boundary = f"----PSBoundary{uuid.uuid4().hex}"
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
                f"Content-Type: image/jpeg\r\n\r\n"
            ).encode()
            + image_bytes
            + f"\r\n--{boundary}--\r\n".encode()
        )
        status, raw = self.request(
            "POST",
            f"images/products/{product_id}",
            body=body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        if status >= 400:
            detail = raw.decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"POST images/products/{product_id} -> HTTP {status}: {detail}")


class ImageResolver:
    """Zarządza pobieraniem zdjęć z archiwum GitHub Releases, katalogu lokalnego i URL-i."""

    def __init__(
        self,
        archive_url: str,
        cache_dir: Path,
        sample_dir: Path,
        max_kb: int = 240,
    ) -> None:
        self.archive_url = normalize_release_url(archive_url)
        self.cache_dir = cache_dir
        self.sample_dir = sample_dir
        self.max_kb = max_kb
        self._local_index: dict[str, Path] = {}
        self._url_bytes_cache: dict[str, bytes] = {}
        self._cache_lock = threading.Lock()

    def prepare(self) -> None:
        """Pobiera i rozpakowuje archiwum zdjęć z Releases oraz buduje indeks lokalny."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        marker = self.cache_dir / ".extracted_ok"
        if not marker.exists() and self.archive_url:
            self._download_and_extract(marker)

        for folder in (self.sample_dir, self.cache_dir):
            if not folder.exists():
                continue
            for file_path in folder.rglob("*"):
                if not file_path.is_file() or "__MACOSX" in file_path.parts:
                    continue
                if file_path.name.startswith("."):
                    continue
                if file_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    self._local_index.setdefault(file_path.stem.lower(), file_path)

        logger.info(
            "Zaindeksowano %d lokalnych plików zdjęć (cache=%s, sample=%s).",
            len(self._local_index),
            self.cache_dir,
            self.sample_dir,
        )

    def _download_and_extract(self, marker: Path) -> None:
        logger.info("Pobieranie archiwum zdjęć z GitHub Releases: %s", self.archive_url)
        req = urllib.request.Request(
            self.archive_url,
            headers={"User-Agent": "PrestaShopImporter/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status != 200:
                    logger.warning(
                        "Archiwum Releases zwróciło HTTP %d — użyję fallbacku.", resp.status
                    )
                    return
                archive_bytes = resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as exc:
            logger.warning(
                "Nie udało się pobrać archiwum Releases (%s) — przechodzę na fallback HTTP.", exc
            )
            return

        if len(archive_bytes) < 512:
            logger.warning("Pobrane archiwum Releases jest puste lub niepoprawne.")
            return

        try:
            if zipfile.is_zipfile(io.BytesIO(archive_bytes)):
                with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                    for member in zf.infolist():
                        if member.is_dir() or ".." in Path(member.filename).parts:
                            continue
                        if "__MACOSX" in member.filename:
                            continue
                        zf.extract(member, self.cache_dir)
            else:
                with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as tf:
                    for member in tf.getmembers():
                        if not member.isfile() or ".." in Path(member.name).parts:
                            continue
                        tf.extract(member, self.cache_dir)
            marker.write_text(self.archive_url, encoding="utf-8")
            logger.info("Rozpakowano archiwum zdjęć do %s.", self.cache_dir)
        except (zipfile.BadZipFile, tarfile.TarError, OSError) as exc:
            logger.warning(
                "Nie udało się rozpakować archiwum zdjęć (%s) — użyję fallbacku HTTP.", exc
            )

    def _normalize_image(self, raw_bytes: bytes) -> bytes | None:
        if len(raw_bytes) < 512:
            return None
        if not HAS_PILLOW:
            return raw_bytes

        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                width, height = img.size
                longest = max(width, height)
                needs_resize = longest > 1600 or longest < 800
                needs_reencode = img.format != "JPEG" or (len(raw_bytes) / 1024.0) > self.max_kb

                if not needs_resize and not needs_reencode:
                    return raw_bytes

                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                if longest > 1600:
                    ratio = 1600.0 / longest
                    img = img.resize(
                        (max(1, int(width * ratio)), max(1, int(height * ratio))),
                        Image.Resampling.LANCZOS,
                    )
                elif 0 < longest < 800:
                    ratio = 800.0 / longest
                    img = img.resize(
                        (max(1, int(width * ratio)), max(1, int(height * ratio))),
                        Image.Resampling.LANCZOS,
                    )

                quality = 85
                while quality >= 35:
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=quality, optimize=True)
                    if (buf.tell() / 1024.0) <= self.max_kb or quality == 35:
                        return buf.getvalue()
                    quality -= 7
        except Exception as exc:
            logger.debug("Błąd normalizacji obrazu Pillow (%s), zwracam surowe bajty.", exc)
            return raw_bytes
        return raw_bytes

    def _fetch_remote(self, url: str) -> bytes | None:
        with self._cache_lock:
            cached = self._url_bytes_cache.get(url)
        if cached is not None:
            return cached

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PrestaShopImporter/1.0)"},
        )
        for attempt in range(1, 3):
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status == 200:
                        normalized = self._normalize_image(resp.read())
                        if normalized:
                            with self._cache_lock:
                                if len(self._url_bytes_cache) < 256:
                                    self._url_bytes_cache[url] = normalized
                            return normalized
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
                if attempt == 1:
                    time.sleep(0.3)
        return None

    def get_image_bytes(
        self,
        ref: str,
        external_id: str,
        archive_prefix: str,
        is_primary_ext_id: bool,
        img_index_1based: int,
        url: str,
    ) -> bytes | None:
        """Zwraca bajty zdjęcia wg hierarchii źródeł z zachowaniem zgodności kolorystycznej."""
        exact_ref_key = f"{ref.lower()}_{img_index_1based}"
        if exact_ref_key in self._local_index:
            raw = self._local_index[exact_ref_key].read_bytes()
            return self._normalize_image(raw)

        ext_key = f"{external_id.lower()}_{img_index_1based}"
        if is_primary_ext_id and ext_key in self._local_index:
            raw = self._local_index[ext_key].read_bytes()
            return self._normalize_image(raw)

        remote_bytes = self._fetch_remote(url)
        if remote_bytes is not None:
            return remote_bytes

        for fb_key in (
            f"{archive_prefix.lower()}_{img_index_1based}",
            f"{archive_prefix.lower()}_1",
            f"{external_id.lower()}_1",
        ):
            if fb_key in self._local_index:
                logger.warning(
                    "Użyto zdjęcia z archiwum (%s) dla ref=%s po błędzie pobrania %s.",
                    fb_key,
                    ref,
                    url,
                )
                return self._normalize_image(self._local_index[fb_key].read_bytes())

        return None


def add_lang_field(parent: ET.Element, tag: str, value: str, lang_ids: list[int]) -> None:
    el = ET.SubElement(parent, tag)
    for lid in lang_ids:
        lang_el = ET.SubElement(el, "language", {"id": str(lid)})
        lang_el.text = value


def extract_lang_text(field_val: Any) -> str:
    if isinstance(field_val, str):
        return field_val
    if isinstance(field_val, list) and field_val:
        first = field_val[0]
        if isinstance(first, dict):
            return str(first.get("value") or "")
        return str(first)
    if isinstance(field_val, dict):
        return str(field_val.get("value") or "")
    return ""


def get_active_languages(api: PrestaShopAPI) -> list[int]:
    data = api.get_json("languages", {"display": "[id,active]"})
    ids = [int(item["id"]) for item in data.get("languages", []) if str(item.get("active")) == "1"]
    return sorted(ids) or [1]


def find_tax_rule_group_map(api: PrestaShopAPI) -> dict[int, int]:
    """Mapuje stawkę VAT (np. 23, 8, 5, 0) na id_tax_rules_group z PrestaShop."""
    data = api.get_json("tax_rule_groups", {"display": "[id,name,active]"})
    groups = [g for g in data.get("tax_rule_groups", []) if str(g.get("active", "1")) == "1"]
    rate_map: dict[int, int] = {}
    default_id = int(groups[0]["id"]) if groups else 1

    for grp in groups:
        gid = int(grp["id"])
        name = str(grp.get("name") or "").lower()
        for rate in (23, 8, 5, 0):
            if f"{rate}%" in name or f"({rate}%)" in name:
                rate_map.setdefault(rate, gid)
        if "23" in name or "pl standard" in name:
            default_id = gid

    rate_map.setdefault(23, default_id)
    return rate_map


def set_configuration_value(api: PrestaShopAPI, name: str, value: str) -> str | None:
    """Ustawia wartość klucza w ps_configuration przez API i zwraca poprzednią wartość."""
    data = api.get_json(
        "configurations",
        {"display": "[id,name,value]", "filter[name]": f"[{name}]"},
    )
    configs = data.get("configurations", [])
    root = ET.Element("prestashop")
    cfg_el = ET.SubElement(root, "configuration")

    if configs:
        cfg_id = int(configs[0]["id"])
        prev_value = str(configs[0].get("value") or "")
        if prev_value == value:
            return prev_value
        ET.SubElement(cfg_el, "id").text = str(cfg_id)
        ET.SubElement(cfg_el, "name").text = name
        ET.SubElement(cfg_el, "value").text = value
        api.put_xml(f"configurations/{cfg_id}", ET.tostring(root, encoding="utf-8"))
        return prev_value

    ET.SubElement(cfg_el, "name").text = name
    ET.SubElement(cfg_el, "value").text = value
    api.post_xml("configurations", ET.tostring(root, encoding="utf-8"))
    return None


def clean_demo_catalog(api: PrestaShopAPI, keep_cat_names: set[str] | None = None) -> None:
    """Usuwa domyślne produkty (id 1..19), kategorie demo (id 3..9) oraz cechy demo (id 1..2)."""
    demo_prods = api.get_json("products", {"display": "[id,reference]", "filter[id]": "[1,19]"})
    deleted_prods = 0
    for prod in demo_prods.get("products", []):
        pid = int(prod["id"])
        ref = str(prod.get("reference") or "")
        if pid <= 19 and not ref.startswith(("MMM", "ILM", "JK", "AP", "FL", "FT", "ESP", "HCM")):
            if api.delete(f"products/{pid}"):
                deleted_prods += 1

    deleted_cats = 0
    protected_names = keep_cat_names or set()
    cats_data = api.get_json("categories", {"display": "[id,name,id_parent]"})
    cats_by_id = {int(c["id"]): c for c in cats_data.get("categories", [])}
    for cid in (4, 5, 7, 8, 3, 6, 9):
        cat_obj = cats_by_id.get(cid)
        if not cat_obj:
            continue
        cname = extract_lang_text(cat_obj.get("name")).strip().lower()
        if cname not in protected_names and api.delete(f"categories/{cid}"):
            deleted_cats += 1

    feats_data = api.get_json("product_features", {"display": "[id,name]"})
    for feat in feats_data.get("product_features", []):
        fid = int(feat["id"])
        fname = extract_lang_text(feat.get("name")).strip().lower()
        if fid <= 2 and fname in {"composition", "property"}:
            api.delete(f"product_features/{fid}")

    logger.info("Czyszczenie danych demo: produkty=%d, kategorie=%d.", deleted_prods, deleted_cats)


def sync_categories(
    api: PrestaShopAPI,
    records: list[PreparedRecord],
    lang_ids: list[int],
) -> tuple[dict[tuple[int, str], int], list[int]]:
    """Tworzy lub aktualizuje drzewo kategorii i zwraca cache oraz ID 5 kategorii głównych."""
    existing_data = api.get_json("categories", {"display": "[id,id_parent,name,active]"})
    cache: dict[tuple[int, str], int] = {}
    active_state: dict[int, str] = {}
    for cat in existing_data.get("categories", []):
        cid = int(cat["id"])
        parent_id = int(cat.get("id_parent", 0))
        cname = extract_lang_text(cat.get("name")).strip()
        if cname:
            cache[(parent_id, cname.lower())] = cid
            active_state[cid] = str(cat.get("active", "1"))

    unique_paths: list[list[str]] = []
    seen_paths: set[tuple[str, ...]] = set()
    main_cat_names_ordered: list[str] = []
    seen_main: set[str] = set()

    for rec in records:
        raw_path = rec.item.get("category_path") or ["Odzież damska", "Kolekcja"]
        clean_path = [sanitize_catalog_text(str(seg), 128) for seg in raw_path if str(seg).strip()]
        if not clean_path:
            clean_path = ["Odzież damska", "Kolekcja"]
        key_tuple = tuple(clean_path)
        if key_tuple not in seen_paths:
            seen_paths.add(key_tuple)
            unique_paths.append(clean_path)
        main_lower = clean_path[0].lower()
        if main_lower not in seen_main:
            seen_main.add(main_lower)
            main_cat_names_ordered.append(clean_path[0])

    created_cats = 0
    updated_cats = 0
    for path in unique_paths:
        parent_id = 2  # Strona główna (Home)
        for cat_name in path:
            lookup = (parent_id, cat_name.lower())
            root = ET.Element("prestashop")
            cat_el = ET.SubElement(root, "category")
            if lookup in cache:
                cid = cache[lookup]
                if active_state.get(cid) != "1":
                    ET.SubElement(cat_el, "id").text = str(cid)
                    ET.SubElement(cat_el, "id_parent").text = str(parent_id)
                    ET.SubElement(cat_el, "active").text = "1"
                    ET.SubElement(cat_el, "is_root_category").text = "0"
                    add_lang_field(cat_el, "name", cat_name, lang_ids)
                    add_lang_field(cat_el, "link_rewrite", slugify(cat_name), lang_ids)
                    api.put_xml(f"categories/{cid}", ET.tostring(root, encoding="utf-8"))
                    active_state[cid] = "1"
                    updated_cats += 1
                parent_id = cid
            else:
                ET.SubElement(cat_el, "id_parent").text = str(parent_id)
                ET.SubElement(cat_el, "active").text = "1"
                ET.SubElement(cat_el, "is_root_category").text = "0"
                add_lang_field(cat_el, "name", cat_name, lang_ids)
                add_lang_field(cat_el, "link_rewrite", slugify(cat_name), lang_ids)
                resp = api.post_xml("categories", ET.tostring(root, encoding="utf-8"))
                cid = int(resp.findtext("./category/id") or 0)
                cache[lookup] = cid
                active_state[cid] = "1"
                parent_id = cid
                created_cats += 1

    main_cat_ids = [
        cache[(2, name.lower())] for name in main_cat_names_ordered if (2, name.lower()) in cache
    ]
    for (pid_key, _cname), cid_val in sorted(cache.items(), key=lambda kv: kv[1]):
        if pid_key == 2 and active_state.get(cid_val) == "1" and cid_val not in main_cat_ids:
            main_cat_ids.append(cid_val)
    logger.info(
        "Kategorie zsynchronizowane: utworzono=%d, zaktualizowano=%d, główne=%s.",
        created_cats,
        updated_cats,
        main_cat_ids,
    )
    return cache, main_cat_ids


def sync_size_options(
    api: PrestaShopAPI,
    records: list[PreparedRecord],
    lang_ids: list[int],
) -> tuple[int, dict[str, int]]:
    """Tworzy grupę opcji 'Rozmiar' i wszystkie unikalne wartości rozmiarów z products.json."""
    opts_data = api.get_json("product_options", {"display": "[id,name]"})
    group_id = 0
    for opt in opts_data.get("product_options", []):
        name = extract_lang_text(opt.get("name")).strip().lower()
        if name in {"rozmiar", "size"}:
            group_id = int(opt["id"])
            break

    if group_id == 0:
        root = ET.Element("prestashop")
        po_el = ET.SubElement(root, "product_option")
        ET.SubElement(po_el, "is_color_group").text = "0"
        ET.SubElement(po_el, "group_type").text = "select"
        add_lang_field(po_el, "name", "Rozmiar", lang_ids)
        add_lang_field(po_el, "public_name", "Rozmiar", lang_ids)
        resp = api.post_xml("product_options", ET.tostring(root, encoding="utf-8"))
        group_id = int(resp.findtext("./product_option/id") or 1)

    vals_data = api.get_json(
        "product_option_values",
        {"display": "[id,id_attribute_group,name]", "filter[id_attribute_group]": str(group_id)},
    )
    size_cache: dict[str, int] = {}
    for val in vals_data.get("product_option_values", []):
        vname = extract_lang_text(val.get("name")).strip()
        if vname:
            size_cache[vname.upper()] = int(val["id"])

    needed_sizes: list[str] = []
    seen_sizes: set[str] = set()
    for rec in records:
        for var in rec.item.get("variants") or []:
            lbl = sanitize_catalog_text(str(var.get("size") or "UNIWERSALNY"), 64)
            norm = lbl.upper()
            if norm not in seen_sizes:
                seen_sizes.add(norm)
                needed_sizes.append(lbl)

    for lbl in needed_sizes:
        norm = lbl.upper()
        if norm in size_cache:
            continue
        root = ET.Element("prestashop")
        pov_el = ET.SubElement(root, "product_option_value")
        ET.SubElement(pov_el, "id_attribute_group").text = str(group_id)
        add_lang_field(pov_el, "name", lbl, lang_ids)
        resp = api.post_xml("product_option_values", ET.tostring(root, encoding="utf-8"))
        size_cache[norm] = int(resp.findtext("./product_option_value/id") or 0)

    logger.info("Rozmiary zsynchronizowane: grupa_id=%d, wartości=%d.", group_id, len(size_cache))
    return group_id, size_cache


def sync_product_features(
    api: PrestaShopAPI,
    records: list[PreparedRecord],
    lang_ids: list[int],
    workers: int,
) -> tuple[dict[str, int], dict[tuple[int, str], int]]:
    """Synchronizuje słownik cech (attributes) do product_features i product_feature_values."""
    feats_data = api.get_json("product_features", {"display": "[id,name]"})
    feat_map: dict[str, int] = {}
    for feat in feats_data.get("product_features", []):
        fname = extract_lang_text(feat.get("name")).strip()
        if fname:
            feat_map[fname.lower()] = int(feat["id"])

    needed_feat_names: list[str] = []
    seen_fnames: set[str] = set()
    needed_pairs: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for rec in records:
        attrs = rec.item.get("attributes") or {}
        if not isinstance(attrs, dict):
            continue
        for raw_k, raw_v in attrs.items():
            clean_k = sanitize_catalog_text(str(raw_k), 128)
            clean_v = sanitize_catalog_text(str(raw_v), 250)
            if not clean_k or not clean_v or clean_v == "-":
                continue
            k_low = clean_k.lower()
            if k_low not in seen_fnames:
                seen_fnames.add(k_low)
                needed_feat_names.append(clean_k)
            pair_key = (k_low, clean_v.lower())
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                needed_pairs.append((clean_k, clean_v))

    for fname in needed_feat_names:
        if fname.lower() in feat_map:
            continue
        root = ET.Element("prestashop")
        f_el = ET.SubElement(root, "product_feature")
        add_lang_field(f_el, "name", fname, lang_ids)
        resp = api.post_xml("product_features", ET.tostring(root, encoding="utf-8"))
        feat_map[fname.lower()] = int(resp.findtext("./product_feature/id") or 0)

    fvals_data = api.get_json("product_feature_values", {"display": "[id,id_feature,value]"})
    fval_map: dict[tuple[int, str], int] = {}
    for fv in fvals_data.get("product_feature_values", []):
        fid = int(fv.get("id_feature", 0))
        vtext = extract_lang_text(fv.get("value")).strip()
        if fid and vtext:
            fval_map[(fid, vtext.lower())] = int(fv["id"])

    missing_fvals: list[tuple[int, str]] = []
    for clean_k, clean_v in needed_pairs:
        fid = feat_map[clean_k.lower()]
        if (fid, clean_v.lower()) not in fval_map:
            missing_fvals.append((fid, clean_v))

    if missing_fvals:
        logger.info("Tworzenie %d nowych wartości cech produktów...", len(missing_fvals))

        def _create_fval(entry: tuple[int, str]) -> tuple[tuple[int, str], int]:
            fid, val_str = entry
            root = ET.Element("prestashop")
            fv_el = ET.SubElement(root, "product_feature_value")
            ET.SubElement(fv_el, "id_feature").text = str(fid)
            ET.SubElement(fv_el, "custom").text = "0"
            add_lang_field(fv_el, "value", val_str, lang_ids)
            resp = api.post_xml("product_feature_values", ET.tostring(root, encoding="utf-8"))
            new_id = int(resp.findtext("./product_feature_value/id") or 0)
            return (fid, val_str.lower()), new_id

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for key_pair, new_id in pool.map(_create_fval, missing_fvals):
                fval_map[key_pair] = new_id

    logger.info("Cechy zsynchronizowane: nazwy=%d, wartości=%d.", len(feat_map), len(fval_map))
    return feat_map, fval_map


@dataclass
class ExistingProductInfo:
    product_id: int
    default_image_id: int = 0
    default_combination_id: int = 0
    image_count: int = 0
    combinations: dict[str, tuple[int, bool]] = field(default_factory=dict)
    stock_rows: list[dict[str, Any]] = field(default_factory=list)


def preload_existing_catalog(api: PrestaShopAPI) -> dict[str, ExistingProductInfo]:
    """Pobiera istniejące produkty, kombinacje i stany w celu szybkiej aktualizacji PUT."""
    prods_data = api.get_json("products", {"display": "full"})
    by_ref: dict[str, ExistingProductInfo] = {}
    by_id: dict[int, ExistingProductInfo] = {}

    for prod in prods_data.get("products", []):
        ref = str(prod.get("reference") or "").strip()
        if not ref or "id" not in prod:
            continue
        pid = int(prod["id"])
        raw_def_img = str(prod.get("id_default_image") or "").strip()
        def_img = int(raw_def_img) if raw_def_img.isdigit() else 0
        raw_def_comb = str(
            prod.get("id_default_combination") or prod.get("cache_default_attribute") or ""
        ).strip()
        def_comb = int(raw_def_comb) if raw_def_comb.isdigit() else 0
        imgs = (prod.get("associations") or {}).get("images") or []
        info = ExistingProductInfo(
            product_id=pid,
            default_image_id=def_img,
            default_combination_id=def_comb,
            image_count=len(imgs) if isinstance(imgs, list) else 0,
        )
        by_ref[ref] = info
        by_id[pid] = info

    if not by_id:
        return by_ref

    combs_data = api.get_json("combinations", {"display": "[id,id_product,reference,default_on]"})
    for comb in combs_data.get("combinations", []):
        pid = int(comb.get("id_product", 0))
        cref = str(comb.get("reference") or "").strip()
        if pid in by_id and cref:
            is_def = str(comb.get("default_on") or "") == "1"
            by_id[pid].combinations[cref] = (int(comb["id"]), is_def)

    stocks_data = api.get_json("stock_availables", {"display": "full"})
    for sa in stocks_data.get("stock_availables", []):
        pid = int(sa.get("id_product", 0))
        if pid in by_id:
            by_id[pid].stock_rows.append(sa)

    return by_ref


def build_product_xml(
    rec: PreparedRecord,
    cat_ids: list[int],
    default_cat_id: int,
    tax_group_id: int,
    lang_ids: list[int],
    feature_pairs: list[tuple[int, int]],
    featured: bool,
    product_id: int | None = None,
    default_image_id: int = 0,
    default_combination_id: int = 0,
) -> bytes:
    item = rec.item
    vat_rate = float(item.get("vat_rate") or 23.0)
    price_gross = float(item["price_gross"])
    price_net = round(price_gross / (1.0 + vat_rate / 100.0), 6)
    weight_kg = float(item.get("weight_kg") or 0.5)
    variants = item.get("variants") or []

    root = ET.Element("prestashop")
    prod = ET.SubElement(root, "product")
    if product_id is not None:
        ET.SubElement(prod, "id").text = str(product_id)

    ET.SubElement(prod, "id_category_default").text = str(default_cat_id)
    ET.SubElement(prod, "id_tax_rules_group").text = str(tax_group_id)
    if product_id is not None and default_image_id > 0:
        ET.SubElement(prod, "id_default_image").text = str(default_image_id)
    if product_id is not None and default_combination_id > 0:
        ET.SubElement(prod, "cache_default_attribute").text = str(default_combination_id)

    ET.SubElement(prod, "reference").text = rec.ref
    ET.SubElement(prod, "price").text = f"{price_net:.6f}"
    ET.SubElement(prod, "weight").text = f"{weight_kg:.6f}"
    ET.SubElement(prod, "minimal_quantity").text = "1"
    ET.SubElement(prod, "active").text = "1"
    ET.SubElement(prod, "state").text = "1"
    ET.SubElement(prod, "available_for_order").text = "1"
    ET.SubElement(prod, "show_price").text = "1"
    ET.SubElement(prod, "visibility").text = "both"
    ET.SubElement(prod, "indexed").text = "1"
    ET.SubElement(prod, "product_type").text = "combinations" if variants else "standard"

    clean_name = sanitize_catalog_text(str(item["name"]), 128)
    full_html, short_html = format_description_html(str(item.get("description") or ""), clean_name)
    add_lang_field(prod, "name", clean_name, lang_ids)
    add_lang_field(prod, "description", full_html, lang_ids)
    add_lang_field(prod, "description_short", short_html, lang_ids)
    add_lang_field(prod, "link_rewrite", slugify(clean_name), lang_ids)

    assoc = ET.SubElement(prod, "associations")
    cats_el = ET.SubElement(assoc, "categories")
    all_cats = list(dict.fromkeys(([2] if featured else []) + cat_ids))
    for cid in all_cats:
        c_el = ET.SubElement(cats_el, "category")
        ET.SubElement(c_el, "id").text = str(cid)

    if feature_pairs:
        pfs_el = ET.SubElement(assoc, "product_features")
        for fid, fvid in feature_pairs:
            pf_el = ET.SubElement(pfs_el, "product_feature")
            ET.SubElement(pf_el, "id").text = str(fid)
            ET.SubElement(pf_el, "id_feature_value").text = str(fvid)

    return ET.tostring(root, encoding="utf-8")


def build_combination_xml(
    product_id: int,
    comb_ref: str,
    option_value_id: int,
    is_default: bool,
    price_impact_net: float = 0.0,
    weight_impact: float = 0.0,
    comb_id: int | None = None,
) -> bytes:
    root = ET.Element("prestashop")
    comb = ET.SubElement(root, "combination")
    if comb_id is not None:
        ET.SubElement(comb, "id").text = str(comb_id)
    ET.SubElement(comb, "id_product").text = str(product_id)
    ET.SubElement(comb, "reference").text = comb_ref[:64]
    ET.SubElement(comb, "price").text = f"{price_impact_net:.6f}"
    ET.SubElement(comb, "weight").text = f"{weight_impact:.6f}"
    ET.SubElement(comb, "minimal_quantity").text = "1"
    if is_default:
        ET.SubElement(comb, "default_on").text = "1"

    assoc = ET.SubElement(comb, "associations")
    povs = ET.SubElement(assoc, "product_option_values")
    pov = ET.SubElement(povs, "product_option_value")
    ET.SubElement(pov, "id").text = str(option_value_id)
    return ET.tostring(root, encoding="utf-8")


def sync_stock_for_product(
    api: PrestaShopAPI,
    product_id: int,
    attr_to_qty: dict[int, int],
    cached_rows: list[dict[str, Any]] | None = None,
) -> None:
    if cached_rows:
        rows = cached_rows
    else:
        data = api.get_json(
            "stock_availables",
            {"display": "full", "filter[id_product]": str(product_id)},
        )
        rows = data.get("stock_availables", [])

    variant_rows = [r for r in rows if int(r.get("id_product_attribute", 0)) != 0]
    summary_rows = [r for r in rows if int(r.get("id_product_attribute", 0)) == 0]
    total_qty = (
        sum(q for aid, q in attr_to_qty.items() if aid != 0)
        if variant_rows
        else attr_to_qty.get(0, 0)
    )

    for sa in variant_rows + summary_rows:
        sa_id = int(sa["id"])
        attr_id = int(sa.get("id_product_attribute", 0))
        if attr_id == 0:
            target_qty = total_qty
        elif attr_id in attr_to_qty:
            target_qty = attr_to_qty[attr_id]
        else:
            continue

        current_qty = int(sa.get("quantity", -1))
        current_dep = str(sa.get("depends_on_stock", "0"))
        if cached_rows and current_qty == target_qty and current_dep == "0":
            continue

        root = ET.Element("prestashop")
        el = ET.SubElement(root, "stock_available")
        ET.SubElement(el, "id").text = str(sa_id)
        ET.SubElement(el, "id_product").text = str(product_id)
        ET.SubElement(el, "id_product_attribute").text = str(attr_id)
        ET.SubElement(el, "id_shop").text = str(sa.get("id_shop", 1))
        ET.SubElement(el, "id_shop_group").text = str(sa.get("id_shop_group", 0))
        ET.SubElement(el, "quantity").text = str(target_qty)
        ET.SubElement(el, "depends_on_stock").text = "0"
        ET.SubElement(el, "out_of_stock").text = str(sa.get("out_of_stock", 2))
        api.put_xml(f"stock_availables/{sa_id}", ET.tostring(root, encoding="utf-8"))


def run_dry_run(
    records: list[PreparedRecord],
    initial_rejected: int,
    simulate_update: bool,
) -> tuple[int, int, int]:
    total = len(records)
    out_of_stock_products = 0
    all_variant_stocks: list[int] = []
    all_product_totals: list[int] = []

    for rec in records:
        variants = rec.item.get("variants") or []
        labels = [str(v.get("size") or "UNIWERSALNY") for v in variants]
        stocks, _ = compute_variant_stocks(rec.ref, labels)
        prod_total = sum(stocks)
        if prod_total == 0:
            out_of_stock_products += 1
        all_variant_stocks.extend(stocks)
        all_product_totals.append(prod_total)

    pct_zero = (out_of_stock_products / total * 100.0) if total else 0.0
    max_var = max(all_variant_stocks) if all_variant_stocks else 0
    max_prod = max(all_product_totals) if all_product_totals else 0

    logger.info("--- [DRY-RUN] Weryfikacja danych i reguł magazynowych ---")
    logger.info("Poprawne rekordy: %d | Odrzucone na wejściu: %d", total, initial_rejected)
    logger.info(
        "Stany wariantów: 0–%d szt. | Maksymalna suma produktu (id_product_attribute=0): %d szt.",
        max_var,
        max_prod,
    )
    logger.info(
        "Produkty ze stanem 0: %d/%d (%.2f%%) [wymóg W3 5%%–20%%: %s]",
        out_of_stock_products,
        total,
        pct_zero,
        "OK" if 5.0 <= pct_zero <= 20.0 else "BŁĄD",
    )

    if simulate_update:
        return 0, total, initial_rejected
    return total, 0, initial_rejected


def configure_logging(log_file: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Idempotentny import produktów do PrestaShop 8.2 przez Webservice API"
    )
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
        help="Limit liczby produktów do zaimportowania (0 = wszystkie)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Liczba wątków roboczych podczas importu produktów (domyślnie 6)",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=2,
        help="Liczba zdjęć dla wyróżnionych produktów wielozdjęciowych (domyślnie 2)",
    )
    parser.add_argument(
        "--multi-image-count",
        type=int,
        default=60,
        help="Liczba produktów otrzymujących >= 2 zdjęcia (domyślnie 60, wymóg W2/W3 >= 50)",
    )
    parser.add_argument(
        "--featured-count",
        type=int,
        default=12,
        help="Liczba dostępnych produktów przypiętych do Strony głównej (domyślnie 12)",
    )
    parser.add_argument(
        "--clean-demo",
        action="store_true",
        help="Usuń domyślne produkty i kategorie demo PrestaShop przed importem",
    )
    parser.add_argument(
        "--defer-search-index",
        action="store_true",
        help="Wstrzymaj indeksowanie w pętli (gdy init.sh przebudowuje indeks po imporcie)",
    )
    parser.add_argument(
        "--archive-url",
        type=str,
        default="",
        help="URL archiwum zdjęć z GitHub Releases (domyślnie z IMAGES_RELEASE_ARCHIVE_URL)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="Klucz API (domyślnie ze zmiennej środowiskowej PRESTASHOP_API_KEY)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="",
        help="Adres URL sklepu (domyślnie z PRESTASHOP_URL / BASE_URL / PS_DOMAIN)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Opcjonalna ścieżka zapisu logu importu",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Walidacja danych i kalkulacji stanów bez połączenia z API",
    )
    parser.add_argument(
        "--simulate-update",
        action="store_true",
        help="Z --dry-run: symuluje ponowne uruchomienie (Updated)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    default_log = args.log_file or (
        repo_root / "deploy" / "import_api.log" if not args.dry_run else None
    )
    configure_logging(default_log)

    started_at = time.monotonic()
    env = load_env_file(repo_root)

    input_path = args.input if args.input.is_absolute() else (repo_root / args.input)
    if not input_path.exists():
        logger.error("Brak pliku wejściowego: %s", input_path)
        sys.exit(1)

    raw_products = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw_products, list):
        logger.error("Plik %s nie zawiera tablicy JSON produktów.", input_path)
        sys.exit(1)

    if args.limit > 0:
        raw_products = raw_products[: args.limit]

    records, initial_rejected = prepare_records(raw_products)

    if args.dry_run:
        created, updated, rejected = run_dry_run(records, initial_rejected, args.simulate_update)
        elapsed = time.monotonic() - started_at
        print(
            f"Podsumowanie importu: Created={created}, Updated={updated}, Rejected={rejected} "
            f"(czas: {elapsed:.1f}s)."
        )
        return

    api_key = (
        args.api_key or os.environ.get("PRESTASHOP_API_KEY") or env.get("PRESTASHOP_API_KEY", "")
    ).strip()
    if not api_key or api_key.startswith("ChangeMe"):
        logger.error("Brak poprawnego klucza PRESTASHOP_API_KEY w środowisku ani w pliku .env.")
        sys.exit(1)

    base_url = (
        args.base_url
        or os.environ.get("PRESTASHOP_URL")
        or os.environ.get("BASE_URL")
        or env.get("BASE_URL")
        or f"https://{env.get('PS_DOMAIN', 'localhost:8443')}"
    ).strip()

    archive_url = (
        args.archive_url
        or os.environ.get("IMAGES_RELEASE_ARCHIVE_URL")
        or env.get("IMAGES_RELEASE_ARCHIVE_URL")
        or DEFAULT_RELEASE_ARCHIVE_URL
    )

    image_resolver = ImageResolver(
        archive_url=archive_url,
        cache_dir=repo_root / "deploy" / ".images_cache",
        sample_dir=repo_root / "scraper-results" / "images",
    )
    image_resolver.prepare()

    api = PrestaShopAPI(base_url=base_url, api_key=api_key, verify_ssl=False)

    if args.clean_demo:
        keep_cats = {
            sanitize_catalog_text(str(seg), 128).lower()
            for r in records
            for seg in (r.item.get("category_path") or [])
            if str(seg).strip()
        }
        clean_demo_catalog(api, keep_cat_names=keep_cats)

    lang_ids = get_active_languages(api)
    tax_map = find_tax_rule_group_map(api)
    set_configuration_value(api, "PS_JPEG_QUALITY", "72")

    cat_cache, main_cat_ids = sync_categories(api, records, lang_ids)
    if main_cat_ids:
        menu_val = ",".join(f"CAT{cid}" for cid in main_cat_ids)
        set_configuration_value(api, "MOD_BLOCKTOPMENU_ITEMS", menu_val)
        logger.info("Zaktualizowano MOD_BLOCKTOPMENU_ITEMS = %s", menu_val)

    _, size_cache = sync_size_options(api, records, lang_ids)
    feat_map, fval_map = sync_product_features(api, records, lang_ids, workers=args.workers)
    existing_catalog = preload_existing_catalog(api)

    featured_refs: set[str] = set()
    for rec in records:
        if len(featured_refs) >= args.featured_count:
            break
        if not is_product_out_of_stock(rec.ref):
            featured_refs.add(rec.ref)

    logger.info(
        "Start fazy produktów: rekordów=%d | istniejących=%d | języki=%s | wątki=%d",
        len(records),
        len(existing_catalog),
        lang_ids,
        args.workers,
    )

    prev_search_idx: str | None = None
    if args.defer_search_index:
        prev_search_idx = set_configuration_value(api, "PS_SEARCH_INDEXATION", "0")

    def _process_record(rec: PreparedRecord) -> tuple[str, int, str]:
        item = rec.item
        raw_path = item.get("category_path") or ["Odzież damska", "Kolekcja"]
        clean_path = [sanitize_catalog_text(str(seg), 128) for seg in raw_path if str(seg).strip()]
        if not clean_path:
            clean_path = ["Odzież damska", "Kolekcja"]

        parent_id = 2
        cat_ids: list[int] = []
        for seg in clean_path:
            cid = cat_cache[(parent_id, seg.lower())]
            cat_ids.append(cid)
            parent_id = cid
        default_cat_id = cat_ids[-1]

        vat_rate = int(float(item.get("vat_rate") or 23))
        tax_group_id = tax_map.get(vat_rate, tax_map[23])

        feature_pairs: list[tuple[int, int]] = []
        seen_feat_ids: set[int] = set()
        attrs = item.get("attributes") or {}
        if isinstance(attrs, dict):
            for raw_k, raw_v in attrs.items():
                clean_k = sanitize_catalog_text(str(raw_k), 128).lower()
                clean_v = sanitize_catalog_text(str(raw_v), 250).lower()
                fid = feat_map.get(clean_k)
                fvid = fval_map.get((fid, clean_v)) if fid else None
                if fid and fvid and fid not in seen_feat_ids:
                    seen_feat_ids.add(fid)
                    feature_pairs.append((fid, fvid))

        existing_info = existing_catalog.get(rec.ref)
        is_existing = existing_info is not None
        featured = rec.ref in featured_refs

        if existing_info is not None:
            pid = existing_info.product_id
            xml_body = build_product_xml(
                rec=rec,
                cat_ids=cat_ids,
                default_cat_id=default_cat_id,
                tax_group_id=tax_group_id,
                lang_ids=lang_ids,
                feature_pairs=feature_pairs,
                featured=featured,
                product_id=pid,
                default_image_id=existing_info.default_image_id,
                default_combination_id=existing_info.default_combination_id,
            )
            api.put_xml(f"products/{pid}", xml_body)
            existing_combs = existing_info.combinations
        else:
            xml_body = build_product_xml(
                rec=rec,
                cat_ids=cat_ids,
                default_cat_id=default_cat_id,
                tax_group_id=tax_group_id,
                lang_ids=lang_ids,
                feature_pairs=feature_pairs,
                featured=featured,
            )
            pid = 0
            for post_attempt in range(1, 4):
                try:
                    resp = api.post_xml("products", xml_body)
                    pid = int(resp.findtext("./product/id") or 0)
                    break
                except RuntimeError:
                    time.sleep(0.3 * post_attempt)
                    probe = api.get_json(
                        "products",
                        {"display": "[id,reference]", "filter[reference]": f"[{rec.ref}]"},
                    )
                    found = probe.get("products", [])
                    if found:
                        pid = int(found[0]["id"])
                        upd_xml = build_product_xml(
                            rec=rec,
                            cat_ids=cat_ids,
                            default_cat_id=default_cat_id,
                            tax_group_id=tax_group_id,
                            lang_ids=lang_ids,
                            feature_pairs=feature_pairs,
                            featured=featured,
                            product_id=pid,
                        )
                        api.put_xml(f"products/{pid}", upd_xml)
                        break
                    if post_attempt == 3:
                        raise
            if pid <= 0:
                raise RuntimeError("API nie zwróciło poprawnego ID nowego produktu.")
            existing_combs = {}

        variants = item.get("variants") or []
        size_labels = [
            sanitize_catalog_text(str(v.get("size") or "UNIWERSALNY"), 64) for v in variants
        ]
        stocks, default_idx = compute_variant_stocks(rec.ref, size_labels)
        attr_to_qty: dict[int, int] = {}
        created_new_comb = False

        if variants:
            base_gross = float(item["price_gross"])
            base_weight = float(item.get("weight_kg") or 0.5)
            vat_mult = 1.0 + float(item.get("vat_rate") or 23.0) / 100.0

            ordered_indices = sorted(
                range(len(variants)), key=lambda idx_: 1 if idx_ == default_idx else 0
            )
            for v_idx in ordered_indices:
                var = variants[v_idx]
                lbl = size_labels[v_idx]
                comb_ref = f"{rec.ref}-{lbl}"[:64]
                opt_val_id = size_cache[lbl.upper()]
                is_def = v_idx == default_idx
                var_gross = float(var.get("price_gross") or base_gross)
                var_weight = float(var.get("weight_kg") or base_weight)
                price_impact = round((var_gross - base_gross) / vat_mult, 6)
                weight_impact = round(var_weight - base_weight, 6)

                if comb_ref in existing_combs:
                    comb_id, was_def = existing_combs[comb_ref]
                    if was_def != is_def or abs(price_impact) > 1e-5 or abs(weight_impact) > 1e-5:
                        c_xml = build_combination_xml(
                            product_id=pid,
                            comb_ref=comb_ref,
                            option_value_id=opt_val_id,
                            is_default=is_def,
                            price_impact_net=price_impact,
                            weight_impact=weight_impact,
                            comb_id=comb_id,
                        )
                        api.put_xml(f"combinations/{comb_id}", c_xml)
                else:
                    c_xml = build_combination_xml(
                        product_id=pid,
                        comb_ref=comb_ref,
                        option_value_id=opt_val_id,
                        is_default=is_def,
                        price_impact_net=price_impact,
                        weight_impact=weight_impact,
                    )
                    comb_id = 0
                    for c_attempt in range(1, 4):
                        try:
                            c_resp = api.post_xml("combinations", c_xml)
                            comb_id = int(c_resp.findtext("./combination/id") or 0)
                            break
                        except RuntimeError:
                            time.sleep(0.25 * c_attempt)
                            c_probe = api.get_json(
                                "combinations",
                                {
                                    "display": "[id,reference]",
                                    "filter[id_product]": str(pid),
                                    "filter[reference]": f"[{comb_ref}]",
                                },
                            )
                            c_found = c_probe.get("combinations", [])
                            if c_found:
                                comb_id = int(c_found[0]["id"])
                                break
                            if c_attempt == 3:
                                raise
                    created_new_comb = True

                attr_to_qty[comb_id] = stocks[v_idx]
        else:
            attr_to_qty[0] = stocks[0]

        cached_sa = (
            existing_info.stock_rows
            if (existing_info is not None and not created_new_comb and existing_info.stock_rows)
            else None
        )
        sync_stock_for_product(api, pid, attr_to_qty, cached_rows=cached_sa)

        image_urls = [str(u) for u in (item.get("image_urls") or []) if str(u).strip()]
        desired_imgs = min(
            len(image_urls),
            args.max_images if rec.index <= args.multi_image_count else 1,
        )
        current_imgs = existing_info.image_count if existing_info is not None else 0

        if current_imgs < desired_imgs:
            for img_pos in range(current_imgs + 1, desired_imgs + 1):
                img_url = image_urls[img_pos - 1]
                img_bytes = image_resolver.get_image_bytes(
                    ref=rec.ref,
                    external_id=rec.external_id,
                    archive_prefix=rec.archive_prefix,
                    is_primary_ext_id=rec.is_primary_ext_id,
                    img_index_1based=img_pos,
                    url=img_url,
                )
                if img_bytes:
                    api.upload_product_image(pid, img_bytes, f"{rec.ref}_{img_pos}.jpg")
                elif img_pos == 1 and current_imgs == 0:
                    raise RuntimeError(f"Brak możliwości pobrania zdjęcia głównego ({img_url}).")

        return ("UPDATED" if is_existing else "CREATED"), pid, rec.ref

    created = 0
    updated = 0
    rejected = initial_rejected

    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            future_to_rec = {pool.submit(_process_record, rec): rec for rec in records}
            completed = 0
            total_recs = len(records)
            for fut in as_completed(future_to_rec):
                rec = future_to_rec[fut]
                completed += 1
                try:
                    status_str, pid, ref = fut.result()
                    if status_str == "UPDATED":
                        updated += 1
                    else:
                        created += 1
                    if completed % 25 == 0 or completed == total_recs or completed <= 5:
                        logger.info(
                            "[%d/%d] %s id=%d ref=%s (%s)",
                            completed,
                            total_recs,
                            status_str,
                            pid,
                            ref,
                            str(rec.item.get("name", ""))[:42],
                        )
                except Exception as exc:
                    rejected += 1
                    logger.error(
                        "[%d/%d] REJECTED ref=%s (%s): %s",
                        completed,
                        total_recs,
                        rec.ref,
                        str(rec.item.get("name", ""))[:40],
                        exc,
                    )
    finally:
        if args.defer_search_index and prev_search_idx is not None:
            try:
                set_configuration_value(api, "PS_SEARCH_INDEXATION", prev_search_idx or "1")
            except Exception as exc:
                logger.warning("Nie udało się przywrócić PS_SEARCH_INDEXATION: %s", exc)

    elapsed = time.monotonic() - started_at
    summary = (
        f"Podsumowanie importu: Created={created}, Updated={updated}, Rejected={rejected} "
        f"(czas: {elapsed:.1f}s)."
    )
    logger.info(summary)
    print(summary)


if __name__ == "__main__":
    main()
