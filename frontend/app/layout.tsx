import type { Metadata } from 'next';
import localFont from 'next/font/local';
import './globals.css';

const onest = localFont({
  src: '../public/fonts/Onest-Variable.ttf',
  weight: '100 900',
  style: 'normal',
  variable: '--font-onest',
  display: 'swap',
  preload: true,
});

export const metadata: Metadata = {
  title: 'Anti-Drop — понятная финансовая безопасность',
  description:
    'Демонстрационный интерфейс сервиса понятных предупреждений о рисках переводов.',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="ru"
      className={onest.variable}
    >
      <body>{children}</body>
    </html>
  );
}
