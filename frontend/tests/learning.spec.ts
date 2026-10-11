import { test, expect, type Page } from '@playwright/test';
const titles = ['Безопасные переводы', 'Если просят перевести дальше', 'Неожиданный перевод', 'Коды и пароли', 'Предупреждение банка', 'Проверка через официальный канал', 'Сохраняем спокойствие'];
const modules = titles.map((title, i) => ({ id: `m${i + 1}`, title, summary: 'Заметьте признаки риска и выберите безопасный следующий шаг.', minutes: 5, article: ['Не спешите переводить деньги. Проверьте просьбу другим способом.', 'Откройте официальное приложение банка самостоятельно.'], cards: [{ id: `c${i}`, prompt: 'Можно ли передавать код другому человеку?', options: ['Да', 'Нет'] }], quiz: [{ id: `q${i}`, prompt: 'Что делать при неожиданной просьбе?', options: ['Проверить через официальный канал', 'Сразу перевести деньги'] }] }));
function state(days = 0) { return { xp: 0, rank: { id: 'new', title: 'Новичок', min_xp: 0 }, next_rank: { id: 'expert', title: 'Знаток денег', min_xp: 100 }, points_to_next: 100, rank_progress_percent: 0, streak_days: days, last_completed_date: null, completed_modules: [] as string[], rewards: [3, 7, 14, 30].map(day => ({ days: day, title: day === 30 ? '+1 учебная категория кешбэка' : 'Учебные бонусы', points: 10, unlocked: days >= day, selected_category: null as string | null })), percentile: null, rank_note: 'Рейтинг пока недоступен: нет сравнительной выборки.', categories: [{ id: 'groceries', title: 'Продукты' }, { id: 'transport', title: 'Транспорт' }], demo: true }; }
async function mock(page: Page, days = 0) {
  const progress = state(days);
  await page.route('**/api/v1/learning/catalog', route => route.fulfill({ json: { modules } }));
  await page.route('**/api/v1/learning/progress', route => route.fulfill({ json: progress }));
  return progress;
}
for (const width of [390, 768, 1024, 1440, 1672]) test(`learning cards fit ${width}px`, async ({ page }) => {
  await mock(page); await page.setViewportSize({ width, height: 941 }); await page.goto('/#learning');
  await expect(page.getByRole('button', { name: /Мини-урок/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Безопасные переводы/ })).toBeVisible();
  await expect(page.getByText('Рейтинг пока недоступен: нет сравнительной выборки.')).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: `test-results/learning-cards-${width}.png`, fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: /Безопасные переводы/ }).click();
  await expect(page.getByRole('region', { name: 'Учебный материал' })).toBeFocused();
  await expect(page.getByRole('article', { name: 'Главное из мини-урока' })).toContainText('Не спешите переводить деньги.');
  await expect(page.getByRole('radio')).toHaveCount(0);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.screenshot({ path: `test-results/learning-intro-${width}.png`, fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'Перейти к карточкам' }).click();
  await page.getByRole('radio', { name: 'Нет', exact: true }).check();
  await page.getByRole('button', { name: 'Далее →', exact: true }).click();
  await expect(page.getByRole('group', { name: 'Что делать при неожиданной просьбе?' })).toBeVisible();
  await page.screenshot({ path: `test-results/learning-lesson-${width}.png`, fullPage: true, animations: 'disabled' });
});
test('server result, failed retry uses same key, changed answer uses a new key', async ({ page }) => {
  const progress = await mock(page); const keys: string[] = [];
  await page.route('**/api/v1/learning/completions', route => { keys.push(route.request().postDataJSON().idempotency_key); return route.fulfill({ status: 503 }); });
  await page.goto('/#learning'); await page.getByRole('button', { name: 'Тест Сразу проверьте знания' }).click(); await page.getByRole('button', { name: /Безопасные переводы/ }).click();
  await page.getByRole('radio').first().check(); await page.getByRole('button', { name: 'Получить результат' }).click();
  await expect(page.locator('#learning').getByRole('alert')).toContainText('Не удалось'); await expect(page.getByRole('heading', { name: /Результат:/ })).toHaveCount(0);
  await page.getByRole('button', { name: 'Получить результат' }).click(); await expect.poll(() => keys.length).toBe(2); expect(keys[0]).toBe(keys[1]);
  await page.getByRole('radio').last().check(); await page.getByRole('button', { name: 'Получить результат' }).click(); await expect.poll(() => keys.length).toBe(3); expect(keys[2]).not.toBe(keys[1]);
  await page.unroute('**/api/v1/learning/completions');
  await page.route('**/api/v1/learning/completions', route => route.fulfill({ json: { progress: { ...progress, xp: 60, completed_modules: ['m1'], streak_days: 1 }, result: { score: 1, total: 1, passed: true, feedback: [{ question_id: 'q0', correct: true, explanation: 'Всегда проверяйте просьбу самостоятельно.', source_needed: true }] } } }));
  await page.getByRole('button', { name: 'Получить результат' }).click(); await expect(page.getByText('Занятие завершено. Прогресс сохранён.')).toBeVisible(); await expect(page.getByText('60 учебных баллов')).toBeVisible(); await expect(page.getByText('Формулировка требует проверки источника')).toBeVisible();
});
test('article attention question and 30-day category use server response', async ({ page }) => {
  const progress = await mock(page, 30);
  await page.route('**/api/v1/learning/completions', route => { expect(route.request().postDataJSON().answers).toEqual({ c0: 1 }); return route.fulfill({ json: { progress, result: { score: 1, total: 1, passed: true, feedback: [] } } }); });
  await page.route('**/api/v1/learning/rewards/30/claim', route => { expect(route.request().postDataJSON().category).toBe('groceries'); return route.fulfill({ json: { progress: { ...progress, rewards: progress.rewards.map(reward => ({ ...reward, selected_category: reward.days === 30 ? 'groceries' : null })) } } }); });
  await page.goto('/#learning'); await page.getByRole('button', { name: 'Статья Прочитайте в своём темпе' }).click(); await page.getByRole('button', { name: /Безопасные переводы/ }).click(); await page.getByRole('button', { name: 'Перейти к вопросу' }).click(); await page.getByRole('radio', { name: 'Нет', exact: true }).check(); await page.getByRole('button', { name: 'Получить результат' }).click();
  await expect(page.getByText('Занятие завершено. Прогресс сохранён.')).toBeVisible(); await page.getByLabel('Выберите +1 учебную категорию кешбэка').selectOption('groceries'); await page.getByRole('button', { name: 'Выбрать учебную категорию', exact: true }).click(); await expect(page.getByRole('status')).toContainText('Продукты');
});
test('load failure retry and keyboard card navigation', async ({ page }) => {
  await page.route('**/api/v1/learning/catalog', route => route.fulfill({ status: 503 }));
  await page.route('**/api/v1/learning/progress', route => route.fulfill({ status: 503 }));
  await page.goto('/#learning');
  await expect(page.locator('#learning').getByRole('alert')).toBeVisible();
  await page.unroute('**/api/v1/learning/catalog');
  await page.unroute('**/api/v1/learning/progress');
  await mock(page);
  await page.getByRole('button', { name: 'Повторить загрузку' }).click();
  await page.getByRole('button', { name: /Безопасные переводы/ }).click();
  await page.getByRole('button', { name: 'Перейти к карточкам' }).click();
  await page.getByRole('radio').last().check();
  await page.getByRole('button', { name: 'Далее →' }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('group', { name: 'Что делать при неожиданной просьбе?' })).toBeVisible();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
});
