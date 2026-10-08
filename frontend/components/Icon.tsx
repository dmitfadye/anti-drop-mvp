export type IconName =
  | 'grid'
  | 'chart'
  | 'info'
  | 'shield'
  | 'book'
  | 'phone'
  | 'cap'
  | 'play'
  | 'file'
  | 'settings'
  | 'help'
  | 'search'
  | 'bell'
  | 'sun'
  | 'arrow'
  | 'layers'
  | 'clock'
  | 'lock'
  | 'check'
  | 'user'
  | 'warning'
  | 'link';
const paths: Record<IconName, string> = {
  grid: 'M3 3h6v6H3z M15 3h6v6h-6z M3 15h6v6H3z M15 15h6v6h-6z',
  chart: 'M4 3h16v18H4z M7 15l4-4 3 2 3-5',
  info: 'M12 11v6 M12 7h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  shield: 'M12 2 3 6v6c0 6 9 10 9 10s9-4 9-10V6z M8 12l3 3 5-6',
  book: 'M4 3h13v15H4z M8 6h12v15H8 M11 10h6 M11 13h6',
  phone: 'M7 2h10v20H7z M11 18h2',
  cap: 'm2 9 10-5 10 5-10 5z M6 11v6l6 3 6-3v-6 M22 9v8',
  play: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M10 8l6 4-6 4z',
  file: 'M6 2h9l4 4v16H6z M14 2v5h5 M9 11h7 M9 15h7 M9 18h4',
  settings:
    'm9 3 1-1h4l1 3 3 1 3 2-1 4 1 4-3 2-3 1-1 3h-4l-1-3-3-1-3-2 1-4-1-4 3-2z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  help: 'M9 8a3 3 0 1 1 4 3c-1 0-1 1-1 3 M12 17h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  search: 'M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0 M15 15l6 6',
  bell: 'M5 17h14l-2-3V9a5 5 0 0 0-10 0v5z M10 21h4',
  sun: 'M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M12 1v2 M12 21v2 M1 12h2 M21 12h2 M4 4l2 2 M18 18l2 2 M4 20l2-2 M18 6l2-2',
  arrow: 'M4 12h16 M15 7l5 5-5 5',
  layers: 'm2 7 10-5 10 5-10 5z M2 12l10 5 10-5 M2 17l10 5 10-5',
  clock: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M12 6v6l4 2',
  lock: 'M6 10h12v11H6z M8 10V6a4 4 0 0 1 8 0v4 M12 14v3',
  check: 'm5 12 4 4L19 6',
  user: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3z',
  warning: 'm12 2 10 19H2z M12 8v6 M12 17h.01',
  link: 'm9 15 6-6 M8 16l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0 M16 8l1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0',
};
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
