'use client';
import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import { Icon, type IconName } from './Icon';
import { ScenarioCard } from './ScenarioCard';
import { learningTheme } from './learning-theme';
import { useSection } from './useSection';
import { learningRequest, type LearningCatalog, type LearningFormat, type LearningModule, type LearningProgress, type LearningResult, type PracticeFeedback } from './learning-api';
import { draftKey, historyKey, newSession, questionsFor, readDraft, readHistory, type AttemptSummary, type LearningSession } from './learning-session';
import styles from './Learning.module.css';

const formats = [
  { id: 'lesson', title: 'Мини-урок + тест', description: 'Разберите ситуации по карточкам', icon: 'layers' },
  { id: 'quiz', title: 'Тест', description: 'Сразу проверьте знания', icon: 'cap' },
  { id: 'article', title: 'Статья', description: 'Прочитайте в своём темпе', icon: 'book' },
] as const;
const topicIcons: IconName[] = ['shield', 'arrow', 'file', 'search', 'warning', 'lock', 'help', 'phone'];
const fetchCourse = () => Promise.all([learningRequest<LearningCatalog>('catalog'), learningRequest<LearningProgress>('progress')]);

export function Learning() {
  const active = useSection();
  const [catalog, setCatalog] = useState<LearningCatalog>({ version: '', modules: [] });
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [storageWarning, setStorageWarning] = useState('');
  const [format, setFormat] = useState<LearningFormat>('lesson');
  const [session, setSession] = useState<LearningSession | null>(null);
  const [paused, setPaused] = useState<LearningSession | null>(null);
  const [result, setResult] = useState<LearningResult | null>(null);
  const [history, setHistory] = useState<AttemptSummary[]>([]);
  const [reviewIds, setReviewIds] = useState<string[]>([]);
  const [category, setCategory] = useState('');
  const hydrated = useRef(false);
  const requestEpoch = useRef(0);
  const submitting = useRef(false);
  const claimKey = useRef<string | null>(null);
  const panel = useRef<HTMLElement>(null);
  const questionHeading = useRef<HTMLDivElement>(null);
  const catalogHeading = useRef<HTMLHeadingElement>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const selected = catalog.modules.find(module => module.id === session?.moduleId);
  const allQuestions = selected && session ? questionsFor(selected, session.format) : [];
  const questions = reviewIds.length ? allQuestions.filter(question => reviewIds.includes(question.id)) : allQuestions;
  const question = session ? questions[session.step] : undefined;
  const feedback = question && session ? session.feedback[question.id] : undefined;
  const practice = !!session && session.format === 'lesson' && !!selected?.cards.some(card => card.id === question?.id);
  const sessionModuleId = session?.moduleId;
  const sessionStage = session?.stage;
  const sessionStep = session?.step;

  function install(data: LearningCatalog, state: LearningProgress) {
    setCatalog(data); setProgress(state); setError('');
    if (!hydrated.current) {
      hydrated.current = true;
      const saved = readDraft(data);
      setSession(saved.session); setNotice(saved.message); setHistory(readHistory());
      if (saved.session) setFormat(saved.session.format);
    } else {
      setSession(current => current && data.modules.some(item => item.id === current.moduleId) ? current : null);
      setPaused(current => current && data.modules.some(item => item.id === current.moduleId) ? current : null);
    }
  }
  async function load() {
    const epoch = ++requestEpoch.current;
    setLoading(true); setError('');
    try {
      const [data, state] = await fetchCourse();
      if (epoch === requestEpoch.current) install(data, state);
    } catch (e) { if (epoch === requestEpoch.current) setError(e instanceof Error ? e.message : 'Не удалось загрузить курс.'); }
    finally { if (epoch === requestEpoch.current) setLoading(false); }
  }
  useEffect(() => {
    if (active !== 'learning') return;
    const epoch = ++requestEpoch.current;
    let live = true;
    // Defer state updates to the request continuation; retained sessions remain mounted.
    void Promise.resolve().then(() => { if (live) { setLoading(true); setError(''); } return fetchCourse(); })
      .then(([data, state]) => { if (live && epoch === requestEpoch.current) install(data, state); })
      .catch(e => { if (live && epoch === requestEpoch.current) setError(e instanceof Error ? e.message : 'Не удалось загрузить курс.'); })
      .finally(() => { if (live && epoch === requestEpoch.current) setLoading(false); });
    return () => { live = false; };
  }, [active]);
  useEffect(() => {
    if (!session || result || reviewIds.length) return;
    try { localStorage.setItem(draftKey, JSON.stringify(session)); }
    catch { queueMicrotask(() => setStorageWarning('Браузер не разрешил сохранить черновик. До закрытия страницы занятие доступно.')); }
  }, [session, result, reviewIds]);
  useEffect(() => {
    if (!sessionModuleId) return;
    const frame = requestAnimationFrame(() => {
      if (sessionStage === 'intro' || result) panel.current?.focus({ preventScroll: true });
      else questionHeading.current?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [sessionModuleId, sessionStage, sessionStep, result]);

  function start(module: LearningModule, chosen = format) {
    if (busy) return;
    trigger.current = document.activeElement instanceof HTMLButtonElement ? document.activeElement : null;
    setSession(newSession(module, chosen, catalog.version)); setPaused(null); setFormat(chosen); setResult(null); setReviewIds([]); setError(''); setNotice('');
    requestAnimationFrame(() => panel.current?.scrollIntoView({ block: 'start' }));
  }
  function close() {
    if (busy) return;
    if (session && !result && !reviewIds.length) { setPaused(session); setNotice('Занятие на паузе. Вы можете продолжить с этого шага.'); }
    setSession(null); setResult(null); setReviewIds([]); setError('');
    requestAnimationFrame(() => { if (trigger.current?.isConnected) trigger.current.focus(); else catalogHeading.current?.focus(); });
  }
  function chooseAnswer(answer: number) {
    if (!session || !question || busy || feedback) return;
    setSession({ ...session, answers: { ...session.answers, [question.id]: answer }, attemptKey: crypto.randomUUID(), updatedAt: new Date().toISOString() });
  }
  function advance(direction: number) {
    if (!session || !question || busy) return;
    if (direction > 0 && (session.answers[question.id] === undefined || (practice && !feedback))) return;
    setSession({ ...session, step: Math.max(0, Math.min(questions.length - 1, session.step + direction)), updatedAt: new Date().toISOString() });
    setError(''); setNotice('');
  }
  async function checkPractice() {
    if (!session || !question || session.answers[question.id] === undefined || submitting.current) return;
    submitting.current = true; setBusy(true); setError('');
    try {
      const checked = await learningRequest<PracticeFeedback>('practice', { module_id: session.moduleId, question_id: question.id, answer: session.answers[question.id], course_version: session.courseVersion });
      setSession(current => current ? { ...current, feedback: { ...current.feedback, [question.id]: checked } } : current);
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось проверить ответ.'); }
    finally { submitting.current = false; setBusy(false); }
  }
  async function finish() {
    if (!session || !selected || submitting.current) return;
    submitting.current = true; ++requestEpoch.current; setLoading(false); setBusy(true); setError('');
    try {
      const response = await learningRequest<{ progress: LearningProgress; result: LearningResult }>('completions', { module_id: selected.id, format: session.format, answers: session.answers, idempotency_key: session.attemptKey, course_version: session.courseVersion });
      setProgress(response.progress); setResult(response.result); setPaused(null); setNotice('');
      const attempt: AttemptSummary = { id: session.attemptKey, moduleId: selected.id, courseVersion: session.courseVersion, format: session.format, completedAt: new Date().toISOString(), passed: response.result.passed, score: response.result.score, total: response.result.total, mistakes: response.result.feedback.filter(item => !item.correct).map(item => item.question_id) };
      const next = [attempt, ...readHistory().filter(item => item.id !== attempt.id)].slice(0, 20);
      setHistory(next);
      try { localStorage.removeItem(draftKey); localStorage.setItem(historyKey, JSON.stringify(next)); }
      catch { setStorageWarning('Результат подтверждён сервером, но локальную историю обновить не удалось.'); }
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось проверить ответы.'); }
    finally { submitting.current = false; setBusy(false); }
  }
  function reviewMistakes() {
    if (!session || !selected || !result) return;
    const ids = result.feedback.filter(item => !item.correct && selected.cards.some(card => card.id === item.question_id)).map(item => item.question_id);
    if (!ids.length) return;
    setReviewIds(ids); setSession({ ...session, stage: 'questions', step: 0, answers: {}, feedback: {} }); setResult(null); setNotice('Повторение — без начисления баллов. Итоговую проверку можно пройти отдельно.');
  }
  function reviewAttempt(attempt: AttemptSummary) {
    const topic = catalog.modules.find(item => item.id === attempt.moduleId);
    if (!topic || busy) return;
    const ids = topic.cards.filter(card => attempt.mistakes.includes(card.id)).map(card => card.id);
    if (!ids.length) { start(topic, 'quiz'); return; }
    trigger.current = document.activeElement instanceof HTMLButtonElement ? document.activeElement : null;
    setSession({ ...newSession(topic, 'lesson', catalog.version), stage: 'questions' });
    setReviewIds(ids); setResult(null); setNotice('Повторение — без начисления баллов. Итоговую проверку можно пройти отдельно.'); setError('');
  }
  function submitQuestion() {
    if (practice && !feedback) void checkPractice();
    else if (session && session.step < questions.length - 1) advance(1);
    else if (!reviewIds.length) void finish();
  }
  async function claim() {
    if (!category || submitting.current) return;
    submitting.current = true; ++requestEpoch.current; setLoading(false); setBusy(true); setError(''); claimKey.current ??= crypto.randomUUID();
    try {
      const response = await learningRequest<{ progress: LearningProgress }>('rewards/30/claim', { category, idempotency_key: claimKey.current });
      setProgress(response.progress);
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось выбрать категорию.'); }
    finally { submitting.current = false; setBusy(false); }
  }
  const monthly = progress?.rewards.find(reward => reward.days === 30);
  const featured = catalog.modules.find(module => module.id === 'm8_phone_fraud') ?? catalog.modules[0];
  const wrongPractice = result?.feedback.some(item => !item.correct && selected?.cards.some(card => card.id === item.question_id));
  const currentVersion = !session || session.courseVersion === catalog.version;

  return <section id="learning" className={styles['learning']} aria-labelledby="learning-title">
    <header className={styles['learning__heading']}><div><p className={styles['learning__eyebrow']}>Центр финансовой безопасности</p><h1 id="learning-title">Учитесь замечать главное</h1><p>Короткие ситуации. Спокойные решения. Навык, который остаётся с вами.</p></div><span className={styles['learning__badge']}>Учебный режим</span></header>
    <p className={styles['learning__disclaimer']}>Общий демо-профиль: прогресс виден участникам стенда. Банк не подключён. Баллы и награды — учебные.</p>
    {notice && <div className={styles['learning__notice']} role="status"><Icon name="info" /><span>{notice}</span></div>}
    {storageWarning && <p role="status">{storageWarning}</p>}
    {loading && <p role="status">Загружаем курс и сохранённый прогресс…</p>}
    {error && <div className={styles['learning__error']} role="alert"><p>{error}</p><button disabled={loading || busy} onClick={() => void load()}>Повторить загрузку</button></div>}
    {progress && <>
      {!session && <>
        <div className={styles['learning__hero']}>
          <div><span className={styles['learning__pill']}>Практика на каждый день</span><h2>Не спешить.<br />Проверить. Решить.</h2><p>Разберите звонки и сообщения в безопасной среде. Здесь можно ошибиться — и понять почему.</p>{featured && <button className={styles['learning__primary']} onClick={() => start(featured, 'lesson')}>Разобрать звонок <Icon name="arrow" size={18} /></button>}</div>
          <div className={styles['learning__hero-art']} aria-hidden="true"><Image className={styles['learning__hero-image']} src="/images/learning/safety-shield.png" alt="" fill sizes="(max-width: 767px) 180px, 440px" priority /><span className={styles['learning__floating-pill']}><Icon name="phone" size={18} /> Без давления</span></div>
        </div>
        {paused && <div className={styles['learning__resume']}><div><span className={styles['learning__eyebrow']}>Ваше занятие на паузе</span><h3>{catalog.modules.find(module => module.id === paused.moduleId)?.title}</h3><p>Шаг {paused.step + 1}. Ответы сохранены в этом браузере.</p></div><button className={styles['learning__primary']} onClick={() => { setSession(paused); setPaused(null); setNotice('Занятие восстановлено. Продолжайте с сохранённого шага.'); }}>Продолжить занятие <Icon name="arrow" size={18} /></button></div>}
        <div className={styles['learning__stats']}>
          <article><Icon name="cap" /><div><strong>{progress.rank.title}</strong><span>{progress.xp} учебных баллов</span></div><progress aria-label="Прогресс до следующего звания" max={100} value={progress.rank_progress_percent} /></article>
          <article><Icon name="clock" /><div><strong>{progress.streak_days} дн. подряд</strong><span>В своём ритме, без гонки</span></div></article>
          <article><Icon name="check" /><div><strong>{progress.completed_modules.length} / {catalog.modules.length} тем</strong><span>Завершён выбранный формат</span></div></article>
        </div>
        <div className={styles['learning__catalog-heading']}><div><h2 ref={catalogHeading} tabIndex={-1}>Выберите, что потренировать</h2><p>«Спокойные переводы» · {catalog.modules.length} тем · можно начать с любой</p></div><span className={styles['learning__pill']}>В своём темпе</span></div>
        <div className={styles['learning__formats']} role="group" aria-label="Формат обучения">{formats.map(item => <button key={item.id} className={`${styles['learning__format']} ${format === item.id ? styles['learning__format--active'] : ''}`} aria-pressed={format === item.id} onClick={() => setFormat(item.id)}><Icon name={item.icon} /><strong>{item.title}</strong><span>{item.description}</span></button>)}</div>
        <div className={styles['learning__modules']} aria-label="Модули курса">{catalog.modules.map((module, index) => {
          const underway = paused?.moduleId === module.id;
          const completed = progress.completed_modules.includes(module.id);
          const count = underway ? Object.keys(paused.answers).length : completed ? questionsFor(module, format).length : 0;
          const total = questionsFor(module, underway ? paused.format : format).length;
          return <button key={module.id} className={styles['learning__module']} data-theme={learningTheme(module.id).color} onClick={() => { if (underway) { setSession(paused); setPaused(null); } else start(module); }}>
            <span className={styles['learning__module-top']}><span className={styles['learning__topic-icon']}><Icon name={topicIcons[index % topicIcons.length]} size={26} /></span><span className={`${styles['learning__pill']} ${completed ? styles['learning__pill--done'] : ''}`}>{underway ? 'В процессе' : completed ? 'Завершён' : 'Не начато'}</span></span>
            <strong>{module.title}</strong><span>{module.summary}</span><small>{module.minutes} мин. · {module.cards.length} карточек · 1 занятие</small>
            <progress aria-label={`Прогресс: ${module.title}`} value={Math.min(count, total)} max={Math.max(total, 1)} /><span className={styles['learning__module-action']}>{underway ? 'Продолжить' : completed ? 'Повторить' : 'Начать занятие'} <Icon name="arrow" size={18} /></span>
          </button>;
        })}</div>
        {!catalog.modules.length && <p>Тем пока нет. Попробуйте загрузить каталог позже.</p>}
        <p className={styles['learning__source']}>Исходные материалы — черновик. Прохождение статьи означает знакомство с темой, а не сдачу итогового теста. {progress.rank_note}</p>
      </>}
      {session && selected && <section ref={panel} tabIndex={-1} className={styles['learning__panel']} aria-label="Учебный материал">
        <div className={styles['learning__panel-heading']}><button className={styles['learning__back']} disabled={busy} onClick={close}><Icon name="arrow" size={16} /> {result ? 'К темам' : 'Пауза и к темам'}</button><span className={styles['learning__pill']}>{reviewIds.length ? 'Повторение ошибок' : session.format === 'quiz' ? 'Итоговая проверка' : session.format === 'article' ? 'Чтение' : practice ? 'Практика' : 'Мини-урок + тест'}</span></div>
        <h2>{selected.title}</h2>
        {!currentVersion && <div role="alert" className={styles['learning__error']}>Материалы обновились. Начните занятие заново, чтобы ответы соответствовали новой версии.<button onClick={() => start(selected, session.format)}>Начать обновлённое занятие</button></div>}
        {result ? <div className={styles['learning__result']} aria-live="polite">
          <span className={styles['learning__result-icon']}><Icon name={result.passed ? 'check' : 'book'} size={36} /></span><p className={styles['learning__eyebrow']}>Ещё один шаг к осознанным решениям</p><h3>Результат: {result.score} из {result.total}</h3>
          <p>{result.passed ? 'Занятие завершено. Прогресс сохранён.' : 'Разберите объяснения и попробуйте ещё раз. Ошибаться во время учёбы нормально.'}</p>
          {result.assessment_total !== undefined && <p>Независимая проверка: {result.assessment_score} из {result.assessment_total}. Практика не заменяет итоговое решение.</p>}
          <p className={styles['learning__muted']}>{session.format === 'article' ? 'Вы познакомились с темой. Для проверки навыка пройдите тест.' : 'Этот результат относится к учебному занятию и не гарантирует безопасность реальных операций.'}</p>
          <div className={styles['learning__actions']}>{wrongPractice && <button className={styles['learning__primary']} onClick={reviewMistakes}>Повторить ошибки</button>}<button onClick={() => start(selected, session.format)}>Пройти ещё раз</button><button onClick={() => start(selected, 'quiz')}>Пройти итоговый тест</button><button onClick={close}>Вернуться к темам</button></div>
          <div className={styles['learning__result-feedback']}>{result.feedback.map(item => <div className={styles['learning__feedback']} key={item.question_id}><strong>{item.correct ? 'Верно' : 'Разберём ещё раз'}</strong><p>{allQuestions.find(q => q.id === item.question_id)?.prompt}</p><p>{item.explanation}</p>{item.source_needed && <small>Формулировка требует проверки источника</small>}</div>)}</div>
        </div> : session.stage === 'intro' ? <article className={styles['learning__article']} aria-label={session.format === 'article' ? 'Статья' : 'Главное из мини-урока'}>
          <div className={styles['learning__intro-icon']}><Icon name={selected.id === 'm8_phone_fraud' ? 'phone' : 'shield'} size={40} /></div><h3>{session.format === 'article' ? 'Читайте в своём темпе' : 'Сначала — главное'}</h3><p>{selected.summary}</p>{selected.article.slice(0, session.format === 'article' ? undefined : 3).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          <p className={styles['learning__muted']}>{session.format === 'article' ? 'После чтения — один вопрос на понимание. Нажатие кнопки не доказывает, что текст прочитан.' : `${selected.cards.length} карточек с разбором, затем ${selected.quiz.length} вопросов без подсказок. Отвечайте спокойно: таймера нет.`}</p><button className={styles['learning__primary']} onClick={() => setSession({ ...session, stage: 'questions' })}>{session.format === 'article' ? 'Перейти к вопросу' : 'Перейти к карточкам'} <Icon name="arrow" size={18} /></button>
        </article> : question ? <div onTouchStart={event => { const touch = event.touches[0]; touchStart.current = touch ? { x: touch.clientX, y: touch.clientY } : null; }} onTouchEnd={event => { const end = event.changedTouches[0]; const start = touchStart.current; if (start && end && Math.abs(end.clientX - start.x) > 85 && Math.abs(end.clientY - start.y) < 45) advance(end.clientX < start.x ? 1 : -1); touchStart.current = null; }} onKeyDown={event => { if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return; if (event.key === 'ArrowLeft') { event.preventDefault(); advance(-1); } if (event.key === 'ArrowRight') { event.preventDefault(); advance(1); } }}>
          <div ref={questionHeading} tabIndex={-1} className={styles['learning__question-progress']} aria-label={`Вопрос ${session.step + 1} из ${questions.length}`}><progress aria-label="Прогресс занятия" max={questions.length} value={session.step} /><span aria-live="polite">{session.step + 1} / {questions.length}</span></div>
          <ScenarioCard key={question.id} topic={selected} question={question} answer={session.answers[question.id]} feedback={feedback} busy={busy || !currentVersion} onAnswer={chooseAnswer} onSubmit={submitQuestion} label={reviewIds.length ? 'Закрепление навыка' : practice ? 'Выберите безопасное действие' : 'Проверьте себя без подсказок'} primaryLabel={practice ? 'Проверить ответ' : session.step === questions.length - 1 ? 'Получить результат' : 'Далее →'} />
          <div className={styles['learning__actions']}><button disabled={session.step === 0 || busy} onClick={() => advance(-1)}>← Назад</button>{feedback && (session.step < questions.length - 1 ? <button className={styles['learning__primary']} disabled={busy} onClick={() => advance(1)}>Далее →</button> : reviewIds.length ? <button className={styles['learning__primary']} onClick={() => { close(); setNotice('Разбор завершён. Для новой проверки пройдите итоговый тест.'); }}>Завершить повторение</button> : <button className={styles['learning__primary']} disabled={busy} onClick={() => void finish()}>Получить результат</button>)}</div>
          <p className={styles['learning__gesture-hint']}>Кнопки, стрелки клавиатуры или свайп — после разбора карточки. Скорость ответа не оценивается.</p>
        </div> : <p>В этом модуле пока нет вопросов. Вернитесь к темам.</p>}
      </section>}
      {!session && <>
        {history.length > 0 && <section className={styles['learning__history']}><h2>Ваши последние занятия</h2><p>История этого браузера. Подтверждённый общий прогресс хранится на сервере.</p>{history.slice(0, 3).map(attempt => <div key={attempt.id}><span>{catalog.modules.find(module => module.id === attempt.moduleId)?.title ?? 'Предыдущее занятие'}</span><strong>{attempt.score} / {attempt.total}</strong><span>{attempt.passed ? 'Завершено' : 'Есть что повторить'}</span>{attempt.mistakes.length > 0 && attempt.courseVersion === catalog.version && <button onClick={() => reviewAttempt(attempt)}>Повторить ошибки занятия</button>}</div>)}</section>}
        <section className={styles['learning__rewards']} aria-label="Награды за серию"><h2>Регулярность важнее скорости</h2><p>Виртуальные бонусы за привычку учиться. Реальные деньги не начисляются.</p><div className={styles['learning__milestones']}>{progress.rewards.map(reward => <article key={reward.days} className={styles['learning__milestone']}><Icon name={reward.unlocked ? 'check' : 'lock'} /><strong>{reward.days} дней</strong><span>{reward.title}</span><small>{reward.unlocked ? 'Открыто' : `Ещё ${Math.max(0, reward.days - progress.streak_days)} дн.`}</small></article>)}</div>
          {monthly?.unlocked && <div className={styles['learning__claim']}>{monthly.selected_category ? <p role="status">Учебная дополнительная категория выбрана: {progress.categories.find(item => item.id === monthly.selected_category)?.title ?? monthly.selected_category}. Реальный кешбэк не изменился.</p> : <><label htmlFor="learning-category">Выберите +1 учебную категорию кешбэка</label><select id="learning-category" value={category} disabled={busy} onChange={event => { setCategory(event.target.value); claimKey.current = null; }}><option value="">Выберите категорию</option>{progress.categories.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select><button className={styles['learning__primary']} disabled={!category || busy} onClick={() => void claim()}>Выбрать учебную категорию</button></>}</div>}
        </section>
      </>}
    </>}
  </section>;
}
