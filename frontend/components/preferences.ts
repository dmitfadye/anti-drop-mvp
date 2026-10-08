'use client';
import { useSyncExternalStore } from 'react';
export type Preference = 'compact' | 'contrast' | 'motion' | 'hints';
const defaults: Record<Preference, boolean> = {
  compact: false,
  contrast: false,
  motion: false,
  hints: true,
};
const key = 'antidrop-preferences-v1';
function subscribe(callback: () => void) {
  window.addEventListener('storage', callback);
  window.addEventListener('antidrop-preferences', callback);
  return () => {
    window.removeEventListener('storage', callback);
    window.removeEventListener('antidrop-preferences', callback);
  };
}
function snapshot() {
  try {
    return localStorage.getItem(key) ?? '';
  } catch {
    return '';
  }
}
export function usePreferences() {
  const stored = useSyncExternalStore(subscribe, snapshot, () => '');
  let values = defaults;
  try {
    const parsed = JSON.parse(stored);
    values = {
      ...defaults,
      ...Object.fromEntries(
        Object.keys(defaults)
          .filter((k) => typeof parsed?.[k] === 'boolean')
          .map((k) => [k, parsed[k]]),
      ),
    };
  } catch {
    /* Default preferences also work when storage is unavailable. */
  }
  function update(name: Preference, value: boolean) {
    try {
      localStorage.setItem(key, JSON.stringify({ ...values, [name]: value }));
      window.dispatchEvent(new Event('antidrop-preferences'));
      return true;
    } catch {
      return false;
    }
  }
  return { values, update };
}
