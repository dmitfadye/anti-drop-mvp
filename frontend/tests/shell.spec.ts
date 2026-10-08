import { test, expect } from '@playwright/test';
for (const width of [390, 768, 1024, 1440, 1728]) {
  test(`shell at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/');
    const nav = page.getByRole('navigation', { name: 'Основная навигация' });
    if (width < 768)
      await page.getByRole('button', { name: '☰ Меню' }).click();
    for (const title of ['ОСНОВНОЕ', 'ЗАЩИТА', 'ОБУЧЕНИЕ', 'СИСТЕМА'])
      await expect(nav.getByRole('heading', { name: title })).toBeVisible();
    await expect(
      nav.getByRole('link', { name: 'Сценарии защиты', exact: true }),
    ).toBeVisible();
    const capsule = nav.locator('[class*="sidebar__active-indicator"]');
    await expect(capsule).toHaveCount(1);
    const initial = await capsule.evaluate(
      (el) => getComputedStyle(el).transform,
    );
    await nav.getByRole('link', { name: 'Мониторинг', exact: true }).click();
    await expect(page).toHaveURL(/#monitoring$/);
    if (width < 768)
      await page.getByRole('button', { name: '☰ Меню' }).click();
    const current = nav.getByRole('link', { name: 'Мониторинг', exact: true });
    await expect(current).toHaveAttribute('aria-current', 'page');
    await expect
      .poll(async () => {
        const a = await capsule.boundingBox(),
          b = await current.boundingBox();
        return a && b ? Math.abs(a.y - b.y) : 999;
      })
      .toBeLessThan(1);
    expect(
      await capsule.evaluate((el) => getComputedStyle(el).transform),
    ).not.toBe(initial);
    if (width < 768) await page.keyboard.press('Escape');
    await page.reload();
    if (width < 768)
      await page.getByRole('button', { name: '☰ Меню' }).click();
    await expect(current).toHaveAttribute('aria-current', 'page');
    if (width < 768) await page.keyboard.press('Escape');
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Обзор');
    await expect(
      page.getByText(/Демонстрационные данные · показатели/),
    ).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: `test-results/overview-${width}.png`, animations: 'disabled' });
    await page.screenshot({
      path: `test-results/workspace-${width}.png`,
      fullPage: true,
    });
    if (width < 768) {
      await page.getByRole('button', { name: '☰ Меню' }).click();
      await page.screenshot({ path: 'test-results/mobile-navigation.png' });
    }
  });
}
test('keyboard, search, notifications, resize and reduced motion', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(
    page.getByRole('link', { name: 'Перейти к содержимому' }),
  ).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  const link = page.getByRole('link', { name: 'Мониторинг', exact: true });
  await link.focus();
  expect(
    await link.evaluate((el) => getComputedStyle(el).outlineStyle),
  ).not.toBe('none');
  await page.keyboard.press('Enter');
  await expect(link).toHaveAttribute('aria-current', 'page');
  const capsule = page.locator('[class*="sidebar__active-indicator"]');
  expect(
    await capsule.evaluate((el) => getComputedStyle(el).transitionDuration),
  ).toBe('0s');
  await page.keyboard.press('Control+k');
  await expect(
    page.getByRole('textbox', { name: 'Поиск по разделам' }),
  ).toBeFocused();
  await page.getByRole('textbox', { name: 'Поиск по разделам' }).fill('квиз');
  await page.locator('[class*="topbar__results"]').getByRole('link').click();
  await expect(page).toHaveURL(/#learning$/);
  await page.getByRole('button', { name: 'Уведомления' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: 'Новых уведомлений нет' }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  const menu = page.getByRole('button', { name: '☰ Меню' });
  await menu.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(menu).toBeFocused();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(
    page.getByRole('link', { name: 'Онбординг + квиз', exact: true }),
  ).toHaveAttribute('aria-current', 'page');
});

test('approved overview, popover dismissal, theme and feature links', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.setViewportSize({ width: 1672, height: 941 });
  await page.goto('/');
  await page.evaluate(() => document.fonts.ready);
  const notice = page.getByRole('button', { name: 'Уведомления' });
  await notice.click();
  await expect(page.getByRole('status')).toBeVisible();
  await page.screenshot({ path: 'test-results/approved-overview-1672.png', animations: 'disabled' });
  await page.keyboard.press('Escape');
  await expect(notice).toBeFocused();
  await expect(page.getByRole('status')).toHaveCount(0);
  await notice.click();
  await page.getByRole('heading', { level: 1 }).click();
  await expect(page.getByRole('status')).toHaveCount(0);
  const theme = page.getByRole('button', { name: 'Мягкая синяя тема' });
  await theme.click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'blue');
  await theme.click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  const shortcuts = page.locator('[class*="overview__shortcuts"]');
  await shortcuts.getByRole('link').first().click();
  await expect(page).toHaveURL(/#monitoring$/);
  await page.goto('/');
  await shortcuts.getByRole('link').last().click();
  await expect(page).toHaveURL(/#learning$/);
  expect(errors).toEqual([]);
});
