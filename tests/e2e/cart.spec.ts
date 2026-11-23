import { expect, type Page, test } from '@playwright/test';

const stepTimeout = 15_000;
const elementTimeout = 10_000;
const productsToAdd = 10;
const weightLimitKg = 50;
const quantityPattern = [1, 2, 3];

type ProductCandidate = {
  id: string;
  href: string;
  categoryUrl: string;
};

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function spreadAcrossCategories(candidates: ProductCandidate[]): ProductCandidate[] {
  const groups = new Map<string, ProductCandidate[]>();
  for (const candidate of candidates) {
    const group = groups.get(candidate.categoryUrl) ?? [];
    group.push(candidate);
    groups.set(candidate.categoryUrl, group);
  }

  const ordered: ProductCandidate[] = [];
  const queues = [...groups.values()];
  let progressed = true;
  while (progressed) {
    progressed = false;
    for (const queue of queues) {
      const next = queue.shift();
      if (!next) {
        continue;
      }
      ordered.push(next);
      progressed = true;
    }
  }
  return ordered;
}

async function readProductFacts(page: Page): Promise<{
  weightKg: number;
  stock: number;
  minimalQuantity: number;
} | null> {
  const weightKg = await page.locator('script[type="application/ld+json"]').evaluateAll((scripts) => {
    for (const script of scripts) {
      try {
        const data = JSON.parse(script.textContent ?? '') as {
          '@type'?: string;
          weight?: { value?: string; unitCode?: string };
        };
        if (data['@type'] !== 'Product' || !data.weight) {
          continue;
        }
        const value = Number(data.weight.value);
        const unit = (data.weight.unitCode ?? '').toLowerCase();
        if (!Number.isFinite(value) || value < 0) {
          return null;
        }
        if (unit === 'kg' || unit === 'kgm') {
          return value;
        }
        if (unit === 'g' || unit === 'grm') {
          return value / 1000;
        }
      } catch {
        // Kolejny skrypt JSON-LD może nie być opisem produktu.
      }
    }
    return null;
  });

  const details = await page.locator('#product-details').getAttribute('data-product');
  if (weightKg === null || !details) {
    return null;
  }

  const product = JSON.parse(details) as {
    quantity?: number;
    minimal_quantity?: number;
    customization_required?: boolean;
  };
  if (product.customization_required) {
    return null;
  }

  return {
    weightKg,
    stock: Number(product.quantity ?? 0),
    minimalQuantity: Number(product.minimal_quantity ?? 1),
  };
}

function quantityWithinLimits(
  preferred: number,
  weightKg: number,
  stock: number,
  minimalQuantity: number,
  totalWeightKg: number,
): number | null {
  const roomKg = weightLimitKg - totalWeightKg;
  const maxByWeight =
    weightKg === 0 ? Math.max(preferred, minimalQuantity) : Math.floor((roomKg - 0.001) / weightKg);
  const quantity = Math.min(Math.max(preferred, minimalQuantity), Math.floor(stock), maxByWeight);
  if (quantity < 1 || quantity < minimalQuantity) {
    return null;
  }
  return quantity;
}

async function collectCandidates(page: Page): Promise<ProductCandidate[]> {
  const categoryUrls = [
    ...new Set(
      await page.locator('#top-menu li.category > a[href]').evaluateAll((links) =>
        links.map((link) => (link as HTMLAnchorElement).href),
      ),
    ),
  ];
  const candidates: ProductCandidate[] = [];
  const seenProducts = new Set<string>();

  for (const categoryUrl of categoryUrls) {
    const seenPages = new Set<string>();
    let nextUrl: string | null = categoryUrl;

    while (nextUrl && !seenPages.has(nextUrl) && seenPages.size < 5) {
      seenPages.add(nextUrl);
      await page.goto(nextUrl, { timeout: stepTimeout });

      const miniatures = page.locator('#js-product-list article.js-product-miniature');
      const count = await miniatures.count();
      for (let index = 0; index < count; index += 1) {
        const miniature = miniatures.nth(index);
        const titleLink = miniature.locator('.product-title a');
        if ((await titleLink.count()) === 0) {
          continue;
        }

        const id = await miniature.getAttribute('data-id-product', { timeout: elementTimeout });
        const href = await titleLink.first().getAttribute('href', { timeout: elementTimeout });
        if (!id || !href || seenProducts.has(id)) {
          continue;
        }
        seenProducts.add(id);
        candidates.push({ id, href, categoryUrl });
      }

      const nextPage = page.locator('nav.pagination a[rel="next"]');
      nextUrl =
        (await nextPage.count()) === 0
          ? null
          : await nextPage.first().getAttribute('href', { timeout: elementTimeout });
    }

    const categories = new Set(candidates.map((candidate) => candidate.categoryUrl));
    if (candidates.length >= productsToAdd + 5 && categories.size >= 2) {
      break;
    }
  }

  return candidates;
}

