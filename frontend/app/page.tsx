import styles from './page.module.css';
import { AppShell } from '../components/AppShell';
import { DemoWorkspace } from '../components/DemoWorkspace';
import { Overview } from '../components/Overview';

export default function Home() {
  return <AppShell>
        <Overview/>
        <DemoWorkspace/>
        <section id="principles" className={styles['principles']} aria-labelledby="principles-title">
          <div className={styles['principles__heading']}><span className={styles['principles__eyebrow']}>ПОНЯТНАЯ БЕЗОПАСНОСТЬ</span><h2 id="principles-title" className={styles['principles__title']}>Сначала разобраться.<br/>Потом действовать.</h2></div>
          <div className={styles['principles__items']}><article className={styles['principles__item']}><span className={styles['principles__number']}>01</span><div><h3 className={styles['principles__item-title']}>Замечать признаки риска</h3><p>Просьба принять чужие деньги и перевести их дальше — повод остановиться и проверить обстоятельства.</p></div></article><article className={styles['principles__item']}><span className={styles['principles__number']}>02</span><div><h3 className={styles['principles__item-title']}>Понимать причины</h3><p>Идея Anti-Drop — объяснять подозрительные ситуации. Прототип не заменяет антифрод банка.</p></div></article></div>
        </section>
  </AppShell>;
}

