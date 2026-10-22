# Architecture Decision Records (`docs/adr/`) – Wymaganie D6

W tym katalogu przechowujemy zapisy kluczowych decyzji architektonicznych podjętych przez zespół podczas realizacji projektu sklepu PrestaShop 8.2.x (`dywanyluszczow.eu`).

## Wymagania (`D6`)
* Minimum **3 zapisy ADR** w repozytorium.
* Każdy dokument musi zawierać sekcje: **Kontekst**, **Rozważane opcje**, **Decyzja** oraz **Konsekwencje**.

## Lista decyzji architektonicznych
1. [ADR-001: Struktura repozytorium, ochrona gałęzi `main` oraz potok CI (GitHub Actions)](001-repo-structure-and-ci.md)
2. `002-scraper-and-image-storage.md` *(planowany: wybór bibliotek Python/Pydantic/Pillow oraz przechowywanie pełnego zbioru zdjęć w GitHub Releases)*
3. `003-containers-ssl-and-data-init.md` *(planowany: architektura Docker Compose `linux/amd64`, terminacja SSL i strategia inicjalizacji danych oraz importu przez Webservice API)*

---

## Szablon nowego wpisu ADR

```markdown
# ADR-00X: [Tytuł decyzji]

* **Status:** Zaakceptowano
* **Data:** RRRR-MM-DD

## Kontekst
[Opis problemu, wymagań projektowych (np. W2/W3/Etap 2 Swarm) oraz ograniczeń technicznych.]

## Rozważane opcje
1. **Opcja 1:** [Krótki opis i charakterystyka]
2. **Opcja 2:** [Krótki opis i charakterystyka]

## Decyzja
[Wskazanie wybranej opcji wraz z uzasadnieniem.]

## Konsekwencje
* **Pozytywne:** [Korzyści wynikające z decyzji]
* **Negatywne / Koszt:** [Kompromisy, na które godzi się zespół]
```
