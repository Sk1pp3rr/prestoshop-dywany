# Katalog `tests/` – Testy End-to-End (E2E) w Playwright (`W4`)

## Przeznaczenie katalogu
Zawiera automatyczne testy przeglądarkowe E2E napisane w **Playwright**, które weryfikują pełną ścieżkę zakupową klienta w sklepie PrestaShop 8.2.x w trybie `headless`.

---

## Docelowa zawartość i struktura plików

```text
tests/
├── package.json                    # Zależności (@playwright/test) oraz skrypt uruchomieniowy
├── playwright.config.ts            # Konfiguracja: BASE_URL z env, headless: true, raporty HTML/JUnit, screenshoty
├── e2e/
│   └── full-shopping-flow.spec.ts  # Pełny 10-krokowy scenariusz testowy (W4)
└── helpers/
    └── shop-actions.ts             # Funkcje pomocnicze (wyszukiwanie, obsługa koszyka, rejestracja)
```

---

## Obowiązkowy scenariusz 10 kroków (`W4` – 5 pkt)

Skrypt testowy musi wykonać w całości w czasie **$\le 5\text{ minut}$** (ze stabilnością **3/3 uruchomień**) następujące kroki:

1. **Dodanie do koszyka 10 produktów** w różnych ilościach, pochodzących z co najmniej **dwóch różnych kategorii** (z uwagą, by łączna waga koszyka nie przekroczyła limitu 50 kg).
2. **Wyszukanie produktu po nazwie** (np. `dywan` lub `chodnik`) za pomocą wyszukiwarki sklepowej i dodanie do koszyka **losowego dostępnego produktu** spośród wyników.
3. **Usunięcie z koszyka 3 produktów** (wraz z asercją sprawdzającą przeliczenie zawartości koszyka).
4. **Rejestracja nowego konta klienta** (z unikalnym adresem e-mail).
5. **Rozpoczęcie składania zamówienia** na zawartość koszyka (uzupełnienie/potwierdzenie adresu dostawy w Polsce).
6. **Wybór jednego z dwóch nowych przewoźników** zdefiniowanych w sklepie.
7. **Wybór metody płatności przy odbiorze** (*Cash on delivery*).
8. **Zatwierdzenie zamówienia** (akceptacja regulaminu i finalizacja zakupu).
9. **Sprawdzenie statusu zamówienia** w panelu klienta / historii zamówień.
10. **Pobranie faktury VAT (PDF)** i asercja weryfikująca poprawne pobranie pliku.

---

## Wymagania techniczne dla testów (`W4` [K])
* **Jedna komenda startowa** przyjmująca adres sklepu przez zmienną środowiskową `BASE_URL` (w Etapie 2 te same testy będą uruchamiane na klastrze Docker Swarm):
  ```bash
  BASE_URL=https://localhost:8443 npx playwright test
  ```
* **Asercje po każdym kroku:** każdy z 10 kroków musi zawierać asercję (`expect(...)`) weryfikującą rzeczywisty efekt akcji w interfejsie lub odpowiedzi serwera, a nie samo kliknięcie.
* **Synchronizacja:** zakaz używania sztywnych opóźnień typu `sleep` / `waitForTimeout` jako głównego mechanizmu synchronizacji – korzystamy z auto-waitingu Playwrighta i asercji web-first.
* **Raportowanie:** automatyczne generowanie raportu (**HTML** oraz **JUnit XML**) i zapisywanie zrzutu ekranu (`screenshot: 'only-on-failure'`) w przypadku błędu.
* **Ignorowanie certyfikatu self-signed:** w `playwright.config.ts` ustawione `ignoreHTTPSErrors: true`.
