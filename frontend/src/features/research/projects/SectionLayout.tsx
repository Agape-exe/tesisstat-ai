import type { ReactNode } from 'react';
import { navigateProject, type Section } from './navigation';
import { UiIcon } from './UiIcon';
import './sections.css';

export function SupportPanel({
  title,
  children,
  projectId,
  destination,
  action,
}: {
  title: string;
  children: ReactNode;
  projectId: string;
  destination?: Section;
  action?: string;
}) {
  return (
    <aside className="rp-support rp-surface">
      <h3>{title}</h3>
      {children}
      {destination && (
        <button
          className="rp-link"
          onClick={() => navigateProject(projectId, destination)}
        >
          {action} →
        </button>
      )}
    </aside>
  );
}

export function Guidance({ items }: { items: string[] }) {
  return (
    <ul className="rp-guidance">
      {items.map((item) => (
        <li key={item}>
          <UiIcon name="help" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function SectionColumns({
  children,
  support,
}: {
  children: ReactNode;
  support: ReactNode;
}) {
  return (
    <div className="rp-section-columns">
      <div className="rp-section-primary">{children}</div>
      {support}
    </div>
  );
}
