import styles from './Overview.module.css';
import { Shield } from './Shield';
const events = [
  ['14:23', '↓', 'Входящий перевод', 'от учебного отправителя', '+ 15 000 ₽', 'Низкий', 'Проверен', 'low'],
  ['13:02', '↑', 'Перевод на карту', 'учебный получатель', '− 8 500 ₽', 'Средний', 'Требует внимания', 'medium'],
  ['11:46', '▤', 'Запрос перевода', 'в мессенджере', '—', 'Высокий', 'Пример блокировки', 'high'],
  ['10:10', '↓', 'Входящий перевод', 'от неизвестного', '+ 3 000 ₽', 'Средний', 'Проверен', 'medium'],
];
function Bars({ green = false }: { green?: boolean }) {
  return <div className={`${styles['overview__bars']} ${green ? styles['overview__bars--green'] : ''}`} aria-hidden="true">{[12,24,32,43,52].map(height => <span key={height} style={{ height }}/>)}</div>;
}
export function Overview() {
  return <section id="overview" className={styles['overview']} aria-labelledby="overview-title">
    <div className={styles['overview__hero-row']}>
      <article className={styles['overview__hero']}>
        <div className={styles['overview__hero-copy']}><div className={styles['overview__eyebrow']}>ANTI-DROP</div><h1 id="overview-title">Обзор защиты<br/>переводов</h1><p>Понятный интерфейс для разбора подозрительных ситуаций без доступа к вашим деньгам.</p><div className={styles['overview__hero-actions']}><a className={styles['overview__primary']} href="#principles">Как это работает <span>→</span></a><a className={styles['overview__text-link']} href="#monitoring"><span aria-hidden="true">▦</span> Открыть сценарии</a></div></div>
        <div className={styles['overview__illustration']} aria-hidden="true"><div className={styles['overview__glass']}><Shield large/></div></div>
      </article>
      <article className={styles['overview__connection']}><span>Статус системы</span><h2>Нет подключения</h2><p>Банковские операции<br/>не загружены.</p><div className={styles['overview__info']}><span aria-hidden="true">ⓘ</span> Это конкурсный прототип,<br/>а не банковский кабинет.</div><a href="#monitoring" className={styles['overview__primary']}>Попробовать демо →</a></article>
    </div>
    <div className={styles['overview__demo-label']}>Демонстрационные данные · показатели и события ниже — учебный пример, не результат проверки</div>
    <div className={styles['overview__metrics']}>
      <article className={styles['overview__metric']}><div className={styles['overview__icon']} aria-hidden="true">▤</div><div><span>Проверенные сигналы</span><strong>156 <small>↗ +12%</small></strong></div><Bars/></article>
      <article className={styles['overview__metric']}><div className={styles['overview__icon']}><Shield/></div><div><span>Уровень риска</span><strong>Низкий</strong></div><svg className={styles['overview__spark']} viewBox="0 0 100 60" aria-hidden="true"><path d="m5 48 22-25 23 12 25-6 20-25"/><g>{[[5,48],[27,23],[50,35],[75,29],[95,4]].map(([cx,cy]) => <circle key={cx} cx={cx} cy={cy} r="4"/>)}</g></svg></article>
      <article className={styles['overview__metric']}><div className={`${styles['overview__icon']} ${styles['overview__icon--green']}`} aria-hidden="true">◇</div><div><span>Активные сценарии</span><strong>3</strong><small>из 6 в учебном примере</small></div><Bars green/></article>
    </div>
    <div className={styles['overview__activity-row']}>
      <article className={styles['overview__events']}><header className={styles['overview__card-header']}><h2><span aria-hidden="true">◷</span> Последние события</h2><a href="#monitoring">Перейти в мониторинг →</a></header><div className={styles['overview__table-scroll']}><table><thead><tr><th>Время</th><th>Описание</th><th>Сумма</th><th>Риск</th><th>Статус</th></tr></thead><tbody>{events.map(([time,icon,title,detail,amount,risk,status,level]) => <tr key={time}><td>{time}<small>Учебный пример</small></td><td><div className={styles['overview__transaction']}><span aria-hidden="true">{icon}</span><div>{title}<br/>{detail}</div></div></td><td>{amount}</td><td><span className={`${styles['overview__risk']} ${styles[`overview__risk--${level}`]}`}>{risk}</span></td><td><span className={styles['overview__status']}>{status}</span></td></tr>)}</tbody></table></div></article>
      <article className={styles['overview__explanation']}><h2><span aria-hidden="true">♧</span> Почему так?</h2><div className={styles['overview__gauge']}><div><strong>72</strong><span>балла риска</span></div></div><p>Учебный пример оценки.<br/>Узнайте, какие признаки<br/>помогают заметить риск.</p><a href="#principles">Посмотреть объяснение →</a></article>
    </div>
    <div className={styles['overview__shortcuts']}>{[['Мониторинг','Автоматически анализируем учебные переводы и объясняем риски','monitoring','shield'],['Онбординг + квиз','Узнайте, как работают схемы мошенников, и проверьте свои знания','learning','book'],['Смена номера','Проверьте сценарий безопасной смены номера','phone','phone']].map(([title,description,id,icon]) => <a key={id} href={`#${id}`} className={styles['overview__shortcut']}><div className={styles['overview__icon']}>{icon === 'shield' ? <Shield/> : <span aria-hidden="true">{icon === 'book' ? '◇' : '▯'}</span>}</div><div><h2>{title}</h2><p>{description}</p></div><span aria-hidden="true">›</span></a>)}</div>
  </section>;
}
