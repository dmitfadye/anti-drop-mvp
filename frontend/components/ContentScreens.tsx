'use client';
import { useEffect, useRef, useState } from 'react';
import type { SectionId } from './useSection';
import { Icon, type IconName } from './Icon';
import { articles, scenarios, type Article } from './education';
import { usePreferences, type Preference } from './preferences';
import styles from './ContentScreens.module.css';
const faq = [
  [
    'AntiDrop подключён к моему банку?',
    'Нет. Это конкурсный прототип с синтетическими операциями. Доступа к вашим счетам нет.',
  ],
  [
    'Что означает уровень риска?',
    'Это объяснение признаков в выбранном учебном сценарии. Оценка не гарантирует безопасность реального перевода.',
  ],
  [
    'Отправляются ли SMS при смене номера?',
    'Нет. В тренажёре используется учебный код 123456. Настоящий номер в банке не меняется.',
  ],
  [
    'Начисляется ли награда за квиз?',
    'Нет. Награда в результате квиза — учебный показатель, реальные деньги не начисляются.',
  ],
  [
    'Как связаться с банком?',
    'Откройте официальное приложение своего банка самостоятельно и используйте указанные в нём контакты. AntiDrop не принимает банковские обращения.',
  ],
  [
    'Где хранятся настройки интерфейса?',
    'Предпочтения сохраняются только в этом браузере. Они не изменяют правила серверного антифрода.',
  ],
];
const meta: Partial<Record<SectionId, [string, string]>> = {
  principles: [
    'Как это работает',
    'Простые объяснения, наглядные примеры и реальные признаки риска.',
  ],
  protection: [
    'Сценарии защиты',
    'Типовые ситуации, которые мы объясняем, и рекомендации.',
  ],
  knowledge: [
    'База знаний',
    'Простые объяснения, примеры ситуаций и рекомендации по защите от мошенников.',
  ],
  guides: ['Видео и гайды', 'Короткие памятки о безопасных действиях.'],
  examples: [
    'Примеры ситуаций',
    'Разберите учебные ситуации и научитесь замечать признаки риска.',
  ],
  settings: [
    'Настройки',
    'Управляйте параметрами интерфейса и знакомьтесь с возможностями прототипа.',
  ],
  support: ['Поддержка', 'Ответы на вопросы о работе AntiDrop.'],
};
export function ContentScreens({ active }: { active: SectionId }) {
  const [category, setCategory] = useState('Все темы');
  const [scenarioCategory, setScenarioCategory] = useState('Все');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Article | null>(null);
  const reading = useRef<HTMLElement>(null);
  const readingTrigger = useRef<HTMLElement | null>(null);
  const [settingsTab, setSettingsTab] = useState('Безопасность');
  const [saveError, setSaveError] = useState('');
  const { values, update } = usePreferences();
  useEffect(() => {
    if (!selected) return;
    const frame = requestAnimationFrame(() => {
      reading.current?.focus({ preventScroll: true });
      reading.current?.scrollIntoView({ block: 'nearest' });
    });
    return () => cancelAnimationFrame(frame);
  }, [selected]);
  const heading = meta[active];
  if (!heading) return null;
  const openArticle = (id: string) => {
    readingTrigger.current = document.activeElement as HTMLElement;
    setSelected(articles.find((a) => a.id === id) ?? null);
  };
  const closeArticle = () => {
    setSelected(null);
    readingTrigger.current?.focus();
  };
  const filtered = articles.filter(
    (a) =>
      (category === 'Все темы' || a.category === category) &&
      `${a.title} ${a.description} ${a.body.join(' ')}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const settingsItems: [string, IconName][] = [
    ['Профиль', 'user'],
    ['Безопасность', 'shield'],
    ['Уведомления', 'bell'],
    ['Интерфейс', 'sun'],
    ['Интеграции', 'layers'],
    ['О системе', 'info'],
  ];
  const switches: [Preference, string, string, IconName][] = [
    [
      'hints',
      'Обучающие подсказки',
      'Показывать пояснения на экране обзора',
      'info',
    ],
    [
      'contrast',
      'Повышенный контраст',
      'Усилить контраст текста и границ',
      'shield',
    ],
    [
      'compact',
      'Компактные таблицы',
      'Уменьшить высоту строк операций',
      'chart',
    ],
    [
      'motion',
      'Уменьшить анимацию',
      'Отключить движение индикатора навигации',
      'clock',
    ],
  ];
  return (
    <section
      id={active}
      className={styles['screens']}
      aria-labelledby={`${active}-title`}
    >
      <header className={styles['screens__heading']}>
        <h1 id={`${active}-title`}>{heading[0]}</h1>
        <p>{heading[1]}</p>
      </header>
      {active === 'principles' && (
        <>
          <div className={styles['screens__process']}>
            {[
              [
                'Анализируем переводы',
                'Проверяем контрагентов, суммы, частоту, время и последовательность операций.',
                'chart',
              ],
              [
                'Выявляем риски',
                'Сопоставляем признаки с известными схемами в учебном детекторе.',
                'warning',
              ],
              [
                'Даём понятные объяснения',
                'Показываем причины оценки и подсказываем, что можно проверить.',
                'shield',
              ],
            ].map(([title, text, icon], i) => (
              <article key={title} className={styles['screens__process-card']}>
                <span
                  className={`${styles['screens__process-icon']} ${styles[`screens__process-icon--${i}`]}`}
                >
                  <Icon name={icon as IconName} size={28} />
                </span>
                <div>
                  <h2>{title}</h2>
                  <p>{text}</p>
                </div>
              </article>
            ))}
          </div>
          <article className={styles['screens__example']}>
            <div>
              <h2>
                <Icon name="info" />
                Пример из учебной ситуации
              </h2>
              <p>
                Вам приходит сообщение с просьбой перевести деньги.
                <br />
                Проверьте просьбу другим способом, прежде чем действовать.
              </p>
              <button onClick={() => openArticle('messenger')}>
                Посмотреть пример <Icon name="arrow" size={16} />
              </button>
            </div>
            <Icon name="phone" size={110} />
          </article>
          <a href="#monitoring" className={styles['screens__primary']}>
            Попробовать учебный анализ <Icon name="arrow" size={16} />
          </a>
        </>
      )}
      {(active === 'protection' || active === 'examples') && (
        <>
          <div
            className={styles['screens__chips']}
            aria-label="Категории сценариев"
          >
            {[
              'Все',
              'Социальная инженерия',
              'Финансовые схемы',
              'Мессенджеры',
              'Знакомые',
              'Покупки',
            ].map((c) => (
              <button
                key={c}
                aria-pressed={scenarioCategory === c}
                onClick={() => setScenarioCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
          <div className={styles['screens__cards']}>
            {scenarios
              .filter(
                (s) =>
                  scenarioCategory === 'Все' || s.category === scenarioCategory,
              )
              .map((scenario, i) => (
                <article
                  className={styles['screens__scenario']}
                  key={scenario.title}
                >
                  <span
                    className={`${styles['screens__icon']} ${styles[`screens__icon--${['blue', 'red', 'purple'][i % 3]}`]}`}
                  >
                    <Icon name={scenario.icon} />
                  </span>
                  <div>
                    <h2>{scenario.title}</h2>
                    <p>{scenario.description}</p>
                    <button onClick={() => openArticle(scenario.article)}>
                      {active === 'examples'
                        ? 'Разобрать ситуацию'
                        : 'Как защититься'}{' '}
                      <Icon name="arrow" size={15} />
                    </button>
                  </div>
                </article>
              ))}
          </div>
          <p className={styles['screens__caption']}>
            Все ситуации вымышлены и предназначены для обучения.
          </p>
        </>
      )}
      {active === 'knowledge' && (
        <>
          <div
            className={styles['screens__chips']}
            aria-label="Категории материалов"
          >
            {[
              'Все темы',
              'Платежи',
              'Мошенничество',
              'Безопасность',
              'Инструкции',
            ].map((c) => (
              <button
                key={c}
                aria-pressed={category === c}
                onClick={() => setCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
          <label className={styles['screens__search']}>
            <Icon name="search" size={17} />
            <input
              aria-label="Поиск по базе знаний"
              placeholder="Поиск по статьям..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <div className={styles['screens__cards']}>
            {filtered.map((article) => (
              <button
                className={styles['screens__article']}
                key={article.id}
                onClick={() => openArticle(article.id)}
              >
                <span
                  className={`${styles['screens__icon']} ${styles[`screens__icon--${article.color}`]}`}
                >
                  <Icon name={article.icon} />
                </span>
                <span>
                  <strong>{article.title}</strong>
                  <span className={styles['screens__article-description']}>
                    {article.description}
                  </span>
                  <small>{article.minutes} минут чтения</small>
                </span>
              </button>
            ))}
          </div>
          {!filtered.length && (
            <p className={styles['screens__empty']}>
              Материалы не найдены. Попробуйте другой запрос.
            </p>
          )}
        </>
      )}
      {active === 'guides' && (
        <>
          <div className={styles['screens__guide-list']}>
            {articles.slice(0, 4).map((article) => (
              <button
                key={article.id}
                className={styles['screens__guide']}
                onClick={() => openArticle(article.id)}
              >
                <span
                  className={`${styles['screens__icon']} ${styles[`screens__icon--${article.color}`]}`}
                >
                  <Icon name="book" />
                </span>
                <span>
                  <strong>{article.title}</strong>
                  <small>{article.description}</small>
                </span>
                <span>{article.minutes} мин</span>
                <Icon name="arrow" size={18} />
              </button>
            ))}
          </div>
          <div className={styles['screens__video-empty']}>
            <Icon name="play" size={38} />
            <h2>Видеоматериалы готовятся</h2>
            <p>Пока доступны текстовые памятки и интерактивный квиз.</p>
            <a href="#learning">Перейти к обучению →</a>
          </div>
        </>
      )}
      {active === 'settings' && (
        <div className={styles['screens__settings']}>
          <nav
            className={styles['screens__settings-nav']}
            aria-label="Разделы настроек"
          >
            {settingsItems.map(([label, icon]) => (
              <button
                key={label}
                aria-current={settingsTab === label ? 'page' : undefined}
                onClick={() => setSettingsTab(label)}
              >
                <Icon name={icon} size={17} />
                {label}
              </button>
            ))}
          </nav>
          <div className={styles['screens__settings-panel']}>
            <h2>
              {settingsTab === 'Безопасность'
                ? 'Параметры безопасности'
                : settingsTab}
            </h2>
            {(settingsTab === 'Безопасность' ||
              settingsTab === 'Интерфейс') && (
              <>
                {switches.map(([key, title, description, icon]) => (
                  <div className={styles['screens__setting']} key={key}>
                    <span className={styles['screens__icon']}>
                      <Icon name={icon} />
                    </span>
                    <div>
                      <strong>{title}</strong>
                      <p>{description}</p>
                    </div>
                    <button
                      className={styles['screens__switch']}
                      role="switch"
                      aria-checked={values[key]}
                      aria-label={title}
                      onClick={() =>
                        setSaveError(
                          update(key, !values[key])
                            ? ''
                            : 'Браузер не разрешил сохранить настройки.',
                        )
                      }
                    >
                      <span />
                    </button>
                  </div>
                ))}
                <p className={styles['screens__caption']}>
                  Настройки сохраняются в этом браузере. Правила серверной
                  проверки не меняются.
                </p>
              </>
            )}
            {settingsTab === 'Профиль' && (
              <div className={styles['screens__setting-info']}>
                <Icon name="user" size={40} />
                <h3>Демо-профиль</h3>
                <p>Учебная сессия без регистрации и банковских счетов.</p>
              </div>
            )}
            {settingsTab === 'Уведомления' && (
              <div className={styles['screens__setting-info']}>
                <Icon name="bell" size={32} />
                <h3>Новых уведомлений нет</h3>
                <p>
                  Предупреждения доступны при запуске учебного анализа. Push и
                  SMS в прототипе не отправляются.
                </p>
                <a href="#monitoring">Открыть мониторинг →</a>
              </div>
            )}
            {settingsTab === 'Интеграции' && (
              <div className={styles['screens__setting-info']}>
                <Icon name="layers" size={32} />
                <h3>Банковские счета не подключены</h3>
                <p>
                  Прототип использует синтетические данные и собственный учебный
                  backend.
                </p>
              </div>
            )}
            {settingsTab === 'О системе' && (
              <div className={styles['screens__setting-info']}>
                <h3>AntiDrop</h3>
                <p>
                  Конкурсный прототип объяснимой финансовой безопасности. Не
                  является банковским сервисом ВТБ.
                </p>
                <p>
                  Шрифт Asket — Glenjan, © 2017. Исходные файлы не изменены.
                </p>
                <a
                  href="https://www.1001fonts.com/asket-font.html"
                  target="_blank"
                  rel="noreferrer"
                >
                  Источник шрифта ↗
                </a>
                <p>
                  <a
                    href="https://creativecommons.org/licenses/by-nd/3.0/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Лицензия CC BY-ND 3.0 ↗
                  </a>
                </p>
              </div>
            )}
            {saveError && <p role="alert">{saveError}</p>}
          </div>
        </div>
      )}
      {active === 'support' && (
        <>
          <label className={styles['screens__search']}>
            <Icon name="search" size={17} />
            <input
              aria-label="Поиск в поддержке"
              placeholder="Найти ответ на вопрос..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <div className={styles['screens__faq']}>
            {faq
              .filter(([q, a]) =>
                `${q} ${a}`.toLowerCase().includes(query.toLowerCase()),
              )
              .map(([q, a]) => (
                <details key={q}>
                  <summary>{q}</summary>
                  <p>{a}</p>
                </details>
              ))}
          </div>
          {!faq.some(([q, a]) =>
            `${q} ${a}`.toLowerCase().includes(query.toLowerCase()),
          ) && (
            <p className={styles['screens__empty']}>
              Ответ не найден. Попробуйте другой запрос.
            </p>
          )}
          <div className={styles['screens__contact']}>
            <Icon name="shield" size={30} />
            <div>
              <h2>Нужна помощь с реальной операцией?</h2>
              <p>
                Обратитесь в свой банк через официальное приложение. Здесь
                банковские обращения не принимаются.
              </p>
            </div>
          </div>
        </>
      )}
      {selected && (
        <article
          className={styles['screens__reading']}
          ref={reading}
          tabIndex={-1}
          role="region"
          aria-label="Материал"
        >
          <header>
            <span>
              {selected.category} · {selected.minutes} мин
            </span>
            <button onClick={closeArticle} aria-label="Закрыть материал">
              Закрыть ×
            </button>
          </header>
          <h2>{selected.title}</h2>
          {selected.body.map((p) => (
            <p key={p}>{p}</p>
          ))}
          <a href="#learning" onClick={closeArticle}>
            Проверить знания в квизе →
          </a>
        </article>
      )}
    </section>
  );
}
