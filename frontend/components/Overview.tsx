import { Icon } from './Icon';
import { Transactions, demoEvents } from './Transactions';
import styles from './Overview.module.css';
function Bars({ green = false }: { green?: boolean }) {
  return (
    <div
      className={`${styles['overview__bars']} ${green ? styles['overview__bars--green'] : ''}`}
      aria-hidden="true"
    >
      {[1, 2, 3, 4, 5].map((bar) => (
        <span key={bar} />
      ))}
    </div>
  );
}
export function Overview() {
  return (
    <section
      id="overview"
      className={styles['overview']}
      aria-labelledby="overview-title"
    >
      <header className={styles['overview__heading']}>
        <h1 id="overview-title">Обзор</h1>
        <p>Защита ваших переводов и финансовых операций</p>
      </header>
      <div className={styles['overview__metrics']}>
        <article className={styles['overview__metric']}>
          <div className={styles['overview__icon']}>
            <Icon name="file" size={30} />
          </div>
          <div>
            <span>Проверенные операции</span>
            <strong>156</strong>
            <small className={styles['overview__growth']}>↗ +12%</small>
          </div>
          <Bars />
        </article>
        <article className={styles['overview__metric']}>
          <div className={styles['overview__icon']}>
            <Icon name="shield" size={32} />
          </div>
          <div>
            <span>Уровень риска</span>
            <strong>Низкий</strong>
          </div>
          <svg
            className={styles['overview__spark']}
            viewBox="0 0 100 50"
            aria-hidden="true"
          >
            <path d="m5 40 18-17 17 8 18-6 17 6 20-25" />
            {[
              [5, 40],
              [23, 23],
              [40, 31],
              [58, 25],
              [75, 31],
              [95, 6],
            ].map(([cx, cy]) => (
              <circle key={cx} cx={cx} cy={cy} r="3" />
            ))}
          </svg>
        </article>
        <article className={styles['overview__metric']}>
          <div
            className={`${styles['overview__icon']} ${styles['overview__icon--green']}`}
          >
            <Icon name="layers" size={30} />
          </div>
          <div>
            <span>Активные сценарии</span>
            <strong>3</strong>
            <small>из 6 в учебном примере</small>
          </div>
          <Bars green />
        </article>
      </div>
      <article className={styles['overview__events']}>
        <header className={styles['overview__card-header']}>
          <h2>
            <Icon name="clock" />
            Последние события
          </h2>
          <a href="#monitoring">
            Перейти в мониторинг <Icon name="arrow" size={16} />
          </a>
        </header>
        <Transactions events={demoEvents.slice(0, 4)} compact />
      </article>
      <div className={styles['overview__shortcuts']}>
        {[
          [
            'Мониторинг',
            'Анализируем учебные операции и объясняем риски',
            'monitoring',
            'shield',
          ],
          [
            'Онбординг + квиз',
            'Узнайте, как работают схемы мошенников, и проверьте свои знания',
            'learning',
            'cap',
          ],
        ].map(([title, description, id, icon]) => (
          <a key={id} href={`#${id}`} className={styles['overview__shortcut']}>
            <div className={styles['overview__icon']}>
              <Icon name={icon as 'shield' | 'cap'} size={42} />
            </div>
            <div>
              <h2>{title}</h2>
              <p>{description}</p>
            </div>
            <span className={styles['overview__shortcut-arrow']} aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m9 5 7 7-7 7" /></svg>
            </span>
          </a>
        ))}
      </div>
      <p className={styles['overview__demo-label']}>
        Демонстрационные данные · показатели и события — учебный пример, не
        результат проверки ваших операций.
      </p>
    </section>
  );
}
