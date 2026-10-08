'use client';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import styles from './AppShell.module.css';
import { Shield } from './Shield';
import { Icon as UiIcon } from './Icon';
import { useSection } from './useSection';
import { usePreferences } from './preferences';
const groups = [
  {
    title: 'ОСНОВНОЕ',
    items: [
      ['Обзор', 'overview'],
      ['Мониторинг', 'monitoring'],
      ['Как это работает', 'principles'],
    ],
  },
  {
    title: 'ЗАЩИТА',
    items: [
      ['Сценарии защиты', 'protection'],
      ['Онбординг + квиз', 'learning'],
      ['Смена номера', 'phone'],
    ],
  },
  {
    title: 'ОБУЧЕНИЕ',
    items: [
      ['База знаний', 'knowledge'],
      ['Видео и гайды', 'guides'],
      ['Примеры ситуаций', 'examples'],
    ],
  },
  {
    title: 'СИСТЕМА',
    items: [
      ['Настройки', 'settings'],
      ['Поддержка', 'support'],
    ],
  },
];
function Icon({ index }: { index: number }) {
  const names = [
    'grid',
    'chart',
    'info',
    'shield',
    'book',
    'phone',
    'cap',
    'play',
    'file',
    'settings',
    'help',
  ] as const;
  return <UiIcon name={names[index % names.length]} size={18} />;
}
export function AppShell({ children }: { children: ReactNode }) {
  const active = useSection();
  const { values } = usePreferences();
  useEffect(() => {
    for (const [key, value] of Object.entries(values))
      document.documentElement.dataset[key] = String(value);
  }, [values]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState(false);
  const nav = useRef<HTMLElement>(null);
  const indicator = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLElement>(null);
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const measure = () => {
      const link = nav.current?.querySelector<HTMLElement>('[aria-current]');
      if (link && indicator.current) {
        indicator.current.style.transform = `translateY(${link.getBoundingClientRect().top - nav.current!.getBoundingClientRect().top}px)`;
        indicator.current.style.height = `${link.offsetHeight}px`;
        indicator.current.style.opacity = '1';
      }
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (nav.current) observer.observe(nav.current);
    void document.fonts.ready.then(measure);
    return () => observer.disconnect();
  }, [active, open]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        search.current?.focus();
      }
      if (!open) return;
      if (event.key === 'Escape') {
        setOpen(false);
        requestAnimationFrame(() => menu.current?.focus());
      }
      if (event.key === 'Tab') {
        const elements = drawer.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not(:disabled)',
        );
        if (!elements?.length) return;
        const first = elements[0],
          last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', key);
    if (open)
      drawer.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const previous = document.body.style.overflow;
    if (open) document.body.style.overflow = 'hidden';
    const resize = () => {
      if (innerWidth >= 768) setOpen(false);
    };
    window.addEventListener('resize', resize);
    return () => {
      document.removeEventListener('keydown', key);
      window.removeEventListener('resize', resize);
      document.body.style.overflow = previous;
    };
  }, [open]);
  const close = () => {
    setOpen(false);
    requestAnimationFrame(() => menu.current?.focus());
  };
  const results = groups
    .flatMap((group) => group.items)
    .filter(
      ([label, id]) =>
        id &&
        label.toLocaleLowerCase('ru').includes(query.toLocaleLowerCase('ru')),
    );
  return (
    <div className={styles['shell']}>
      <a
        className={styles['shell__skip']}
        href="#main"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById('main')?.focus();
        }}
      >
        Перейти к содержимому
      </a>
      {open && (
        <button
          className={styles['shell__backdrop']}
          aria-label="Закрыть навигацию"
          onClick={close}
        />
      )}
      <aside
        ref={drawer}
        id="navigation-panel"
        className={`${styles['sidebar']} ${open ? styles['sidebar--open'] : ''}`}
        role={open ? 'dialog' : undefined}
        aria-modal={open || undefined}
        aria-label="Навигация приложения"
      >
        <button className={styles['sidebar__close']} onClick={close}>
          Закрыть меню ×
        </button>
        <a className={styles['sidebar__brand']} href="#overview">
          <Shield />
          <span>
            antidrop<span> × ВТБ</span>
          </span>
        </a>
        <div className={styles['sidebar__attribution']}>
          Конкурсный прототип
        </div>
        <nav
          ref={nav}
          className={styles['sidebar__nav']}
          aria-label="Основная навигация"
        >
          <div
            ref={indicator}
            className={styles['sidebar__active-indicator']}
            aria-hidden="true"
          />
          {groups.map((group, groupIndex) => (
            <section key={group.title} className={styles['sidebar__section']}>
              <h2 className={styles['sidebar__section-title']}>
                {group.title}
              </h2>
              {group.items.map(([label, id], index) =>
                id ? (
                  <a
                    key={label}
                    href={`#${id}`}
                    aria-current={active === id ? 'page' : undefined}
                    className={styles['sidebar__item']}
                    onClick={() => {
                      if (open) {
                        setOpen(false);
                        requestAnimationFrame(() => {
                          const target = document.getElementById(id);
                          target?.setAttribute('tabindex', '-1');
                          target?.focus();
                        });
                      }
                    }}
                  >
                    <Icon index={groupIndex * 3 + index} />
                    {label}
                  </a>
                ) : (
                  <button
                    key={label}
                    className={styles['sidebar__item']}
                    disabled
                    title="Раздел пока не реализован"
                  >
                    <Icon index={groupIndex * 3 + index} />
                    <span>
                      {label}
                      <small>Скоро</small>
                    </span>
                  </button>
                ),
              )}
            </section>
          ))}
        </nav>
        <div className={styles['sidebar__profile']}>
          <span className={styles['sidebar__avatar']}>АД</span>
          <div>
            <strong>Демо-профиль</strong>
            <small>Без подключения счетов</small>
          </div>
          <a href="#settings" aria-label="Открыть профиль">
            ›
          </a>
        </div>
      </aside>
      <div className={styles['shell__body']} inert={open || undefined}>
        <header className={styles['topbar']}>
          <button
            ref={menu}
            className={styles['topbar__menu']}
            aria-expanded={open}
            aria-controls="navigation-panel"
            onClick={() => setOpen(true)}
          >
            ☰ Меню
          </button>
          <div className={styles['topbar__search']}>
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              aria-hidden="true"
            >
              <circle cx="10" cy="10" r="7" />
              <path d="m15 15 6 6" />
            </svg>
            <input
              ref={search}
              aria-label="Поиск по разделам"
              placeholder="Поиск по переводам, рискам, подсказкам..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <kbd>Ctrl K</kbd>
            {query && (
              <div className={styles['topbar__results']}>
                <small>Поиск по доступным разделам</small>
                {results.length ? (
                  results.map(([label, id]) => (
                    <a
                      key={id}
                      href={`#${id}`}
                      onClick={() => {
                        setQuery('');
                      }}
                    >
                      {label}
                    </a>
                  ))
                ) : (
                  <p>Разделы не найдены</p>
                )}
              </div>
            )}
          </div>
          <div className={styles['topbar__actions']}>
            <button
              className={styles['topbar__icon']}
              aria-label="Уведомления"
              aria-expanded={notice}
              onClick={() => setNotice(!notice)}
            >
              <UiIcon name="bell" />
            </button>
            <a
              className={styles['topbar__icon']}
              href="#support"
              aria-label="Помощь"
            >
              <UiIcon name="help" />
            </a>
            <a
              className={styles['topbar__icon']}
              href="#settings"
              aria-label="Настройки интерфейса"
            >
              <UiIcon name="sun" />
            </a>
            <a className={styles['topbar__demo-button']} href="#monitoring">
              Демо-режим
            </a>
            <a
              className={styles['sidebar__avatar']}
              href="#settings"
              aria-label="Профиль"
            >
              АД
            </a>
          </div>
          {notice && (
            <div className={styles['topbar__notice']} role="status">
              Новых уведомлений нет. Банковские счета не подключены.
            </div>
          )}
        </header>
        <main id="main" tabIndex={-1} className={styles['shell__main']}>
          {children}
          <footer className={styles['shell__footer']}>
            AntiDrop · Конкурсный прототип. Не является банковским сервисом ВТБ.
          </footer>
        </main>
      </div>
    </div>
  );
}