type CartLine = {
  path: string;
  quantity: number;
};

type RemovableCartLine = CartLine & {
  productId: string;
  attributeId: string;
};

async function readCartLines(page: Page): Promise<CartLine[]> {
  return page.locator('li.cart-item').evaluateAll((items) =>
    items.map((item) => {
      const link = item.querySelector('a.label');
      const input = item.querySelector('input.js-cart-line-product-quantity');
      return {
        path: link instanceof HTMLAnchorElement ? link.pathname : '',
        quantity: input instanceof HTMLInputElement ? Number(input.value) : 0,
      };
    }),
  );
}

async function readRemovableLines(page: Page): Promise<RemovableCartLine[]> {
  return page.locator('li.cart-item').evaluateAll((items) =>
    items.flatMap((item) => {
      const link = item.querySelector('a.label');
      const input = item.querySelector('input.js-cart-line-product-quantity');
      const remove = item.querySelector('a[data-link-action="delete-from-cart"]');
      if (!(remove instanceof HTMLAnchorElement)) {
        return [];
      }
      const productId = remove.dataset.idProduct ?? '';
      const attributeId = remove.dataset.idProductAttribute ?? '';
      if (!/^\d+$/.test(productId) || !/^\d+$/.test(attributeId)) {
        return [];
      }
      return [
        {
          path: link instanceof HTMLAnchorElement ? link.pathname : '',
          quantity: input instanceof HTMLInputElement ? Number(input.value) : 0,
          productId,
          attributeId,
        },
      ];
    }),
  );
}

function shuffledIndexes(length: number): number[] {
  const order = [...Array(length).keys()];
  for (let index = order.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(Math.random() * (index + 1));
    [order[index], order[swap]] = [order[swap], order[index]];
  }
  return order;
}

let testStarted = 0;

function logStage(message: string): void {
  console.log(`[cart +${Date.now() - testStarted} ms] ${message}`);
}

async function isAddToCartEnabled(page: Page): Promise<boolean> {
  return page.locator('button[data-button-action="add-to-cart"]').evaluateAll((buttons) =>
    buttons.some((button) => button instanceof HTMLButtonElement && !button.disabled),
  );
}

async function chooseVariant(page: Page, action: () => Promise<void>): Promise<boolean> {
  const refresh = page
    .waitForResponse(
      (response) => {
        const body = response.request().postData() ?? '';
        return response.request().method() === 'POST' && body.includes('action=refresh');
      },
      { timeout: elementTimeout },
    )
    .catch(() => undefined);
  await action();
  await refresh;
  return page
    .waitForFunction(
      () => {
        const button = document.querySelector('button[data-button-action="add-to-cart"]');
        return button instanceof HTMLButtonElement && !button.disabled;
      },
      undefined,
      { timeout: 1_000 },
    )
    .then(() => true)
    .catch(() => false);
}

/**
 * Domyślny rozmiar bywa niedostępny (przycisk Dodaj do koszyka ma atrybut disabled,
 * a sklep pokazuje „Dostępny produkt z innymi opcjami”). Drugi argument
 * page.waitForFunction jest danymi strony, nie limitem czasu, więc oczekiwanie
 * aż ten przycisk sam się włączy trwa do końca limitu testu.
 * Tutaj od razu przełączamy kolejne warianty i pomijamy produkt, gdy żaden nie jest dostępny.
 */
