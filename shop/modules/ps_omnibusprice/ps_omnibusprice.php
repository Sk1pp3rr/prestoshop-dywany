<?php
/**
 * Moduł PrestaShop 8.2: Dyrektywa Omnibus – najniższa cena z 30 dni przed obniżką (Wymaganie D3).
 *
 * Rejestruje historię zmian cen produktów i wariantów w tabeli ps_omnibusprice_history
 * oraz wyświetla najniższą cenę z 30 dni przed wprowadzeniem aktualnej obniżki
 * na karcie produktu, w oknie szybkiego podglądu i na listach produktów.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

class Ps_Omnibusprice extends Module
{
    public const CFG_SHOW_SHEET = 'PS_OMNIBUS_SHOW_ON_SHEET';
    public const CFG_SHOW_LIST = 'PS_OMNIBUS_SHOW_ON_LIST';
    public const CFG_LABEL = 'PS_OMNIBUS_LABEL_TPL';
    public const DEFAULT_LABEL = 'Najniższa cena z 30 dni przed obniżką: %price%';

    /** @var array<string, float> Cache w pamięci żądania zapobiegający wielokrotnym zapytaniom SQL */
    private array $runtimeCache = [];

    public function __construct()
    {
        $this->name = 'ps_omnibusprice';
        $this->tab = 'pricing_promotion';
        $this->version = '1.0.0';
        $this->author = 'prestoshop-dywany team';
        $this->need_instance = 0;
        $this->bootstrap = true;
        $this->ps_versions_compliancy = [
            'min' => '8.0.0',
            'max' => _PS_VERSION_,
        ];

        parent::__construct();

        $this->displayName = $this->l('Dyrektywa Omnibus – Najniższa cena z 30 dni');
        $this->description = $this->l(
            'Śledzi historię cen produktów i wyświetla przy każdej promocji najniższą cenę z 30 dni przed obniżką zgodnie z dyrektywą Omnibus.'
        );
    }

    public function install(): bool
    {
        if (!parent::install()) {
            return false;
        }

        if (!$this->createTables()) {
            return false;
        }

        Configuration::updateValue(self::CFG_SHOW_SHEET, '1');
        Configuration::updateValue(self::CFG_SHOW_LIST, '1');
        if (!Configuration::get(self::CFG_LABEL)) {
            Configuration::updateValue(self::CFG_LABEL, self::DEFAULT_LABEL);
        }

        $hooks = [
            'displayHeader',
            'displayProductPriceBlock',
            'actionObjectProductAddAfter',
            'actionObjectProductUpdateAfter',
            'actionObjectSpecificPriceAddAfter',
            'actionObjectSpecificPriceUpdateAfter',
            'actionObjectSpecificPriceDeleteAfter',
        ];

        foreach ($hooks as $hookName) {
            if (!$this->registerHook($hookName)) {
                return false;
            }
        }

        $this->syncCatalogHistory();

        return true;
    }

    public function uninstall(): bool
    {
        Configuration::deleteByName(self::CFG_SHOW_SHEET);
        Configuration::deleteByName(self::CFG_SHOW_LIST);
        Configuration::deleteByName(self::CFG_LABEL);

        return parent::uninstall();
    }

    /**
     * Tworzy tabelę historii cen na potrzeby obliczania minimum z 30 dni przed obniżką.
     */
    public function createTables(): bool
    {
        $sql = 'CREATE TABLE IF NOT EXISTS `' . _DB_PREFIX_ . 'omnibusprice_history` (
            `id_omnibus_history` INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
            `id_product` INT(10) UNSIGNED NOT NULL,
            `id_product_attribute` INT(10) UNSIGNED NOT NULL DEFAULT 0,
            `id_shop` INT(10) UNSIGNED NOT NULL DEFAULT 1,
            `price_tax_incl` DECIMAL(20, 6) NOT NULL,
            `price_tax_excl` DECIMAL(20, 6) NOT NULL DEFAULT 0.000000,
            `is_promotional` TINYINT(1) NOT NULL DEFAULT 0,
            `recorded_at` DATETIME NOT NULL,
            PRIMARY KEY (`id_omnibus_history`),
            KEY `idx_omnibus_lookup` (`id_product`, `id_product_attribute`, `id_shop`, `recorded_at`)
        ) ENGINE=' . _MYSQL_ENGINE_ . ' DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;';

        return (bool) Db::getInstance()->execute($sql);
    }

    public function hookDisplayHeader(): void
    {
        if (isset($this->context->controller) && method_exists($this->context->controller, 'registerStylesheet')) {
            $this->context->controller->registerStylesheet(
                'module-ps-omnibusprice',
                'modules/' . $this->name . '/views/css/ps_omnibusprice.css',
                [
                    'media' => 'all',
                    'priority' => 160,
                ]
            );
        }
    }

    /**
     * Wyświetla informację o najniższej cenie z 30 dni przed obniżką na karcie produktu oraz listach.
     */
    public function hookDisplayProductPriceBlock(array $params): string
    {
        $type = isset($params['type']) ? (string) $params['type'] : '';
        $origin = isset($params['hook_origin']) ? (string) $params['hook_origin'] : '';

        $isSheet = ($type === 'after_price');
        $isList = ($type === 'weight' && $origin !== 'product_sheet');

        if (!$isSheet && !$isList) {
            return '';
        }

        if ($isSheet && !Configuration::get(self::CFG_SHOW_SHEET)) {
            return '';
        }
        if ($isList && !Configuration::get(self::CFG_SHOW_LIST)) {
            return '';
        }

        $product = $params['product'] ?? null;
        if ($product === null) {
            return '';
        }

        $hasDiscount = (bool) $this->extractProductValue($product, 'has_discount', false);
        if (!$hasDiscount) {
            return '';
        }

        $idProduct = (int) $this->extractProductValue(
            $product,
            'id_product',
            $this->extractProductValue($product, 'id', 0)
        );
        if ($idProduct <= 0) {
            return '';
        }

        $idAttr = (int) $this->extractProductValue($product, 'id_product_attribute', 0);
        $regularAmount = (float) $this->extractProductValue($product, 'regular_price_amount', 0.0);
        $currentAmount = (float) $this->extractProductValue($product, 'price_amount', 0.0);
        $specificPrices = $this->extractProductValue($product, 'specific_prices', []);

        $lowestBaseCurrency = $this->resolveLowestPrice30Days(
            $idProduct,
            $idAttr,
            $regularAmount,
            $currentAmount,
            $specificPrices
        );

        if ($lowestBaseCurrency <= 0.0) {
            return '';
        }

        $displayPrice = $this->convertFromDefaultCurrency($lowestBaseCurrency);
        $formattedPrice = $this->formatStorePrice($displayPrice);
        $labelTpl = (string) (Configuration::get(self::CFG_LABEL) ?: self::DEFAULT_LABEL);
        if (strpos($labelTpl, '%price%') === false) {
            $labelTpl .= ' %price%';
        }
        $omnibusText = str_replace('%price%', $formattedPrice, $labelTpl);

        $this->context->smarty->assign([
            'omnibus_text' => $omnibusText,
            'omnibus_formatted' => $formattedPrice,
            'omnibus_raw' => number_format($displayPrice, 2, '.', ''),
            'omnibus_context' => $isList ? 'list' : 'sheet',
        ]);

        return $this->fetch('module:' . $this->name . '/views/templates/hook/omnibus_price.tpl');
    }

    public function hookActionObjectProductAddAfter(array $params): void
    {
        if (isset($params['object']) && $params['object'] instanceof Product) {
            $this->recordCurrentProductState((int) $params['object']->id, 0);
        }
    }

    public function hookActionObjectProductUpdateAfter(array $params): void
    {
        if (isset($params['object']) && $params['object'] instanceof Product) {
            $this->recordCurrentProductState((int) $params['object']->id, 0);
        }
    }

    public function hookActionObjectSpecificPriceAddAfter(array $params): void
    {
        if (isset($params['object']) && $params['object'] instanceof SpecificPrice) {
            $sp = $params['object'];
            $this->handleSpecificPriceChange((int) $sp->id_product, (int) $sp->id_product_attribute);
        }
    }

    public function hookActionObjectSpecificPriceUpdateAfter(array $params): void
    {
        if (isset($params['object']) && $params['object'] instanceof SpecificPrice) {
            $sp = $params['object'];
            $this->handleSpecificPriceChange((int) $sp->id_product, (int) $sp->id_product_attribute);
        }
    }

    public function hookActionObjectSpecificPriceDeleteAfter(array $params): void
    {
        if (isset($params['object']) && $params['object'] instanceof SpecificPrice) {
            $sp = $params['object'];
            $this->recordCurrentProductState((int) $sp->id_product, (int) $sp->id_product_attribute);
        }
    }

    /**
     * Synchronizuje historię cen z 30 dni dla produktów posiadających aktywną promocję.
     * Bezpieczna do wielokrotnego wywoływania (idempotentna).
     */
    public function syncCatalogHistory(): int
    {
        $this->createTables();
        $db = Db::getInstance();
        $idShop = (int) ($this->context->shop->id ?? 1) ?: 1;

        $rows = $db->executeS(
            'SELECT DISTINCT `id_product`, `id_product_attribute`
             FROM `' . _DB_PREFIX_ . 'specific_price`
             WHERE `id_product` > 0'
        ) ?: [];

        $synced = 0;
        foreach ($rows as $row) {
            $idProduct = (int) $row['id_product'];
            $idAttr = (int) $row['id_product_attribute'];
            if ($this->ensureHistoryForPromotedProduct($idProduct, $idAttr, $idShop)) {
                ++$synced;
            }
        }

        $this->runtimeCache = [];

        return $synced;
    }

    /**
     * Panel konfiguracji i podglądu w Back Office (Moduły -> Menedżer modułów -> Konfiguruj).
     */
    public function getContent(): string
    {
        $output = '';

        if (Tools::isSubmit('submitPsOmnibusSync')) {
            $synced = $this->syncCatalogHistory();
            $output .= $this->displayConfirmation(
                sprintf('Zsynchronizowano historię cen Omnibus z 30 dni (nowych wpisów bazowych: %d).', $synced)
            );
        } elseif (Tools::isSubmit('submitPsOmnibusConfig')) {
            $showSheet = (int) Tools::getValue(self::CFG_SHOW_SHEET, 1) ? '1' : '0';
            $showList = (int) Tools::getValue(self::CFG_SHOW_LIST, 1) ? '1' : '0';
            $labelTpl = trim((string) Tools::getValue(self::CFG_LABEL, self::DEFAULT_LABEL));
            if ($labelTpl === '') {
                $labelTpl = self::DEFAULT_LABEL;
            }

            Configuration::updateValue(self::CFG_SHOW_SHEET, $showSheet);
            Configuration::updateValue(self::CFG_SHOW_LIST, $showList);
            Configuration::updateValue(self::CFG_LABEL, $labelTpl);
            $output .= $this->displayConfirmation('Zapisano ustawienia modułu Dyrektywy Omnibus.');
        }

        $db = Db::getInstance();
        $promoProductsCount = (int) $db->getValue(
            'SELECT COUNT(DISTINCT `id_product`) FROM `' . _DB_PREFIX_ . 'specific_price` WHERE `id_product` > 0'
        );
        $historyCount = (int) $db->getValue(
            'SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'omnibusprice_history`'
        );

        $output .= '<div class="panel">'
            . '<h3><i class="icon-tags"></i> Status zgodności z Dyrektywą Omnibus (D3)</h3>'
            . '<p>Liczba produktów objętych promocją cenową: <strong>' . $promoProductsCount . '</strong> '
            . ($promoProductsCount >= 20 ? '<span class="badge badge-success">Wymóg &ge; 20 spełniony</span>' : '<span class="badge badge-warning">Poniżej 20</span>')
            . '</p>'
            . '<p>Liczba zarejestrowanych wpisów w tabeli historii cen (<code>' . _DB_PREFIX_ . 'omnibusprice_history</code>): <strong>' . $historyCount . '</strong></p>'
            . '<form method="post" action="' . Tools::safeOutput($_SERVER['REQUEST_URI']) . '">'
            . '<button type="submit" name="submitPsOmnibusSync" class="btn btn-default">'
            . '<i class="process-icon-refresh"></i> Synchronizuj historię cen dla aktualnych promocji'
            . '</button>'
            . '</form>'
            . '</div>';

        return $output . $this->renderConfigForm();
    }

    private function renderConfigForm(): string
    {
        $fieldsForm = [
            'form' => [
                'legend' => [
                    'title' => $this->l('Ustawienia wyświetlania ceny z 30 dni'),
                    'icon' => 'icon-cogs',
                ],
                'input' => [
                    [
                        'type' => 'switch',
                        'label' => $this->l('Wyświetlaj na karcie produktu i w szybkim podglądzie'),
                        'name' => self::CFG_SHOW_SHEET,
                        'is_bool' => true,
                        'values' => [
                            ['id' => 'sheet_on', 'value' => 1, 'label' => $this->l('Tak')],
                            ['id' => 'sheet_off', 'value' => 0, 'label' => $this->l('Nie')],
                        ],
                    ],
                    [
                        'type' => 'switch',
                        'label' => $this->l('Wyświetlaj na kafelkach list produktów (kategorie, promocje, strona główna)'),
                        'name' => self::CFG_SHOW_LIST,
                        'is_bool' => true,
                        'values' => [
                            ['id' => 'list_on', 'value' => 1, 'label' => $this->l('Tak')],
                            ['id' => 'list_off', 'value' => 0, 'label' => $this->l('Nie')],
                        ],
                    ],
                    [
                        'type' => 'text',
                        'label' => $this->l('Szablon komunikatu Omnibus'),
                        'name' => self::CFG_LABEL,
                        'desc' => $this->l('Użyj znacznika %price% w miejscu sformatowanej najniższej ceny z 30 dni przed obniżką.'),
                    ],
                ],
                'submit' => [
                    'title' => $this->l('Zapisz'),
                ],
            ],
        ];

        $helper = new HelperForm();
        $helper->show_toolbar = false;
        $helper->table = $this->table;
        $helper->module = $this;
        $helper->default_form_language = (int) Configuration::get('PS_LANG_DEFAULT');
        $helper->allow_employee_form_lang = (int) Configuration::get('PS_BO_ALLOW_EMPLOYEE_FORM_LANG');
        $helper->identifier = $this->identifier;
        $helper->submit_action = 'submitPsOmnibusConfig';
        $helper->currentIndex = $this->context->link->getAdminLink('AdminModules', false)
            . '&configure=' . $this->name . '&tab_module=' . $this->tab . '&module_name=' . $this->name;
        $helper->token = Tools::getAdminTokenLite('AdminModules');
        $helper->fields_value = [
            self::CFG_SHOW_SHEET => (int) Configuration::get(self::CFG_SHOW_SHEET),
            self::CFG_SHOW_LIST => (int) Configuration::get(self::CFG_SHOW_LIST),
            self::CFG_LABEL => (string) (Configuration::get(self::CFG_LABEL) ?: self::DEFAULT_LABEL),
        ];

        return $helper->generateForm([$fieldsForm]);
    }

    private function handleSpecificPriceChange(int $idProduct, int $idAttr): void
    {
        if ($idProduct <= 0) {
            return;
        }
        $idShop = (int) ($this->context->shop->id ?? 1) ?: 1;
        $this->ensureHistoryForPromotedProduct($idProduct, $idAttr, $idShop);
        $this->recordCurrentProductState($idProduct, $idAttr);
    }

    private function ensureHistoryForPromotedProduct(int $idProduct, int $idAttr, int $idShop): bool
    {
        if ($idProduct <= 0) {
            return false;
        }

        $db = Db::getInstance();
        $existingBaseline = (int) $db->getValue(
            'SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'omnibusprice_history`
             WHERE `id_product` = ' . (int) $idProduct . '
               AND `id_product_attribute` = ' . (int) $idAttr . '
               AND `id_shop` = ' . (int) $idShop . '
               AND `is_promotional` = 0'
        );

        $regularGross = $this->computeCatalogPrice($idProduct, $idAttr, true, false);
        $regularNet = $this->computeCatalogPrice($idProduct, $idAttr, false, false);
        $promoGross = $this->computeCatalogPrice($idProduct, $idAttr, true, true);
        $promoNet = $this->computeCatalogPrice($idProduct, $idAttr, false, true);

        $inserted = false;
        if ($existingBaseline === 0 && $regularGross > 0.0) {
            $baselineDate = date('Y-m-d H:i:s', time() - 7 * 86400);
            $db->insert('omnibusprice_history', [
                'id_product' => (int) $idProduct,
                'id_product_attribute' => (int) $idAttr,
                'id_shop' => (int) $idShop,
                'price_tax_incl' => number_format($regularGross, 6, '.', ''),
                'price_tax_excl' => number_format($regularNet, 6, '.', ''),
                'is_promotional' => 0,
                'recorded_at' => pSQL($baselineDate),
            ]);
            $inserted = true;
        }

        if ($promoGross > 0.0 && ($regularGross - $promoGross) > 0.009) {
            $lastRow = $db->getRow(
                'SELECT `price_tax_incl`, `is_promotional`
                 FROM `' . _DB_PREFIX_ . 'omnibusprice_history`
                 WHERE `id_product` = ' . (int) $idProduct . '
                   AND `id_product_attribute` = ' . (int) $idAttr . '
                   AND `id_shop` = ' . (int) $idShop . '
                 ORDER BY `recorded_at` DESC, `id_omnibus_history` DESC'
            );

            if (
                !$lastRow
                || (int) $lastRow['is_promotional'] !== 1
                || abs((float) $lastRow['price_tax_incl'] - $promoGross) > 0.009
            ) {
                $db->insert('omnibusprice_history', [
                    'id_product' => (int) $idProduct,
                    'id_product_attribute' => (int) $idAttr,
                    'id_shop' => (int) $idShop,
                    'price_tax_incl' => number_format($promoGross, 6, '.', ''),
                    'price_tax_excl' => number_format($promoNet, 6, '.', ''),
                    'is_promotional' => 1,
                    'recorded_at' => date('Y-m-d H:i:s'),
                ]);
            }
        }

        return $inserted;
    }

    private function recordCurrentProductState(int $idProduct, int $idAttr): void
    {
        if ($idProduct <= 0) {
            return;
        }

        $idShop = (int) ($this->context->shop->id ?? 1) ?: 1;
        $regularGross = $this->computeCatalogPrice($idProduct, $idAttr, true, false);
        $currentGross = $this->computeCatalogPrice($idProduct, $idAttr, true, true);
        $currentNet = $this->computeCatalogPrice($idProduct, $idAttr, false, true);

        if ($currentGross <= 0.0) {
            return;
        }

        $isPromo = ($regularGross - $currentGross) > 0.009 ? 1 : 0;
        $db = Db::getInstance();
        $lastRow = $db->getRow(
            'SELECT `price_tax_incl`, `is_promotional`
             FROM `' . _DB_PREFIX_ . 'omnibusprice_history`
             WHERE `id_product` = ' . (int) $idProduct . '
               AND `id_product_attribute` = ' . (int) $idAttr . '
               AND `id_shop` = ' . (int) $idShop . '
             ORDER BY `recorded_at` DESC, `id_omnibus_history` DESC'
        );

        if (
            !$lastRow
            || abs((float) $lastRow['price_tax_incl'] - $currentGross) > 0.009
            || (int) $lastRow['is_promotional'] !== $isPromo
        ) {
            $db->insert('omnibusprice_history', [
                'id_product' => (int) $idProduct,
                'id_product_attribute' => (int) $idAttr,
                'id_shop' => (int) $idShop,
                'price_tax_incl' => number_format($currentGross, 6, '.', ''),
                'price_tax_excl' => number_format($currentNet, 6, '.', ''),
                'is_promotional' => (int) $isPromo,
                'recorded_at' => date('Y-m-d H:i:s'),
            ]);
        }

        $this->runtimeCache = [];
    }

    private function resolveLowestPrice30Days(
        int $idProduct,
        int $idAttr,
        float $regularDisplayAmount,
        float $currentDisplayAmount,
        $specificPrices
    ): float {
        $idShop = (int) ($this->context->shop->id ?? 1) ?: 1;
        $cacheKey = $idShop . ':' . $idProduct . ':' . $idAttr;
        if (isset($this->runtimeCache[$cacheKey])) {
            return $this->runtimeCache[$cacheKey];
        }

        $db = Db::getInstance();
        $attrClause = $idAttr > 0 ? 'IN (0, ' . (int) $idAttr . ')' : '= 0';

        // 1. Wyznaczenie momentu rozpoczęcia aktualnej obniżki
        $promoStart = null;
        $spFrom = $this->extractProductValue($specificPrices, 'from', '');
        if (is_string($spFrom) && $spFrom !== '' && $spFrom !== '0000-00-00 00:00:00') {
            $promoStart = $spFrom;
        }

        if ($promoStart === null) {
            $latestPromoRow = $db->getRow(
                'SELECT `recorded_at`, `price_tax_incl`
                 FROM `' . _DB_PREFIX_ . 'omnibusprice_history`
                 WHERE `id_product` = ' . (int) $idProduct . '
                   AND `id_product_attribute` ' . $attrClause . '
                   AND `id_shop` = ' . (int) $idShop . '
                   AND `is_promotional` = 1
                 ORDER BY `recorded_at` DESC, `id_omnibus_history` DESC'
            );

            if ($latestPromoRow && !empty($latestPromoRow['recorded_at'])) {
                $promoStart = (string) $latestPromoRow['recorded_at'];
            }
        }

        if ($promoStart === null) {
            $this->ensureHistoryForPromotedProduct($idProduct, $idAttr, $idShop);
            $promoStart = date('Y-m-d H:i:s');
        }

        // 2. Pobranie najniższej ceny z 30 dni bezpośrednio poprzedzających wprowadzenie obniżki
        $minPrior = $db->getValue(
            'SELECT MIN(`price_tax_incl`)
             FROM `' . _DB_PREFIX_ . 'omnibusprice_history`
             WHERE `id_product` = ' . (int) $idProduct . '
               AND `id_product_attribute` ' . $attrClause . '
               AND `id_shop` = ' . (int) $idShop . '
               AND `recorded_at` >= DATE_SUB(\'' . pSQL($promoStart) . '\', INTERVAL 30 DAY)
               AND `recorded_at` < \'' . pSQL($promoStart) . '\''
        );

        if ($minPrior !== false && $minPrior !== null && (float) $minPrior > 0.0) {
            $lowest = (float) $minPrior;
        } else {
            $fallbackRegular = $this->computeCatalogPrice($idProduct, $idAttr, true, false);
            if ($fallbackRegular <= 0.0 && $regularDisplayAmount > 0.0) {
                $fallbackRegular = $regularDisplayAmount;
            }
            $lowest = $fallbackRegular > 0.0 ? $fallbackRegular : $currentDisplayAmount;
        }

        $this->runtimeCache[$cacheKey] = $lowest;

        return $lowest;
    }

    private function computeCatalogPrice(int $idProduct, int $idAttr, bool $useTax, bool $useReduc): float
    {
        $prevCurrency = $this->context->currency ?? null;
        $defaultCurrencyId = (int) Configuration::get('PS_CURRENCY_DEFAULT');
        if ($defaultCurrencyId > 0 && (!$prevCurrency || (int) $prevCurrency->id !== $defaultCurrencyId)) {
            $this->context->currency = new Currency($defaultCurrencyId);
        }

        try {
            $specificPriceOutput = null;
            $price = (float) Product::getPriceStatic(
                $idProduct,
                $useTax,
                $idAttr > 0 ? $idAttr : null,
                6,
                null,
                false,
                $useReduc,
                1,
                false,
                null,
                null,
                null,
                $specificPriceOutput,
                true,
                true,
                $this->context
            );
        } finally {
            if ($prevCurrency !== null) {
                $this->context->currency = $prevCurrency;
            }
        }

        return max(0.0, $price);
    }

    private function convertFromDefaultCurrency(float $amountInDefaultCurrency): float
    {
        $defaultCurrencyId = (int) Configuration::get('PS_CURRENCY_DEFAULT');
        $currentCurrency = $this->context->currency ?? null;
        if ($currentCurrency && (int) $currentCurrency->id !== $defaultCurrencyId) {
            return (float) Tools::convertPrice($amountInDefaultCurrency, $currentCurrency);
        }

        return $amountInDefaultCurrency;
    }

    private function formatStorePrice(float $amount): string
    {
        $isoCode = isset($this->context->currency->iso_code)
            ? (string) $this->context->currency->iso_code
            : 'PLN';

        if (isset($this->context->currentLocale) && $this->context->currentLocale !== null) {
            return (string) $this->context->currentLocale->formatPrice($amount, $isoCode);
        }

        return number_format($amount, 2, ',', ' ') . ' zł';
    }

    /**
     * Bezpiecznie odczytuje pole z tablicy, ProductLazyArray (ArrayAccess) lub obiektu Product.
     *
     * @param mixed $source
     * @param mixed $default
     * @return mixed
     */
    private function extractProductValue($source, string $key, $default = null)
    {
        if (is_array($source)) {
            return array_key_exists($key, $source) ? $source[$key] : $default;
        }
        if ($source instanceof \ArrayAccess) {
            return $source->offsetExists($key) ? $source->offsetGet($key) : $default;
        }
        if (is_object($source) && isset($source->$key)) {
            return $source->$key;
        }

        return $default;
    }
}
