import { test, expect } from '@playwright/test';

test('real backend: scenarios, alert, quiz and phone simulation', async ({ page }) => {
  await page.goto('/');
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
  await page.getByRole('button', { name: 'Начать обучение' }).click();
  const questions = page.getByRole('group');
  await expect(questions).toHaveCount(5);
  for (const question of await questions.all()) await question.getByRole('radio').first().check();
  await page.getByRole('button', { name: 'Получить результат' }).click();
  await expect(page.getByRole('heading', { name: /Результат:/ })).toBeVisible();
  await page.getByRole('button', { name: 'Проверить смену номера' }).click();
  await expect(page.getByRole('heading', { name: 'Смена не разрешена' })).toBeVisible();
  await page.getByLabel('Имитировать SMS-код со старого номера').check();
  await page.getByLabel('Имитировать SMS-код с нового номера').check();
  await page.getByRole('button', { name: 'Проверить смену номера' }).click();
  await expect(page.getByRole('heading', { name: 'Демонстрация: подтверждения приняты' })).toBeVisible();
});

test('API failure allows retry', async ({ page }) => {
  await page.route('**/api/analyze', route => route.fulfill({ status: 503 }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Обычные операции' }).click();
  await page.getByRole('button', { name: 'Проверить', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Сервис недоступен' })).toBeVisible();
  await page.unroute('**/api/analyze');
  await page.getByRole('button', { name: 'Проверить', exact: true }).click();
  await expect(page.getByText(/Низкий риск ·/)).toBeVisible();
});

test('loaded content reflows on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Сценарий вербовщика' }).click();
  await page.getByRole('button', { name: 'Проверить', exact: true }).click();
  await expect(page.getByText(/Высокий риск ·/)).toBeVisible();
  await page.getByRole('button', { name: 'Начать обучение' }).click();
  await expect(page.getByRole('group')).toHaveCount(5);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: 'test-results/demo-mobile-loaded.png', fullPage: true });
});
