import 'server-only';

export class DemoServiceError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export function demoIdentity() {
  const token = process.env.SANDBOX_WEB_TOKEN;
  const subject = process.env.SANDBOX_WEB_SUBJECT;
  if (!token || token.length < 32 || !subject || !/^sub_[a-f0-9]{8,64}$/.test(subject))
    throw new DemoServiceError(503, 'Учебный профиль не настроен. Запустите проект по README.');
  return { token, subject };
}
export async function backend(path: string, method = 'GET', body?: unknown, authenticated = false, key?: string) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (authenticated) headers.Authorization = `Bearer ${demoIdentity().token}`;
  if (key) headers['Idempotency-Key'] = key;
  const base = (process.env.BACKEND_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, { method, headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store', signal: AbortSignal.timeout(15000) });
  } catch { throw new DemoServiceError(503, 'Сервис недоступен. Проверьте запуск backend и повторите попытку.'); }
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: 'Учебный профиль не авторизован. Проверьте серверную конфигурацию.',
      403: 'Это действие недоступно учебному профилю.', 404: 'Учебный материал или кейс не найден.',
      409: 'Запрос конфликтует с предыдущим действием или награда ещё недоступна.',
      410: 'Устаревший учебный API отключён. Используйте текущий интерфейс.',
      413: 'Учебный запрос слишком большой.', 422: 'Проверьте ответы и выбранные параметры.',
      503: 'Хранилище или сервис недоступны. Успешное сохранение не подтверждено.',
    };
    throw new DemoServiceError(response.status, messages[response.status] ?? 'Сервис отклонил запрос. Повторите попытку.');
  }
  return response.json();
}
export function rejectForeignOrigin(request: Request) {
  const origin = request.headers.get('origin');
  let allowed: string;
  try { allowed = new URL(process.env.APP_ORIGIN ?? 'http://127.0.0.1:3000').origin; }
  catch { throw new DemoServiceError(503, 'Адрес приложения не настроен.'); }
  if (origin && origin !== allowed)
    throw new DemoServiceError(403, 'Действие разрешено только со страницы приложения.');
}
export async function boundedJson(request: Request) {
  if (!request.headers.get('content-type')?.startsWith('application/json')) throw new DemoServiceError(415, 'Ожидается JSON.');
  const limit = 64 * 1024;
  if (Number(request.headers.get('content-length') ?? 0) > limit) throw new DemoServiceError(413, 'Учебный запрос слишком большой.');
  const reader = request.body?.getReader();
  if (!reader) throw new DemoServiceError(400, 'Отсутствует запрос.');
  let size = 0;
  const chunks: Uint8Array[] = [];
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > limit) { await reader.cancel(); throw new DemoServiceError(413, 'Учебный запрос слишком большой.'); }
    chunks.push(value);
  }
  try {
    const buffer = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { buffer.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder().decode(buffer));
  } catch { throw new DemoServiceError(400, 'Некорректный JSON.'); }
}
export function serviceError(error: unknown) {
  const known = error instanceof DemoServiceError;
  return Response.json({ detail: known ? error.message : 'Сервис недоступен. Повторите попытку.' },
    { status: known ? error.status : 503, headers: { 'Cache-Control': 'no-store' } });
}
