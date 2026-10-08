'use client';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import styles from './AppShell.module.css';
import { Shield } from './Shield';
const groups = [
  { title: 'ОСНОВНОЕ', items: [['Обзор', 'overview'], ['Мониторинг', 'monitoring'], ['Как это работает', 'principles']] },
  { title: 'ЗАЩИТА', items: [['Сценарии защиты', ''], ['Онбординг + квиз', 'learning'], ['Смена номера', 'phone']] },
  { title: 'ОБУЧЕНИЕ', items: [['База знаний', ''], ['Видео и гайды', ''], ['Примеры ситуаций', '']] },
  { title: 'СИСТЕМА', items: [['Настройки', ''], ['Поддержка', '']] },
];
function Icon({ index }: { index: number }) {
  const paths = ['M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z', 'M4 3h16v18H4z M8 16v-3 M12 16V8 M16 16v-6', 'M12 11v6 M12 7h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0', 'M12 3 3 7v5c0 5 9 10 9 10s9-5 9-10V7z M8 12l3 3 5-6', 'M3 5h7l2 2 2-2h7v15h-7l-2 2-2-2H3z M12 7v15', 'M7 2h10v20H7z M11 18h2'];
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[index % paths.length]}/></svg>;
}
export function AppShell({ children }: { children: ReactNode }) {
  const [active, setActive] = useState('overview');
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState(false);
  const nav = useRef<HTMLElement>(null);
  const indicator = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLElement>(null);
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const sync = () => setActive(location.hash.slice(1) || 'overview');
    sync(); window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  useEffect(() => {
    const measure = () => {
      const link = nav.current?.querySelector<HTMLElement>('[aria-current]');
      if (link && indicator.current) {
        indicator.current.style.transform = `translateY(${link.offsetTop}px)`;
        indicator.current.style.height = `${link.offsetHeight}px`;
        indicator.current.style.opacity = '1';
      }
    };
    measure(); const observer = new ResizeObserver(measure);
    if (nav.current) observer.observe(nav.current);
    void document.fonts.ready.then(measure);
    return () => observer.disconnect();
  }, [active, open]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') { event.preventDefault(); search.current?.focus(); }
      if (!open) return;
      if (event.key === 'Escape') { setOpen(false); requestAnimationFrame(() => menu.current?.focus()); }
      if (event.key === 'Tab') {
        const elements = drawer.current?.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)');
        if (!elements?.length) return;
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', key);
    if (open) drawer.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const previous = document.body.style.overflow;
    if (open) document.body.style.overflow = 'hidden';
    const resize = () => { if (innerWidth >= 768) setOpen(false); };
    window.addEventListener('resize', resize);
    return () => { document.removeEventListener('keydown', key); window.removeEventListener('resize', resize); document.body.style.overflow = previous; };
  }, [open]);
  const close = () => { setOpen(false); requestAnimationFrame(() => menu.current?.focus()); };
  const results = groups.flatMap(group => group.items).filter(([label, id]) => id && label.toLocaleLowerCase('ru').includes(query.toLocaleLowerCase('ru')));
  return <div className={styles['shell']}>
    <a className={styles['shell__skip']} href="#main">Перейти к содержимому</a>
    {open && <button className={styles['shell__backdrop']} aria-label="Закрыть навигацию" onClick={close}/>}
    <aside ref={drawer} id="navigation-panel" className={`${styles['sidebar']} ${open ? styles['sidebar--open'] : ''}`} role={open ? 'dialog' : undefined} aria-modal={open || undefined} aria-label="Навигация приложения">
      <button className={styles['sidebar__close']} onClick={close}>Закрыть меню ×</button>
      <a className={styles['sidebar__brand']} href="#overview"><Shield/><span>antidrop<span>.</span></span></a>
      <div className={styles['sidebar__attribution']}>Конкурсный прототип · для конкурса ВТБ</div>
      <nav ref={nav} className={styles['sidebar__nav']} aria-label="Основная навигация">
        <div ref={indicator} className={styles['sidebar__active-indicator']} aria-hidden="true"/>
        {groups.map((group, groupIndex) => <section key={group.title} className={styles['sidebar__section']}>
          <h2 className={styles['sidebar__section-title']}>{group.title}</h2>
          {group.items.map(([label, id], index) => id ? <a key={label} href={`#${id}`} aria-current={active === id ? 'page' : undefined} className={styles['sidebar__item']} onClick={() => { setActive(id); if (open) { setOpen(false); requestAnimationFrame(() => { const target = document.getElementById(id); target?.setAttribute('tabindex', '-1'); target?.focus(); }); } }}><Icon index={groupIndex * 3 + index}/>{label}</a> : <button key={label} className={styles['sidebar__item']} disabled title="Раздел пока не реализован"><Icon index={groupIndex * 3 + index}/><span>{label}<small>Скоро</small></span></button>)}
        </section>)}
      </nav>
      <div className={styles['sidebar__profile']}><span className={styles['sidebar__avatar']}>АД</span><div><strong>Демо-профиль</strong><small>Без подключения счетов</small></div></div>
    </aside>
    <div className={styles['shell__body']} inert={open || undefined}>
      <header className={styles['topbar']}>
        <button ref={menu} className={styles['topbar__menu']} aria-expanded={open} aria-controls="navigation-panel" onClick={() => setOpen(true)}>☰ Меню</button>
        <div className={styles['topbar__search']}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/></svg><input ref={search} aria-label="Поиск по разделам" placeholder="Поиск по переводам, рискам, подсказкам..." value={query} onChange={event => setQuery(event.target.value)}/><kbd>Ctrl K</kbd>
          {query && <div className={styles['topbar__results']}><small>Поиск по доступным разделам</small>{results.length ? results.map(([label, id]) => <a key={id} href={`#${id}`} onClick={() => { setActive(id); setQuery(''); }}>{label}</a>) : <p>Разделы не найдены</p>}</div>}
        </div>
        <div className={styles['topbar__actions']}><button className={styles['topbar__icon']} aria-label="Уведомления" aria-expanded={notice} onClick={() => setNotice(!notice)}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5z M10 21h4"/></svg></button><a className={styles['topbar__icon']} href="#principles" aria-label="Помощь"><Icon index={2}/></a><a className={styles['topbar__demo-button']} href="#monitoring">Демо-режим</a></div>
        {notice && <div className={styles['topbar__notice']} role="status">Новых уведомлений нет. Банковские счета не подключены.</div>}
      </header>
      <main id="main" tabIndex={-1} className={styles['shell__main']}>{children}<footer className={styles['shell__footer']}>AntiDrop · Конкурсный прототип. Не является банковским сервисом ВТБ.</footer></main>
    </div>
  </div>;
}
