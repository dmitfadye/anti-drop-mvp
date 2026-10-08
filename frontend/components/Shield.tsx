export function Shield({ large = false }: { large?: boolean }) {
  return <svg width={large ? 72 : 28} height={large ? 72 : 28} viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M16 3 27 7v8c0 7-11 14-11 14S5 22 5 15V7L16 3Z" stroke="currentColor" strokeWidth="1.8"/><path d="m11 15 4 4 7-8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
