import { useEffect, useRef, useState } from 'react';
import { ProjectDocuments } from '../documents/ProjectDocuments';
import { ProjectDatasets } from '../datasets/ProjectDatasets';
import { createProjectApi, ProjectApiError } from './api';
import { DeleteProjectDialog } from './DeleteProjectDialog';
import { ProjectForm } from './ProjectForm';
import { degreeLabels } from './types';
import type { Project, ProjectDraft, ProjectService } from './types';
import './projects.css';

type View =
  | { kind: 'list' | 'create' }
  | { kind: 'detail' | 'edit'; project: Project }
  | { kind: 'loading'; id: string }
  | { kind: 'detail-error'; id: string; message: string };
const defaultService = createProjectApi();
const dateLabel = (value: string) =>
  new Date(value).toLocaleString('es-PE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });

export function ResearchProjects({
  service = defaultService,
}: {
  service?: ProjectService;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [view, setView] = useState<View>({ kind: 'list' });
  const [notice, setNotice] = useState('');
  const [deleting, setDeleting] = useState(false);
  const detailRequest = useRef<AbortController | null>(null);
  const deleteButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    service
      .list(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) {
          setProjects(items);
          setError('');
          setLoading(false);
        }
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setError(
            caught instanceof ProjectApiError
              ? caught.message
              : 'No se pudieron cargar las investigaciones.',
          );
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [service, refresh]);

  useEffect(() => () => detailRequest.current?.abort(), []);

  function goList() {
    detailRequest.current?.abort();
    setView({ kind: 'list' });
    setNotice('');
    setLoading(true);
    setRefresh((value) => value + 1);
  }

  async function showDetail(id: string) {
    detailRequest.current?.abort();
    const controller = new AbortController();
    detailRequest.current = controller;
    setNotice('');
    setView({ kind: 'loading', id });
    try {
      const project = await service.get(id, controller.signal);
      if (!controller.signal.aborted) setView({ kind: 'detail', project });
    } catch (caught) {
      if (!controller.signal.aborted)
        setView({
          kind: 'detail-error',
          id,
          message:
            caught instanceof ProjectApiError
              ? caught.message
              : 'No se pudo cargar la investigación.',
        });
    }
  }

  async function save(draft: ProjectDraft) {
    const edited = view.kind === 'edit';
    const project = edited
      ? await service.update(view.project.id, draft)
      : await service.create(draft);
    setProjects((items) => [
      project,
      ...items.filter((item) => item.id !== project.id),
    ]);
    setView({ kind: 'detail', project });
    setError('');
    setNotice(edited ? 'Investigación actualizada.' : 'Investigación creada.');
  }

  async function remove() {
    if (view.kind !== 'detail') return;
    await service.delete(view.project.id);
    setProjects((items) => items.filter((item) => item.id !== view.project.id));
    setDeleting(false);
    setView({ kind: 'list' });
    setNotice('Investigación eliminada.');
  }

  const title =
    view.kind === 'list'
      ? 'Mis investigaciones'
      : view.kind === 'create'
        ? 'Nueva investigación'
        : view.kind === 'edit'
          ? 'Editar investigación'
          : 'Detalle de investigación';
  return (
    <main className="rp-shell">
      <header className="rp-header">
        <a href="/research-demo/" aria-label="TesisStat AI, investigaciones">
          TesisStat <strong>AI</strong>
        </a>
        <span>Research · Entorno de desarrollo</span>
      </header>
      <p className="rp-eyebrow">TU ESPACIO DE INVESTIGACIÓN</p>
      <div className="rp-heading">
        <div>
          <h1>{title}</h1>
          <p>Organiza el punto de partida de tu tesis.</p>
        </div>
        {view.kind === 'list' && (
          <button
            disabled={loading}
            onClick={() => {
              setNotice('');
              setView({ kind: 'create' });
            }}
          >
            Nueva investigación
          </button>
        )}
      </div>
      <p className="rp-dev-note">
        Demostración local sin autenticación. Utiliza únicamente información
        ficticia.
      </p>
      {notice && (
        <p role="status" className="rp-success">
          {notice}
        </p>
      )}
      {view.kind === 'list' && (
        <section aria-label="Listado de investigaciones" aria-busy={loading}>
          {loading ? (
            <p role="status" className="rp-state">
              Cargando investigaciones…
            </p>
          ) : error ? (
            <div className="rp-state">
              <p role="alert" className="rp-error">
                {error}
              </p>
              <button className="rp-secondary" onClick={goList}>
                Reintentar
              </button>
            </div>
          ) : projects.length === 0 ? (
            <div className="rp-state">
              <span className="rp-empty-icon" aria-hidden="true">
                ＋
              </span>
              <h2>Tu próxima investigación empieza aquí</h2>
              <p>
                Aún no tienes proyectos. Crea uno y completa su información
                académica.
              </p>
            </div>
          ) : (
            <>
              <p className="rp-count">
                {projects.length}{' '}
                {projects.length === 1 ? 'investigación' : 'investigaciones'} ·
                Más recientes primero
              </p>
              <div className="rp-cards">
                {projects.map((project) => (
                  <article className="rp-card" key={project.id}>
                    <span className="rp-badge">Borrador</span>
                    <h2>{project.title}</h2>
                    <p>{project.description || 'Sin descripción todavía.'}</p>
                    <p className="rp-meta">
                      {project.university} · {project.program}
                    </p>
                    <footer>
                      <span>
                        {degreeLabels[project.degree]}
                        {project.academic_year
                          ? ` · ${project.academic_year}`
                          : ''}
                      </span>
                      <button
                        className="rp-link"
                        aria-label={`Ver investigación: ${project.title}`}
                        onClick={() => void showDetail(project.id)}
                      >
                        Ver investigación →
                      </button>
                    </footer>
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      )}
      {view.kind === 'create' && (
        <ProjectForm key="create" onSave={save} onCancel={goList} />
      )}
      {view.kind === 'edit' && (
        <ProjectForm
          key={view.project.id}
          initial={view.project}
          onSave={save}
          onCancel={() => setView({ kind: 'detail', project: view.project })}
        />
      )}
      {view.kind === 'loading' && (
        <section className="rp-state">
          <p role="status">Cargando detalle…</p>
          <button className="rp-secondary" onClick={goList}>
            Volver al listado
          </button>
        </section>
      )}
      {view.kind === 'detail-error' && (
        <section className="rp-state">
          <p role="alert" className="rp-error">
            {view.message}
          </p>
          <div className="rp-actions">
            <button onClick={() => void showDetail(view.id)}>
              Reintentar detalle
            </button>
            <button className="rp-secondary" onClick={goList}>
              Volver al listado
            </button>
          </div>
        </section>
      )}
      {view.kind === 'detail' && (
        <section
          className="rp-detail"
          aria-label="Información de la investigación"
        >
          <span className="rp-badge">Borrador</span>
          <h2>{view.project.title}</h2>
          <p className="rp-description">
            {view.project.description || 'Sin descripción todavía.'}
          </p>
          <dl>
            <div>
              <dt>Universidad</dt>
              <dd>{view.project.university}</dd>
            </div>
            <div>
              <dt>Facultad</dt>
              <dd>{view.project.faculty || 'Sin especificar'}</dd>
            </div>
            <div>
              <dt>Carrera o programa</dt>
              <dd>{view.project.program}</dd>
            </div>
            <div>
              <dt>Grado académico</dt>
              <dd>{degreeLabels[view.project.degree]}</dd>
            </div>
            <div>
              <dt>Año académico</dt>
              <dd>{view.project.academic_year ?? 'Sin especificar'}</dd>
            </div>
            <div>
              <dt>Creada</dt>
              <dd>{dateLabel(view.project.created_at)}</dd>
            </div>
            <div>
              <dt>Última actualización</dt>
              <dd>{dateLabel(view.project.updated_at)}</dd>
            </div>
          </dl>
          <ProjectDocuments projectId={view.project.id} />
          <ProjectDatasets projectId={view.project.id} />
          <div className="rp-actions">
            <button
              onClick={() => {
                setNotice('');
                setView({ kind: 'edit', project: view.project });
              }}
            >
              Editar investigación
            </button>
            <button className="rp-secondary" onClick={goList}>
              Volver al listado
            </button>
            <button
              ref={deleteButton}
              className="rp-delete"
              onClick={() => setDeleting(true)}
            >
              Eliminar investigación
            </button>
          </div>
          {deleting && (
            <DeleteProjectDialog
              title={view.project.title}
              onConfirm={remove}
              onCancel={() => {
                setDeleting(false);
                deleteButton.current?.focus();
              }}
            />
          )}
        </section>
      )}
      <footer className="rp-footer">
        Research Module · Los proyectos se guardan en SQLite local. La
        metodología y los análisis se incorporarán después.
      </footer>
    </main>
  );
}
