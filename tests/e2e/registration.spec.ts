import { expect, test } from '@playwright/test';

test('rejestracja nowego klienta loguje go do sklepu', async ({ page }) => {
  const email = `e2e.${Date.now()}@example.com`;
  const firstName = 'Anna';
  const lastName = 'Testowa';
  const password = `Test-${Date.now()}-Aa9!`;

  await page.goto('/');
  await page.locator('#_desktop_user_info a[href*="/logowanie"]').click();
  await page.locator('a[data-link-action="display-register-form"]').click();

  const form = page.locator('#customer-form');
  await expect(form).toBeVisible();

  await form.locator('#field-firstname').fill(firstName);
  await form.locator('#field-lastname').fill(lastName);
  await form.locator('#field-email').fill(email);
  await form.locator('#field-password').fill(password);
  await form.locator('input[name="psgdpr"]').check();
  await form.locator('input[name="customer_privacy"]').check();
  await form.locator('button[data-link-action="save-customer"]').click();

  
  await expect(page.locator('#_desktop_user_info a.account')).toContainText(
    `${firstName} ${lastName}`,
  );
  await expect(page.locator('#_desktop_user_info a.logout')).toBeVisible();
});
