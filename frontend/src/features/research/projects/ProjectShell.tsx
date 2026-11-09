import type { ReactNode } from 'react';
import { useEffect, useRef, useState } from 'react';
import {
  navigateProject,
  sections,
  secondarySections,
  primarySection,
  type Section,
} from './navigation';
import type { Project } from './types';
import { UiIcon } from './UiIcon';
import { sectionInfo } from './sectionInfo';

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
  assistant = false,
  listing = false,
}: {
  assistant?: boolean;
  listing?: boolean;
  project: Project | null;
  section: Section;
  homeHref: string;
  children: ReactNode;
}) {
  const [menu, setMenu] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const content = useRef<HTMLElement>(null);
  const navigationClose = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (menu) navigationClose.current?.focus();
  }, [menu]);
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
    <div
      className={`rp-shell ${assistant ? 'rp-assistant-shell' : ''} ${listing ? 'rp-list-shell' : ''}`}
    >
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
        <strong>
          <UiIcon name="chart" /> TesisStat AI
        </strong>
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
          <span className="rp-sr-only">
            {menu ? 'Cerrar menú' : 'Abrir menú'}
          </span>
          <UiIcon name={menu ? 'x' : 'menu'} />
        </button>
      </header>
      {menu && (
        <button
          className="rp-menu-scrim"
          aria-label="Cerrar navegación"
          onClick={() => {
            setMenu(false);
            menuButton.current?.focus();
          }}
        />
      )}
      <aside
        className={`rp-sidebar ${menu ? 'rp-menu-open' : ''}`}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setMenu(false);
            menuButton.current?.focus();
          }
        }}
      >
        <button
          ref={navigationClose}
          className="rp-navigation-close"
          aria-label="Cerrar menú de navegación"
          onClick={() => {
            setMenu(false);
            menuButton.current?.focus();
          }}
        >
          <UiIcon name="x" />
        </button>
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
            <UiIcon name="chart" />
          </span>{' '}
          TesisStat AI
        </a>
        <nav id="primary-navigation" aria-label="Navegación principal">
          {project && (
            <div className="rp-selected-project">
              <small>INVESTIGACIÓN ACTUAL</small>
              <strong>
                <UiIcon name="folder" />
                <span>{project.title}</span>
              </strong>
            </div>
          )}
          <p className="rp-nav-label">NAVEGACIÓN</p>
          <button
            aria-current={!project ? 'page' : undefined}
            onClick={() => go()}
          >
            <UiIcon name="folder" />
            <span>Mis investigaciones</span>
          </button>
          {project && (
            <>
              <div className="rp-nav-divider" />
              {sections.map(([id, label]) => (
                <button
                  key={id}
                  aria-current={
                    id === primarySection(section) ? 'page' : undefined
                  }
                  onClick={() => go(id)}
                >
                  <UiIcon name={sectionInfo[id].icon} />
                  <span>{label}</span>
                </button>
              ))}
              <div className="rp-nav-divider" />
              <p className="rp-nav-label">APOYO Y HERRAMIENTAS</p>
              {secondarySections.map(([id, label]) => (
                <button
                  key={id}
                  aria-current={id === section ? 'page' : undefined}
                  onClick={() => go(id)}
                >
                  <UiIcon name={sectionInfo[id].icon} />
                  <span>{label}</span>
                </button>
              ))}
            </>
          )}
        </nav>
        <div className="rp-sidebar-bottom">
          <details className="rp-help">
            <summary>
              <UiIcon name="help" />
              Ayuda
            </summary>
            <p>
              Selecciona una investigación. Revisa sus fuentes y aprueba cada
              propuesta antes de ejecutarla. Entorno local sin autenticación:
              utiliza únicamente información ficticia.
            </p>
          </details>
          <div className="rp-profile">
            <span className="rp-avatar">E</span>
            <div>
              <strong>Estudiante</strong>
              <small>Entorno local · datos ficticios</small>
            </div>
          </div>
        </div>
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
}: {
  project: Project;
  section: Section;
}) {
  return (
    <header className="rp-project-header rp-section-header">
      <div className="rp-section-header-inner">
        <div className="rp-section-breadcrumb">
          <button className="rp-link" onClick={() => navigateProject()}>
            Mis investigaciones
          </button>
          <UiIcon name="chevron" />
          <span title={project.title}>{project.title}</span>
        </div>
        <h1>{sectionInfo[section].title}</h1>
        <p>{sectionInfo[section].description}</p>
        <nav className="rp-section-tabs" aria-label="Apartados del proyecto">
          {sections.map(([id, label]) => (
            <a
              key={id}
              aria-current={primarySection(section) === id ? 'page' : undefined}
              href={`#project=${encodeURIComponent(project.id)}&section=${id}`}
              onClick={(event) => {
                if (
                  event.button === 0 &&
                  !event.ctrlKey &&
                  !event.metaKey &&
                  !event.shiftKey &&
                  !event.altKey
                ) {
                  event.preventDefault();
                  navigateProject(project.id, id);
                }
              }}
            >
              <UiIcon name={sectionInfo[id].icon} />
              {label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
