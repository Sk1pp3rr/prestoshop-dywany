# Katalog `scraper-results/` – Wyniki Scrapowania i Przykładowe Zdjęcia (`W2`, `W1`)

## Przeznaczenie katalogu
Przechowuje ustrukturyzowane, zwalidowane dane wyjściowe ze scrapera (w kodowaniu **UTF-8**) gotowe do zaimportowania do sklepu PrestaShop 8.2.x, a także próbkę maksymalnie **20 zdjęć produktów**.

---

## Docelowa zawartość i struktura plików

```text
scraper-results/
├── products.json                   # Lista >= 1000 zwalidowanych produktów (UTF-8) z URL-ami źródłowymi zdjęć
└── images/                  # Maksymalnie 20 przykładowych zdjęć po przeskalowaniu (800-1600 px, <= 300 KB)
```

---

## Kluczowe zasady i ograniczenia (`W1`, `W2`)

1. **Kompletność danych (`W2` [K]):**
   * Pliki `products.json` muszą być zapisane w kodowaniu **UTF-8** z poprawnymi polskimi znakami.
   * **0 produktów** bez nazwy, ceny, opisu lub adresów zdjęć.
   * Każdy produkt posiada adresy źródłowe zdjęć (`image_urls`) oraz ścieżkę przypisania do pliku z archiwum zdjęć.
2. **Zakaz przechowywania pełnego zbioru zdjęć w Git (`W1`, `W2`):**
   * W tym katalogu w repozytorium może znajdować się **co najwyżej 20 przykładowych zdjęć** (pilnuje tego automatycznie job `repo-guard` w `.github/workflows/ci.yml`).
   * Pełny zbiór zdjęć ($\ge 1000$ produktów + $\ge 50$ z min. 2 zdjęciami) jest pakowany do jednego archiwum (`images.tar.gz` lub `images.zip`, do 1 GB) i publikowany w zakładce **GitHub Releases**.
   * Skrypt inicjalizacji w `deploy/` pobiera to archiwum z GitHub Releases (lub w razie niedostępności pobiera zdjęcia bezpośrednio z adresów źródłowych zapisanych w `products.json`).
