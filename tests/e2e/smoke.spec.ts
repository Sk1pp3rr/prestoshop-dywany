import { expect, test } from '@playwright/test';

test('strona główna sklepu się ładuje', async ({ page }) => {
  const response = await page.goto('/');

  expect(response, 'brak odpowiedzi HTTP').not.toBeNull();
  expect(response!.status(), 'strona główna zwróciła błąd HTTP').toBeLessThan(400);
  await expect(page.locator('body')).toBeVisible();
  await expect(page).toHaveTitle(/.+/);
});
