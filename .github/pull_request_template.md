## Cel zmian i powiązane zadanie (Issue)
- Zamyka: #
- Krótki opis zmian:

## Checklist przed scaleniem do `main` (W1, D5, D6)
- [ ] Kod jest zgodny z docelową strukturą katalogów (`shop/`, `scraper/`, `scraper-results/`, `tests/`, `deploy/`, `docs/`).
- [ ] Brak zahardkodowanych haseł, kluczy API i plików `.env` w commicie (`gitleaks` przechodzi na zielono).
- [ ] Pipeline CI (`repo-guard` oraz `scraper-ci` - `ruff` + `pytest`) zakończył się sukcesem.
- [ ] Jeśli korzystano z narzędzi AI: dodano etykietę `ai-assisted` do PR oraz uzupełniono wpis w `docs/AI_LOG.md`.

## Weryfikacja (szczególnie dla PR z etykietą `ai-assisted`)
- Jak przetestowano zmiany (np. uruchomienie testów jednostkowych, ręczne sprawdzenie kontenerów):
