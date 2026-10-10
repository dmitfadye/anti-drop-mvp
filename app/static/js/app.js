/* Анти-Дроп P1 — клиентский слой.
 *
 * Правила, которые здесь соблюдаются намеренно:
 *  - никакого innerHTML для данных: текст, коды причин, переводы и case_id
 *    ставятся только через textContent / createElement;
 *  - каждый запрос получает AbortController и порядковый номер: смена сценария
 *    или языка не должна приводить к тому, что старый ответ перетрёт новый;
 *  - кнопка блокируется на время запроса, ошибка показывается текстом;
 *  - состояние форм не теряется при сетевой ошибке — сценарий и язык остаются.
 */
'use strict';

const SUBJECT_REF = 'sub_00000000cafe0001';
const ANALYSIS_AT = '2026-10-08T12:00:00Z';

/* Counterparty pseudonyms. The RiskSnapshotV1 contract only accepts
 * `^(sub|cp|dev|evt|src|ep|case|tpl)_[a-f0-9]{8,64}$` (anti-injection
 * boundary, see anti_drop_ml/contracts.py) — human-readable names like
 * 'cp_relay001' are rejected with 422. Rows below carry the hex refs;
 * CP_LABEL keeps the human-readable table captions. */
const CP_REF = {
  employer: 'cp_10000000ca1e0001',
  shop: 'cp_20000000ca1e0001',
  pharmacy: 'cp_30000000ca1e0001',
  grocery: 'cp_40000000ca1e0001',
  relay1: 'cp_50000000ca1e0001',
  relay2: 'cp_50000000ca1e0002',
  relay3: 'cp_50000000ca1e0003',
  relay4: 'cp_50000000ca1e0004',
  relay5: 'cp_50000000ca1e0005',
  atm: 'cp_60000000ca1e0001',
  friend1: 'cp_70000000ca1e0001',
  friend2: 'cp_70000000ca1e0002',
  friend3: 'cp_70000000ca1e0003',
  friend4: 'cp_70000000ca1e0004',
  friend5: 'cp_70000000ca1e0005',
  landlord: 'cp_80000000ca1e0001'
};
const CP_LABEL = {
  cp_10000000ca1e0001: 'работодатель',
  cp_20000000ca1e0001: 'магазин',
  cp_30000000ca1e0001: 'аптека',
  cp_40000000ca1e0001: 'продукты',
  cp_50000000ca1e0001: 'отправитель_1',
  cp_50000000ca1e0002: 'отправитель_2',
  cp_50000000ca1e0003: 'отправитель_3',
  cp_50000000ca1e0004: 'отправитель_4',
  cp_50000000ca1e0005: 'кошелёк_вербовщика',
  cp_60000000ca1e0001: 'банкомат',
  cp_70000000ca1e0001: 'друг_1',
  cp_70000000ca1e0002: 'друг_2',
  cp_70000000ca1e0003: 'друг_3',
  cp_70000000ca1e0004: 'друг_4',
  cp_70000000ca1e0005: 'друг_5',
  cp_80000000ca1e0001: 'арендодатель'
};

const SCENARIOS = {
  normal: {
    label: 'Обычная активность',
    analysisAt: ANALYSIS_AT,
    transactions: [
      ['2026-10-07T09:00:00Z', 'in', 'salary', 6000000, CP_REF.employer, 90],
      ['2026-10-07T12:10:00Z', 'out', 'other', 120000, CP_REF.shop, 90],
      ['2026-10-07T15:40:00Z', 'out', 'other', 80000, CP_REF.pharmacy, 90],
      ['2026-10-07T09:15:00Z', 'out', 'other', 150000, CP_REF.grocery, 90]
    ]
  },
  attack: {
    label: 'Дроп-схема (транзит + вывод)',
    analysisAt: '2026-10-07T12:00:00Z',
    transactions: [
      ['2026-10-07T10:00:00Z', 'in', 'salary', 1500000, CP_REF.employer, 1],
      ['2026-10-07T11:02:00Z', 'in', 'transfer', 300000, CP_REF.relay1, 1],
      ['2026-10-07T11:07:00Z', 'in', 'transfer', 250000, CP_REF.relay2, 1],
      ['2026-10-07T11:12:00Z', 'in', 'transfer', 400000, CP_REF.relay3, 1],
      ['2026-10-07T11:20:00Z', 'in', 'transfer', 180000, CP_REF.relay4, 1],
      ['2026-10-07T11:25:00Z', 'in', 'transfer', 350000, CP_REF.relay5, 1],
      ['2026-10-07T11:40:00Z', 'out', 'transfer', 1300000, CP_REF.relay5, 1],
      ['2026-10-07T11:45:00Z', 'out', 'cash_withdrawal', 500000, CP_REF.atm, 1]
    ]
  },
  family: {
    label: 'Сбор с друзьями (legitimate negative)',
    analysisAt: '2026-10-07T12:00:00Z',
    transactions: [
      ['2026-10-07T11:20:00Z', 'in', 'family_collection', 300000, CP_REF.friend1, 90],
      ['2026-10-07T11:25:00Z', 'in', 'family_collection', 300000, CP_REF.friend2, 90],
      ['2026-10-07T11:30:00Z', 'in', 'family_collection', 300000, CP_REF.friend3, 90],
      ['2026-10-07T11:35:00Z', 'in', 'family_collection', 300000, CP_REF.friend4, 90],
      ['2026-10-07T11:40:00Z', 'in', 'family_collection', 300000, CP_REF.friend5, 90],
      ['2026-10-07T11:50:00Z', 'out', 'transfer', 200000, CP_REF.landlord, 90]
    ]
  },
  salary: {
    label: 'Зарплата и снятие наличных (legitimate negative)',
    analysisAt: '2026-10-07T12:00:00Z',
    transactions: [
      ['2026-10-07T09:00:00Z', 'in', 'salary', 6000000, CP_REF.employer, 90],
      ['2026-10-07T11:00:00Z', 'out', 'cash_withdrawal', 5000000, CP_REF.atm, 90]
    ]
  }
};

