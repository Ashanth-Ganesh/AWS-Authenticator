const { test, expect } = require('@playwright/test');
const { readFile } = require('node:fs/promises');

async function fillRegistration(page, username) {
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Password', { exact: true }).fill('assignment123');
  await page.getByLabel('First name', { exact: true }).fill('Ada');
  await page.getByLabel('Last name', { exact: true }).fill('Lovelace');
  await page.getByLabel('Email', { exact: true }).fill('ada@example.com');
  await page.getByLabel('Address', { exact: true }).fill('1 Example Street\nBoston, MA');
}

test('register, view details, download, sign out, and re-login', async ({ page }, testInfo) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const username = `student_${Date.now()}`;
  const content = 'One two\nthree\tfour five.\n';

  await page.goto('/register');
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
  await fillRegistration(page, username);
  await page.getByLabel('Text file').setInputFiles({ name: 'Limerick (1).txt', mimeType: 'text/plain', buffer: Buffer.from(content) });
  await page.screenshot({ path: testInfo.outputPath('registration.png'), fullPage: true });
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.getByRole('heading', { name: 'Hello, Ada' })).toBeVisible();
  await expect(page.locator('dd').filter({ hasText: 'Lovelace' })).toBeVisible();
  await expect(page.getByText('ada@example.com', { exact: true })).toBeVisible();
  await expect(page.locator('dd').filter({ hasText: '1 Example Street' })).toBeVisible();
  await expect(page.locator('.word-count')).toHaveText('5 words');
  await page.screenshot({ path: testInfo.outputPath('profile.png'), fullPage: true });

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download file' }).click();
  const download = await downloadPromise;
  expect(await readFile(await download.path(), 'utf-8')).toBe(content);

  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Password', { exact: true }).fill('incorrect');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('Incorrect username or password.');
  await page.getByLabel('Password', { exact: true }).fill('assignment123');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.locator('.word-count')).toHaveText('5 words');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Hello, Ada' })).toBeVisible();

  await page.getByLabel('Text file').setInputFiles({ name: 'updated.txt', mimeType: 'text/plain', buffer: Buffer.from('two words') });
  await page.getByRole('button', { name: 'Replace file' }).click();
  await expect(page.getByRole('status')).toHaveText('Your file has been saved.');
  await expect(page.locator('.word-count')).toHaveText('2 words');
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto('/profile');
  await expect(page).toHaveURL(/\/login$/);
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('registration works without an optional file', async ({ page }) => {
  await page.goto('/register');
  await fillRegistration(page, `nofile_${Date.now()}`);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.getByText('No file uploaded yet. Add your text file below.')).toBeVisible();
});
