import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Anti-Drop — понятная финансовая безопасность',
  description: 'Демонстрационный интерфейс сервиса понятных предупреждений о рисках переводов.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ru"><body>{children}</body></html>;
}
