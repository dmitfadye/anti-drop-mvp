'use client';
import { useState } from 'react';
import { Icon } from './Icon';
import styles from './Transactions.module.css';

export type DemoEvent = {
  id: number;
  day: number;
  time: string;
  type: string;
  counterparty: string;
  description: string;
  amount: number | null;
  risk: 'low' | 'medium' | 'high';
  status: string;
  reason: string;
};
export const demoEvents: DemoEvent[] = [
  {
    id: 1,
    day: 7,
    time: '14:23',
    type: 'incoming',
    counterparty: 'Максим С.',
    description: 'Входящий перевод',
    amount: 15000,
    risk: 'low',
    status: 'Проверен',
    reason: 'В учебном примере нет необычной последовательности переводов.',
  },
  {
    id: 2,
    day: 6,
    time: '19:02',
    type: 'outgoing',
    counterparty: 'СберБанк',
    description: 'Перевод на карту',
    amount: -8500,
    risk: 'medium',
    status: 'Требует внимания',
    reason: 'Перед отправкой проверьте получателя и назначение перевода.',
  },
  {
    id: 3,
    day: 5,
    time: '11:46',
    type: 'request',
    counterparty: 'Telegram',
    description: 'Запрос перевода',
    amount: null,
    risk: 'high',
    status: 'Заблокирован · демо',
    reason:
      'Срочная просьба в мессенджере. Свяжитесь с человеком другим способом. Реальная блокировка не выполнялась.',
  },
  {
    id: 4,
    day: 4,
    time: '18:10',
    type: 'incoming',
    counterparty: 'Неизвестный',
    description: 'Входящий перевод',
    amount: 3000,
    risk: 'medium',
    status: 'Проверен',
    reason:
      'Не переводите неожиданное поступление по реквизитам из сообщения. Обратитесь в банк.',
  },
  {
    id: 5,
    day: 3,
    time: '16:24',
    type: 'outgoing',
    counterparty: 'Алексей П.',
    description: 'Перевод на карту',
    amount: -12000,
    risk: 'low',
    status: 'Проверен',
    reason:
      'Обычная операция в учебном наборе. Это не оценка реального получателя.',
  },
  {
    id: 6,
    day: 2,
    time: '12:37',
    type: 'purchase',
    counterparty: 'Маркетплейс',
    description: 'Покупка',
    amount: -2490,
    risk: 'low',
    status: 'Проверен',
    reason: 'Покупка в учебном наборе.',
  },
  {
    id: 7,
    day: 1,
    time: '09:05',
    type: 'purchase',
    counterparty: 'Аптека',
    description: 'Покупка',
    amount: -1240,
    risk: 'low',
    status: 'Проверен',
    reason: 'Покупка в учебном наборе.',
  },
];
export function Transactions({
  events = demoEvents,
  compact = false,
}: {
  events?: DemoEvent[];
  compact?: boolean;
}) {
  const [selected, setSelected] = useState<DemoEvent | null>(null);
  return (
    <>
      <div
        className={styles['transactions__scroll']}
        tabIndex={0}
        aria-label="Учебные операции, прокручиваемая таблица"
      >
        <table className={styles['transactions']}>
          <thead>
            <tr>
              <th scope="col">Время</th>
              {!compact && (
                <>
                  <th scope="col">Тип</th>
                  <th scope="col">Контрагент</th>
                </>
              )}
              <th scope="col">{compact ? 'Описание' : 'Сумма'}</th>
              {compact && <th scope="col">Сумма</th>}
              <th scope="col">Риск</th>
              <th scope="col">Статус</th>
              <th scope="col">
                <span className={styles['transactions__sr']}>Действия</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>
                  {event.day} окт, {event.time}
                </td>
                {!compact && (
                  <>
                    <td>{event.description}</td>
                    <td>{event.counterparty}</td>
                  </>
                )}
                {compact && (
                  <td>
                    <div className={styles['transactions__description']}>
                      <span className={styles['transactions__icon']}>
                        {event.type === 'incoming' ? (
                          '↓'
                        ) : event.type === 'request' ? (
                          <Icon name="file" size={16} />
                        ) : (
                          '↑'
                        )}
                      </span>
                      <span>
                        {event.description}
                        <br />
                        {event.type === 'incoming' ? 'от ' : ''}
                        {event.counterparty}
                      </span>
                    </div>
                  </td>
                )}
                <td className={styles['transactions__amount']}>
                  {event.amount === null
                    ? '—'
                    : `${event.amount > 0 ? '+ ' : '− '}${Math.abs(event.amount).toLocaleString('ru-RU')} ₽`}
                </td>
                <td>
                  <span
                    className={`${styles['transactions__risk']} ${styles[`transactions__risk--${event.risk}`]}`}
                  >
                    {
                      { low: 'Низкий', medium: 'Средний', high: 'Высокий' }[
                        event.risk
                      ]
                    }
                  </span>
                </td>
                <td>
                  <span className={styles['transactions__status']}>
                    {event.status}
                  </span>
                </td>
                <td>
                  <button
                    className={styles['transactions__more']}
                    aria-label={`Детали операции ${event.id}`}
                    onClick={() => setSelected(event)}
                  >
                    •••
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!events.length && (
          <p className={styles['transactions__empty']}>
            Операций по выбранным фильтрам нет.
          </p>
        )}
      </div>
      {selected && (
        <div
          className={styles['transactions__details']}
          role="region"
          aria-label="Детали операции"
        >
          <div>
            <strong>
              {selected.description} · {selected.counterparty}
            </strong>
            <p>{selected.reason}</p>
            <small>
              Синтетическая операция. Банковские счета не подключены.
            </small>
          </div>
          <button onClick={() => setSelected(null)} aria-label="Закрыть детали">
            ×
          </button>
        </div>
      )}
    </>
  );
}
