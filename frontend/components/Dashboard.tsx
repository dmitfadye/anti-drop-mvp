'use client';
import { AppShell } from './AppShell';
import { Overview } from './Overview';
import { DemoWorkspace } from './DemoWorkspace';
import { ContentScreens } from './ContentScreens';
import { useSection } from './useSection';
export function Dashboard() {
  const active = useSection();
  return (
    <AppShell>
      <div hidden={active !== 'overview'}>
        <Overview />
      </div>
      <DemoWorkspace active={active} />
      <ContentScreens key={active} active={active} />
    </AppShell>
  );
}
