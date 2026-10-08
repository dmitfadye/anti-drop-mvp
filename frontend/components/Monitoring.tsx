'use client';
import { useState } from 'react';
import { Transactions, demoEvents } from './Transactions';
import { Icon } from './Icon';
import { request } from './api';
import styles from './Workspace.module.css';
type Transaction = {
  id: string;
  user_id: string;
  ts: string;
  type: string;
  amount: number;
  counterparty: string;
  device_id: string;
  sim_changed_days_ago: number;
};
type Analysis = {
  score: number;
  level: 'GREEN' | 'YELLOW' | 'RED';
  reasons: string[];
  alert: null | {
    title: string;
    body: string;
    lang: string;
    lang_name: string;
  };
};
const scenarios: Record<string, [string, string, number, string][]> = {
  normal: [
    ['09:00', 'incoming_salary', 60000, 'Работодатель'],
    ['12:10', 'purchase', 1200, 'Магазин'],
    ['18:40', 'purchase', 800, 'Аптека'],
  ],
  attack: [
    ['13:00', 'incoming_salary', 15000, 'Работодатель'],
    ...[3000, 2500, 4000, 1800, 3500].map(
      (amount, i): [string, string, number, string] => [
        `14:${String(2 + i * 5).padStart(2, '0')}`,
        'incoming_p2p',
        amount,
        `Отправитель ${i + 1}`,
      ],
    ),
    ['14:40', 'outgoing_p2p', 9000, 'Получатель'],
    ['14:45', 'cash_withdraw', 5000, 'Банкомат'],
  ],
};
const typeNames: Record<string, string> = {
  incoming_salary: 'Зарплата',
  purchase: 'Покупка',
  incoming_p2p: 'Входящий перевод',
  outgoing_p2p: 'Исходящий перевод',
  cash_withdraw: 'Снятие наличных',
};
const languages = [
  ['ru', 'Русский'],
  ['uz', 'O‘zbekcha'],
  ['tg', 'Тоҷикӣ'],
  ['ky', 'Кыргызча'],
  ['en', 'English'],
  ['zh', '中文'],
  ['ar', 'العربية'],
];
export function Monitoring() {
  const [draft, setDraft] = useState({ period: '7', type: 'all', risk: 'all' });
  const [filters, setFilters] = useState(draft);
  const [page, setPage] = useState(1);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [lang, setLang] = useState('ru');
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [alertHidden, setAlertHidden] = useState(false);
  const [support, setSupport] = useState(false);
  const filtered = demoEvents.filter(
    (e) =>
      (filters.period !== '1' || e.day === 7) &&
      (filters.type === 'all' || filters.type === e.type) &&
      (filters.risk === 'all' || filters.risk === e.risk),
  );
  const pages = Math.max(1, Math.ceil(filtered.length / 5));
  function loadScenario(key: string) {
    setTransactions(
      scenarios[key].map(([time, type, amount, counterparty], i) => ({
        id: String(i),
        user_id: 'demo',
        ts: `2026-10-07 ${time}:00`,
        type,
        amount,
        counterparty,
        device_id: 'demo_device',
        sim_changed_days_ago: key === 'attack' ? 1 : 90,
      })),
    );
    setAnalysis(null);
    setAlertHidden(false);
    setSupport(false);
    setError('');
  }
  async function analyze() {
    setBusy(true);
    setError('');
    setAnalysis(null);
    setSupport(false);
    setAlertHidden(false);
    try {
      setAnalysis(await request<Analysis>('analyze', { transactions, lang }));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Не удалось проверить операции.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      id="monitoring"
      className={styles['workspace']}
      aria-labelledby="monitoring-title"
    >
      <header className={styles['workspace__heading']}>
        <h1 id="monitoring-title">Мониторинг</h1>
        <p>Проверка переводов и анализ подозрительной активности</p>
      </header>
      <form
        className={styles['workspace__filters']}
        onSubmit={(e) => {
          e.preventDefault();
          setFilters(draft);
          setPage(1);
        }}
      >
        <label className={styles['workspace__field']}>
          Период
          <select
            aria-label="Период"
            value={draft.period}
            onChange={(e) => setDraft({ ...draft, period: e.target.value })}
          >
            <option value="7">Последние 7 дней</option>
            <option value="1">Последний день</option>
            <option value="30">Последние 30 дней</option>
          </select>
        </label>
        <label className={styles['workspace__field']}>
          Тип операции
          <select
            aria-label="Тип операции"
            value={draft.type}
            onChange={(e) => setDraft({ ...draft, type: e.target.value })}
          >
            <option value="all">Все операции</option>
            <option value="incoming">Входящие переводы</option>
            <option value="outgoing">Исходящие переводы</option>
            <option value="request">Запросы перевода</option>
            <option value="purchase">Покупки</option>
          </select>
        </label>
        <label className={styles['workspace__field']}>
          Уровень риска
          <select
            aria-label="Уровень риска"
            value={draft.risk}
            onChange={(e) => setDraft({ ...draft, risk: e.target.value })}
          >
            <option value="all">Все уровни</option>
            <option value="low">Низкий</option>
            <option value="medium">Средний</option>
            <option value="high">Высокий</option>
          </select>
        </label>
        <button className={styles['workspace__primary']}>Применить</button>
      </form>
      <div className={styles['workspace__table']}>
        <Transactions events={filtered.slice((page - 1) * 5, page * 5)} />
      </div>
      <nav
        className={styles['workspace__pagination']}
        aria-label="Страницы операций"
      >
        <button
          aria-label="Предыдущая страница"
          disabled={page === 1}
          onClick={() => setPage(page - 1)}
        >
          ‹
        </button>
        {Array.from({ length: pages }, (_, i) => (
          <button
            key={i}
            aria-current={page === i + 1 ? 'page' : undefined}
            onClick={() => setPage(i + 1)}
          >
            {i + 1}
          </button>
        ))}
        <button
          aria-label="Следующая страница"
          disabled={page === pages}
          onClick={() => setPage(page + 1)}
        >
          ›
        </button>
      </nav>
      <p className={styles['workspace__caption']}>
        Синтетические операции · 1–7 октября 2026 · банковские счета не
        подключены.
      </p>
      <details className={styles['workspace__simulation']}>
        <summary>
          <Icon name="shield" />
          Проверить учебный сценарий<span>Антифрод-демонстрация</span>
        </summary>
        <p>
          Выберите сценарий и запустите существующий детектор. Оценка относится
          только к учебным операциям.
        </p>
        <div className={styles['workspace__toolbar']}>
          <label className={styles['workspace__field']}>
            Язык предупреждения
            <select
              value={lang}
              disabled={busy}
              onChange={(e) => {
                setLang(e.target.value);
                setAnalysis(null);
              }}
            >
              {languages.map(([code, name]) => (
                <option value={code} key={code}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <button
            className={styles['workspace__button']}
            disabled={busy}
            onClick={() => loadScenario('normal')}
          >
            Обычные операции
          </button>
          <button
            className={styles['workspace__button']}
            disabled={busy}
            onClick={() => loadScenario('attack')}
          >
            Сценарий вербовщика
          </button>
          <button
            className={styles['workspace__primary']}
            disabled={!transactions.length || busy}
            onClick={() => void analyze()}
          >
            {busy ? 'Проверяем…' : 'Проверить'}
          </button>
        </div>
        {error && (
          <p className={styles['workspace__error']} role="alert">
            {error}
          </p>
        )}
        {!!transactions.length && (
          <div className={styles['workspace__table-scroll']}>
            <table className={styles['workspace__data-table']}>
              <caption>Учебные транзакции</caption>
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Операция</th>
                  <th>Сумма, ₽</th>
                  <th>Контрагент</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id}>
                    <td>{t.ts.slice(11, 16)}</td>
                    <td>{typeNames[t.type]}</td>
                    <td>{t.amount.toLocaleString('ru-RU')}</td>
                    <td>{t.counterparty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {analysis && (
          <article className={styles['workspace__finding']} aria-live="polite">
            <h2>Почему так решили</h2>
            <strong>
              {
                {
                  GREEN: 'Низкий риск',
                  YELLOW: 'Требует внимания',
                  RED: 'Высокий риск',
                }[analysis.level]
              }{' '}
              · {analysis.score}/100
            </strong>
            <progress
              value={analysis.score}
              max={100}
              aria-label="Оценка риска"
            />
            <ul>
              {analysis.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </article>
        )}
        {analysis?.alert && !alertHidden && (
          <article className={styles['workspace__alert']}>
            <h3 lang={analysis.alert.lang}>
              {analysis.alert.title} · {analysis.alert.lang_name}
            </h3>
            <p
              lang={analysis.alert.lang}
              dir={analysis.alert.lang === 'ar' ? 'rtl' : 'auto'}
            >
              {analysis.alert.body}
            </p>
            <div className={styles['workspace__toolbar']}>
              <button
                className={styles['workspace__button']}
                onClick={() => setSupport(true)}
              >
                Поддержка — демо
              </button>
              <button
                className={styles['workspace__button']}
                onClick={() => setAlertHidden(true)}
              >
                Скрыть предупреждение
              </button>
            </div>
            {support && (
              <p role="status">
                Демонстрация обращения: реальная заявка не отправлена, переводы
                не заблокированы. Свяжитесь с банком через его официальное
                приложение.
              </p>
            )}
          </article>
        )}
      </details>
    </section>
  );
}
