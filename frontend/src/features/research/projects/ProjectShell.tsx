import type { ReactNode } from 'react';
import { useEffect, useRef, useState } from 'react';
import { navigateProject, sections, type Section } from './navigation';
import type { Project } from './types';

export function EmptyState({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rp-state">
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}

export function ProjectShell({
  project,
  section,
  homeHref,
  children,
}: {
  project: Project | null;
  section: Section;
  homeHref: string;
  children: ReactNode;
}) {
  const [menu, setMenu] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const content = useRef<HTMLElement>(null);
  useEffect(() => {
    const focus = () => {
      content.current?.focus({ preventScroll: true });
      document.documentElement.scrollTop = 0;
    };
    window.addEventListener('tesisstat:navigate', focus);
    window.addEventListener('popstate', focus);
    window.addEventListener('hashchange', focus);
    return () => {
      window.removeEventListener('tesisstat:navigate', focus);
      window.removeEventListener('popstate', focus);
      window.removeEventListener('hashchange', focus);
    };
  }, []);
  function go(id?: Section) {
    setMenu(false);
    navigateProject(id && project ? project.id : null, id);
  }
  return (
    <div className="rp-shell">
      <a
        className="rp-skip"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          content.current?.focus();
        }}
      >
        Saltar al contenido
      </a>
      <header className="rp-mobile-head">
        <strong>TesisStat AI</strong>
        <button
          ref={menuButton}
          className="rp-secondary"
          aria-expanded={menu}
          aria-controls="primary-navigation"
          onClick={() => setMenu(!menu)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setMenu(false);
          }}
        >
          {menu ? 'Cerrar menú' : 'Abrir menú'}
        </button>
      </header>
      <aside
        className={`rp-sidebar ${menu ? 'rp-menu-open' : ''}`}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setMenu(false);
            menuButton.current?.focus();
          }
        }}
      >
        <a
          className="rp-brand"
          href={homeHref}
          aria-label="TesisStat AI, investigaciones"
          onClick={(event) => {
            event.preventDefault();
            go();
          }}
        >
          <span className="rp-brand-mark" aria-hidden="true">
            T
          </span>{' '}
          TesisStat <strong>AI</strong>
        </a>
        <nav id="primary-navigation" aria-label="Navegación principal">
          <p className="rp-nav-label">TU ESPACIO</p>
          <button
            aria-current={!project ? 'page' : undefined}
            onClick={() => go()}
          >
            Mis investigaciones
          </button>
          {project && (
            <>
              <div className="rp-selected-project">
                <small>INVESTIGACIÓN ACTUAL</small>
                <strong>{project.title}</strong>
              </div>
              {sections.map(([id, label]) => (
                <button
                  key={id}
                  aria-current={id === section ? 'page' : undefined}
                  onClick={() => go(id)}
                >
                  {label}
                  {id === 'instrument' && <small>Pendiente</small>}
                </button>
              ))}
            </>
          )}
        </nav>
        <p className="rp-sidebar-note">
          Un espacio para comprender
          <br />y avanzar con tu tesis.
        </p>
      </aside>
      <main id="main-content" ref={content} tabIndex={-1} className="rp-main">
        {children}
      </main>
    </div>
  );
}

export function ProjectHeader({
  project,
  section,
  children,
}: {
  project: Project;
  section: Section;
  children: ReactNode;
}) {
  return (
    <header className="rp-project-header">
      <button className="rp-link" onClick={() => navigateProject()}>
        ← Volver al listado
      </button>
      <p className="rp-eyebrow">
        {sections.find(([id]) => id === section)?.[1]}
      </p>
      <div className="rp-heading">
        <div>
          <h1>{project.title}</h1>
          <p>
            {project.university} · {project.program}
          </p>
        </div>
        <span className="rp-badge">Borrador</span>
      </div>
      <div className="rp-project-actions">{children}</div>
    </header>
  );
}
