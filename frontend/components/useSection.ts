'use client';
import { useSyncExternalStore } from 'react';
export const sectionIds = [
  'overview',
  'monitoring',
  'principles',
  'protection',
  'learning',
  'phone',
  'knowledge',
  'guides',
  'examples',
  'settings',
  'support',
] as const;
export type SectionId = (typeof sectionIds)[number];
function subscribe(callback: () => void) {
  window.addEventListener('hashchange', callback);
  return () => window.removeEventListener('hashchange', callback);
}
function snapshot(): SectionId {
  const value = location.hash.slice(1);
  return sectionIds.includes(value as SectionId)
    ? (value as SectionId)
    : 'overview';
}
export function useSection() {
  return useSyncExternalStore(
    subscribe,
    snapshot,
    () => 'overview' as SectionId,
  );
}
