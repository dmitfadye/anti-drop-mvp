'use client';
import { useState } from 'react';
import { Icon } from './Icon';
import { request } from './api';
import styles from './Workspace.module.css';
type SimResult = {
  ok: boolean;
  errors: string[];
  limits?: { note?: string };
  checklist?: string[];
};
const steps = ['Проверка личности', 'Новый номер', 'Подтверждение', 'Готово'];
function canonical(value: string) {
  const clean = value.trim().replace(/[\s()-]/g, '');
  return /^8\d{10}$/.test(clean) ? `+7${clean.slice(1)}` : clean;
}
export function PhoneChange() {
  const [step, setStep] = useState(0);
  const [oldPhone, setOldPhone] = useState('+7 916 000 00 01');
  const [newPhone, setNewPhone] = useState('');
  const [oldCode, setOldCode] = useState('');
  const [newCode, setNewCode] = useState('');
  const [oldVerified, setOldVerified] = useState(false);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<SimResult | null>(null);
  function reset() {
    setStep(0);
    setOldCode('');
    setNewCode('');
    setOldVerified(false);
    setSent(false);
    setError('');
    setResult(null);
    setNewPhone('');
  }
  async function next() {
    setError('');
    if (step === 0) {
      if (!/^\+?\d{10,15}$/.test(canonical(oldPhone))) {
        setError('Укажите корректный текущий номер.');
        return;
      }
      if (!sent || oldCode !== '123456') {
        setError('Введите учебный код 123456 после запроса кода.');
        return;
      }
      setOldVerified(true);
      setSent(false);
      setStep(1);
    } else if (step === 1) {
      if (!/^\+?\d{10,15}$/.test(canonical(newPhone))) {
        setError('Укажите корректный новый номер: от 10 до 15 цифр.');
        return;
      }
      if (canonical(oldPhone) === canonical(newPhone)) {
        setError('Новый номер должен отличаться от текущего.');
        return;
      }
      setSent(false);
      setStep(2);
    } else if (step === 2) {
      if (!oldVerified || !sent || newCode !== '123456') {
        setError('Подтвердите новый номер учебным кодом 123456.');
        return;
      }
      setBusy(true);
      try {
        const response = await request<SimResult>('sim', {
          old_phone: oldPhone,
          new_phone: newPhone,
          otp_ok_old: oldVerified,
          otp_ok_new: newCode === '123456',
        });
        setResult(response);
        if (response.ok) setStep(3);
        else setError(response.errors.join(' '));
      } catch (e) {
        setError(
          e instanceof Error ? e.message : 'Не удалось выполнить проверку.',
        );
      } finally {
        setBusy(false);
      }
    }
  }
  return (
    <section
      id="phone"
      className={styles['workspace']}
      aria-labelledby="phone-title"
    >
      <header className={styles['workspace__heading']}>
        <h1 id="phone-title">Смена номера</h1>
        <p>Безопасная смена номера телефона (защита от перехвата SMS)</p>
      </header>
      <ol
        className={styles['workspace__steps']}
        aria-label="Этапы смены номера"
      >
        {steps.map((label, i) => (
          <li
            key={label}
            aria-current={step === i ? 'step' : undefined}
            className={`${styles['workspace__step']} ${i < step ? styles['workspace__step--complete'] : ''}`}
          >
            <span>{i < step ? <Icon name="check" size={14} /> : i + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      <div className={styles['workspace__card']}>
        <div className={styles['workspace__phone-grid']}>
          <form
            id="phone-form"
            onSubmit={(e) => {
              e.preventDefault();
              void next();
            }}
          >
            <h2>
              {
                [
                  'Проверка личности',
                  'Введите новый номер',
                  'Подтвердите новый номер',
                  'Демонстрация завершена',
                ][step]
              }
            </h2>
            <p>
              {
                [
                  'Для безопасности нам нужно убедиться, что это действительно вы.',
                  'Укажите вымышленный номер для учебной проверки.',
                  'Подтвердите доступ ко второму номеру.',
                  'Подтверждения приняты. Реальный номер в банке не изменён.',
                ][step]
              }
            </p>
            {step === 0 && (
              <>
                <label className={styles['workspace__field']}>
                  Текущий номер телефона
                  <input
                    type="tel"
                    name="old_phone"
                    value={oldPhone}
                    onChange={(e) => {
                      setOldPhone(e.target.value);
                      setOldVerified(false);
                      setSent(false);
                      setOldCode('');
                    }}
                    required
                  />
                </label>
                <label className={styles['workspace__field']}>
                  Введите код из SMS
                  <input
                    autoComplete="off"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="Код из SMS"
                    value={oldCode}
                    onChange={(e) =>
                      setOldCode(e.target.value.replace(/\D/g, ''))
                    }
                    disabled={!sent}
                  />
                </label>
              </>
            )}
            {step === 1 && (
              <label className={styles['workspace__field']}>
                Новый номер телефона
                <input
                  type="tel"
                  name="new_phone"
                  placeholder="+7 ___ ___ __ __"
                  value={newPhone}
                  onChange={(e) => {
                    setNewPhone(e.target.value);
                    setNewCode('');
                  }}
                  required
                />
              </label>
            )}
            {step === 2 && (
              <>
                <p className={styles['workspace__phone-number']}>{newPhone}</p>
                <label className={styles['workspace__field']}>
                  Код для нового номера
                  <input
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="Код из SMS"
                    value={newCode}
                    onChange={(e) =>
                      setNewCode(e.target.value.replace(/\D/g, ''))
                    }
                    disabled={!sent}
                  />
                </label>
              </>
            )}
            {(step === 0 || step === 2) && (
              <button
                type="button"
                className={styles['workspace__button']}
                onClick={() => {
                  setSent(true);
                  setError('');
                }}
              >
                {sent ? 'Повторить учебный код' : 'Отправить код'}
              </button>
            )}
            {sent && (step === 0 || step === 2) && (
              <p className={styles['workspace__caption']} role="status">
                Учебный код: 123456. Настоящее SMS не отправлено.
              </p>
            )}
            {step === 3 && result?.ok && (
              <div role="status">
                <h3>Демонстрация: подтверждения приняты</h3>
                <p>{result.limits?.note}</p>
                <ul>
                  {result.checklist?.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {error && (
              <p className={styles['workspace__error']} role="alert">
                {error}
              </p>
            )}
          </form>
          <aside className={styles['workspace__aside']}>
            <span className={styles['workspace__aside-icon']}>
              <Icon name="lock" size={32} />
            </span>
            <h3>Почему это безопасно?</h3>
            <p>
              Два подтверждения проверяют доступ к старому и новому номерам.
              После учебной смены backend применяет ограничения на переводы.
            </p>
          </aside>
        </div>
        <div className={styles['workspace__actions']}>
          <button
            className={styles['workspace__button']}
            disabled={busy}
            onClick={reset}
          >
            {step === 3 ? 'Начать заново' : 'Отмена'}
          </button>
          {step < 3 && (
            <button
              className={styles['workspace__primary']}
              form="phone-form"
              disabled={busy}
            >
              {busy ? 'Проверяем…' : 'Далее'}
              <Icon name="arrow" size={17} />
            </button>
          )}
        </div>
      </div>
      <p className={styles['workspace__caption']}>
        Учебный тренажёр · SMS не отправляются, номер в банке не меняется.
      </p>
    </section>
  );
}
