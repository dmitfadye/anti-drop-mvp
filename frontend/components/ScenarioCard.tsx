import { useEffect, useRef } from 'react';
import Image from 'next/image';
import { Icon } from './Icon';
import type { LearningModule, LearningQuestion, PracticeFeedback } from './learning-api';
import { learningTheme } from './learning-theme';
import styles from './Learning.module.css';
export function ScenarioCard({ topic, question, answer, feedback, busy, onAnswer, onSubmit, label, primaryLabel }: { topic: LearningModule; question: LearningQuestion; answer?: number; feedback?: PracticeFeedback; busy: boolean; onAnswer: (answer: number) => void; onSubmit: () => void; label: string; primaryLabel: string }) {
  const feedbackPanel = useRef<HTMLDivElement>(null);
  const theme = learningTheme(topic.id);
  const isCall = question.scenario_type === 'call';
  useEffect(() => { if (feedback) feedbackPanel.current?.focus({ preventScroll: true }); }, [feedback]);
  return <div className={styles['learning__scenario-layout']}>
    <aside className={styles['learning__situation']} data-theme={theme.color} data-scene={isCall ? 'call' : 'topic'} aria-label="Учебная ситуация">
      <span className={styles['learning__pill']}><Icon name={theme.icon} size={14} />{question.scenario_text ? 'Вымышленная ситуация' : theme.label}</span>
      {isCall ? <div className={styles['learning__phone']}>
        <Image className={styles['learning__phone-art']} src="/images/learning/scenario-phone.png" alt="" fill sizes="(max-width: 767px) 320px, 380px" />
        <div className={styles['learning__phone-content']}>
          <div className={styles['learning__caller-icon']}><Icon name="user" size={30} /></div>
          <p className={styles['learning__eyebrow']}>Входящий звонок</p>
          <h3>Собеседник на линии</h3>
          <blockquote>{question.scenario_text}</blockquote>
        </div>
      </div> : <>
        <div className={styles['learning__scene-art']}><Image src={`/images/learning/${question.scenario_type === 'message' ? 'messages' : theme.asset}.png`} alt="" fill sizes="(max-width: 767px) 300px, 400px" /></div>
        <div className={styles['learning__scene-context']}><span className={styles['learning__eyebrow']}>{question.scenario_type === 'message' ? 'Входящее сообщение' : 'Тема ситуации'}</span><h3>{question.scenario_type === 'message' ? 'Незнакомый отправитель' : theme.title}</h3><p>{question.scenario_text ?? topic.summary}</p></div>
      </>}
      <p className={styles['learning__situation-note']}>Сделайте паузу. Решение за вами.</p>
    </aside>
    <div className={styles['learning__decision']}>
      <span className={styles['learning__eyebrow']}>{label}</span>
      <form onSubmit={event => { event.preventDefault(); onSubmit(); }}>
        <fieldset className={styles['learning__question']} disabled={busy || !!feedback}>
          <legend>{question.prompt}</legend>
          {question.options.map((option, index) => <label key={`${question.id}-${index}`} className={`${styles['learning__option']} ${feedback && index === feedback.correct_index ? styles['learning__option--correct'] : ''} ${feedback && !feedback.correct && answer === index ? styles['learning__option--incorrect'] : ''}`}>
            <input type="radio" name={question.id} checked={answer === index} onChange={() => onAnswer(index)} required />
            <span className={styles['learning__answer-letter']} aria-hidden="true">{String.fromCharCode(1040 + index)}</span>
            <span>{option}</span>{feedback && index === feedback.correct_index && <Icon name="check" size={20} />}
          </label>)}
        </fieldset>
        {!feedback && <button className={styles['learning__primary']} disabled={answer === undefined || busy}>{busy ? 'Проверяем…' : primaryLabel}</button>}
      </form>
      {feedback && <div ref={feedbackPanel} tabIndex={-1} className={`${styles['learning__feedback']} ${feedback.correct ? styles['learning__feedback--correct'] : styles['learning__feedback--incorrect']}`} role="status">
        <h3><Icon name={feedback.correct ? 'check' : 'info'} />{feedback.correct ? 'Верно. Вы выбрали безопасный шаг' : 'Разберём ситуацию вместе'}</h3>
        <p>{feedback.explanation}</p>
        {feedback.danger_sign && <p><strong>Признак риска:</strong> {feedback.danger_sign}</p>}
        {feedback.safe_action && <p><strong>Безопасный шаг:</strong> {feedback.safe_action}</p>}
        {feedback.source_needed && <small>Формулировка требует проверки источника</small>}
        {question.source_url && <a href={question.source_url} target="_blank" rel="noreferrer">Материал Банка России ↗</a>}
      </div>}
    </div>
  </div>;
}
