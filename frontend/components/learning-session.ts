import type { LearningCatalog, LearningFormat, LearningModule, PracticeFeedback } from './learning-api';
import { hasBrokenLearningText } from './learning-api';
export const draftKey = 'antidrop-learning-session-v1';
export const historyKey = 'antidrop-learning-attempts-v1';
export type LearningSession = { schema: 1; courseVersion: string; moduleId: string; format: LearningFormat; stage: 'intro' | 'questions'; step: number; answers: Record<string, number>; feedback: Record<string, PracticeFeedback>; attemptKey: string; updatedAt: string };
export type AttemptSummary = { id: string; moduleId: string; courseVersion: string; format: LearningFormat; completedAt: string; passed: boolean; score: number; total: number; mistakes: string[] };
export function questionsFor(module: LearningModule, format: LearningFormat) {
  return format === 'quiz' ? module.quiz : format === 'article' ? module.cards.slice(0, 1) : [...module.cards, ...module.quiz];
}
export function newSession(module: LearningModule, format: LearningFormat, version: string): LearningSession {
  return { schema: 1, courseVersion: version, moduleId: module.id, format, stage: format === 'quiz' ? 'questions' : 'intro', step: 0, answers: {}, feedback: {}, attemptKey: crypto.randomUUID(), updatedAt: new Date().toISOString() };
}
export function readDraft(catalog: LearningCatalog): { session: LearningSession | null; message: string } {
  try {
    const raw = localStorage.getItem(draftKey);
    if (!raw) return { session: null, message: '' };
    const value = JSON.parse(raw) as LearningSession;
    if (value.courseVersion !== catalog.version) return { session: null, message: 'Материалы обновились. Старый черновик не применён к новым вопросам; начните занятие заново.' };
    const topic = catalog.modules.find(item => item.id === value.moduleId);
    if (!topic || value.schema !== 1 || !['quiz', 'lesson', 'article'].includes(value.format) || !['intro', 'questions'].includes(value.stage) || !Number.isInteger(value.step) || typeof value.attemptKey !== 'string' || !/^[A-Za-z0-9._:-]{1,128}$/.test(value.attemptKey) || !value.answers || typeof value.answers !== 'object' || Array.isArray(value.answers)) throw new Error('invalid');
    const questions = questionsFor(topic, value.format);
    if (value.step < 0 || value.step >= questions.length || (value.stage === 'intro' && value.step !== 0)) throw new Error('invalid');
    for (const [id, answer] of Object.entries(value.answers)) {
      const question = questions.find(item => item.id === id);
      if (!question || !Number.isInteger(answer) || answer < 0 || answer >= question.options.length) throw new Error('invalid');
    }
    const feedback: Record<string, PracticeFeedback> = {};
    if (value.feedback && typeof value.feedback === 'object') for (const question of topic.cards) {
      const item = value.feedback[question.id];
      if (item && item.question_id === question.id && typeof item.correct === 'boolean' && typeof item.explanation === 'string' && !hasBrokenLearningText(item) && Number.isInteger(item.correct_index) && item.correct_index >= 0 && item.correct_index < question.options.length && value.answers[question.id] !== undefined && item.correct === (value.answers[question.id] === item.correct_index)) feedback[question.id] = {
        question_id: question.id, correct: item.correct, correct_index: item.correct_index,
        explanation: item.explanation, source_needed: item.source_needed === true,
        ...(typeof item.safe_action === 'string' ? { safe_action: item.safe_action } : {}),
        ...(typeof item.danger_sign === 'string' ? { danger_sign: item.danger_sign } : {}),
      };
    }
    if (value.stage === 'questions') for (const previous of questions.slice(0, value.step)) {
      if (value.answers[previous.id] === undefined || (value.format === 'lesson' && topic.cards.some(card => card.id === previous.id) && !feedback[previous.id])) throw new Error('invalid');
    }
    return { session: { ...value, feedback }, message: 'Занятие восстановлено. Продолжайте с сохранённого шага.' };
  } catch { return { session: null, message: 'Не удалось восстановить черновик. Можно начать новое занятие.' }; }
}
export function readHistory(): AttemptSummary[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(historyKey) ?? '[]');
    return Array.isArray(value) ? value.filter(item => item && typeof item.id === 'string' && typeof item.moduleId === 'string' && typeof item.courseVersion === 'string' && ['quiz', 'lesson', 'article'].includes(item.format) && typeof item.passed === 'boolean' && Number.isInteger(item.score) && Number.isInteger(item.total) && item.score >= 0 && item.total >= item.score && Array.isArray(item.mistakes) && item.mistakes.every((id: unknown) => typeof id === 'string')).slice(0, 20) : [];
  } catch { return []; }
}
