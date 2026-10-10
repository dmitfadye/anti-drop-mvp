'use client';

import { useState } from 'react';
import styles from './DemoWorkspace.module.css';

type Transaction = { id: string; user_id: string; ts: string; type: string; amount: number; counterparty: string; device_id: string; sim_changed_days_ago: number };
type Analysis = { score: number; level: 'GREEN' | 'YELLOW' | 'RED'; reasons: string[]; alert: null | { title: string; body: string; lang: string; lang_name: string } };
type Content = { stories: { title: string; text: string; emoji: string }[]; quiz: { q: string; options: string[] }[] };
type QuizResult = { score: number; total: number; cashback: number; details: { q: string; ok: boolean; explain: string }[] };
type SimResult = { ok: boolean; errors: string[]; limits: { note?: string }; checklist: string[] };
const languages = [['ru', 'Русский'], ['uz', "O‘zbekcha"], ['tg', 'Тоҷикӣ'], ['ky', 'Кыргызча'], ['en', 'English'], ['zh', '中文'], ['ar', 'العربية']];
const typeNames: Record<string, string> = { incoming_salary: 'Зарплата', purchase: 'Покупка', incoming_p2p: 'Входящий перевод', outgoing_p2p: 'Исходящий перевод', cash_withdraw: 'Снятие наличных' };
const scenarios: Record<string, [string, string, number, string][]> = {
  normal: [['09:00', 'incoming_salary', 60000, 'Работодатель'], ['12:10', 'purchase', 1200, 'Магазин'], ['18:40', 'purchase', 800, 'Аптека']],
  attack: [['13:00', 'incoming_salary', 15000, 'Работодатель'], ...[3000, 2500, 4000, 1800, 3500].map((amount, i): [string, string, number, string] => [`14:${String(2 + i * 5).padStart(2, '0')}`, 'incoming_p2p', amount, `Отправитель ${i + 1}`]), ['14:40', 'outgoing_p2p', 9000, 'Получатель'], ['14:45', 'cash_withdraw', 5000, 'Банкомат']],
};

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error('Сервис недоступен или отклонил запрос. Проверьте запуск backend и повторите попытку.');
  return response.json();
}

