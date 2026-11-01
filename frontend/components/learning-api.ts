export type LearningFormat = 'quiz' | 'lesson' | 'article';
export type LearningQuestion = { id: string; prompt: string; options: string[]; source_needed?: boolean; scenario_type?: 'call' | 'message'; scenario_text?: string; learning_goal?: string; difficulty?: string; source_url?: string; content_version?: string };
export type LearningModule = { id: string; title: string; summary: string; minutes: number; article: string[]; cards: LearningQuestion[]; quiz: LearningQuestion[] };
export type LearningProgress = { xp: number; rank: { id: string; title: string; min_xp: number }; next_rank: { id: string; title: string; min_xp: number } | null; points_to_next: number; rank_progress_percent: number; streak_days: number; last_completed_date: string | null; completed_modules: string[]; rewards: { days: number; title: string; points: number; unlocked: boolean; selected_category?: string | null }[]; percentile: number | null; rank_note: string; categories: { id: string; title: string }[]; demo: boolean };
export type LearningCatalog = { version: string; modules: LearningModule[] };
export type PracticeFeedback = { question_id: string; correct: boolean; correct_index: number; explanation: string; source_needed?: boolean; safe_action?: string; danger_sign?: string };
export type LearningResult = { score: number; total: number; passed: boolean; assessment_score?: number; assessment_total?: number; feedback: { question_id: string; correct: boolean; explanation: string; source_needed?: boolean }[] };
export class LearningApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export function hasBrokenLearningText(value: unknown): boolean {
  if (typeof value === 'string') return !/^https?:\/\//.test(value) && /\?{2,}|\uFFFD/.test(value);
  if (Array.isArray(value)) return value.some(hasBrokenLearningText);
  if (value && typeof value === 'object') return Object.values(value).some(hasBrokenLearningText);
  return false;
}
export async function learningRequest<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/learning/${path}`, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(15000), cache: 'no-store' });
  } catch { throw new LearningApiError(0, 'Нет соединения с обучением. Ответы сохранены в этом браузере. Попробуйте ещё раз.'); }
  if (!response.ok) {
    const messages: Record<number, string> = { 401: 'Учебный профиль не авторизован. Проверьте настройку стенда.', 409: 'Материалы изменились или запрос конфликтует с предыдущим. Обновите каталог; черновик сохранён.', 422: 'Не удалось проверить ответы. Убедитесь, что все вопросы заполнены.', 503: 'Обучение временно недоступно. Успешное сохранение не подтверждено. Повторите попытку.' };
    throw new LearningApiError(response.status, messages[response.status] ?? 'Не удалось сохранить или загрузить обучение. Повторите попытку.');
  }
  const data: unknown = await response.json();
  if (hasBrokenLearningText(data)) throw new LearningApiError(502, 'Получен повреждённый текст учебных материалов. Обновите каталог и начните занятие заново.');
  return data as T;
}
