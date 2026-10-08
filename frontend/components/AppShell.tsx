import type { ReactNode } from 'react';
import styles from '../app/page.module.css';
import { Shield } from './Shield';

export function AppShell({ children }: { children: ReactNode }) {
  return <div className={styles['workspace']}>
    <a className={styles['workspace__skip']} href="#main">Перейти к содержимому</a>
    <aside className={styles['workspace__sidebar']}>
      <a className={styles['workspace__brand']} href="#overview" aria-label="Anti-Drop — начало"><Shield/><span>anti<span className={styles['workspace__brand-accent']}>drop</span><span className={styles['workspace__brand-dot']}>.</span></span></a>
      <div className={styles['workspace__nav-label']}>РАБОЧЕЕ ПРОСТРАНСТВО</div>
      <nav aria-label="Основная навигация" className={styles['workspace__nav']}>
        <a className={`${styles['workspace__nav-link']} ${styles['workspace__nav-link--current']}`} href="#overview" ><span aria-hidden="true">◫</span> Обзор</a>
        <a className={styles['workspace__nav-link']} href="#principles"><span aria-hidden="true">ⓘ</span> Как это работает</a>
        <a className={styles['workspace__nav-link']} href="#monitoring">Мониторинг</a>
        <a className={styles['workspace__nav-link']} href="#learning">Обучение и квиз</a>
        <a className={styles['workspace__nav-link']} href="#phone">Смена номера</a>
      </nav>
      <div className={styles['workspace__sidebar-note']}><Shield/><strong>Понимать — значит<br/>принимать решения.</strong><p>Финансовая безопасность начинается с понятных объяснений.</p></div>
      <span className={styles['workspace__version']}>ПРОТОТИП / 01</span>
    </aside>
    <div className={styles['workspace__body']}>
      <header className={styles['workspace__topbar']}><span>Личное пространство <span className={styles['workspace__topbar-divider']}>/</span> Обзор</span><span className={styles['workspace__demo']}>Демонстрационный режим</span></header>
      <main id="main" tabIndex={-1} className={styles['workspace__main']}>
{children}
        <footer className={styles['workspace__footer']}><span>Anti-Drop · Финансовая безопасность без барьеров</span><span>Прототип для обсуждения</span></footer>
      </main>
    </div>
  </div>;
}
