import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';

function assertReadableContent(value: unknown, path = 'response') {
  if (typeof value === 'string') {
    expect(value, path).not.toMatch(/\?{3,}|\uFFFD/);
  } else if (Array.isArray(value)) {
    value.forEach((item, index) => assertReadableContent(item, `${path}[${index}]`));
  } else if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value)) assertReadableContent(item, `${path}.${key}`);
  }
}

test('BFF allows only supported paths, same-origin JSON and bounded bodies', async ({ request, baseURL }) => {
  expect((await request.get('/api/not-an-allowed-route')).status()).toBe(404);
  const foreign = await request.post('/api/demo/sandbox', {
    headers: { Origin: 'https://foreign.example' },
    data: { action: 'analyze', scenario: 'normal' },
  });
  expect(foreign.status()).toBe(403);
  const large = await request.post('/api/v1/learning/completions', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { module_id: 'invalid', answers: 'x'.repeat(64 * 1024) },
  });
  expect(large.status()).toBe(413);
  expect((await request.post('/api/analyze', {
    headers: { 'Content-Type': 'text/plain' }, data: '{}',
  })).status()).toBe(415);
});

test('BFF persists matching legacy/strict fixtures and idempotent owned cases', async ({ request, baseURL }) => {
  const headers = { Origin: new URL(baseURL!).origin };
  for (const [scenario, level, score] of [['normal', 'GREEN', 0], ['attack', 'RED', 85]] as const) {
    const response = await request.post('/api/demo/sandbox', {
      headers, data: { action: 'analyze', scenario, lang: 'ru' },
    });
    expect(response.status()).toBe(200);
    const analysis = await response.json();
    expect(analysis.level).toBe(level);
    expect(analysis.score).toBe(score);
    expect(analysis.evaluation_id).toMatch(/^[a-f0-9]{64}$/);
    expect(response.headers()['cache-control']).toContain('no-store');
    const body = { action: 'create', evaluation_id: analysis.evaluation_id, lang: 'ru', idempotency_key: randomUUID() };
    const first = await request.post('/api/demo/sandbox', { headers, data: body });
    expect(first.status()).toBe(201);
    const saved = await first.json();
    expect(saved.case_id).toMatch(/^[a-f0-9-]{36}$/);
    const replay = await request.post('/api/demo/sandbox', { headers, data: body });
    expect(replay.status()).toBe(201);
    expect(await replay.json()).toEqual(saved);
    const conflict = await request.post('/api/demo/sandbox', { headers, data: { ...body, lang: 'en' } });
    expect(conflict.status()).toBe(409);
    const read = await request.get(`/api/demo/sandbox?case_id=${saved.case_id}`);
    expect(read.status()).toBe(200);
    expect(await read.json()).toEqual(saved);
    expect(saved.sandbox).toBe(true);
  }
});

test('browser receives public questions and progress without server credentials', async ({ page, request }) => {
  const catalog = await request.get('/api/v1/learning/catalog');
  expect(catalog.status()).toBe(200);
  const data = await catalog.json();
  assertReadableContent(data);
  expect(data.modules.map((module: { id: string }) => module.id)).toEqual([
    'm1_safe_transfers', 'm2_asked_forward', 'm3_unexpected', 'm4_normal_vs_suspicious',
    'm5_bank_warning', 'm6_digital_hygiene', 'm7_contact_bank', 'm8_phone_fraud',
  ]);
  for (const lesson of data.modules) {
    for (const question of [...lesson.cards, ...lesson.quiz]) {
      expect(question).not.toHaveProperty('correct');
      expect(question).not.toHaveProperty('explanation');
    }
  }
  // Browser-supplied identity is ignored; the BFF authenticates its configured demo profile.
  const spoof = await request.get('/api/v1/learning/progress', {
    headers: { Authorization: 'Bearer attacker-supplied', 'X-Sandbox-Subject': 'sub_ffffffff' },
  });
  expect(spoof.status()).toBe(200);
  const captured: { headers: Record<string, string>; body: string }[] = [];
  page.on('request', r => {
    if (r.url().includes('/api/')) captured.push({ headers: r.headers(), body: r.postData() ?? '' });
  });
  await page.goto('/');
  const progress = await page.evaluate(async () => {
    const response = await fetch('/api/v1/learning/progress');
    return { status: response.status, text: await response.text() };
  });
  expect(progress.status).toBe(200);
  expect(captured.length).toBeGreaterThan(0);
  for (const r of captured) {
    expect(r.headers).not.toHaveProperty('authorization');
    expect(r.headers).not.toHaveProperty('x-sandbox-subject');
    for (const secret of [process.env.SANDBOX_WEB_TOKEN, process.env.SANDBOX_WEB_SUBJECT].filter(Boolean) as string[]) {
      expect(r.body).not.toContain(secret);
      expect(progress.text).not.toContain(secret);
    }
  }
});

test('actual m8 remote-access and insufficient-information practice remain readable and quiz stays private', async ({ request, baseURL }) => {
  const catalogResponse = await request.get('/api/v1/learning/catalog');
  expect(catalogResponse.status()).toBe(200);
  const catalog = await catalogResponse.json();
  assertReadableContent(catalog);
  const topic = catalog.modules.find((item: { id: string }) => item.id === 'm8_phone_fraud');
  expect(topic).toBeTruthy();
  const headers = { Origin: new URL(baseURL!).origin };
  for (const [questionId, correctAnswer] of [['phone_c4_file', 1], ['phone_c5_uncertainty', 2]] as const) {
    const card = topic.cards.find((item: { id: string }) => item.id === questionId);
    expect(card).toBeTruthy();
    expect(card.scenario_text.length).toBeGreaterThan(30);
    expect(card.prompt.length).toBeGreaterThan(15);
    for (const answer of [correctAnswer, 0]) {
      const response = await request.post('/api/v1/learning/practice', { headers, data: { module_id: topic.id, question_id: questionId, answer, course_version: catalog.version } });
      expect(response.status()).toBe(200);
      const feedback = await response.json();
      assertReadableContent(feedback);
      expect(feedback.question_id).toBe(questionId);
      expect(feedback.correct_index).toBe(correctAnswer);
      expect(feedback.correct).toBe(answer === correctAnswer);
      expect(feedback.explanation.length).toBeGreaterThan(30);
      expect(feedback.safe_action.length).toBeGreaterThan(20);
      expect(feedback.danger_sign.length).toBeGreaterThan(20);
      expect(feedback.course_version).toBe(catalog.version);
    }
  }
  const rejectedQuiz = await request.post('/api/v1/learning/practice', { headers, data: { module_id: topic.id, question_id: topic.quiz[0].id, answer: 0, course_version: catalog.version } });
  expect(rejectedQuiz.status()).toBe(404);
  const rejectedBody = await rejectedQuiz.json();
  expect(rejectedBody).not.toHaveProperty('correct_index');
  expect(rejectedBody).not.toHaveProperty('explanation');
});
