import { test, expect } from '@playwright/test';

test('real backend: scenarios, alert, sequential quiz and verified phone wizard', async ({
  page,
}) => {
  await page.goto('/#monitoring');
  await page.getByText('Проверить учебный сценарий', { exact: false }).click();
  const check = page.getByRole('button', { name: 'Проверить', exact: true });
  await expect(check).toBeDisabled();
  await page.getByRole('button', { name: 'Обычные операции' }).click();
  await check.click();
  await expect(page.getByText(/Низкий риск ·/)).toBeVisible();
  await page.getByRole('button', { name: 'Сценарий вербовщика' }).click();
  await expect(page.getByText(/Низкий риск ·/)).toHaveCount(0);
  await page.getByLabel('Язык предупреждения').selectOption('en');
  await check.click();
  await expect(page.getByText(/Высокий риск ·/)).toBeVisible();
  await page.getByRole('button', { name: 'Поддержка — демо' }).click();
  await expect(page.getByText(/реальная заявка не отправлена/)).toBeVisible();
  await page
    .getByRole('navigation', { name: 'Основная навигация' })
    .getByRole('link', { name: 'Онбординг + квиз', exact: true })
    .click();
  await page.getByRole('button', { name: 'Тест Сразу проверьте знания' }).click();
  await page.getByRole('button', { name: /Безопасные переводы/ }).click();
  for (let i = 0; i < 5; i++) {
    await page.getByRole('radio').first().check();
    await page
      .getByRole('button', {
        name: i === 4 ? 'Получить результат' : 'Далее →',
        exact: true,
      })
      .click();
  }
  await expect(page.getByRole('heading', { name: /Результат:/ })).toBeVisible();
  await page.getByRole('button', { name: 'Пройти ещё раз' }).click();
  await expect(page.getByRole('radio').first()).not.toBeChecked();
  await page.goto('/#phone');
  await page.getByRole('button', { name: 'Далее', exact: true }).click();
  await expect(page.locator('#phone').getByRole('alert')).toContainText(
    'Введите учебный код',
  );
  await page
    .getByRole('button', { name: 'Отправить код', exact: true })
    .click();
  await page.getByLabel('Введите код из SMS', { exact: true }).fill('000000');
  await page.getByRole('button', { name: 'Далее', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Проверка личности', exact: true }),
  ).toBeVisible();
  await page.getByLabel('Введите код из SMS', { exact: true }).fill('123456');
  await page.getByRole('button', { name: 'Далее', exact: true }).click();
  await page.getByLabel('Новый номер телефона').fill('8 (916) 000-00-01');
  await page.getByRole('button', { name: 'Далее', exact: true }).click();
  await expect(page.locator('#phone').getByRole('alert')).toContainText(
    'должен отличаться',
  );
  await page.getByLabel('Новый номер телефона').fill('+79160000002');
  await page.getByRole('button', { name: 'Далее', exact: true }).click();
  await page
    .getByRole('button', { name: 'Отправить код', exact: true })
    .click();
  await page
    .getByLabel('Код для нового номера', { exact: true })
    .fill('123456');
  await page.getByRole('button', { name: 'Далее', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Демонстрация: подтверждения приняты' }),
  ).toBeVisible();
  await expect(page.getByRole('status')).toContainText('5000');
});

test('real backend: article completion persists after page reload', async ({ page }) => {
  await page.goto('/#learning');
  await page.getByRole('button', { name: 'Статья Прочитайте в своём темпе' }).click();
  await page.getByRole('button', { name: /Безопасные переводы/ }).click();
  await expect(page.getByText('Что такое дроппер простыми словами', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Перейти к вопросу' }).click();
  await page.getByRole('radio', { name: 'Ложь', exact: true }).check();
  const saved = page.waitForResponse(response => response.url().endsWith('/api/v1/learning/completions') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Получить результат' }).click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(body.result.passed).toBe(true);
  expect(body.progress.completed_modules).toContain('m1_safe_transfers');
  await expect(page.getByText('Занятие завершено. Прогресс сохранён.')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: /Безопасные переводы/ })).toContainText('Завершён');
});

test('API failure allows retry', async ({ page }) => {
  await page.route('**/api/demo/sandbox', (route) => route.fulfill({ status: 503 }));
  await page.goto('/#monitoring');
  await page.getByText('Проверить учебный сценарий', { exact: false }).click();
  await page.getByRole('button', { name: 'Обычные операции' }).click();
  await page.getByRole('button', { name: 'Проверить', exact: true }).click();
  await expect(
    page.getByRole('alert').filter({ hasText: 'Сервис недоступен' }),
  ).toBeVisible();
  await page.unroute('**/api/demo/sandbox');
  await page.getByRole('button', { name: 'Проверить', exact: true }).click();
  await expect(page.getByText(/Низкий риск ·/)).toBeVisible();
});

test('loaded content reflows on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#monitoring');
  await page.getByText('Проверить учебный сценарий', { exact: false }).click();
  await page.getByRole('button', { name: 'Сценарий вербовщика' }).click();
  await page.getByRole('button', { name: 'Проверить', exact: true }).click();
  await expect(page.getByText(/Высокий риск ·/)).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: 'test-results/demo-mobile-loaded.png',
    fullPage: true,
  });
  await page.goto('/#learning');
  await page.getByRole('button', { name: 'Тест Сразу проверьте знания' }).click();
  await page.getByRole('button', { name: /Безопасные переводы/ }).click();
  await expect(page.locator('#learning').getByRole('radio')).toHaveCount(4);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