async function ensurePurchasableVariant(page: Page, label: string): Promise<boolean> {
  const button = page.locator('button[data-button-action="add-to-cart"]');
  const visible = await button
    .waitFor({ state: 'visible', timeout: elementTimeout })
    .then(() => true)
    .catch(() => false);
  if (!visible) {
    logStage(`${label}: brak przycisku dodawania, pomijam`);
    return false;
  }
  if (await isAddToCartEnabled(page)) {
    return true;
  }

  const started = Date.now();
  logStage(
    `${label}: domyślny wariant ma wyłączone „Dodaj do koszyka”; nie czekam na samą zmianę stanu, sprawdzam pozostałe rozmiary`,
  );

  const selects = page.locator('.js-product-variants select');
  const selectCount = await selects.count();
  for (let index = 0; index < selectCount; index += 1) {
    const options = await selects.nth(index).locator('option').evaluateAll((nodes) =>
      nodes.map((node) => ({
        value: (node as HTMLOptionElement).value,
        name: (node.textContent ?? '').trim(),
        selected: (node as HTMLOptionElement).selected,
      })),
    );
    for (const option of options) {
      if (option.selected || option.value === '') {
        continue;
      }
      const attempt = Date.now();
      const enabled = await chooseVariant(page, () =>
        selects.nth(index).selectOption(option.value, { timeout: elementTimeout }),
      );
      logStage(
        `${label}: wariant ${option.name || option.value} ${enabled ? 'dostępny' : 'niedostępny'} po ${Date.now() - attempt} ms`,
      );
      if (enabled) {
        return true;
      }
    }
  }

  const radios = page.locator('.js-product-variants input[type="radio"]');
  const radioCount = await radios.count();
  for (let index = 0; index < radioCount; index += 1) {
    const radio = radios.nth(index);
    if (await radio.isChecked()) {
      continue;
    }
    const name = (await radio.getAttribute('title')) || (await radio.getAttribute('value')) || String(index);
    const attempt = Date.now();
    const enabled = await chooseVariant(page, () => radio.check({ force: true, timeout: elementTimeout }));
    logStage(`${label}: wariant ${name} ${enabled ? 'dostępny' : 'niedostępny'} po ${Date.now() - attempt} ms`);
    if (enabled) {
      return true;
    }
  }

  logStage(`${label}: żaden wariant nie jest dostępny, pomijam po ${Date.now() - started} ms`);
  return false;
}

async function registerCustomer(page: Page): Promise<void> {
  const started = Date.now();
  const email = `e2e.${Date.now()}@example.com`;
  const firstName = 'Anna';
  const lastName = 'Testowa';
  const password = `Test-${Date.now()}-Aa9!`;

  await page.locator('#_desktop_user_info a[href*="/logowanie"]').click({ timeout: elementTimeout });
  await page
    .locator('a[data-link-action="display-register-form"]')
    .click({ timeout: elementTimeout });

  const form = page.locator('#customer-form');
  await expect(form).toBeVisible({ timeout: elementTimeout });
  await form.locator('#field-firstname').fill(firstName, { timeout: elementTimeout });
  await form.locator('#field-lastname').fill(lastName, { timeout: elementTimeout });
  await form.locator('#field-email').fill(email, { timeout: elementTimeout });
  await form.locator('#field-password').fill(password, { timeout: elementTimeout });
  await form.locator('input[name="psgdpr"]').check({ timeout: elementTimeout });
  await form.locator('input[name="customer_privacy"]').check({ timeout: elementTimeout });
  await form.locator('button[data-link-action="save-customer"]').click({ timeout: elementTimeout });

  await expect(page.locator('#_desktop_user_info a.account')).toContainText(`${firstName} ${lastName}`, {
    timeout: elementTimeout,
  });
  await expect(page.locator('#_desktop_user_info a.logout')).toBeVisible({ timeout: elementTimeout });
  logStage(`rejestracja klienta: ${Date.now() - started} ms`);
}

