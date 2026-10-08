import type { Metadata } from 'next';
import localFont from 'next/font/local';
import './globals.css';

const asket = localFont({
  src: '../public/fonts/Asket-Extended-Light.otf',
  weight: '300',
  style: 'normal',
  variable: '--font-asket',
  display: 'swap',
  preload: true,
});
const display = localFont({
  src: '../public/fonts/Asket-Extrabold.otf',
  weight: '800',
  style: 'normal',
  variable: '--font-display',
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
      className={`${asket.variable} ${display.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
