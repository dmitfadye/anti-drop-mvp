import { test, expect } from '@playwright/test';

for (const width of [390, 768, 1024, 1440]) {
  test(`workspace and real navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Ваши деньги.Ваше решение.');
    await expect(page.getByRole('navigation', { name: 'Основная навигация' })).toBeVisible();
    await expect(page.getByText('Демонстрационный режим')).toBeVisible();
    await page.getByRole('link', { name: 'Как это работает', exact: true }).click();
    await expect(page).toHaveURL(/#principles$/);
    await expect(page.getByRole('heading', { name: /Сначала разобраться\.\s*Потом действовать\./ })).toBeInViewport();
    for (const href of await page.locator('a').evaluateAll(links => links.map(link => link.getAttribute('href')))) {
      expect(href?.startsWith('#')).toBeTruthy();
      await expect(page.locator(href!)).toHaveCount(1);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.goto('/');
    await page.screenshot({ path: `test-results/workspace-${width}.png`, fullPage: true });
  });
}

test('keyboard skip link and native disclosure', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Перейти к содержимому' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  const disclosure = page.locator('summary');
  await disclosure.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('Сейчас доступны обзор и описание подхода.', { exact: false })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page.getByText('Сейчас доступны обзор и описание подхода.', { exact: false })).toBeHidden();
});