const LEVEL_PRESENTATION = {
  GREEN: { icon: '✅', text: 'ЗЕЛЁНЫЙ — признаков риска нет', className: 'level-badge--green' },
  YELLOW: { icon: '⚠️', text: 'ЖЁЛТЫЙ — есть признаки для проверки', className: 'level-badge--yellow' },
  RED: { icon: '⛔', text: 'КРАСНЫЙ — рискованная схема', className: 'level-badge--red' }
};

const state = {
  requestSeq: 0,
  inFlight: null,
  quiz: [],
  lastDecision: null,
  lastWarning: null
};

const $ = (id) => document.getElementById(id);

/* ---------------------------------------------------------------- helpers */

function setText(node, value) {
  node.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function appendLine(node, text, className) {
  const item = document.createElement('li');
  item.textContent = text;
  if (className) item.className = className;
  node.appendChild(item);
}

function showError(message) {
  const box = $('apiErr');
  box.textContent = message;
  box.hidden = false;
}

function hideError() {
  const box = $('apiErr');
  box.textContent = '';
  box.hidden = true;
}

function setBusy(busy, label) {
  state.inFlight = busy ? label : null;
  ['btnCheck', 'btnAttack', 'btnSupport', 'btnQuiz', 'btnSim'].forEach((id) => {
    const button = $(id);
    if (button) button.disabled = busy;
  });
  setText($('requestState'), busy ? `${label}… идёт запрос, кнопки временно недоступны.` : '');
}

/* One request helper: aborts the previous call, always disables the buttons,
 * and reports failures as text rather than throwing markup into the DOM.
 * extraHeaders carry sandbox identity (X-Sandbox-Subject, Idempotency-Key);
 * returnMeta additionally reports the Idempotency-Replayed flag. */
async function api(path, body, method = 'POST', extraHeaders = {}, returnMeta = false) {
  if (state.inFlight) return null;
  setBusy(true, labelFor(path));
  hideError();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {
      method,
      headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...extraHeaders },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal
    });
    if (!response.ok) {
      // Structured envelope ({error_code, message}) first, then legacy
      // string detail, then the bare status. Never swallow the message:
      // a bare 'HTTP 422' hides which field failed validation.
      let detail = `HTTP ${response.status}`;
      try {
        const payload = await response.json();
        if (payload && typeof payload.message === 'string' && payload.message) {
          const code = payload.error_code ? ` (${payload.error_code})` : '';
          detail = `HTTP ${response.status}${code}: ${payload.message}`;
        } else if (payload && typeof payload.detail === 'string') {
          detail = payload.detail;
        }
      } catch (ignored) { /* keep the status code as the message */ }
      throw new Error(detail);
    }
    const data = await response.json();
    if (returnMeta) {
      return { data, replayed: response.headers.get('Idempotency-Replayed') === 'true' };
    }
    return data;
  } catch (error) {
    const aborted = error.name === 'AbortError';
    showError(aborted
      ? 'Сервер не ответил за 15 секунд. Ничего не применено, сценарий и язык сохранены — можно повторить.'
      : `Ошибка запроса: ${error.message}. Ничего не применено.`);
    return null;
  } finally {
    clearTimeout(timer);
    setBusy(false, labelFor(path));
  }
}

