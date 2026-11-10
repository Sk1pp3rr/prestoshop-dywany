"""Główny punkt wejścia CLI scrapera z obsługą wznawiania (Wymaganie W2)."""

import argparse
import json
import logging
import signal
import sys
from pathlib import Path

from mosquito_scraper.crawler import MosquitoCrawler
from mosquito_scraper.image_processor import process_image
from mosquito_scraper.parser import parse_product_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("mosquito_scraper")


class ScraperApp:
    def __init__(
        self,
        output_file: Path,
        images_dir: Path,
        state_file: Path,
        errors_file: Path,
        limit: int = 1000,
        sample_images_limit: int = 20,
    ) -> None:
        self.output_file = output_file
        self.images_dir = images_dir
        self.state_file = state_file
        self.errors_file = errors_file
        self.limit = limit
        self.sample_images_limit = sample_images_limit

        self.crawler = MosquitoCrawler()
        self.stop_requested = False
        self.scraped_products: list[dict] = []
        self.scraped_urls: set[str] = set()
        self.saved_images_count = 0

        # Obsługa sygnałów przerwania (Ctrl+C)
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

        self._load_state()

    def _handle_interrupt(self, signum, frame) -> None:  # noqa: ANN001
        logger.warning("\nOtrzymano sygnał przerwania. Bezpieczne zapisywanie stanu...")
        self.stop_requested = True

    def _load_state(self) -> None:
        """Wczytuje stan i już zapisane produkty w celu wznowienia pracy."""
        if self.state_file.exists():
            try:
                state_data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.scraped_urls = set(state_data.get("scraped_urls", []))
                self.saved_images_count = state_data.get("saved_images_count", 0)
                logger.info(
                    f"Wznowiono ze stanu: {len(self.scraped_urls)} przetworzonych URL-i, "
                    f"{self.saved_images_count} zapisanych zdjęć."
                )
            except Exception as e:
                logger.warning(f"Nie udało się wczytać pliku stanu: {e}")

        if self.output_file.exists():
            try:
                self.scraped_products = json.loads(self.output_file.read_text(encoding="utf-8"))
                logger.info(f"Wczytano {len(self.scraped_products)} produktów z pliku wyjściowego.")
            except Exception as e:
                logger.warning(f"Nie udało się wczytać istniejących wyników: {e}")

    def _save_state(self) -> None:
        """Zapisuje bieżący stan scrapera oraz produkty do pliku JSON."""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(
            json.dumps(self.scraped_products, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        state_data = {
            "scraped_urls": list(self.scraped_urls),
            "saved_images_count": self.saved_images_count,
            "total_products": len(self.scraped_products),
        }
        self.state_file.write_text(
            json.dumps(state_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def log_error(self, url: str, error_msg: str) -> None:
        """Zapisuje błąd do logu błędów."""
        self.errors_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.errors_file, "a", encoding="utf-8") as f:
            f.write(f"[{url}] {error_msg}\n")

    def run(self) -> None:
        """Główna pętla zbierania danych."""
        logger.info(f"Rozpoczynanie scrapowania mosquito-sklep.pl (cel: {self.limit} produktów)...")

        # 1. Pobieramy listę URL-i z sitemapy
        all_urls = self.crawler.fetch_product_urls_from_sitemap()
        if not all_urls:
            logger.error("Nie udało się pobrać adresów produktów z sitemapy.")
            return

        urls_to_scrape = [u for u in all_urls if u not in self.scraped_urls]
        logger.info(
            f"Łącznie produktów w sitemapie: {len(all_urls)}. Do pobrania: {len(urls_to_scrape)}."
        )

        try:
            for url in urls_to_scrape:
                if self.stop_requested or len(self.scraped_products) >= self.limit:
                    break

                logger.info(f"[{len(self.scraped_products) + 1}/{self.limit}] Pobieranie: {url}")
                html = self.crawler.fetch_page(url)
                if not html:
                    self.log_error(url, "Pusta odpowiedź lub błąd pobierania strony")
                    self.scraped_urls.add(url)
                    continue

                product = parse_product_page(html, url=url)
                if not product:
                    self.log_error(url, "Błąd parsowania produktu lub brak wymaganych pól")
                    self.scraped_urls.add(url)
                    continue

                # Walidacja pydantic już zaszła w parse_product_page, serializujemy
                product_dict = product.model_dump(mode="json")

                # Pobieranie przykładowych zdjęć (do limitu 20 w repozytorium)
                if self.saved_images_count < self.sample_images_limit and product.image_urls:
                    img_url = str(product.image_urls[0])
                    img_filename = f"{product.external_id}_1.jpg"
                    img_target = self.images_dir / img_filename
                    if not img_target.exists():
                        img_bytes = self.crawler.fetch_image_bytes(img_url)
                        if img_bytes and process_image(img_bytes, img_target):
                            self.saved_images_count += 1
                            logger.info(
                                f"Zapisano przykładowe zdjęcie ({self.saved_images_count}/"
                                f"{self.sample_images_limit}): {img_target.name}"
                            )

                self.scraped_products.append(product_dict)
                self.scraped_urls.add(url)

                # Zapis stanu co 10 produktów
                if len(self.scraped_products) % 10 == 0:
                    self._save_state()

        finally:
            self._save_state()
            self.crawler.close()
            logger.info(
                f"Zakończono. Zebrano {len(self.scraped_products)} produktów. "
                f"Zapisano w {self.output_file}."
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper dla sklepu mosquito-sklep.pl")
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Liczba produktów do zebrania (domyślnie 1000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../scraper-results/products.json"),
        help="Ścieżka do pliku wynikowego JSON",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=Path("../scraper-results/images"),
        help="Ścieżka do katalogu z przykładowymi zdjęciami (max 20)",
    )
    parser.add_argument(
        "--sample-images",
        type=int,
        default=20,
        help="Maksymalna liczba przykładowych zdjęć w repozytorium (domyślnie 20)",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(".scraper_state.json"),
        help="Ścieżka do pliku checkpoint",
    )
    parser.add_argument(
        "--errors-file",
        type=Path,
        default=Path("scraper_errors.log"),
        help="Ścieżka do pliku logu błędów",
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help="Rozpocznij scrapowanie od nowa (ignoruje poprzedni stan)",
    )

    args = parser.parse_args()

    if args.clean:
        if args.state_file.exists():
            args.state_file.unlink()
        if args.output_file.exists():
            args.output_file.unlink()

    app = ScraperApp(
        output_file=args.output,
        images_dir=args.images_dir,
        state_file=args.state_file,
        errors_file=args.errors_file,
        limit=args.limit,
        sample_images_limit=args.sample_images,
    )
    app.run()


if __name__ == "__main__":
    main()
