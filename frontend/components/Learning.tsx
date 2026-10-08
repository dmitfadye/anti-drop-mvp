'use client';
import { useState } from 'react';
import { Icon } from './Icon';
import { request } from './api';
import styles from './Workspace.module.css';
type Content = {
  stories: { title: string; text: string; emoji: string }[];
  quiz: { q: string; options: string[] }[];
};
type QuizResult = {
  score: number;
  total: number;
  cashback: number;
  details: { q: string; ok: boolean; explain: string }[];
};
const lessons = [
  {
    title: 'Основные схемы мошенников',
    text: 'Мошенники используют разные методы, чтобы получить доступ к вашим деньгам. На этом этапе вы узнаете о самых распространённых схемах и научитесь их распознавать.',
    icon: 'shield',
  },
  {
    title: 'Как распознать риск',
    text: 'Срочность, секретность и просьба назвать код — поводы остановиться. Неожиданное поступление с просьбой перевести деньги дальше также требует проверки.',
    icon: 'warning',
  },
  {
    title: 'Безопасные действия',
    text: 'Сделайте паузу. Проверьте отправителя другим способом. Откройте приложение банка самостоятельно и используйте контакты из него.',
    icon: 'lock',
  },
  {
    title: 'Что делать при подозрении',
    text: 'Прекратите разговор и не переводите деньги. Если вы уже раскрыли данные, обратитесь в банк через официальный канал и расскажите, что произошло.',
    icon: 'help',
  },
  {
    title: 'Полезные материалы',
    text: 'Прочитайте памятки в базе знаний и разберите примеры. Затем пройдите квиз, чтобы проверить, какие признаки риска вы запомнили.',
    icon: 'book',
  },
] as const;
export function Learning() {
  const [tab, setTab] = useState<'learning' | 'quiz'>('learning');
  const [lesson, setLesson] = useState(0);
  const [content, setContent] = useState<Content | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [question, setQuestion] = useState(0);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function load(startQuiz = false) {
    setBusy(true);
    setError('');
    try {
      setContent(await request<Content>('content'));
      if (startQuiz) setTab('quiz');
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Не удалось загрузить обучение.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function finish() {
    setBusy(true);
    setError('');
    try {
      setResult(
        await request<QuizResult>('quiz', {
          answers: content!.quiz.map((_, i) => answers[i] ?? -1),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось проверить ответы.');
    } finally {
      setBusy(false);
    }
  }
  const current = content?.quiz[question];
  return (
    <section
      id="learning"
      className={styles['workspace']}
      aria-labelledby="learning-title"
    >
      <header className={styles['workspace__heading']}>
        <h1 id="learning-title">Онбординг + квиз</h1>
        <p>Узнайте, как работают схемы мошенников, и проверьте свои знания</p>
      </header>
      <div
        className={styles['workspace__tabs']}
        role="tablist"
        aria-label="Обучение и квиз"
      >
        <button
          id="learning-tab"
          role="tab"
          aria-selected={tab === 'learning'}
          aria-controls="learning-panel"
          tabIndex={tab === 'learning' ? 0 : -1}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
              setTab('quiz');
              document.getElementById('quiz-tab')?.focus();
            }
          }}
          onClick={() => setTab('learning')}
        >
          Обучение
        </button>
        <button
          id="quiz-tab"
          role="tab"
          aria-selected={tab === 'quiz'}
          aria-controls="quiz-panel"
          tabIndex={tab === 'quiz' ? 0 : -1}
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
              setTab('learning');
              document.getElementById('learning-tab')?.focus();
            }
          }}
          onClick={() => setTab('quiz')}
        >
          Квиз
        </button>
      </div>
      <div
        id="learning-panel"
        role="tabpanel"
        aria-labelledby="learning-tab"
        hidden={tab !== 'learning'}
        className={styles['workspace__learning']}
      >
        <nav
          className={styles['workspace__lessons']}
          aria-label="Этапы обучения"
        >
          {lessons.map((item, i) => (
            <button
              key={item.title}
              aria-current={lesson === i ? 'step' : undefined}
              onClick={() => setLesson(i)}
            >
              <span>{i + 1}</span>
              {item.title}
              {i < lesson && <Icon name="check" size={14} />}
            </button>
          ))}
        </nav>
        <div className={styles['workspace__lesson']}>
          <div className={styles['workspace__lesson-main']}>
            <div className={styles['workspace__lesson-art']} aria-hidden="true">
              <Icon name={lessons[lesson].icon} size={80} />
            </div>
            <div>
              <h2>{lessons[lesson].title}</h2>
              <p>{lessons[lesson].text}</p>
              <button
                className={styles['workspace__primary']}
                disabled={busy}
                onClick={() => {
                  if (!content) void load();
                  else if (lesson < 4) setLesson(lesson + 1);
                  else setTab('quiz');
                }}
              >
                {busy
                  ? 'Загружаем…'
                  : !content
                    ? 'Начать обучение'
                    : lesson < 4
                      ? 'Следующий этап'
                      : 'Перейти к квизу'}
                <Icon name="arrow" size={16} />
              </button>
            </div>
          </div>
          {content && (
            <article className={styles['workspace__story']}>
              <h3>{content.stories[lesson % content.stories.length]?.title}</h3>
              <p>{content.stories[lesson % content.stories.length]?.text}</p>
            </article>
          )}
          <div className={styles['workspace__note']}>
            <Icon name="info" />
            <span>
              После изучения материала вы сможете пройти квиз и проверить свои
              знания.
            </span>
          </div>
        </div>
      </div>
      <div
        id="quiz-panel"
        role="tabpanel"
        aria-labelledby="quiz-tab"
        hidden={tab !== 'quiz'}
      >
        {!content ? (
          <div className={styles['workspace__card']}>
            <h2>Проверим ваши знания</h2>
            <p>
              Короткие вопросы о безопасных переводах и признаках мошенничества.
            </p>
            <button
              className={styles['workspace__primary']}
              disabled={busy}
              onClick={() => void load(true)}
            >
              {busy ? 'Загружаем…' : 'Начать квиз'}
            </button>
          </div>
        ) : result ? (
          <article className={styles['workspace__card']} aria-live="polite">
            <div className={styles['workspace__result-icon']}>
              <Icon name="cap" size={44} />
            </div>
            <h2>
              Результат: {result.score} из {result.total}
            </h2>
            <p>
              Учебная награда: {result.cashback} ₽. Реального начисления нет.
            </p>
            {result.details.map((detail) => (
              <div key={detail.q} className={styles['workspace__feedback']}>
                <strong>{detail.ok ? 'Верно' : 'Разберём ещё раз'}</strong>
                <p>{detail.explain}</p>
              </div>
            ))}
            <button
              className={styles['workspace__primary']}
              onClick={() => {
                setResult(null);
                setAnswers({});
                setQuestion(0);
              }}
            >
              Пройти ещё раз
            </button>
          </article>
        ) : (
          current && (
            <>
              <div className={styles['workspace__quiz-progress']}>
                <progress
                  max={content.quiz.length}
                  value={question + 1}
                  aria-label="Прогресс квиза"
                />
                <span>
                  {question + 1} / {content.quiz.length}
                </span>
              </div>
              <div className={styles['workspace__quiz-grid']}>
                <form
                  className={styles['workspace__card']}
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (question < content.quiz.length - 1)
                      setQuestion(question + 1);
                    else void finish();
                  }}
                >
                  <fieldset
                    className={styles['workspace__question']}
                    disabled={busy}
                  >
                    <legend>{current.q}</legend>
                    {current.options.map((option, i) => (
                      <label
                        key={option}
                        className={styles['workspace__option']}
                      >
                        <input
                          type="radio"
                          name={`question-${question}`}
                          required
                          checked={answers[question] === i}
                          onChange={() =>
                            setAnswers({ ...answers, [question]: i })
                          }
                        />
                        {option}
                      </label>
                    ))}
                  </fieldset>
                  <div className={styles['workspace__actions']}>
                    <button
                      type="button"
                      className={styles['workspace__button']}
                      disabled={question === 0 || busy}
                      onClick={() => setQuestion(question - 1)}
                    >
                      ← Назад
                    </button>
                    <button
                      className={styles['workspace__primary']}
                      disabled={answers[question] === undefined || busy}
                    >
                      {busy
                        ? 'Проверяем…'
                        : question === content.quiz.length - 1
                          ? 'Получить результат'
                          : 'Далее'}
                      <Icon name="arrow" size={16} />
                    </button>
                  </div>
                </form>
                <aside className={styles['workspace__aside']}>
                  <Icon name="lock" size={32} />
                  <h3>Почему это важно</h3>
                  <p>
                    Пауза и проверка помогают заметить давление и принять
                    взвешенное решение.
                  </p>
                </aside>
              </div>
            </>
          )
        )}
      </div>
      {error && (
        <p className={styles['workspace__error']} role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