export function DemoWorkspace() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [lang, setLang] = useState('ru');
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [alertHidden, setAlertHidden] = useState(false);
  const [support, setSupport] = useState(false);
  const [content, setContent] = useState<Content | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [quiz, setQuiz] = useState<QuizResult | null>(null);
  const [sim, setSim] = useState<SimResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<{ section: string; message: string } | null>(null);

  async function run(section: string, action: () => Promise<void>) {
    setBusy(section); setError(null);
    try { await action(); } catch (error) { setError({ section, message: error instanceof Error ? error.message : 'Не удалось выполнить запрос. Повторите попытку.' }); }
    finally { setBusy(null); }
  }
  function loadScenario(key: string) {
    setTransactions(scenarios[key].map(([time, type, amount, counterparty], i) => ({ id: String(i), user_id: 'demo', ts: `2026-10-07 ${time}:00`, type, amount, counterparty, device_id: 'demo_device', sim_changed_days_ago: key === 'attack' ? 1 : 90 })));
    setAnalysis(null); setAlertHidden(false); setSupport(false); setError(null);
  }
  const button = styles['demo__button'];
  const primary = `${button} ${styles['demo__button--primary']}`;
  const sectionError = (section: string) => error?.section === section ? <p className={styles['demo__error']} role="alert">{error.message}</p> : null;

  return <div className={styles['demo']}>
    <section id="monitoring" className={styles['demo__section']} aria-labelledby="monitoring-title">
      <div className={styles['demo__heading']}><div><span className={styles['demo__eyebrow']}>01 / МОНИТОРИНГ</span><h2 id="monitoring-title">Проверить перевод.<br/>Понять риски.</h2></div><span className={styles['demo__tag']}>Только учебные данные</span></div>
      <p className={styles['demo__description']}>Выберите сценарий и запустите проверку. Детектор ищет транзит, переводы от разных отправителей, обналичивание и другие признаки риска.</p>
      <div className={styles['demo__toolbar']}><label className={styles['demo__field']}>Язык предупреждения<select value={lang} onChange={e => { setLang(e.target.value); setAnalysis(null); }} disabled={busy !== null}>{languages.map(([code, name]) => <option value={code} key={code}>{name}</option>)}</select></label><button className={button} disabled={busy !== null} onClick={() => loadScenario('normal')}>Обычные операции</button><button className={button} disabled={busy !== null} onClick={() => loadScenario('attack')}>Сценарий вербовщика</button><button className={primary} disabled={!transactions.length || busy !== null} onClick={() => { setAnalysis(null); setSupport(false); setAlertHidden(false); void run('monitoring', async () => setAnalysis(await request<Analysis>('analyze', { transactions, lang }))); }}>{busy === 'monitoring' ? 'Проверяем…' : 'Проверить'}</button></div>
      {sectionError('monitoring')}
      <div className={styles['demo__grid']}><article className={styles['demo__card']}><h3>Учебные транзакции</h3>{!transactions.length ? <p className={styles['demo__muted']}>Операции не загружены. Выберите один из двух сценариев выше.</p> : <div className={styles['demo__table-wrap']} tabIndex={0} aria-label="Учебные транзакции, прокручиваемая таблица"><table className={styles['demo__table']}><caption>Синтетические операции · 7 октября 2026</caption><thead><tr><th scope="col">Время</th><th scope="col">Операция</th><th scope="col">Сумма, ₽</th><th scope="col">Контрагент</th></tr></thead><tbody>{transactions.map(t => <tr key={t.id}><td>{t.ts.slice(11, 16)}</td><td>{typeNames[t.type]}</td><td>{t.amount.toLocaleString('ru-RU')}</td><td>{t.counterparty}</td></tr>)}</tbody></table></div>}</article>
      <article className={styles['demo__card']} aria-live="polite"><h3>Почему так решили</h3>{analysis ? <><span className={`${styles['demo__risk']} ${styles[`demo__risk--${analysis.level.toLowerCase()}`]}`}>{ { GREEN: 'Низкий риск', YELLOW: 'Требует внимания', RED: 'Высокий риск' }[analysis.level]} · {analysis.score}/100</span><progress className={styles['demo__progress']} value={analysis.score} max={100} aria-label="Оценка риска"/><ul>{analysis.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul><p className={styles['demo__muted']}>Оценка относится только к выбранному учебному сценарию.</p></> : <p className={styles['demo__muted']}>Проверка ещё не выполнена. Это не оценка безопасности ваших денег.</p>}</article></div>
      {analysis?.alert && !alertHidden && <article className={`${styles['demo__card']} ${styles['demo__card--alert']}`} aria-live="polite"><h3 lang={analysis.alert.lang}>{analysis.alert.title} · {analysis.alert.lang_name}</h3><p className={styles['demo__alert-text']} lang={analysis.alert.lang} dir={analysis.alert.lang === 'ar' ? 'rtl' : 'auto'}>{analysis.alert.body}</p><div className={styles['demo__toolbar']}><button className={button} onClick={() => setSupport(true)}>Поддержка — демо</button><button className={button} onClick={() => setAlertHidden(true)}>Скрыть предупреждение</button></div>{support && <p role="status">Демонстрация обращения: реальная заявка не отправлена, переводы не заблокированы. Свяжитесь с банком через его официальное приложение.</p>}</article>}
    </section>

    <section id="learning" className={styles['demo__section']} aria-labelledby="learning-title"><div className={styles['demo__heading']}><div><span className={styles['demo__eyebrow']}>02 / ОБУЧЕНИЕ</span><h2 id="learning-title">Знать, чтобы<br/>не стать участником.</h2></div></div><p className={styles['demo__description']}>Короткие истории и квиз из прежней версии. Награда 100 ₽ — учебная, деньги не начисляются.</p><button className={primary} disabled={busy !== null} onClick={() => void run('learning', async () => { setContent(await request<Content>('content')); setAnswers({}); setQuiz(null); })}>{busy === 'learning' ? 'Загружаем…' : content ? 'Загрузить обучение заново' : 'Начать обучение'}</button>{sectionError('learning')}
      {content && <><div className={styles['demo__stories']}>{content.stories.map(story => <article key={story.title} className={styles['demo__card']}><h3>{story.emoji} {story.title}</h3><p>{story.text}</p></article>)}</div><form className={styles['demo__card']} onSubmit={e => { e.preventDefault(); setQuiz(null); void run('quiz', async () => setQuiz(await request<QuizResult>('quiz', { answers: content.quiz.map((_, i) => answers[i] ?? -1) }))); }}><h3>Проверим знания</h3>{content.quiz.map((question, i) => <fieldset key={question.q} className={styles['demo__question']} disabled={busy !== null}><legend>{i + 1}. {question.q}</legend>{question.options.map((option, j) => <label key={option} className={styles['demo__option']}><input type="radio" name={`question-${i}`} value={j} checked={answers[i] === j} required onChange={() => { setAnswers({ ...answers, [i]: j }); setQuiz(null); }}/>{option}</label>)}</fieldset>)}<button className={primary} disabled={busy !== null}>{busy === 'quiz' ? 'Проверяем…' : 'Получить результат'}</button>{sectionError('quiz')}{quiz && <div role="status"><h3>Результат: {quiz.score} из {quiz.total}</h3><p>Учебная награда: {quiz.cashback} ₽. Реального начисления нет.</p>{quiz.details.map(detail => <p key={detail.q}>{detail.ok ? 'Верно' : 'Неверно'}: {detail.explain}</p>)}</div>}</form></>}
    </section>

    <section id="phone" className={styles['demo__section']} aria-labelledby="phone-title"><div className={styles['demo__heading']}><div><span className={styles['demo__eyebrow']}>03 / СМЕНА НОМЕРА</span><h2 id="phone-title">Два подтверждения.<br/>Один безопасный шаг.</h2></div></div><p className={styles['demo__description']}>Учебная проверка подтверждений старого и нового номеров. SMS не отправляются, номер в банке не меняется. Используйте вымышленные номера.</p><form className={styles['demo__card']} onChange={() => setSim(null)} onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); setSim(null); void run('phone', async () => setSim(await request<SimResult>('sim', { old_phone: data.get('old_phone'), new_phone: data.get('new_phone'), otp_ok_old: data.has('otp_old'), otp_ok_new: data.has('otp_new') }))); }}><div className={styles['demo__toolbar']}><label className={styles['demo__field']}>Старый номер<input type="tel" name="old_phone" defaultValue="+79160000001" required disabled={busy !== null}/></label><label className={styles['demo__field']}>Новый номер<input type="tel" name="new_phone" defaultValue="+79160000002" required disabled={busy !== null}/></label></div><label className={styles['demo__option']}><input type="checkbox" name="otp_old" disabled={busy !== null}/>Имитировать SMS-код со старого номера</label><label className={styles['demo__option']}><input type="checkbox" name="otp_new" disabled={busy !== null}/>Имитировать SMS-код с нового номера</label><button className={primary} disabled={busy !== null}>{busy === 'phone' ? 'Проверяем…' : 'Проверить смену номера'}</button>{sectionError('phone')}{sim && <div role="status">{sim.ok ? <><h3>Демонстрация: подтверждения приняты</h3><p>Реальный номер не изменён.</p><p>{sim.limits.note}</p>{sim.checklist.map(item => <p key={item}>{item}</p>)}</> : <><h3>Смена не разрешена</h3><ul>{sim.errors.map(item => <li key={item}>{item}</li>)}</ul></>}</div>}</form></section>
  </div>;
}