function labelFor(path) {
  if (path.includes('/api/analyze') || path.includes('/communication/evaluate')) return 'Проверка сценария';
  if (path.includes('/sandbox/cases') || path.includes('/api/cases') || path.includes('/operator/cases')) return 'Создание песочного обращения';
  if (path.includes('/api/quiz')) return 'Проверка квиза';
  if (path.includes('/api/sim')) return 'Учебная смена номера';
  if (path.includes('/content') || path.includes('/locales')) return 'Загрузка данных';
  return 'Запрос';
}

/* -------------------------------------------------------------- snapshots */

function buildSnapshot(scenarioKey) {
  const scenario = SCENARIOS[scenarioKey];
  return {
    schema_version: 'RiskSnapshotV1',
    subject_ref: SUBJECT_REF,
    analysis_at: scenario.analysisAt,
    timezone_policy: 'normalize_to_utc',
    allow_future_events: false,
    transactions: scenario.transactions.map((row, index) => ({
      event_id: `evt_${String(index).padStart(4, '0')}cafe0001`,
      source_event_id: `src_${String(index).padStart(4, '0')}cafe0001`,
      subject_ref: SUBJECT_REF,
      occurred_at: row[0],
      direction: row[1],
      type: row[2],
      amount_minor: row[3],
      currency: 'RUB',
      counterparty_ref: row[4],
      device_id: 'dev_cafe00000001',
      sim_changed_days_ago: row[5]
    })),
    metadata: {
      dataset_version: 'demo-ui-v1',
      label_source: 'synthetic_placeholder',
      is_holdout: false,
      episode_class: scenarioKey === 'attack' ? 'risk' : 'legitimate_negative'
    }
  };
}

