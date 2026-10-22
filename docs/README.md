# Katalog `docs/` – Dokumentacja, Dziennik AI i Decyzje Architektoniczne (`W1`, `D6`)

## Przeznaczenie katalogu
Gromadzi dokumentację projektową wymaganą w Etapie 1: dziennik wykorzystania narzędzi sztucznej inteligencji (`AI_LOG.md`), rejestr decyzji architektonicznych (`adr/`) oraz dodatkowe instrukcje techniczne dla zespołu i prowadzącego.

---

## Docelowa zawartość i struktura plików

```text
docs/
├── AI_LOG.md                                       # Obowiązkowy dziennik użycia AI + refleksja zespołu (D6)
└── adr/                                            # Architecture Decision Records (minimum 3 wpisy) (D6)
    ├── README.md                                   # Spis i szablon decyzji architektonicznych (ADR)
    ├── 001-repo-structure-and-ci.md                # ADR-001: Struktura repozytorium i potok GitHub Actions CI
    ├── 002-scraper-and-image-storage.md            # ADR-002: Wybór narzędzi scrapera i publikacja zdjęć w Releases
    └── 003-containers-ssl-and-data-init.md         # ADR-003: Architektura kontenerów, HTTPS i inicjalizacja danych
```

---

## Kluczowe zasady prowadzenia dokumentacji (`D6` – 3 pkt)

1. **Dziennik AI ([`AI_LOG.md`](AI_LOG.md)):**
   * Każda osoba korzystająca z narzędzi AI (ChatGPT, Claude, Copilot, Antigravity itp.) dodaje wpis do tabeli **w tym samym Pull Requeście**, w którym znajduje się wygenerowany kod, oraz oznacza PR etykietą `ai-assisted`.
   * Wymagane jest **minimum 2 wpisy na każdego członka zespołu** w trakcie trwania etapu.
   * Na końcu pliku znajduje się **refleksja zespołu (do 1 strony)**: gdzie AI realnie przyspieszyło pracę, gdzie wprowadziło w błąd i czego zespół musiał nauczyć się samodzielnie.
2. **Decyzje Architektoniczne (`docs/adr/`):**
   * Wymagane są **co najmniej 3 dokumenty ADR**.
   * Każdy dokument ADR musi zawierać cztery sekcje:
     1. **Kontekst** (jaki problem projektowy lub ograniczenie rozwiązujemy),
     2. **Rozważane opcje** (jakie alternatywy braliśmy pod uwagę),
     3. **Decyzja** (którą opcję wybraliśmy i dlaczego),
     4. **Konsekwencje** (plusy, minusy i wpływ m.in. na Etap 2 – Docker Swarm).
