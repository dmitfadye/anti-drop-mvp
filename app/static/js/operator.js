/* Анти-Дроп P1 — экран оператора (локальная песочница).
 *
 * Ограничения, которые код отражает, а не прячет:
 *  - нет авторизации: доступ обеспечивается только флагами и loopback;
 *  - никаких innerHTML для данных: всё через textContent;
 *  - свободный текст в заметках невозможен: только note_code из allowlist;
 *  - каждый запрос несёт Idempotency-Key, повтор возвращает idempotent_replay;
 *  - недопустимый переход статуса возвращает 409 и показывается как текст.
 */
'use strict';

const state = { selected: null, statuses: [], transitions: {}, busy: false, requestSeq: 0 };

const $ = (id) => document.getElementById(id);

function setText(node, value) {
  node.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function showError(message) {
  const box = $('opErr');
  box.textContent = message;
  box.hidden = false;
}

function hideError() {
  const box = $('opErr');
  box.textContent = '';
  box.hidden = true;
}

function setBusy(busy) {
  state.busy = busy;
  ['btnRefresh', 'btnExportJson', 'btnExportCsv', 'btnReset', 'btnApply'].forEach((id) => {
    const button = $(id);
    if (button) button.disabled = busy;
  });
}

function uuid() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  (window.crypto || {}).getRandomValues?.(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

async function api(path, options = {}) {
  if (state.busy) return null;
  setBusy(true);
  hideError();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const payload = await response.json();
        detail = typeof payload.detail === 'string' ? payload.detail : detail;
      } catch (ignored) { /* keep the status code */ }
      throw new Error(detail);
    }
    return await response.json();
  } catch (error) {
    showError(error.name === 'AbortError'
      ? 'Сервер не ответил за 15 секунд. Данные песочницы не изменились.'
      : `Ошибка: ${error.message}. Данные песочницы не изменились.`);
    return null;
  } finally {
    clearTimeout(timer);
    setBusy(false);
  }
}

function query() {
  const params = new URLSearchParams();
  const pairs = [['level', 'fLevel'], ['status', 'fStatus'], ['locale', 'fLocale'],
    ['experiment_arm', 'fArm'], ['episode_class', 'fClass'], ['created_from', 'fFrom'], ['created_to', 'fTo']];
  pairs.forEach(([key, id]) => {
    const value = $(id).value.trim();
    if (value) params.set(key, value);
  });
  const text = params.toString();
  return text ? `?${text}` : '';
}

async function loadMetrics() {
  const payload = await api('/api/operator/metrics', { method: 'GET' });
  if (!payload) return;
  setText($('sandboxBanner'), payload.banner_ru);
  const grid = $('metrics');
  clear(grid);
  const rows = [
    ['Всего кейсов', payload.total_cases, true],
    ['RED / YELLOW / GREEN', `${payload.cases_by_level.RED || 0} / ${payload.cases_by_level.YELLOW || 0} / ${payload.cases_by_level.GREEN || 0}`, true],
    ['Языки', Object.entries(payload.cases_by_locale).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'нет данных', false],
    ['Arm control/treatment', `${payload.cases_by_arm.control || 0} / ${payload.cases_by_arm.treatment || 0}`, true],
    ['Alert rate', formatRate(payload.alert_rate), false],
    ['Legitimate negative alert rate', payload.legitimate_negative_alert_rate ? formatRate(payload.legitimate_negative_alert_rate) : 'нет размеченных легитимных негативов', false],
    ['translation_fallback', payload.translation_fallback_count, true],
    ['Присвоений эксперимента', payload.experiment_assignment_count, true],
    ['Ошибки/отклонения', payload.errors_and_rejections, true],
    ['Действий оператора в логе', payload.operator_actions_logged, true]
  ];
  rows.forEach(([label, value, numeric]) => {
    const box = document.createElement('div');
    box.className = 'metric';
    const name = document.createElement('div');
    name.className = 'metric__label';
    name.textContent = label;
    const number = document.createElement('div');
    number.className = numeric ? 'metric__value' : 'metric__value metric__value--undefined';
    number.textContent = String(value);
    box.appendChild(name);
    box.appendChild(number);
    grid.appendChild(box);
  });
  setText($('metricsNote'), (payload.limitations || []).join(' • '));

  const statusSelect = $('fStatus');
  const current = statusSelect.value;
  clear(statusSelect);
  const any = document.createElement('option');
  any.value = '';
  any.textContent = 'любой';
  statusSelect.appendChild(any);
  (payload.statuses || []).forEach((status) => {
    const option = document.createElement('option');
    option.value = status;
    option.textContent = status;
    statusSelect.appendChild(option);
  });
  statusSelect.value = current;
}

