"""Moduł pobierania stron i sitemapy z zachowaniem kultury pracy (Wymaganie W2)."""

import logging
import re
import time
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "MosquitoScraperBot/1.0 (+student project PG; Politechnika Gdanska)"


class MosquitoCrawler:
    """Klient HTTP odpowiedzialny za pobieranie stron zgodnie z robots.txt i limitem <= 2 req/s."""

    def __init__(
        self,
        base_url: str = "https://mosquito-sklep.pl",
        delay_seconds: float = 0.55,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.delay_seconds = max(delay_seconds, 0.5)  # Gwarancja <= 2 req/s
        self.user_agent = user_agent
        self.last_request_time: float = 0.0

        self.client = httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=15.0,
            follow_redirects=True,
        )

        self.robot_parser = RobotFileParser()
        self._load_robots_txt()

    def _load_robots_txt(self) -> None:
        """Pobiera i parsuje plik robots.txt sklepu."""
        robots_url = f"{self.base_url}/robots.txt"
        try:
            resp = self.client.get(robots_url)
            if resp.status_code == 200:
                self.robot_parser.parse(resp.text.splitlines())
                logger.info("Plik robots.txt został pomyślnie załadowany.")
            else:
                logger.warning(
                    f"Nie udało się pobrać robots.txt (status {resp.status_code}). Zezwalam."
                )
                self.robot_parser.allow_all = True
        except Exception as e:
            logger.warning(f"Błąd podczas pobierania robots.txt: {e}. Zezwalam na ruch.")
            self.robot_parser.allow_all = True

    def can_fetch(self, url: str) -> bool:
        """Sprawdza, czy robots.txt zezwala na pobranie danego URL."""
        return self.robot_parser.can_fetch(self.user_agent, url)

    def _wait_rate_limit(self) -> None:
        """Zapewnia odstęp czasu gwarantujący maksymalnie 2 zapytania na sekundę."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self.last_request_time = time.time()

    def fetch_page(self, url: str) -> str | None:
        """Pobiera zawartość strony HTML z obsługą limitu zapytań i błędów sieciowych."""
        if not self.can_fetch(url):
            logger.warning(f"URL zablokowany przez robots.txt: {url}")
            return None

        self._wait_rate_limit()

        try:
            resp = self.client.get(url)
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"Błąd HTTP {resp.status_code} dla {url}")
            return None
        except Exception as e:
            logger.error(f"Wyjątek podczas pobierania {url}: {e}")
            return None

    def fetch_image_bytes(self, image_url: str) -> bytes | None:
        """Pobiera surowe bajty zdjęcia ze sklepu źródłowego."""
        self._wait_rate_limit()
        try:
            resp = self.client.get(image_url)
            if resp.status_code == 200:
                return resp.content
            logger.warning(f"Błąd HTTP {resp.status_code} dla zdjęcia {image_url}")
            return None
        except Exception as e:
            logger.error(f"Błąd pobierania zdjęcia {image_url}: {e}")
            return None

    def fetch_product_urls_from_sitemap(
        self, sitemap_url: str | None = None, limit: int | None = None
    ) -> list[str]:
        """Pobiera listę unikalnych adresów produktów z oficjalnej sitemapy sklepu."""
        if not sitemap_url:
            sitemap_url = f"{self.base_url}/1_pl_0_sitemap.xml"

        logger.info(f"Pobieranie sitemapy: {sitemap_url}")
        self._wait_rate_limit()

        try:
            resp = self.client.get(sitemap_url)
            if resp.status_code != 200:
                logger.error(f"Błąd pobierania sitemapy: status {resp.status_code}")
                return []

            content = resp.text.replace("<![CDATA[", "").replace("]]>", "")
            locs = re.findall(r"<loc>(.*?)</loc>", content)

            # Filtrujemy tylko adresy produktów (.html z identyfikatorem cyfrowym)
            product_urls = [
                u.strip()
                for u in locs
                if u.strip().endswith(".html")
                and re.search(r"/\d+-[a-zA-Z0-9-]+\.html$", u)
                and "test" not in u.lower()
            ]

            # Odwracamy listę, aby pobierać najnowsze produkty z aktualnych kolekcji
            product_urls.reverse()

            # Usuwamy duplikaty z zachowaniem kolejności
            unique_urls: list[str] = []
            seen: set[str] = set()
            for u in product_urls:
                if u not in seen:
                    seen.add(u)
                    unique_urls.append(u)

            logger.info(f"Znaleziono {len(unique_urls)} produktów w sitemapie.")
            if limit and limit > 0:
                return unique_urls[:limit]
            return unique_urls
        except Exception as e:
            logger.error(f"Błąd parsowania sitemapy {sitemap_url}: {e}")
            return []

    def close(self) -> None:
        """Zamyka klienta HTTP."""
        self.client.close()
