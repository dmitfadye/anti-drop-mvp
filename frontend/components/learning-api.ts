export type LearningFormat = 'quiz' | 'lesson' | 'article';
export type LearningQuestion = { id: string; prompt: string; options: string[] };
export type LearningModule = { id: string; title: string; summary: string; minutes: number; article: string[]; cards: LearningQuestion[]; quiz: LearningQuestion[] };
export type LearningProgress = { xp: number; rank: { id: string; title: string; min_xp: number }; next_rank: { id: string; title: string; min_xp: number } | null; points_to_next: number; rank_progress_percent: number; streak_days: number; last_completed_date: string | null; completed_modules: string[]; rewards: { days: number; title: string; points: number; unlocked: boolean; selected_category?: string | null }[]; percentile: number | null; rank_note: string; categories: { id: string; title: string }[]; demo: boolean };
export type LearningResult = { score: number; total: number; passed: boolean; feedback: { question_id: string; correct: boolean; explanation: string; source_needed?: boolean }[] };
export async function learningRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1/learning/${path}`, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(15000), cache: 'no-store' });
  if (!response.ok) throw new Error('Не удалось сохранить или загрузить обучение. Проверьте соединение и повторите попытку.');
  return response.json();
}