async function placeOrder(page: Page, expectedLines: number, expectedPieces: number): Promise<void> {
  await registerCustomer(page);

  await page.locator('#_desktop_cart a[href]').click({ timeout: elementTimeout });
  await expect(page.locator('li.cart-item')).toHaveCount(expectedLines, { timeout: elementTimeout });
  await expect(page.locator('#_desktop_cart .cart-products-count')).toHaveText(`(${expectedPieces})`, {
    timeout: elementTimeout,
  });

  await page.locator('.cart-detailed-actions a.btn-primary').click({ timeout: elementTimeout });
  logStage('otwarto kasę z zachowanym koszykiem');

  const address = page.locator('#checkout-addresses-step');
  await expect(address.locator('#delivery-address')).toBeVisible({ timeout: stepTimeout });
  await expect(address.locator('#field-id_country')).toHaveValue('14', { timeout: elementTimeout });
  await address.locator('#field-alias').fill('Dom', { timeout: elementTimeout });
  await address.locator('#field-firstname').fill('Anna', { timeout: elementTimeout });
  await address.locator('#field-lastname').fill('Testowa', { timeout: elementTimeout });
  await address.locator('#field-address1').fill('ul. Długa 1', { timeout: elementTimeout });
  await address.locator('#field-postcode').fill('80-309', { timeout: elementTimeout });
  await address.locator('#field-city').fill('Gdańsk', { timeout: elementTimeout });
  await address.locator('#field-phone').fill('500600700', { timeout: elementTimeout });
  await expect(address.locator('#use_same_address')).toBeChecked();
  await address.locator('#delivery-address button[name="confirm-addresses"]').click({
    timeout: elementTimeout,
  });

  const delivery = page.locator('#checkout-delivery-step.js-current-step');
  await expect(delivery).toBeVisible({ timeout: stepTimeout });
  const carrierOption = delivery.locator('.js-delivery-option').filter({ hasText: 'pobraniowa' });
  await expect(carrierOption).toHaveCount(1, { timeout: elementTimeout });
  const carrierName = (await carrierOption.locator('.carrier-name').innerText()).trim();
  expect(carrierName).toMatch(/pobraniowa/i);
  const carrierRadio = carrierOption.locator('input[type="radio"]');
  // Classic (core.js) wysyła POST na data-url-update formularza #js-delivery,
  // czyli akcję selectDeliveryOption, wyłącznie przy zdarzeniu change.
  // Zaznaczone już radio nie emituje change, więc czekanie na odpowiedź trwałoby do timeoutu.
  if (await carrierRadio.isChecked({ timeout: elementTimeout })) {
    logStage(
      `przewoźnik ${carrierName} jest już zaznaczony; selectDeliveryOption nie jest wysyłane bez zmiany opcji`,
    );
  } else {
    const deliveryUpdate = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' && response.url().includes('selectDeliveryOption'),
      { timeout: elementTimeout },
    );
    await carrierRadio.check({ timeout: elementTimeout });
    const deliveryResponse = await deliveryUpdate;
    if (deliveryResponse.status() !== 200) {
      throw new Error(
        `selectDeliveryOption zwrócił HTTP ${deliveryResponse.status()} dla ${deliveryResponse.url()}.`,
      );
    }
  }
  await expect(carrierRadio).toBeChecked();
  await delivery.locator('button[name="confirmDeliveryOption"]').click({ timeout: elementTimeout });
  logStage(`wybrano przewoźnika: ${carrierName}`);

  const payment = page.locator('#checkout-payment-step.js-current-step');
  await expect(payment).toBeVisible({ timeout: stepTimeout });
  const cod = payment.locator('input[data-module-name="ps_cashondelivery"]');
  await cod.check({ timeout: elementTimeout });
  await expect(cod).toBeChecked();
  await page.locator('#conditions-to-approve input[type="checkbox"]').check({ timeout: elementTimeout });
  const placeOrderButton = page.locator('#payment-confirmation button[type="submit"]');
  await expect(placeOrderButton).toBeEnabled({ timeout: elementTimeout });
  await placeOrderButton.click({ timeout: elementTimeout });

  await expect(page.locator('#content-hook_order_confirmation')).toContainText(
    'Twoje zamówienie zostało potwierdzone',
    { timeout: stepTimeout },
  );
  const details = page.locator('#order-details');
  await expect(details).toContainText(/odbiorze/i, { timeout: elementTimeout });
  await expect(details).toContainText(carrierName, { timeout: elementTimeout });
  const reference = (await page.locator('#order-reference-value').innerText()).split(':').pop()?.trim() ?? '';
  expect(reference).toMatch(/^[A-Z0-9]{8,9}$/);

  const invoice = page.locator('#content-hook_order_confirmation a[href*="pdf-invoice"]');
  await expect(invoice).toBeVisible({ timeout: elementTimeout });
  const href = await invoice.getAttribute('href');
  expect(href).toContain('pdf-invoice');
  const pdfResponse = await page.request.get(new URL(href as string, page.url()).href);
  expect(pdfResponse.ok()).toBe(true);
  const pdf = await pdfResponse.body();
  expect(pdf.subarray(0, 5).toString('latin1')).toBe('%PDF-');
  expect(pdf.length).toBeGreaterThan(1000);
  logStage(`potwierdzono zamówienie ${reference}, faktura PDF ${pdf.length} B`);

  await page.locator('#_desktop_user_info a.account').click({ timeout: elementTimeout });
  await page.locator('#history-link').click({ timeout: elementTimeout });
  const row = page.locator('table.table-labeled tbody tr').filter({ hasText: reference });
  await expect(row).toHaveCount(1, { timeout: elementTimeout });
  await expect(row.locator('.label')).toHaveText('Oczekiwanie na płatność przy odbiorze', {
    timeout: elementTimeout,
  });
  await expect(row.locator('a[href*="pdf-invoice"]')).toBeVisible({ timeout: elementTimeout });
}

