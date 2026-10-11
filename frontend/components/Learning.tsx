'use client';
import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icon';
import { useSection } from './useSection';
import { learningRequest, type LearningFormat, type LearningModule, type LearningProgress, type LearningResult } from './learning-api';
import styles from './Learning.module.css';
const formats = [
  { id: 'quiz', title: 'Тест', description: 'Сразу проверьте знания', icon: 'cap' },
  { id: 'lesson', title: 'Мини-урок + тест', description: 'Разберите ситуации по карточкам', icon: 'layers' },
  { id: 'article', title: 'Статья', description: 'Прочитайте в своём темпе', icon: 'book' },
] as const;
const fetchCourse = () => Promise.all([learningRequest<{ modules: LearningModule[] }>('catalog'), learningRequest<LearningProgress>('progress')]);
export function Learning() {
  const active = useSection();
  const [modules, setModules] = useState<LearningModule[]>([]);
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [format, setFormat] = useState<LearningFormat>('lesson');
  const [selected, setSelected] = useState<LearningModule | null>(null);
  const [step, setStep] = useState(0);
  const [articleRead, setArticleRead] = useState(false);
  const [lessonRead, setLessonRead] = useState(false);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<LearningResult | null>(null);
  const [category, setCategory] = useState('');
  const completionKey = useRef<string | null>(null);
  const claimKey = useRef<string | null>(null);
  const touchStart = useRef<number | null>(null);
  const panel = useRef<HTMLElement>(null);
  async function load() {
    setLoading(true); setError('');
    try {
      const [catalog, state] = await fetchCourse();
      setModules(catalog.modules); setProgress(state);
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось загрузить курс.'); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    if (active !== 'learning') return;
    let live = true;
    void fetchCourse().then(([catalog, state]) => { if (live) { setModules(catalog.modules); setProgress(state); } })
      .catch(e => { if (live) setError(e instanceof Error ? e.message : 'Не удалось загрузить курс.'); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [active]);
  function reset(module: LearningModule | null = null) {
    setSelected(module); setStep(0); setAnswers({}); setArticleRead(false); setLessonRead(false); setResult(null); setError(''); completionKey.current = null;
  }
  function chooseAnswer(id: string, answer: number) {
    setAnswers(previous => ({ ...previous, [id]: answer })); completionKey.current = null;
  }
  const questions = selected ? format === 'quiz' ? selected.quiz : format === 'article' ? selected.cards.slice(0, 1) : [...selected.cards, ...selected.quiz] : [];
  const question = questions[step];
  function move(direction: number) {
    if (busy || !question || (direction > 0 && answers[question.id] === undefined)) return;
    setStep(current => Math.max(0, Math.min(questions.length - 1, current + direction)));
  }
  async function finish() {
    if (!selected || busy) return;
    setBusy(true); setError(''); completionKey.current ??= crypto.randomUUID();
    try {
      const response = await learningRequest<{ progress: LearningProgress; result: LearningResult }>('completions', { module_id: selected.id, format, answers, idempotency_key: completionKey.current });
      setProgress(response.progress); setResult(response.result);
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось проверить ответы.'); }
    finally { setBusy(false); }
  }
  async function claim() {
    if (!category || busy) return;
    setBusy(true); setError(''); claimKey.current ??= crypto.randomUUID();
    try {
      const response = await learningRequest<{ progress: LearningProgress }>('rewards/30/claim', { category, idempotency_key: claimKey.current });
      setProgress(response.progress);
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось выбрать категорию.'); }
    finally { setBusy(false); }
  }
  const monthly = progress?.rewards.find(reward => reward.days === 30);
  return <section id="learning" className={styles['learning']} aria-labelledby="learning-title">
    <header className={styles['learning__heading']}><div><h1 id="learning-title">Онбординг + квиз</h1><p>«Спокойные переводы» — короткий курс о безопасных действиях с деньгами</p></div><span className={styles['learning__badge']}>Учебный режим</span></header>
    <p className={styles['learning__disclaimer']}>Общий демо-профиль: прогресс виден участникам этого стенда. Баллы, кешбэк и категории — учебные. Реальных начислений и подключения к банку нет.</p>
    <p className={styles['learning__source']}>Учебные материалы · черновик. Формулировки о правилах банка требуют проверки.</p>
    {loading && <p role="status">Загружаем курс и сохранённый прогресс…</p>}
    {error && <div className={styles['learning__error']} role="alert"><p>{error}</p>{!progress && <button onClick={() => void load()} disabled={loading}>Повторить загрузку</button>}</div>}
    {progress && <>
      <div className={styles['learning__stats']}>
        <article className={styles['learning__stat']}><Icon name="cap" size={28} /><div><span>Ваше звание</span><h2>{progress.rank.title}</h2><p>{progress.xp} учебных баллов</p></div><progress aria-label="Прогресс до следующего звания" max={100} value={progress.rank_progress_percent} /><p>{progress.next_rank ? `Ещё ${progress.points_to_next} баллов до звания «${progress.next_rank.title}»` : 'Вы достигли последнего звания курса'}</p></article>
        <article className={styles['learning__stat']}><Icon name="clock" size={28} /><div><span>Серия занятий</span><h2>{progress.streak_days} дн.</h2><p>Одно завершённое занятие в день продолжает серию</p></div><p>Дни считаются по московскому времени. Пропуск не отнимает знания и баллы.</p></article>
        <article className={styles['learning__stat']}><Icon name="chart" size={28} /><div><span>Ваш путь</span><h2>{progress.completed_modules.length} / {modules.length}</h2><p>Модулей завершено</p></div><p>{progress.rank_note || 'Рейтинг пока недоступен: нет сравнительной выборки.'}</p></article>
      </div>
      <h2 className={styles['learning__section-title']}>Как хотите учиться сегодня?</h2>
      <div className={styles['learning__formats']} role="group" aria-label="Формат обучения">{formats.map(item => <button key={item.id} className={`${styles['learning__format']} ${format === item.id ? styles['learning__format--active'] : ''}`} aria-pressed={format === item.id} disabled={busy} onClick={() => { setFormat(item.id); reset(); }}><Icon name={item.icon} size={26} /><strong>{item.title}</strong><span>{item.description}</span></button>)}</div>
      {!selected && <div className={styles['learning__modules']} aria-label="Модули курса">{modules.map((module, index) => <button key={module.id} className={styles['learning__module']} disabled={busy} onClick={() => { reset(module); requestAnimationFrame(() => { panel.current?.focus(); panel.current?.scrollIntoView({ block: 'nearest' }); }); }}><span className={styles['learning__number']}>{index + 1}</span><strong>{module.title}</strong><span>{module.summary}</span><small>{module.minutes} мин. {progress.completed_modules.includes(module.id) ? '· Завершён' : ''}</small></button>)}</div>}
      {selected && <section ref={panel} tabIndex={-1} className={styles['learning__panel']} aria-label="Учебный материал">
        <div className={styles['learning__panel-heading']}><div><span>{formats.find(item => item.id === format)?.title}</span><h2>{selected.title}</h2></div><button disabled={busy} onClick={() => reset()} aria-label="Закрыть занятие">×</button></div>
        {result ? <div aria-live="polite"><h3>Результат: {result.score} из {result.total}</h3><p>{result.passed ? 'Занятие завершено. Прогресс сохранён.' : 'Разберите объяснения и попробуйте ещё раз. Ошибаться во время учёбы нормально.'}</p>{result.feedback.map(item => <div className={styles['learning__feedback']} key={item.question_id}><strong>{item.correct ? 'Верно' : 'Разберём ещё раз'}</strong><p>{questions.find(q => q.id === item.question_id)?.prompt}</p><p>{item.explanation}</p>{item.source_needed && <small>Формулировка требует проверки источника</small>}</div>)}<button className={styles['learning__primary']} onClick={() => reset(selected)}>Пройти ещё раз</button></div>
        : format === 'lesson' && !lessonRead ? <article className={styles['learning__article']} aria-label="Главное из мини-урока"><h3>Сначала — главное</h3><p>{selected.summary}</p>{selected.article.filter(paragraph => paragraph.length > 60).slice(0, 2).map((paragraph, index) => <p key={index}>{paragraph}</p>)}<p className={styles['learning__muted']}>Далее — карточки «верно или неверно», затем короткий тест. Объяснения ответов появятся после проверки.</p><button className={styles['learning__primary']} onClick={() => setLessonRead(true)}>Перейти к карточкам</button></article>
        : format === 'article' && !articleRead ? <article className={styles['learning__article']}>{selected.article.map((paragraph, index) => <p key={index}>{paragraph}</p>)}<p className={styles['learning__muted']}>После чтения — один вопрос на понимание. Нажатие кнопки не доказывает, что текст прочитан.</p><button className={styles['learning__primary']} onClick={() => setArticleRead(true)}>Перейти к вопросу</button></article>
        : question ? <div onTouchStart={event => { touchStart.current = event.touches[0]?.clientX ?? null; }} onTouchEnd={event => { const end = event.changedTouches[0]?.clientX; if (touchStart.current !== null && end !== undefined && Math.abs(end - touchStart.current) > 70) move(end < touchStart.current ? 1 : -1); touchStart.current = null; }} onKeyDown={event => { if (event.target instanceof HTMLInputElement) return; if (event.key === 'ArrowLeft') { event.preventDefault(); move(-1); } if (event.key === 'ArrowRight') { event.preventDefault(); move(1); } }}>
          <div className={styles['learning__question-progress']}><progress aria-label="Прогресс занятия" max={questions.length} value={step + 1} /><span>{step + 1} / {questions.length}</span></div>
          {format === 'lesson' && <p className={styles['learning__muted']}>{step < selected.cards.length ? 'Карточка: выберите ответ. Можно листать кнопками или свайпом.' : 'Короткий тест в конце мини-урока'}</p>}
          <form onSubmit={event => { event.preventDefault(); if (step < questions.length - 1) move(1); else void finish(); }}><fieldset className={styles['learning__question']} disabled={busy}><legend>{question.prompt}</legend>{question.options.map((option, index) => <label className={styles['learning__option']} key={`${question.id}-${index}`}><input type="radio" name={question.id} checked={answers[question.id] === index} onChange={() => chooseAnswer(question.id, index)} required />{option}</label>)}</fieldset><div className={styles['learning__actions']}><button type="button" disabled={step === 0 || busy} onClick={() => move(-1)}>← Назад</button><button className={styles['learning__primary']} disabled={answers[question.id] === undefined || busy}>{busy ? 'Сохраняем…' : step === questions.length - 1 ? 'Получить результат' : 'Далее →'}</button></div></form>
        </div> : <p>В этом модуле пока нет вопросов. Выберите другой модуль.</p>}
      </section>}
      <section className={styles['learning__rewards']} aria-label="Награды за серию"><h2>Регулярность приносит учебные бонусы</h2><p>Все награды виртуальные. Денежная программа с банком не подключена.</p><div className={styles['learning__milestones']}>{progress.rewards.map(reward => <article key={reward.days} className={`${styles['learning__milestone']} ${reward.unlocked ? styles['learning__milestone--unlocked'] : ''}`}><Icon name={reward.unlocked ? 'check' : 'lock'} size={22} /><strong>{reward.days} дней</strong><span>{reward.title}</span><small>{reward.unlocked ? 'Открыто' : `Ещё ${Math.max(0, reward.days - progress.streak_days)} дн.`}</small></article>)}</div>
        {monthly?.unlocked && <div className={styles['learning__claim']}>{monthly.selected_category ? <p role="status">Учебная дополнительная категория выбрана: {progress.categories.find(item => item.id === monthly.selected_category)?.title ?? monthly.selected_category}. Реальный кешбэк не изменился.</p> : <><label htmlFor="learning-category">Выберите +1 учебную категорию кешбэка</label><select id="learning-category" value={category} disabled={busy} onChange={event => { setCategory(event.target.value); claimKey.current = null; }}><option value="">Выберите категорию</option>{progress.categories.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select><button className={styles['learning__primary']} disabled={!category || busy} onClick={() => void claim()}>{busy ? 'Сохраняем…' : 'Выбрать учебную категорию'}</button></>}</div>}
      </section>
    </>}
  </section>;
}
