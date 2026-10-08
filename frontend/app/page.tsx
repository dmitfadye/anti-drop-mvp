import styles from './page.module.css';
import { AppShell } from '../components/AppShell';
import { DemoWorkspace } from '../components/DemoWorkspace';

export default function Home() {
  return <AppShell>
        <section id="overview" aria-labelledby="intro-title" className={styles['intro']}>
          <div className={styles['intro__eyebrow']}>ЯСНОСТЬ В КАЖДОМ ПЕРЕВОДЕ</div>
          <h1 id="intro-title" className={styles['intro__title']}>Ваши деньги.<br/><span className={styles['intro__title-accent']}>Ваше решение.</span></h1>
          <p className={styles['intro__description']}>Разобраться в подозрительной просьбе о переводе проще, когда риски объясняют понятным языком.</p>
          <a href="#principles" className={styles['intro__action']}>Узнать, как работает Anti-Drop <span aria-hidden="true">↗</span></a>
          <div className={styles['intro__footnote']}>Без подключения счетов. Без доступа к вашим деньгам.</div>
        </section>
        <DemoWorkspace/>
        <section id="principles" className={styles['principles']} aria-labelledby="principles-title">
          <div className={styles['principles__heading']}><span className={styles['principles__eyebrow']}>ПОНЯТНАЯ БЕЗОПАСНОСТЬ</span><h2 id="principles-title" className={styles['principles__title']}>Сначала разобраться.<br/>Потом действовать.</h2></div>
          <div className={styles['principles__items']}><article className={styles['principles__item']}><span className={styles['principles__number']}>01</span><div><h3 className={styles['principles__item-title']}>Замечать признаки риска</h3><p>Просьба принять чужие деньги и перевести их дальше — повод остановиться и проверить обстоятельства.</p></div></article><article className={styles['principles__item']}><span className={styles['principles__number']}>02</span><div><h3 className={styles['principles__item-title']}>Понимать причины</h3><p>Идея Anti-Drop — объяснять подозрительные ситуации. Прототип не заменяет антифрод банка.</p></div></article></div>
        </section>
  </AppShell>;
}
