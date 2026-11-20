# ADR-002: Zmiana sklepu źródłowego na `mosquito-sklep.pl`

* **Status:** Zaakceptowano
* **Data:** 2026-11-10

## Kontekst
Pierwotnie wybrany sklep (`dywanyluszczow.eu`) uniemożliwiał skuteczne i stabilne scrapowanie danych ze względu na blokady antybotowe oraz skomplikowaną logikę cen zależnych od dynamicznie przeliczanych wymiarów dywanów. Z kolei rozważany sklep `chruscinska.pl` posiadał jedynie ok. 429–465 produktów, co stwarzało ryzyko niespełnienia krytycznego wymagania metryki **W3** ($\ge 1000$ produktów w panelu administracyjnym). Zespół potrzebował sklepu źródłowego bez blokad Cloudflare, o asortymencie odzieżowym z wariantami rozmiarowymi (nie wpływającymi na zmianę ceny podstawowej), bogatym drzewie kategorii i odpowiedniej liczbie produktów.

## Rozważane opcje
1. **Pozostanie przy pierwotnym sklepie z dywanami (`dywanyluszczow.eu`)** – konieczność używania ciężkich przeglądarek (Playwright/Selenium) do omijania zabezpieczeń, bardzo wysokie ryzyko timeoutów i niestabilności scrapera.
2. **Przejście na `chruscinska.pl`** – sklep oparty o PrestaShop, ale posiadający tylko ~465 produktów, co wymagałoby sztucznej multiplikacji danych w celu spełnienia progu 1000 produktów.
3. **Przejście na `topsecret.pl`** – duża polska sieć odzieżowa, brak Cloudflare, jednak sitemap zawierał jedynie 937 produktów (balansowanie na krawędzi limitu 1000 produktów) oraz autorski silnik e-commerce.
4. **Wybór `mosquito-sklep.pl`** – duży, polski sklep z modą damską działający na **PrestaShop 8**, bez barier Cloudflare, posiadający 6 609 produktów w oficjalnej sitemapie XML, przejrzystą strukturę JSON-LD oraz warianty rozmiarowe (XS, S, M, L, XL), które nie modyfikują ceny bazowej.

## Decyzja
Wybrano **Opcję 4 (`mosquito-sklep.pl`)**.

## Konsekwencje
* **Pozytywne:** Pełna zgodność architektury sklepu źródłowego z docelowym środowiskiem PrestaShop 8 (ta sama struktura danych, kategorii, breadcrumbs i wariantów).
* **Pozytywne:** Ponad 6 600 dostępnych produktów pozwala na elastyczne i bezproblemowe zebranie wymaganych 1 000 produktów z zapasem, spełniając warunek krytyczny **W3 [K]**.
* **Pozytywne:** Brak zmian ceny w zależności od rozmiaru odzieży drastycznie upraszcza strukturę wariantów (`ProductVariant`) oraz import kombinacji do bazy danych.
* **Pozytywne:** Natywne linki do zdjęć wysokiej rozdzielczości (`tm_large_default.jpg`) w JSON-LD ułatwiają spełnienie wymagań wymiarów (800–1600 px) i kompresji ($\le 300\text{ KB}$).
* **Negatywne / Koszt:** Konieczność modyfikacji motywu potomnego PrestaShop (zamiast motywu dywanowego, stworzenie estetycznego motywu i banerów z modą damską).
