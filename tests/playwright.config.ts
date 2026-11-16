import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.BASE_URL;

if (!baseURL) {
  throw new Error(
    'Brak adresu sklepu. Ustaw zmienną środowiskową BASE_URL, np. BASE_URL=https://twoj-sklep npx playwright test',
  );
}

export default defineConfig({
  testDir: './e2e',
  timeout: 240_000,
  workers: 1,
  retries: 0,
  fullyParallel: false,
  reporter: [
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
  ],
  use: {
    baseURL,
    headless: true,
    ignoreHTTPSErrors: true,
    locale: 'pl-PL',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        browserName: 'chromium',
      },
    },
  ],
});