function renderTransactions(scenarioKey) {
  const body = $('txTable');
  clear(body);
  SCENARIOS[scenarioKey].transactions.forEach((row) => {
    const tr = document.createElement('tr');
    const cells = [row[0].replace('T', ' ').replace('Z', ''), row[2],
      (row[3] / 100).toLocaleString('ru-RU'), CP_LABEL[row[4]] || row[4]];
    cells.forEach((value) => {
      const td = document.createElement('td');
      td.textContent = value;
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

/* --------------------------------------------------------------- decision */

function renderDecision(decision) {
  const level = LEVEL_PRESENTATION[decision.level] || LEVEL_PRESENTATION.GREEN;
  const badge = $('levelBadge');
  badge.className = `level-badge ${level.className}`;
  setText($('levelIcon'), level.icon);
  $('levelIcon').setAttribute('aria-hidden', 'true');
  setText($('levelText'), level.text);
  setText($('levelScore'), `score ${decision.score}/100`);
  setText($('scoreNote'),
    `Score — детерминированный скоринг правил, не вероятность мошенничества. Решение: ${decision.rule_version}, пороги: ${decision.threshold_version}. Статус данных: ${decision.status}.`);

  const reasons = $('reasons');
  clear(reasons);
  (decision.reason_codes || []).forEach((code) => appendLine(reasons, code));
  if (!decision.reason_codes.length) appendLine(reasons, 'Скорируемых правил не сработало.');
  setText($('reasonCodes'), (decision.reason_codes || []).join(', ') || 'нет кодов причин');
}

function renderWarning(warning, note) {
  const box = $('alertBox');
  if (!warning) {
    box.hidden = true;
    return;
  }
  box.hidden = false;
  box.className = warning.risk_level === 'YELLOW' ? 'alert-card alert-card--yellow' : 'alert-card';
  setText($('alertTitle'), `${warning.title} (${warning.language_name})`);
  const body = $('alertBody');
  body.textContent = warning.body;
  body.setAttribute('lang', warning.locale);
  body.setAttribute('dir', warning.direction || 'ltr');
  document.documentElement.setAttribute('lang', warning.locale);
  document.documentElement.setAttribute('dir', warning.direction || 'ltr');

  const badge = $('draftBadge');
  if (warning.draft_badge) {
    badge.textContent = warning.draft_badge;
    badge.hidden = false;
  } else {
    badge.textContent = '';
    badge.hidden = true;
  }

  const fallbackKeys = warning.used_fallback_keys || [];
  const metaParts = [
    `Шаблон: ${warning.template_id} v${warning.template_version}`,
    `Статус перевода: ${warning.template_status}`,
    `Пакет локализации: ${warning.localization_version}`
  ];
  if (fallbackKeys.length) metaParts.push(`translation_fallback: ${fallbackKeys.join(', ')} (текст взят из базовой локали, помечено)`);
  if (note && note.experiment) metaParts.push(note.experiment);
  setText($('alertMeta'), metaParts.join(' • '));
  setText($('sandboxNotice'), warning.sandbox_notice);
  setText($('legalDisclaimer'), warning.legal_disclaimer);
  setText($('privacyNotice'), warning.privacy_notice);
}

async function analyze() {
  const scenarioKey = $('scenario').value;
  const locale = $('lang').value;
  renderTransactions(scenarioKey);
  const seq = ++state.requestSeq;
  const payload = { snapshot: buildSnapshot(scenarioKey), preferred_locale: locale,
                    subject_pseudonym: SUBJECT_REF };
  const result = await api('/api/v1/communication/evaluate', payload);
  // Stale-response guard: a newer request already owns the screen.
  if (!result || seq !== state.requestSeq) return;
  state.lastDecision = result.decision;
  state.lastWarning = result.warning;
  renderDecision(result.decision);
  const experiment = result.experiment || {};
  const experimentNote = experiment.enabled
    ? `Эксперимент ${experiment.experiment_id}: arm=${experiment.assignment ? experiment.assignment.arm : '—'}` +
      (experiment.blocked_reason ? `; treatment недоступен: ${experiment.blocked_reason}` : '')
    : 'Эксперимент выключен флагом ANTI_DROP_EXPERIMENT_ENABLED (по умолчанию).';
  renderWarning(result.warning, { experiment: experimentNote });
  if (result.decision.level === 'GREEN') $('ticket').textContent = '';
}

async function contactSupport() {
  if (!state.lastDecision) {
    showError('Сначала нажмите «Проверить»: без решения обращение не создаётся.');
    return;
  }
  // Sandbox-кейс вместо legacy /api/cases (тот отвечает 410 LEGACY_CASES_DISABLED).
  // Субъект только из заголовка, тело без subject_ref (граница доверия).
  // Язык кейса — короткий код из локали UI (ru-RU -> ru).
  const decision = state.lastDecision;
  const locale = ($('lang') && $('lang').value) || 'ru-RU';
  const language = String(locale).split('-')[0] || 'ru';
  const idempotencyKey = `${SUBJECT_REF}-${decision.evaluation_id}`;
  const result = await api('/sandbox/cases', {
    evaluation_id: decision.evaluation_id,
    selected_language: language,
    contact_reason: 'suspicious_transfer_request'
  }, 'POST', {
    'X-Sandbox-Subject': SUBJECT_REF,
    'Idempotency-Key': idempotencyKey
  }, true);
  if (!result) {
    $('ticket').textContent = '⚠️ Обращение не создано. Поддержка не вызывалась, ничего не заморожено.';
    return;
  }
  const c = result.data || {};
  $('ticket').textContent = (result.replayed ? '↺ Повторный запрос — кейс не дублируется. ' : '✅ Обращение зарегистрировано в песочнице. ') +
    `Кейс: ${c.case_id}, статус: ${c.status}. Оценка эпизода: ${decision.score}/100 (сумма правил, не вероятность).${c.notice ? ` ${c.notice}` : ''}`;
}

/* ------------------------------------------------------------ localization */

async function loadLocales() {
  const select = $('lang');
  const status = $('langStatus');
  const payload = await api('/api/locales', null, 'GET');
  if (!payload) {
    status.textContent = 'Каталог локализаций недоступен. Используется базовая локаль ru-RU.';
    return;
  }
  const previous = select.value;
  clear(select);
  payload.locales.forEach((pack) => {
    const option = document.createElement('option');
    option.value = pack.locale;
    const suffix = pack.draft_badge ? ` — ${pack.draft_badge}` : ' — approved';
    option.textContent = `${pack.display_name_native} (${pack.locale}) — статус: ${pack.status}${suffix}`;
    select.appendChild(option);
  });
  if (previous && payload.locales.some((pack) => pack.locale === previous)) select.value = previous;
  const target = payload.locales.find((pack) => pack.locale === payload.target_locale);
  const missing = (target && target.missing_keys.length)
    ? ` В пакете ${target.locale} нет ключей: ${target.missing_keys.join(', ')} — для них используется fallback на базовый язык (это видно в поле translation_fallback).`
    : '';
  status.textContent = `Пакетов локализаций: ${payload.locales.length}. Целевой язык: ${payload.target_locale}.` +
    ' Язык не является фактором риска и не меняет score. Ни один перевод не является approved без проверки носителем и юристом.' + missing;
}

/* ------------------------------------------------------------------ quiz */

async function loadContent() {
  const stories = $('stories');
  const quizBox = $('quizBox');
  try {
    const response = await fetch('/api/content');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const content = await response.json();
    clear(stories);
    (content.stories || []).forEach((story) => {
      const box = document.createElement('div');
      box.style.cssText = 'background:#0b1120;border-inline-start:4px solid var(--ad-accent);border-radius:.5rem;padding:.6rem .8rem;margin-block-end:.5rem';
      const title = document.createElement('b');
      title.textContent = `${story.emoji || ''} ${story.title || ''}`.trim();
      const text = document.createElement('p');
      text.style.cssText = 'margin:.25rem 0 0';
      text.textContent = story.text || '';
      box.appendChild(title);
      box.appendChild(text);
      stories.appendChild(box);
    });
    state.quiz = content.quiz || [];
    clear(quizBox);
    state.quiz.forEach((question, index) => {
      const box = document.createElement('div');
      box.style.cssText = 'background:#0b1120;border-radius:.5rem;padding:.75rem;margin-block-start:.5rem';
      const title = document.createElement('b');
      title.textContent = `Вопрос ${index + 1}. ${question.q}`;
      box.appendChild(title);
      (question.options || []).forEach((option, optionIndex) => {
        const wrap = document.createElement('label');
        wrap.style.cssText = 'display:flex;gap:.5rem;align-items:center;margin-block-start:.35rem;cursor:pointer';
        const input = document.createElement('input');
        input.type = 'radio';
        input.name = `quiz-${index}`;
        input.value = String(optionIndex);
        const text = document.createElement('span');
        text.textContent = option;
        wrap.appendChild(input);
        wrap.appendChild(text);
        box.appendChild(wrap);
      });
      quizBox.appendChild(box);
    });
  } catch (error) {
    clear(stories);
    const message = document.createElement('p');
    message.className = 'legal-note';
    message.textContent = `Не удалось загрузить контент: ${error.message}`;
    stories.appendChild(message);
  }
}

async function sendQuiz() {
  const answers = state.quiz.map((_, index) => {
    const picked = document.querySelector(`input[name="quiz-${index}"]:checked`);
    return picked ? Number(picked.value) : -1;
  });
  const result = await api('/api/quiz', { answers });
  if (!result) return;
  const target = $('quizRes');
  clear(target);
  const summary = document.createElement('div');
  summary.textContent = `${result.message} (${result.score}/${result.total}). Статус приза: ${result.reward_status}.`;
  target.appendChild(summary);
  (result.details || []).forEach((detail) => {
    const line = document.createElement('div');
    line.textContent = `${detail.ok ? '✓' : '✗'} ${detail.explain}`;
    target.appendChild(line);
  });
}

async function sendSim() {
  const body = {
    old_phone: $('oldP').value,
    new_phone: $('newP').value,
    otp_ok_old: $('otpO').checked,
    otp_ok_new: $('otpN').checked
  };
  const result = await api('/api/sim', body);
  if (!result) return;
  const target = $('simRes');
  clear(target);
  const head = document.createElement('div');
  head.textContent = result.ok ? result.message : 'Учебная смена отклонена:';
  target.appendChild(head);
  if (result.ok) {
    const limits = document.createElement('div');
    limits.textContent = result.limits && result.limits.note ? result.limits.note : '';
    target.appendChild(limits);
    (result.checklist || []).forEach((item) => {
      const line = document.createElement('div');
      line.textContent = `• ${item}`;
      target.appendChild(line);
    });
  } else {
    (result.errors || []).forEach((item) => {
      const line = document.createElement('div');
      line.textContent = `• ${item}`;
      target.appendChild(line);
    });
  }
}

/* ------------------------------------------------------------------ tabs */

function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach((other) => {
        other.setAttribute('aria-selected', String(other === button));
      });
      ['dash', 'quiz', 'sim'].forEach((name) => {
        const panel = $(`panel-${name}`);
        if (panel) panel.hidden = name !== button.dataset.tab;
      });
      if (button.dataset.tab === 'quiz' && !state.quiz.length) loadContent();
    });
  });
}

function setup() {
  setupTabs();
  $('btnCheck').addEventListener('click', analyze);
  $('btnAttack').addEventListener('click', () => {
    $('scenario').value = 'attack';
    analyze();
  });
  $('btnSupport').addEventListener('click', contactSupport);
  $('btnHide').addEventListener('click', () => { $('alertBox').hidden = true; });
  $('btnQuiz').addEventListener('click', sendQuiz);
  $('btnSim').addEventListener('click', sendSim);
  $('scenario').addEventListener('change', analyze);
  $('lang').addEventListener('change', analyze);
  renderTransactions('normal');
  loadLocales().then(analyze);
}

setup();