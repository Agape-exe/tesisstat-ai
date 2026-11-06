import { useState } from 'react';
import { EmptyState } from './ProjectShell';
import { degreeLabels, type Project } from './types';

export function ProjectList({
  projects,
  onOpen,
}: {
  projects: Project[];
  onOpen: (id: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('recent');
  const normalized = query.trim().toLocaleLowerCase('es');
  const filtered = projects
    .filter((p) =>
      [p.title, p.description, p.university, p.program].some((value) =>
        value.toLocaleLowerCase('es').includes(normalized),
      ),
    )
    .sort((a, b) =>
      sort === 'name'
        ? a.title.localeCompare(b.title, 'es')
        : b.updated_at.localeCompare(a.updated_at),
    );
  return (
    <>
      <div className="rp-list-toolbar">
        <label className="rp-search">
          Buscar investigaciones
          <input
            type="search"
            placeholder="Buscar por título, tema o universidad…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          Ordenar por
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value)}
          >
            <option value="recent">Más recientes</option>
            <option value="name">Nombre</option>
          </select>
        </label>
      </div>
      <p className="rp-count" role="status">
        {filtered.length}{' '}
        {filtered.length === 1 ? 'investigación' : 'investigaciones'}
      </p>
      {!projects.length ? (
        <EmptyState title="Tu próxima investigación empieza aquí">
          Aún no tienes proyectos. Crea uno y completa su información académica.
        </EmptyState>
      ) : !filtered.length ? (
        <EmptyState title="No hay coincidencias">
          Prueba con otro título, tema o universidad.
        </EmptyState>
      ) : (
        <div className="rp-cards">
          {filtered.map((project) => (
            <article className="rp-card" key={project.id}>
              <span className="rp-project-icon" aria-hidden="true">
                ▤
              </span>
              <div className="rp-card-copy">
                <h2>{project.title}</h2>
                <p>
                  {project.university} · {project.program} ·{' '}
                  {degreeLabels[project.degree]}
                </p>
                <small>
                  Actualizada el{' '}
                  {new Date(project.updated_at).toLocaleDateString('es-PE')}
                </small>
              </div>
              <span className="rp-badge">Borrador</span>
              <button
                className="rp-link"
                aria-label={`Ver investigación: ${project.title}`}
                onClick={() => onOpen(project.id)}
              >
                Abrir asistente →
              </button>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
