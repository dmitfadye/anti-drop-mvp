'use client';
import type { SectionId } from './useSection';
import { Monitoring } from './Monitoring';
import { Learning } from './Learning';
import { PhoneChange } from './PhoneChange';
export function DemoWorkspace({ active }: { active: SectionId }) {
  return (
    <>
      <div hidden={active !== 'monitoring'}>
        <Monitoring />
      </div>
      <div hidden={active !== 'learning'}>
        <Learning />
      </div>
      <div hidden={active !== 'phone'}>
        <PhoneChange />
      </div>
    </>
  );
}
