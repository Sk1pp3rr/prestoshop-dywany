# Katalog `shop/` – Kod Źródłowy Sklepu PrestaShop 8.2.x (`W3`, `D1`, `D3`)

## Przeznaczenie katalogu
Ten katalog zawiera obraz kontenerowy sklepu, dostosowania wyglądu (motyw potomny) oraz moduły własne rozszerzające funkcjonalność **PrestaShop 8.2.x** pod sklep z dywanami i pokryciami podłogowymi (`dywanyluszczow.eu`).

---

## Docelowa zawartość i struktura plików

```text
shop/
├── Dockerfile                      # Definicja obrazu PrestaShop 8.2.x (PHP 8.1, linux/amd64)
├── config/                         # Dodatkowe pliki konfiguracyjne PHP (np. php.ini - limity uploadu)
├── themes/
│   └── classic-dywany/             # Motyw potomny (Child Theme) dziedziczący po 'classic' (D1)
│       ├── config/
│       │   └── theme.yml           # Konfiguracja motywu potomnego (parent: classic)
│       ├── assets/
│       │   ├── css/custom.css      # Style własne (responsywność 360px, kontrast WCAG >= 85)
│       │   └── img/                # Banery tematyczne (dywany) i grafiki motywu
│       └── templates/              # Nadpisane szablony Smarty (.tpl), np. stopka, karta produktu
└── modules/
    └── ps_omnibusprice/            # Moduł wyświetlający najniższą cenę z 30 dni przed obniżką (D3)
```

---

## Kluczowe wymagania realizowane w tym katalogu

1. **Obraz Docker (`W3` [K]):**
   * Bazuje na oficjalnym obrazie `prestashop/prestashop:8.2-apache` (PHP 8.1).
   * Budowany obowiązkowo dla architektury **`linux/amd64`** (wymóg pod klaster Docker Swarm w Etapie 2).
2. **Wygląd sklepu – Child Theme (`D1` – 5 pkt):**
   * Wszystkie modyfikacje wizualne muszą być realizowane w motywie potomnym (`themes/classic-dywany/`), **nie wolno edytować bezpośrednio plików bazowego motywu `classic`**.
   * Na stronie głównej musi znajdować się co najmniej jeden działający baner w tematyce dywanów/wykładzin.
   * Poprawne wyświetlanie na ekranie telefonu o szerokości **360 px** oraz wynik **Lighthouse Accessibility $\ge 85$** i **Performance $\ge 60$**.
3. **Dyrektywa Omnibus i Promocje (`D3` – 3 pkt):**
   * W katalogu `modules/` umieszczamy moduł odpowiedzialny za prezentację informacji o najniższej cenie z 30 dni przed wprowadzeniem obniżki na karcie produktu objętego promocją.

---

## Czego NIE umieszczać w tym katalogu (wykluczone w `.gitignore`)
* Katalogów generowanych w runtime przez PrestaShop: `var/cache/`, `var/logs/`, `img/p/` (zdjęcia produktów), `upload/`, `download/`.
* Pliku `app/config/parameters.php` zawierającego hasła i klucze kryptograficzne instancji.
