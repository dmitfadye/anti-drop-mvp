import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { LearningCatalog, LearningProgress, LearningQuestion, PracticeFeedback } from '../components/learning-api';

const version = 'scenario-test.v1';
const draftKey = 'antidrop-learning-session-v1';
// Use every real module while matching the public catalog's removal of grading data.
const realCatalog = JSON.parse(readFileSync(resolve(process.cwd(), '../data/learning/course.json'), 'utf8'), (key, value: unknown) => ['correct', 'explanation', 'danger_sign', 'safe_action'].includes(key) ? undefined : value) as LearningCatalog;
type GradedCard = LearningQuestion & { correct: number; explanation: string; safe_action?: string; danger_sign?: string };
const sourceCourse = JSON.parse(readFileSync(resolve(process.cwd(), '../data/learning/course.json'), 'utf8')) as { modules: { id: string; cards: GradedCard[] }[] };
const catalog: LearningCatalog = { version, modules: [{
  id: 'm8_phone_fraud', title: 'Звонок под давлением', summary: 'Выберите безопасное действие.', minutes: 6,
  article: ['Остановитесь и проверьте просьбу через официальный канал.'],
  cards: [
    { id: 'c1', prompt: 'Как поступить с просьбой о коде?', options: ['Назвать код', 'Завершить звонок', 'Назвать часть кода'], scenario_type: 'call', scenario_text: 'Собеседник просит код для отмены покупки.', learning_goal: 'Сохранить код', difficulty: 'easy', source_url: 'https://www.cbr.ru/Reception/TopicalMessage/Page/6327', content_version: version },
    { id: 'c2', prompt: 'Где найти контакт для проверки?', options: ['На официальном сайте', 'В присланном сообщении', 'У звонящего'], scenario_type: 'message', scenario_text: 'Сообщение требует срочно перезвонить по приложенному номеру.', learning_goal: 'Найти независимый контакт', difficulty: 'medium', source_url: 'https://www.cbr.ru/information_security/pmp/typical_fraudulent_schemes/28092026/', content_version: version },
  ],
  quiz: [{ id: 'q1', prompt: 'Что делать с предложением оформить кредит?', options: ['Оформить сразу', 'Попросить удостоверение', 'Прекратить разговор и проверить'], scenario_type: 'call', scenario_text: 'Мнимый полицейский просит оформить кредит для спецоперации.', learning_goal: 'Не брать кредит по чужой инструкции', difficulty: 'hard', source_url: 'https://www.cbr.ru/Reception/TopicalMessage/Page/8726', content_version: version }],
}] };
const correct: Record<string, number> = { c1: 1, c2: 0, q1: 2 };
const explanations: Record<string, string> = { c1: 'Не передавайте код собеседнику.', c2: 'Проверяйте контакт независимо от сообщения.', q1: 'Не оформляйте кредит по указанию звонящего.' };
function state(): LearningProgress {
  return { xp: 0, rank: { id: 'new', title: 'Новичок', min_xp: 0 }, next_rank: null, points_to_next: 0, rank_progress_percent: 0, streak_days: 0, last_completed_date: null, completed_modules: [], rewards: [3, 7, 14, 30].map(days => ({ days, title: 'Учебная награда', points: 10, unlocked: false })), percentile: null, rank_note: 'Рейтинг пока недоступен.', categories: [], demo: true };
}
type CompletionBody = { module_id: string; format: 'lesson' | 'quiz' | 'article'; answers: Record<string, number>; idempotency_key: string; course_version: string };
async function mock(page: Page) {
  const control = { unavailable: false, failCompletion: false, practiceIds: [] as string[], completions: [] as CompletionBody[], progress: state() };
  await page.route('**/api/v1/learning/catalog', route => route.fulfill(control.unavailable ? { status: 503 } : { json: catalog }));
  await page.route('**/api/v1/learning/progress', route => route.fulfill(control.unavailable ? { status: 503 } : { json: control.progress }));
  await page.route('**/api/v1/learning/practice', route => {
    const body = route.request().postDataJSON() as { question_id: string; answer: number; course_version: string };
    control.practiceIds.push(body.question_id);
    expect(body.course_version).toBe(version);
    // Match the real stateless endpoint: only practice cards have an answer key here.
    if (!catalog.modules[0].cards.some(card => card.id === body.question_id)) return route.fulfill({ status: 404 });
    const feedback: PracticeFeedback = { question_id: body.question_id, correct: body.answer === correct[body.question_id], correct_index: correct[body.question_id], explanation: explanations[body.question_id], source_needed: false, danger_sign: 'Просят выполнить действие без независимой проверки.', safe_action: 'Сделать паузу и проверить.' };
    return route.fulfill({ json: feedback });
  });
  await page.route('**/api/v1/learning/completions', route => {
    const body = route.request().postDataJSON() as CompletionBody;
    control.completions.push(body);
    if (control.failCompletion) return route.fulfill({ status: 503 });
    expect(body.module_id).toBe('m8_phone_fraud'); expect(body.course_version).toBe(version);
    const ids = body.format === 'lesson' ? ['c1', 'c2', 'q1'] : body.format === 'quiz' ? ['q1'] : ['c1'];
    expect(Object.keys(body.answers).sort()).toEqual([...ids].sort());
    const feedback = ids.map(question_id => ({ question_id, correct: body.answers[question_id] === correct[question_id], explanation: explanations[question_id], source_needed: false }));
    const score = feedback.filter(item => item.correct).length;
    const assessmentScore = body.answers.q1 === correct.q1 ? 1 : 0;
    const passed = body.format === 'article' ? score === 1 : assessmentScore === 1;
    if (passed) control.progress = { ...control.progress, xp: 60, completed_modules: ['m8_phone_fraud'], streak_days: 1 };
    return route.fulfill({ json: { progress: control.progress, result: { score, total: ids.length, passed, feedback, ...(body.format === 'lesson' ? { assessment_score: assessmentScore, assessment_total: 1 } : {}) } } });
  });
  return control;
}
async function startLesson(page: Page) {
  await page.goto('/#learning');
  await page.getByRole('button', { name: 'Разобрать звонок', exact: true }).click();
  await page.getByRole('button', { name: 'Перейти к карточкам' }).click();
}
async function checkCard(page: Page, answer: string) {
  await page.getByRole('radio', { name: answer, exact: true }).check();
  await page.getByRole('button', { name: 'Проверить ответ', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Далее →', exact: true })).toBeVisible();
}
async function reachQuiz(page: Page, wrongFirst = false) {
  await startLesson(page);
  await checkCard(page, wrongFirst ? 'Назвать код' : 'Завершить звонок');
  await page.getByRole('button', { name: 'Далее →', exact: true }).click();
  await checkCard(page, 'На официальном сайте');
  await page.getByRole('button', { name: 'Далее →', exact: true }).click();
  await expect(page.getByRole('group', { name: 'Что делать с предложением оформить кредит?' })).toBeVisible();
}

test('practice gates navigation, explains immediately and keeps keyboard focus in the lesson', async ({ page }) => {
  const control = await mock(page); await startLesson(page);
  await expect(page.getByRole('button', { name: 'Проверить ответ', exact: true })).toBeDisabled();
  await page.getByRole('radio', { name: 'Назвать код', exact: true }).check();
  await page.getByRole('button', { name: 'Проверить ответ', exact: true }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('group', { name: 'Как поступить с просьбой о коде?' })).toBeVisible();
  expect(control.practiceIds).toEqual([]);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Разберём ситуацию вместе' })).toBeVisible();
  await expect(page.getByText(explanations.c1, { exact: true })).toBeVisible();
  await expect(page.getByText('Признак риска:', { exact: true })).toBeVisible();
  await expect(page.getByText('Безопасный шаг:', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Материал Банка России ↗' })).toHaveAttribute('href', catalog.modules[0].cards[0].source_url!);
  await expect(page.getByRole('radio', { name: 'Назвать код', exact: true })).toBeChecked();
  await expect(page.getByRole('radio', { name: 'Завершить звонок', exact: true })).toBeDisabled();
  await expect(page.getByRole('status').filter({ has: page.getByRole('heading', { name: 'Разберём ситуацию вместе', exact: true }) })).toBeFocused();
  expect(control.practiceIds).toEqual(['c1']); expect(control.completions).toHaveLength(0);
  await page.getByRole('button', { name: 'Далее →', exact: true }).click();
  await expect(page.getByRole('group', { name: 'Где найти контакт для проверки?' })).toBeVisible();
});

test('F5 restores practice answer, feedback and next step; failed final retry keeps UUID after F5', async ({ page }) => {
  const control = await mock(page); await startLesson(page);
  await checkCard(page, 'Завершить звонок');
  await expect.poll(() => page.evaluate(key => JSON.parse(localStorage.getItem(key)!).feedback.c1?.correct, draftKey)).toBe(true);
  await page.reload();
  await expect(page.getByRole('radio', { name: 'Завершить звонок', exact: true })).toBeChecked();
  await expect(page.getByText(explanations.c1, { exact: true })).toBeVisible();
  expect(control.practiceIds).toEqual(['c1']);
  await page.getByRole('button', { name: 'Далее →', exact: true }).click();
  await checkCard(page, 'На официальном сайте');
  await page.getByRole('button', { name: 'Далее →', exact: true }).click();
  await page.getByRole('radio', { name: 'Прекратить разговор и проверить', exact: true }).check();
  control.failCompletion = true;
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.locator('#learning').getByRole('alert')).toContainText('Успешное сохранение не подтверждено');
  expect(control.completions).toHaveLength(1);
  const original = control.completions[0]; expect(original.idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
  await page.reload();
  await expect(page.getByRole('group', { name: 'Что делать с предложением оформить кредит?' })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Прекратить разговор и проверить', exact: true })).toBeChecked();
  control.failCompletion = false;
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.getByText('Занятие завершено. Прогресс сохранён.', { exact: true })).toBeVisible();
  expect(control.completions).toHaveLength(2); expect(control.completions[1]).toEqual(original);
  await expect.poll(() => page.evaluate(key => localStorage.getItem(key), draftKey)).toBeNull();
});

for (const passed of [true, false]) test(`independent quiz ${passed ? 'passes' : 'fails'} without practice answer leakage`, async ({ page }) => {
  const control = await mock(page); await reachQuiz(page);
  await expect(page.getByText(explanations.q1, { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Проверить ответ', exact: true })).toHaveCount(0);
  await page.getByRole('radio', { name: passed ? 'Прекратить разговор и проверить' : 'Оформить сразу', exact: true }).check();
  await expect(page.getByText(explanations.q1, { exact: true })).toHaveCount(0);
  expect(control.practiceIds).toEqual(['c1', 'c2']);
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.getByRole('heading', { name: `Результат: ${passed ? 3 : 2} из 3`, exact: true })).toBeVisible();
  await expect(page.getByText(passed ? 'Занятие завершено. Прогресс сохранён.' : 'Разберите объяснения и попробуйте ещё раз. Ошибаться во время учёбы нормально.', { exact: true })).toBeVisible();
  await expect(page.getByText(`Независимая проверка: ${passed ? 1 : 0} из 1. Практика не заменяет итоговое решение.`, { exact: true })).toBeVisible();
  await expect(page.getByText(explanations.q1, { exact: true })).toBeVisible();
  expect(control.practiceIds).toEqual(['c1', 'c2']);
  await page.getByRole('button', { name: 'Вернуться к темам', exact: true }).click();
  await expect(page.getByText(`${passed ? 60 : 0} учебных баллов`, { exact: true })).toBeVisible();
});

test('review repeats only mistaken practice and never awards or submits another completion', async ({ page }) => {
  const control = await mock(page); await reachQuiz(page, true);
  await page.getByRole('radio', { name: 'Прекратить разговор и проверить', exact: true }).check();
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Результат: 2 из 3', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Повторить ошибки', exact: true }).click();
  await expect(page.getByText('Повторение — без начисления баллов. Итоговую проверку можно пройти отдельно.', { exact: true })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Как поступить с просьбой о коде?' })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Назвать код', exact: true })).not.toBeChecked();
  await page.getByRole('radio', { name: 'Завершить звонок', exact: true }).check();
  await page.getByRole('button', { name: 'Проверить ответ', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Верно. Вы выбрали безопасный шаг', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Далее →', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Завершить повторение', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Выберите, что потренировать', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Выберите, что потренировать', exact: true })).toBeFocused();
  expect(control.completions).toHaveLength(1); expect(control.practiceIds).toEqual(['c1', 'c2', 'c1']);
  await expect(page.getByText('60 учебных баллов', { exact: true })).toBeVisible();
});

test('stale draft version is not applied to the current catalog', async ({ page }) => {
  const control = await mock(page);
  await page.addInitScript(({ key, currentVersion }) => localStorage.setItem(key, JSON.stringify({ schema: 1, courseVersion: `${currentVersion}.old`, moduleId: 'm8_phone_fraud', format: 'lesson', stage: 'questions', step: 1, answers: { c1: 1 }, feedback: {}, attemptKey: 'stale-attempt', updatedAt: '2026-01-01T00:00:00Z' })), { key: draftKey, currentVersion: version });
  await page.goto('/#learning');
  await expect(page.getByText('Материалы обновились. Старый черновик не применён к новым вопросам; начните занятие заново.', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Учебный материал', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Разобрать звонок', exact: true }).click();
  await page.getByRole('button', { name: 'Перейти к карточкам' }).click();
  await expect(page.getByRole('group', { name: 'Как поступить с просьбой о коде?' })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Завершить звонок', exact: true })).not.toBeChecked();
  expect(control.practiceIds).toEqual([]); expect(control.completions).toEqual([]);
});

test('storage denied leaves practice and server-confirmed completion usable', async ({ page }) => {
  await mock(page);
  await page.addInitScript(() => { for (const method of ['getItem', 'setItem', 'removeItem']) Object.defineProperty(Storage.prototype, method, { configurable: true, value() { throw new DOMException('Blocked', 'SecurityError'); } }); });
  await reachQuiz(page);
  await expect(page.getByText('Браузер не разрешил сохранить черновик. До закрытия страницы занятие доступно.', { exact: true })).toBeVisible();
  await page.getByRole('radio', { name: 'Прекратить разговор и проверить', exact: true }).check();
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.getByText('Занятие завершено. Прогресс сохранён.', { exact: true })).toBeVisible();
  await expect(page.getByText('Результат подтверждён сервером, но локальную историю обновить не удалось.', { exact: true })).toBeVisible();
});

test('503 clears after recovered backend and hash return', async ({ page }) => {
  const control = await mock(page); control.unavailable = true;
  await page.goto('/#learning');
  await expect(page.locator('#learning').getByRole('alert')).toContainText('Обучение временно недоступно');
  await page.evaluate(() => { location.hash = 'overview'; });
  await expect(page.getByRole('heading', { name: 'Обзор', exact: true })).toBeVisible();
  control.unavailable = false;
  await page.evaluate(() => { location.hash = 'learning'; });
  await expect(page.getByRole('button', { name: 'Разобрать звонок', exact: true })).toBeVisible();
  await expect(page.locator('#learning').getByRole('alert')).toHaveCount(0);
});

test('delayed progress GET cannot overwrite a later successful completion', async ({ page }) => {
  await mock(page); await reachQuiz(page);
  await page.getByRole('radio', { name: 'Прекратить разговор и проверить', exact: true }).check();
  let releaseProgress!: () => void;
  const delayed = new Promise<void>(resolve => { releaseProgress = resolve; });
  let progressRequested!: () => void;
  const requested = new Promise<void>(resolve => { progressRequested = resolve; });
  await page.route('**/api/v1/learning/progress', async route => {
    progressRequested();
    await delayed;
    await route.fulfill({ json: state() });
  });
  await page.evaluate(() => { location.hash = 'overview'; });
  await expect(page.getByRole('heading', { name: 'Обзор', exact: true })).toBeVisible();
  await page.evaluate(() => { location.hash = 'learning'; });
  await requested;
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.getByText('Занятие завершено. Прогресс сохранён.', { exact: true })).toBeVisible();
  const staleResponse = page.waitForResponse(response => response.url().endsWith('/api/v1/learning/progress'));
  releaseProgress(); await staleResponse;
  // Let the GET's JSON continuation and React commit run before inspecting catalog state.
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await page.getByRole('button', { name: 'Вернуться к темам', exact: true }).click();
  await expect(page.getByText('60 учебных баллов', { exact: true })).toBeVisible();
  await expect(page.getByText('1 / 1 тем', { exact: true })).toBeVisible();
  await expect(page.getByText('0 учебных баллов', { exact: true })).toHaveCount(0);
});

test('module removed on catalog refetch returns to usable catalog instead of blank session', async ({ page }) => {
  await mock(page); await startLesson(page);
  await expect(page.getByRole('region', { name: 'Учебный материал', exact: true })).toBeVisible();
  await page.route('**/api/v1/learning/catalog', route => route.fulfill({ json: { version: `${version}.next`, modules: [] } }));
  await page.evaluate(() => { location.hash = 'overview'; });
  await expect(page.getByRole('heading', { name: 'Обзор', exact: true })).toBeVisible();
  await page.evaluate(() => { location.hash = 'learning'; });
  await expect(page.getByRole('heading', { name: 'Выберите, что потренировать', exact: true })).toBeVisible();
  await expect(page.getByText('Тем пока нет. Попробуйте загрузить каталог позже.', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Учебный материал', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Продолжить занятие' })).toHaveCount(0);
  await expect(page.getByRole('group', { name: 'Формат обучения', exact: true })).toBeVisible();
});

for (const topic of realCatalog.modules) for (const format of ['lesson', 'quiz'] as const) {
  test(`real content ${topic.id} ${format} opens a thematic card without grading leaks`, async ({ page }) => {
    expect(realCatalog.modules).toHaveLength(8);
    expect(JSON.stringify(realCatalog)).not.toMatch(/\?{3,}|\uFFFD/);
    const practiceRequests: string[] = [];
    const completionRequests: string[] = [];
    await page.route('**/api/v1/learning/catalog', route => route.fulfill({ json: realCatalog }));
    await page.route('**/api/v1/learning/progress', route => route.fulfill({ json: state() }));
    await page.route('**/api/v1/learning/practice', route => { practiceRequests.push(route.request().postData()!); return route.fulfill({ status: 500 }); });
    await page.route('**/api/v1/learning/completions', route => { completionRequests.push(route.request().postData()!); return route.fulfill({ status: 500 }); });
    await page.goto('/#learning');
    if (format === 'quiz') await page.getByRole('button', { name: 'Тест Сразу проверьте знания', exact: true }).click();
    await page.getByRole('button').filter({ has: page.locator('strong', { hasText: topic.title }) }).click();
    if (format === 'lesson') await page.getByRole('button', { name: 'Перейти к карточкам' }).click();
    const question = format === 'quiz' ? topic.quiz[0] : topic.cards[0];
    const situation = page.getByRole('complementary', { name: 'Учебная ситуация', exact: true });
    await expect(situation).toBeVisible();
    await expect(situation).not.toContainText(/\?{3,}|\uFFFD/);
    await expect(situation).toContainText(/[А-Яа-яЁё]/);
    const artwork = situation.locator('img');
    await expect(artwork).toBeVisible();
    await expect.poll(() => artwork.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
    await expect(page.getByRole('group', { name: question.prompt, exact: true })).toBeVisible();
    await expect(page.getByRole('radio')).toHaveCount(question.options.length);
    await expect(page.getByRole('heading', { name: 'Верно. Вы выбрали безопасный шаг', exact: true })).toHaveCount(0);
    await expect(page.getByText('Признак риска:', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Безопасный шаг:', { exact: true })).toHaveCount(0);
    await page.getByRole('radio').first().check();
    // Selection alone never asks the server for a grading key or reveals feedback.
    expect(practiceRequests).toEqual([]); expect(completionRequests).toEqual([]);
    await expect(page.getByRole('heading', { name: 'Разберём ситуацию вместе', exact: true })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Материал Банка России ↗', exact: true })).toHaveCount(0);
  });
}

test('a fresh final attempt replaces the failed result using a new completion key', async ({ page }) => {
  const control = await mock(page); await reachQuiz(page);
  await page.getByRole('radio', { name: 'Оформить сразу', exact: true }).check();
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Результат: 2 из 3', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Пройти итоговый тест', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Результат:/ })).toHaveCount(0);
  await expect(page.getByText(explanations.q1, { exact: true })).toHaveCount(0);
  await expect(page.getByRole('radio', { name: 'Оформить сразу', exact: true })).not.toBeChecked();
  await page.getByRole('radio', { name: 'Прекратить разговор и проверить', exact: true }).check();
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Результат: 1 из 1', exact: true })).toBeVisible();
  await expect(page.getByText('Занятие завершено. Прогресс сохранён.', { exact: true })).toBeVisible();
  await expect(page.getByText('Разберите объяснения и попробуйте ещё раз. Ошибаться во время учёбы нормально.', { exact: true })).toHaveCount(0);
  expect(control.completions).toHaveLength(2);
  expect(control.completions[1].idempotency_key).not.toBe(control.completions[0].idempotency_key);
  expect(control.completions[1].answers).toEqual({ q1: 2 });
  expect(control.practiceIds).toEqual(['c1', 'c2']);
});

test('corrupted draft answer is rejected even when its course version matches', async ({ page }) => {
  await mock(page);
  await page.addInitScript(({ key, currentVersion }) => localStorage.setItem(key, JSON.stringify({ schema: 1, courseVersion: currentVersion, moduleId: 'm8_phone_fraud', format: 'lesson', stage: 'questions', step: 0, answers: { c1: 99 }, feedback: {}, attemptKey: 'corrupted-answer', updatedAt: '2026-01-01T00:00:00Z' })), { key: draftKey, currentVersion: version });
  await page.goto('/#learning');
  await expect(page.getByText('Не удалось восстановить черновик. Можно начать новое занятие.', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Учебный материал', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Разобрать звонок', exact: true })).toBeVisible();
});

test('inconsistent current-card draft feedback is discarded and the selected answer must be checked again', async ({ page }) => {
  const control = await mock(page);
  await page.addInitScript(({ key, currentVersion }) => localStorage.setItem(key, JSON.stringify({ schema: 1, courseVersion: currentVersion, moduleId: 'm8_phone_fraud', format: 'lesson', stage: 'questions', step: 0, answers: { c1: 0 }, feedback: { c1: { question_id: 'c1', correct: true, correct_index: 1, explanation: 'Неверно сохранённая похвала.' } }, attemptKey: 'inconsistent-feedback', updatedAt: '2026-01-01T00:00:00Z' })), { key: draftKey, currentVersion: version });
  await page.goto('/#learning');
  await expect(page.getByRole('group', { name: 'Как поступить с просьбой о коде?', exact: true })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Назвать код', exact: true })).toBeChecked();
  await expect(page.getByRole('radio', { name: 'Назвать код', exact: true })).toBeEnabled();
  await expect(page.getByText('Неверно сохранённая похвала.', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Верно. Вы выбрали безопасный шаг', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Далее →', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Проверить ответ', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Разберём ситуацию вместе', exact: true })).toBeVisible();
  await expect(page.getByText(explanations.c1, { exact: true })).toBeVisible();
  expect(control.practiceIds).toEqual(['c1']);
});

test('draft jumped to final question without earlier answers is rejected', async ({ page }) => {
  const control = await mock(page);
  await page.addInitScript(({ key, currentVersion }) => localStorage.setItem(key, JSON.stringify({ schema: 1, courseVersion: currentVersion, moduleId: 'm8_phone_fraud', format: 'lesson', stage: 'questions', step: 2, answers: { q1: 2 }, feedback: {}, attemptKey: 'missing-earlier-answers', updatedAt: '2026-01-01T00:00:00Z' })), { key: draftKey, currentVersion: version });
  await page.goto('/#learning');
  await expect(page.getByText('Не удалось восстановить черновик. Можно начать новое занятие.', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Учебный материал', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Разобрать звонок', exact: true })).toBeVisible();
  expect(control.completions).toEqual([]);
});

test('corrupted completion replay is not rendered and retry keeps its request identity', async ({ page }) => {
  const control = await mock(page); await reachQuiz(page);
  await page.getByRole('radio', { name: 'Прекратить разговор и проверить', exact: true }).check();
  const corruptedRequests: CompletionBody[] = [];
  await page.route('**/api/v1/learning/completions', route => {
    corruptedRequests.push(route.request().postDataJSON() as CompletionBody);
    return route.fulfill({ json: { progress: { ...state(), xp: 999 }, result: { score: 3, total: 3, passed: true, feedback: [{ question_id: 'q1', correct: true, explanation: '??? ????????' }] } } });
  });
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.locator('#learning').getByRole('alert')).toContainText('Получен повреждённый текст учебных материалов');
  await expect(page.locator('#learning')).not.toContainText('???');
  await expect(page.getByRole('heading', { name: /Результат:/ })).toHaveCount(0);
  await expect(page.getByRole('radio', { name: 'Прекратить разговор и проверить', exact: true })).toBeChecked();
  expect(corruptedRequests).toHaveLength(1);
  await expect.poll(() => page.evaluate(key => JSON.parse(localStorage.getItem(key)!).attemptKey, draftKey)).toBe(corruptedRequests[0].idempotency_key);
  // Remove only the corrupt replay handler; the original mock now returns readable server data.
  await page.unroute('**/api/v1/learning/completions');
  await page.route('**/api/v1/learning/completions', route => {
    const retried = route.request().postDataJSON() as CompletionBody;
    control.completions.push(retried);
    expect(retried).toEqual(corruptedRequests[0]);
    return route.fulfill({ json: { progress: { ...state(), xp: 60, completed_modules: ['m8_phone_fraud'] }, result: { score: 3, total: 3, passed: true, feedback: [{ question_id: 'q1', correct: true, explanation: explanations.q1 }] } } });
  });
  await page.getByRole('button', { name: 'Получить результат', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Результат: 3 из 3', exact: true })).toBeVisible();
  await expect(page.locator('#learning').getByRole('alert')).toHaveCount(0);
  await expect(page.getByText(explanations.q1, { exact: true })).toBeVisible();
  expect(control.completions).toHaveLength(1);
});

for (const width of [390, 1024]) for (const questionId of ['phone_c4_file', 'phone_c5_uncertainty']) {
  test(`real ${questionId} at ${width}px keeps the full call and feedback readable`, async ({ page }) => {
    const topic = sourceCourse.modules.find(item => item.id === 'm8_phone_fraud')!;
    const step = topic.cards.findIndex(card => card.id === questionId);
    expect(step).toBeGreaterThanOrEqual(0);
    const card = topic.cards[step];
    const previous = topic.cards.slice(0, step);
    const saved = { schema: 1, courseVersion: realCatalog.version, moduleId: topic.id, format: 'lesson', stage: 'questions', step,
      answers: Object.fromEntries(previous.map(item => [item.id, item.correct])),
      feedback: Object.fromEntries(previous.map(item => [item.id, { question_id: item.id, correct: true, correct_index: item.correct, explanation: item.explanation, source_needed: item.source_needed, safe_action: item.safe_action, danger_sign: item.danger_sign }])),
      attemptKey: `layout-${questionId}-${width}`, updatedAt: '2026-11-01T00:00:00Z' };
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(({ key, value }) => localStorage.setItem(key, JSON.stringify(value)), { key: draftKey, value: saved });
    await page.route('**/api/v1/learning/catalog', route => route.fulfill({ json: realCatalog }));
    await page.route('**/api/v1/learning/progress', route => route.fulfill({ json: state() }));
    let practiceCount = 0;
    await page.route('**/api/v1/learning/practice', route => {
      const body = route.request().postDataJSON();
      expect(body).toEqual({ module_id: topic.id, question_id: card.id, answer: card.correct, course_version: realCatalog.version });
      practiceCount++;
      return route.fulfill({ json: { course_version: realCatalog.version, question_id: card.id, correct: true, correct_index: card.correct, explanation: card.explanation, source_needed: card.source_needed, danger_sign: card.danger_sign, safe_action: card.safe_action } });
    });
    await page.goto('/#learning');
    const situation = page.getByRole('complementary', { name: 'Учебная ситуация', exact: true });
    const quote = situation.locator('blockquote');
    await expect(quote).toHaveText(card.scenario_text!);
    await expect(quote).toContainText(/[А-Яа-яЁё]/);
    await expect(quote).not.toContainText(/\?{2,}|\uFFFD/);
    await expect(situation.getByRole('heading', { name: 'Собеседник на линии', exact: true })).toBeVisible();
    await expect(situation.getByRole('heading', { name: 'Неизвестный номер', exact: true })).toHaveCount(0);
    if (questionId === 'phone_c5_uncertainty') await expect(quote).toContainText('знакомый номер банка');
    await page.evaluate(() => document.fonts.ready);
    await expect.poll(() => situation.locator('img').evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
    const bounds = await quote.evaluate(element => {
      const phone = element.parentElement!.parentElement!;
      const image = phone.querySelector('img')!;
      const text = element.getBoundingClientRect();
      const shell = phone.getBoundingClientRect();
      const art = image.getBoundingClientRect();
      const inside = (container: DOMRect) => text.left >= container.left - 1 && text.right <= container.right + 1 && text.top >= container.top - 1 && text.bottom <= container.bottom + 1;
      return { insidePhone: inside(shell), insideImage: inside(art), phoneHasNoClippedHeight: phone.scrollHeight <= phone.clientHeight + 1, quoteHeight: text.height };
    });
    expect(bounds.insidePhone, JSON.stringify(bounds)).toBe(true);
    expect(bounds.insideImage, JSON.stringify(bounds)).toBe(true);
    expect(bounds.phoneHasNoClippedHeight, JSON.stringify(bounds)).toBe(true);
    expect(bounds.quoteHeight).toBeGreaterThan(30);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('radio', { name: card.options[card.correct], exact: true }).check();
    await page.getByRole('button', { name: 'Проверить ответ', exact: true }).click();
    const feedback = page.getByRole('status').filter({ has: page.getByRole('heading', { name: 'Верно. Вы выбрали безопасный шаг', exact: true }) });
    await expect(feedback).toBeFocused();
    await expect(feedback.getByText(card.explanation, { exact: true })).toBeVisible();
    await expect(feedback).toContainText(card.safe_action!);
    await expect(feedback).toContainText(card.danger_sign!);
    await expect(feedback).not.toContainText(/\?{2,}|\uFFFD/);
    expect(practiceCount).toBe(1);
  });
}
