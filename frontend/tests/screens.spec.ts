import { test, expect } from '@playwright/test';
const screens = {
  overview: 'Обзор',
  monitoring: 'Мониторинг',
  principles: 'Как это работает',
  protection: 'Сценарии защиты',
  learning: 'Онбординг + квиз',
  phone: 'Смена номера',
  knowledge: 'База знаний',
  guides: 'Видео и гайды',
  examples: 'Примеры ситуаций',
  settings: 'Настройки',
  support: 'Поддержка',
};
for (const width of [390, 768, 1024, 1440, 1728]) {
  test(`all screens fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const [id, title] of Object.entries(screens)) {
      await page.goto(`/#${id}`);
      await expect(
        page.getByRole('heading', { level: 1, name: title, exact: true }),
      ).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBeTruthy();
      await page.screenshot({
        path: `test-results/screens/${id}-${width}.png`,
        fullPage: true,
        animations: 'disabled',
      });
    }
  });
}
test('monitoring filters apply, pagination and operation detail', async ({
  page,
}) => {
  await page.goto('/#monitoring');
  await expect(page.getByRole('row')).toHaveCount(6);
  await page.getByRole('button', { name: 'Следующая страница' }).click();
  await expect(page.getByRole('row')).toHaveCount(3);
  await page.getByLabel('Уровень риска', { exact: true }).selectOption('high');
  await page.getByRole('button', { name: 'Применить', exact: true }).click();
  await expect(page.getByRole('row')).toHaveCount(2);
  await page.getByRole('button', { name: 'Детали операции 3' }).click();
  await expect(
    page.getByRole('region', { name: 'Детали операции' }),
  ).toContainText('Реальная блокировка не выполнялась');
  await page
    .getByLabel('Тип операции', { exact: true })
    .selectOption('purchase');
  await page.getByRole('button', { name: 'Применить' }).click();
  await expect(
    page.getByText('Операций по выбранным фильтрам нет.'),
  ).toBeVisible();
});
test('knowledge search, reading, scenario filter and settings persistence', async ({
  page,
}) => {
  await page.goto('/#knowledge');
  await page
    .getByRole('textbox', { name: 'Поиск по базе знаний' })
    .fill('фишинг');
  await page.getByRole('button', { name: /Фишинг Как/ }).click();
  await expect(page.getByRole('region', { name: 'Материал' })).toContainText(
    'Откройте нужный сервис самостоятельно',
  );
  await expect(page.getByRole('region', { name: 'Материал' })).toBeFocused();
  await page.getByRole('button', { name: 'Закрыть материал' }).click();
  await expect(page.getByRole('button', { name: /Фишинг Как/ })).toBeFocused();
  await page.goto('/#protection');
  await page.getByRole('button', { name: 'Мессенджеры', exact: true }).click();
  await expect(page.getByRole('article')).toHaveCount(1);
  await page.goto('/#settings');
  await page.getByRole('switch', { name: 'Компактные таблицы' }).click();
  await page.reload();
  await expect(
    page.getByRole('switch', { name: 'Компактные таблицы' }),
  ).toHaveAttribute('aria-checked', 'true');
  await expect(page.locator('html')).toHaveAttribute('data-compact', 'true');
  await page.goto('/#support');
  await page.getByRole('textbox', { name: 'Поиск в поддержке' }).fill('SMS');
  await page.getByText('Отправляются ли SMS при смене номера?').click();
  await expect(
    page.getByText(/В тренажёре используется учебный код/),
  ).toBeVisible();
});