function formatRate(rate) {
  if (!rate || rate.value === null || rate.value === undefined) return 'не определено (нет знаменателя)';
  return `${(rate.value * 100).toFixed(1)}% (${rate.numerator}/${rate.denominator})`;
}

async function loadCases() {
  const seq = ++state.requestSeq;
  const payload = await api(`/api/operator/cases${query()}`, { method: 'GET' });
  if (!payload || seq !== state.requestSeq) return;
  const body = $('caseRows');
  clear(body);
  payload.cases.forEach((item) => {
    const tr = document.createElement('tr');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn';
    button.textContent = item.case_id;
    button.addEventListener('click', () => openCase(item.case_id));
    const idCell = document.createElement('td');
    idCell.appendChild(button);
    tr.appendChild(idCell);
    [item.created_at, item.status, item.level, `${item.score}/100`, item.locale,
      item.experiment_arm || 'none', item.template_id || '—', (item.reason_codes || '') || '—']
      .forEach((value) => {
        const td = document.createElement('td');
        td.textContent = String(value ?? '—');
        tr.appendChild(td);
      });
    body.appendChild(tr);
  });
  setText($('casesNote'), `Показано кейсов: ${payload.count}. Score — не вероятность. Действий банка не выполняется.`);
}

async function loadStatusMachine() {
  const payload = await api('/api/operator/status-machine', { method: 'GET' });
  if (!payload) return;
  state.statuses = payload.statuses || [];
  state.transitions = payload.transitions || {};
  const notes = $('noteCode');
  const previousNote = notes.value;
  clear(notes);
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = 'без заметки';
  notes.appendChild(empty);
  (payload.allowlisted_note_codes || []).forEach((code) => {
    const option = document.createElement('option');
    option.value = code;
    option.textContent = code;
    notes.appendChild(option);
  });
  notes.value = previousNote;

  const roles = $('actorRole');
  const previousRole = roles.value;
  clear(roles);
  (payload.allowlisted_actor_roles || []).forEach((role) => {
    const option = document.createElement('option');
    option.value = role;
    option.textContent = role;
    roles.appendChild(option);
  });
  if (previousRole) roles.value = previousRole;
}