test('dodaje 10 produktów z dwóch kategorii, wyszukuje, usuwa 3 pozycje i składa zamówienie za pobraniem', async ({ page }) => {
  testStarted = Date.now();
  await page.goto('/', { timeout: stepTimeout, waitUntil: 'domcontentloaded' });

  const candidates = spreadAcrossCategories(await collectCandidates(page));
  logStage(
    `zebrano ${candidates.length} kandydatów z ${new Set(candidates.map((candidate) => candidate.categoryUrl)).size} kategorii`,
  );
  const discoveredCategories = new Set(candidates.map((candidate) => candidate.categoryUrl));
  if (candidates.length < productsToAdd || discoveredCategories.size < 2) {
    throw new Error(
      `Sklep nie ma 10 różnych dostępnych produktów z co najmniej dwóch kategorii. Znaleziono ${candidates.length} produktów w ${discoveredCategories.size} kategoriach.`,
    );
  }

  let totalPieces = 0;
  let totalWeightKg = 0;
  const addedCategories = new Set<string>();
  const addedQuantities = new Set<number>();
  const discoveredNames: string[] = [];
  let addedProducts = 0;

  for (const candidate of candidates) {
    if (addedProducts === productsToAdd) {
      break;
    }

    const opened = Date.now();
    try {
      await page.goto(candidate.href, { timeout: stepTimeout, waitUntil: 'domcontentloaded' });
    } catch (error) {
      logStage(`produkt ${candidate.id}: nawigacja nieudana po ${Date.now() - opened} ms (${String(error)})`);
      continue;
    }
    logStage(`produkt ${candidate.id}: otwarto w ${Date.now() - opened} ms`);

    const addToCart = page.locator('button[data-button-action="add-to-cart"]');
    if (!(await ensurePurchasableVariant(page, `produkt ${candidate.id}`))) {
      continue;
    }

    const facts = await readProductFacts(page);
    if (!facts) {
      continue;
    }

    const quantity = quantityWithinLimits(
      quantityPattern[addedProducts % quantityPattern.length],
      facts.weightKg,
      facts.stock,
      facts.minimalQuantity,
      totalWeightKg,
    );
    if (quantity === null) {
      continue;
    }

    const productName = (await page.locator('h1.h1').innerText()).trim();
    expect(productName).not.toBe('');
    discoveredNames.push(productName);

    const quantityInput = page.locator('#quantity_wanted');
    await quantityInput.fill(String(quantity), { timeout: stepTimeout });
    await expect(quantityInput).toHaveValue(String(quantity), { timeout: stepTimeout });
    await addToCart.click({ timeout: stepTimeout });

    totalPieces += quantity;
    totalWeightKg += facts.weightKg * quantity;
    addedProducts += 1;
    addedCategories.add(candidate.categoryUrl);
    addedQuantities.add(quantity);

    const modal = page.locator('#blockcart-modal');
    await expect(modal).toBeVisible({ timeout: stepTimeout });
    await expect(modal.locator('.product-name')).toHaveText(
      new RegExp(`^${escapeRegExp(productName)}$`, 'i'),
      { timeout: stepTimeout },
    );
    await expect(modal.locator('.product-quantity strong')).toHaveText(String(quantity), {
      timeout: stepTimeout,
    });
    await expect(page.locator('#_desktop_cart .cart-products-count')).toHaveText(
      `(${totalPieces})`,
      { timeout: stepTimeout },
    );
    expect(totalWeightKg).toBeLessThan(weightLimitKg);
    logStage(`dodano ${addedProducts}/${productsToAdd}: ${productName}, ilość ${quantity}, ${totalPieces} szt., ${totalWeightKg.toFixed(2)} kg`);
  }
  logStage(`koniec dodawania produktów: ${addedProducts} pozycji`);

  if (addedProducts < productsToAdd || addedCategories.size < 2 || addedQuantities.size < 2) {
    throw new Error(
      `Nie udało się dodać 10 różnych dostępnych produktów z dwóch kategorii i w różnych ilościach. Dodano ${addedProducts} produktów z ${addedCategories.size} kategorii, ilości: ${[...addedQuantities].join(', ') || 'brak'}.`,
    );
  }

  await page.locator('#blockcart-modal').getByRole('button', { name: 'Kontynuuj zakupy' }).click({ timeout: stepTimeout });
  await expect(page.locator('#blockcart-modal')).toBeHidden({ timeout: stepTimeout });
  await page.locator('#_desktop_cart a[href]').click({ timeout: stepTimeout });

  const cartLines = page.locator('li.cart-item');
  await expect(cartLines).toHaveCount(productsToAdd, { timeout: stepTimeout });
  const productPaths = await cartLines.locator('a.label').evaluateAll((links) =>
    links.map((link) => (link as HTMLAnchorElement).pathname),
  );
  expect(new Set(productPaths).size).toBe(productsToAdd);
  logStage(`koszyk ma ${productsToAdd} różnych pozycji`);

  const linesBefore = await readCartLines(page);
  const searchQuery = discoveredNames[0];
  const searchInput = page.locator('#search_widget input[name="s"]');
  await searchInput.fill(searchQuery, { timeout: elementTimeout });
  await searchInput.press('Enter');

  const results = page.locator('#js-product-list article.js-product-miniature');
  await expect(results.first()).toBeVisible({ timeout: elementTimeout });
  const resultHrefs = await results.evaluateAll((articles) =>
    articles.flatMap((article) => {
      const link = article.querySelector('.product-title a');
      return link instanceof HTMLAnchorElement && link.href ? [link.href] : [];
    }),
  );
  expect(resultHrefs.length).toBeGreaterThan(0);

  let searchedProductPath = '';
  let quantityBefore = 0;

  logStage(`wyszukiwanie „${searchQuery}”: ${resultHrefs.length} wyników`);

  for (const index of shuffledIndexes(resultHrefs.length)) {
    const opened = Date.now();
    try {
      await page.goto(resultHrefs[index], { timeout: stepTimeout, waitUntil: 'domcontentloaded' });
    } catch (error) {
      logStage(`wynik wyszukiwania: nawigacja nieudana po ${Date.now() - opened} ms (${String(error)})`);
      continue;
    }
    const addToCart = page.locator('button[data-button-action="add-to-cart"]');
    if (!(await ensurePurchasableVariant(page, 'wynik wyszukiwania'))) {
      continue;
    }

    const facts = await readProductFacts(page);
    const quantity = facts
      ? quantityWithinLimits(1, facts.weightKg, facts.stock, facts.minimalQuantity, totalWeightKg)
      : null;
    if (!facts || quantity !== 1) {
      continue;
    }

    const productName = (await page.locator('h1.h1').innerText()).trim();
    expect(productName).not.toBe('');
    searchedProductPath = new URL(page.url()).pathname;
    quantityBefore = linesBefore.find((line) => line.path === searchedProductPath)?.quantity ?? 0;

    const quantityInput = page.locator('#quantity_wanted');
    await quantityInput.fill('1', { timeout: elementTimeout });
    await expect(quantityInput).toHaveValue('1', { timeout: elementTimeout });
    await addToCart.click({ timeout: elementTimeout });

    totalPieces += 1;
    totalWeightKg += facts.weightKg;

    const modal = page.locator('#blockcart-modal');
    await expect(modal).toBeVisible({ timeout: elementTimeout });
    await expect(modal.locator('.product-name')).toHaveText(
      new RegExp(`^${escapeRegExp(productName)}$`, 'i'),
      { timeout: elementTimeout },
    );
    await expect(modal.locator('.product-quantity strong')).toHaveText(String(quantityBefore + 1), {
      timeout: elementTimeout,
    });
    await expect(page.locator('#_desktop_cart .cart-products-count')).toHaveText(
      `(${totalPieces})`,
      { timeout: elementTimeout },
    );
    expect(totalWeightKg).toBeLessThan(weightLimitKg);
    break;
  }

  if (!searchedProductPath) {
    throw new Error('Żaden wynik wyszukiwania nie mógł zostać dodany do koszyka w jednej sztuce.');
  }

  await page
    .locator('#blockcart-modal')
    .getByRole('button', { name: 'Kontynuuj zakupy' })
    .click({ timeout: elementTimeout });
  await expect(page.locator('#blockcart-modal')).toBeHidden({ timeout: elementTimeout });
  await page.locator('#_desktop_cart a[href]').click({ timeout: elementTimeout });

  const linesAfter = await readCartLines(page);
  const quantityAfter = linesAfter.find((line) => line.path === searchedProductPath)?.quantity;
  expect(quantityAfter).toBe(quantityBefore + 1);
  expect(linesAfter.reduce((sum, line) => sum + line.quantity, 0)).toBe(totalPieces);
  expect(linesAfter.length).toBe(linesBefore.length + (quantityBefore === 0 ? 1 : 0));
  logStage(`po wyszukiwaniu koszyk ma ${linesAfter.length} pozycji i ${totalPieces} szt.`);

  const removable = await readRemovableLines(page);
  const productsToRemove = 3;
  if (removable.length < productsToRemove) {
    throw new Error(
      `W koszyku są ${removable.length} pozycje do usunięcia, a wymagane są ${productsToRemove}.`,
    );
  }

  const toRemove = removable.slice(0, productsToRemove);
  let expectedLines = linesAfter.length;
  let expectedPieces = totalPieces;

  for (const line of toRemove) {
    const removeLink = page.locator(
      `li.cart-item a[data-link-action="delete-from-cart"][data-id-product="${line.productId}"][data-id-product-attribute="${line.attributeId}"]`,
    );
    await removeLink.click({ timeout: elementTimeout });
    await expect(removeLink).toHaveCount(0, { timeout: elementTimeout });

    const remaining = await readCartLines(page);
    expect(remaining.some((item) => item.path === line.path)).toBe(false);
    expectedLines -= 1;
    expectedPieces -= line.quantity;
    expect(remaining).toHaveLength(expectedLines);
    expect(remaining.reduce((sum, item) => sum + item.quantity, 0)).toBe(expectedPieces);
    await expect(page.locator('#_desktop_cart .cart-products-count')).toHaveText(
      `(${expectedPieces})`,
      { timeout: elementTimeout },
    );
  }

  expect(linesAfter.length - expectedLines).toBe(productsToRemove);
  expect(totalPieces - expectedPieces).toBe(
    toRemove.reduce((sum, line) => sum + line.quantity, 0),
  );
  logStage(`usunięto ${productsToRemove} pozycje, zostało ${expectedLines} pozycji i ${expectedPieces} szt.`);

  await placeOrder(page, expectedLines, expectedPieces);
});
