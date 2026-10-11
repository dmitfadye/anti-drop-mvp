import { createHash } from 'node:crypto';
import { backend, boundedJson, demoIdentity, DemoServiceError, rejectForeignOrigin, serviceError } from '../../../../lib/demo-backend';

export const dynamic = 'force-dynamic';
const ref = (prefix: string, value: string) => `${prefix}_${createHash('sha256').update(value).digest('hex').slice(0, 16)}`;
const languages = new Set(['ru', 'en', 'uz', 'tg', 'ky', 'zh', 'ar']);
function fixture(scenario: string) {
  const { subject } = demoIdentity();
  const attack = scenario === 'attack';
  const rows: [string, string, number, string][] = attack ? [
    ['13:00', 'incoming_salary', 15000, 'Работодатель'],
    ...[3000, 2500, 4000, 1800, 3500].map((amount, i): [string, string, number, string] =>
      [`14:${String(2 + i * 5).padStart(2, '0')}`, 'incoming_p2p', amount, `Отправитель ${i + 1}`]),
    ['14:40', 'outgoing_p2p', 9000, 'Получатель'], ['14:45', 'cash_withdraw', 5000, 'Банкомат'],
  ] : [['09:00', 'incoming_salary', 60000, 'Работодатель'], ['12:10', 'purchase', 1200, 'Магазин'], ['18:40', 'purchase', 800, 'Аптека']];
  const analysis_at = `2026-10-07T${attack ? '14:45' : '18:40'}:00+03:00`;
  const transactions = rows.map(([time, type, amount, counterparty], i) => ({
    id: String(i), user_id: subject, ts: `2026-10-07T${time}:00+03:00`, type, amount, counterparty,
    device_id: ref('dev', 'demo-device'), sim_changed_days_ago: attack ? 1 : 90,
  }));
  const snapshot = {
    schema_version: 'RiskSnapshotV1', subject_ref: subject, analysis_at, source_type: 'synthetic',
    timezone_policy: 'normalize_to_utc', metadata: { dataset_version: 'web-demo-v1', label_source: 'synthetic_placeholder', episode_class: attack ? 'risk' : 'normal' },
    transactions: transactions.map(t => ({
      event_id: ref('evt', `${scenario}:${t.id}`), occurred_at: t.ts,
      direction: t.type.startsWith('incoming') ? 'in' : 'out',
      type: t.type.includes('p2p') ? 'transfer' : t.type === 'incoming_salary' ? 'salary' : t.type === 'cash_withdraw' ? 'cash_withdrawal' : 'other',
      amount_minor: t.amount * 100, currency: 'RUB', counterparty_ref: ref('cp', t.counterparty),
      device_id: t.device_id, sim_changed_days_ago: t.sim_changed_days_ago,
    })),
  };
  return { transactions, snapshot, analysis_at };
}
export async function POST(request: Request) {
  try {
    rejectForeignOrigin(request);
    const body = await boundedJson(request);
    if (!body || typeof body !== 'object' || Array.isArray(body)) throw new DemoServiceError(422, 'Некорректное действие.');
    const lang = body.lang ?? 'ru';
    if (!languages.has(lang)) throw new DemoServiceError(422, 'Неизвестный язык.');
    if (body.action === 'analyze') {
      if (!['normal', 'attack'].includes(body.scenario)) throw new DemoServiceError(422, 'Выберите учебный сценарий.');
      const data = fixture(body.scenario);
      const analysis = await backend('/api/analyze', 'POST', { transactions: data.transactions, analysis_at: data.analysis_at, lang });
      const decision = await backend('/sandbox/evaluations', 'POST', data.snapshot, true);
      if (analysis.score !== decision.score || analysis.level !== decision.level)
        throw new DemoServiceError(503, 'Контракты анализа не согласованы. Сохранение кейса не подтверждено.');
      return Response.json({ ...analysis, evaluation_id: decision.evaluation_id }, { headers: { 'Cache-Control': 'no-store' } });
    }
    if (body.action === 'create' && /^[a-f0-9]{64}$/.test(body.evaluation_id ?? '') && /^[A-Za-z0-9._:-]{1,128}$/.test(body.idempotency_key ?? '')) {
      const result = await backend('/sandbox/cases', 'POST', {
        evaluation_id: body.evaluation_id, selected_language: lang, contact_reason: 'explain_risk',
      }, true, body.idempotency_key);
      return Response.json(result, { status: 201, headers: { 'Cache-Control': 'no-store' } });
    }
    throw new DemoServiceError(422, 'Некорректное действие или идентификатор.');
  } catch (error) { return serviceError(error); }
}
export async function GET(request: Request) {
  try {
    const id = new URL(request.url).searchParams.get('case_id');
    if (!id || !/^[a-f0-9-]{36}$/.test(id)) throw new DemoServiceError(422, 'Некорректный идентификатор кейса.');
    return Response.json(await backend(`/sandbox/cases/${id}`, 'GET', undefined, true), { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) { return serviceError(error); }
}