async function openCase(caseId) {
  const payload = await api(`/api/operator/cases/${encodeURIComponent(caseId)}`, { method: 'GET' });
  if (!payload) return;
  state.selected = caseId;
  const card = $('detailCard');
  card.hidden = false;
  const box = $('detail');
  clear(box);

  const facts = [
    ['case_id', payload.case_id], ['evaluation_id', payload.evaluation_id],
    ['subject_pseudonym', payload.subject_pseudonym], ['created_at', payload.created_at],
    ['rule_version', payload.rule_version], ['threshold_version', payload.threshold_version],
    ['template_id', payload.template_id], ['locale', payload.locale],
    ['locale_status', payload.locale_status], ['experiment_id', payload.experiment_id || '—'],
    ['experiment_arm', payload.experiment_arm || '—'], ['scenario_code', payload.scenario_code],
    ['episode_class', payload.episode_class], ['reason_codes', (payload.reason_codes || []).join(', ') || '—'],
    ['score (не вероятность)', `${payload.score}/100`], ['translation_fallback', String(payload.translation_fallback)],
    ['sandbox_notice', payload.sandbox_notice]
  ];
  const grid = document.createElement('div');
  grid.className = 'metric-grid';
  facts.forEach(([label, value]) => {
    const cell = document.createElement('div');
    cell.className = 'metric';
    const name = document.createElement('div');
    name.className = 'metric__label';
    name.textContent = label;
    const text = document.createElement('div');
    text.className = 'metric__value metric__value--undefined';
    text.style.wordBreak = 'break-all';
    text.textContent = value;
    cell.appendChild(name);
    cell.appendChild(text);
    grid.appendChild(cell);
  });
  box.appendChild(grid);

  const timelineTitle = document.createElement('h3');
  timelineTitle.className = 'card__title';
  timelineTitle.style.fontSize = '1rem';
  timelineTitle.textContent = 'Лента событий';
  box.appendChild(timelineTitle);
  const list = document.createElement('ul');
  list.style.paddingInlineStart = '1.25rem';
  (payload.timeline || []).forEach((event) => {
    const item = document.createElement('li');
    item.textContent = `${event.at} — ${event.status} (${event.actor_role}${event.note_code ? `, note_code=${event.note_code}` : ''})`;
    list.appendChild(item);
  });
  box.appendChild(list);

  const select = $('nextStatus');
  clear(select);
  const allowed = state.transitions[payload.status] || [];
  if (!allowed.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = `нет допустимых переходов из ${payload.status}`;
    select.appendChild(option);
    select.disabled = true;
    $('btnApply').disabled = true;
  } else {
    select.disabled = false;
    $('btnApply').disabled = false;
    allowed.forEach((status) => {
      const option = document.createElement('option');
      option.value = status;
      option.textContent = status;
      select.appendChild(option);
    });
  }
  setText($('detailNote'), `Допустимые переходы из ${payload.status}: ${allowed.join(', ') || 'нет'}. Заметки принимаются только кодом из allowlist.`);
}

async function applyStatus() {
  if (!state.selected) {
    showError('Сначала откройте карточку кейса.');
    return;
  }
  const status = $('nextStatus').value;
  if (!status) return;
  const response = await api(`/api/operator/cases/${encodeURIComponent(state.selected)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': uuid() },
    body: JSON.stringify({ status, actor_role: $('actorRole').value, note_code: $('noteCode').value || null })
  });
  if (!response) return;
  setText($('detailNote'), `Статус: ${response.status}, обновлён ${response.updated_at}, idempotent_replay=${response.idempotent_replay}.`);
  await openCase(state.selected);
  await loadMetrics();
}

async function exportCases(format) {
  const response = await fetch(`/api/operator/export?format=${format}`);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === 'string' ? payload.detail : detail;
    } catch (ignored) { /* keep the status code */ }
    showError(`Экспорт недоступен: ${detail}`);
    return;
  }
  const text = format === 'csv' ? await response.text() : JSON.stringify(await response.json(), null, 2);
  const blob = new Blob([text], { type: format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `anti-drop-operator-export.${format}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  setText($('exportNote'), `Экспорт ${format} сформирован: псевдонимные поля, redacted, без персональных данных.`);
}

function setup() {
  $('btnRefresh').addEventListener('click', async () => { await loadMetrics(); await loadCases(); });
  $('btnApply').addEventListener('click', applyStatus);
  $('btnExportJson').addEventListener('click', () => exportCases('json'));
  $('btnExportCsv').addEventListener('click', () => exportCases('csv'));
  $('btnReset').addEventListener('click', () => {
    ['fLevel', 'fStatus', 'fLocale', 'fArm', 'fClass', 'fFrom', 'fTo'].forEach((id) => { $(id).value = ''; });
    loadCases();
  });
  setText($('sandboxBanner'), 'Локальная песочница. Синтетические данные. Не банковская система поддержки.');
  setText($('exportNote'), 'Экспорт псевдонимный: raw phone, полное имя, паспорт, карта, OTP отсутствуют; цифровые последовательности маскируются.');
  loadStatusMachine().then(async () => { await loadMetrics(); await loadCases(); });
}

setup();