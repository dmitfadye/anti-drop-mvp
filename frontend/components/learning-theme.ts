import type { IconName } from './Icon';
type LearningTheme = { title: string; label: string; asset: string; color: 'blue' | 'cyan' | 'mint' | 'violet' | 'amber'; icon: IconName };
const themes: Record<string, LearningTheme> = {
  m1_safe_transfers: { title: 'У каждого перевода есть контекст', label: 'Безопасные переводы', asset: 'transfers', color: 'blue', icon: 'shield' },
  m2_asked_forward: { title: 'Что скрывается за просьбой?', label: 'Сообщения и просьбы', asset: 'messages', color: 'violet', icon: 'file' },
  m3_unexpected: { title: 'Неожиданно — не значит безопасно', label: 'Неожиданный перевод', asset: 'transfers', color: 'cyan', icon: 'arrow' },
  m4_normal_vs_suspicious: { title: 'Замечайте детали, а не ярлыки', label: 'Разбираем признаки', asset: 'safety-shield', color: 'mint', icon: 'search' },
  m5_bank_warning: { title: 'Предупреждение — повод проверить', label: 'Без паники', asset: 'messages', color: 'amber', icon: 'warning' },
  m6_digital_hygiene: { title: 'Доступ остаётся только у вас', label: 'Цифровая безопасность', asset: 'security', color: 'blue', icon: 'lock' },
  m7_contact_bank: { title: 'Выбирайте независимый канал', label: 'Связь с банком', asset: 'support', color: 'mint', icon: 'help' },
  m8_phone_fraud: { title: 'Сделайте паузу перед решением', label: 'Звонки под давлением', asset: 'messages', color: 'blue', icon: 'phone' },
};
export function learningTheme(id: string): LearningTheme {
  return themes[id] ?? { title: 'Посмотрите на ситуацию внимательнее', label: 'Практика решений', asset: 'safety-shield', color: 'blue', icon: 'shield' };
}
