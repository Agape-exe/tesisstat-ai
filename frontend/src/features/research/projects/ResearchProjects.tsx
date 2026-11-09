import { useEffect, useRef, useState } from 'react';
import { createProjectApi, ProjectApiError } from './api';
import { DeleteProjectDialog } from './DeleteProjectDialog';
import { ProjectForm } from './ProjectForm';
import { ProjectList } from './ProjectList';
import { ProjectHeader, ProjectShell } from './ProjectShell';
import { ProjectWorkspace } from './ProjectWorkspace';
import { navigateProject, useProjectRoute } from './navigation';
import type { Project, ProjectDraft, ProjectService } from './types';
import { degreeLabels } from './types';
import { UiIcon } from './UiIcon';
import './projects.css';
import './redesign.css';

const defaultService = createProjectApi();
const errorText = (error: unknown, fallback: string) =>
  error instanceof ProjectApiError ? error.message : fallback;

export function ResearchProjects({
  service = defaultService,
  homeHref = '/research-demo/',
  integrated = false,
}: {
  service?: ProjectService;
  homeHref?: string;
  integrated?: boolean;
}) {
  const route = useProjectRoute();
  const { projectId, section, form } = route;
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState<Project | null>(null);
  const [detailError, setDetailError] = useState('');
  const [notice, setNotice] = useState('');
  const [deleting, setDeleting] = useState<Project | null>(null);
  const deleteButton = useRef<HTMLButtonElement | null>(null);
  const activeRoute = useRef(route);
  useEffect(() => {
    activeRoute.current = route;
  });
  useEffect(() => {
    const closeDialog = () => setDeleting(null);
    window.addEventListener('popstate', closeDialog);
    window.addEventListener('hashchange', closeDialog);
    window.addEventListener('tesisstat:navigate', closeDialog);
    return () => {
      window.removeEventListener('popstate', closeDialog);
      window.removeEventListener('hashchange', closeDialog);
      window.removeEventListener('tesisstat:navigate', closeDialog);
    };
  }, []);
  const project = selected?.id === projectId ? selected : null;

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
            errorText(caught, 'No se pudieron cargar las investigaciones.'),
          );
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [service, refresh]);

  useEffect(() => {
    if (!projectId) return;
    const controller = new AbortController();
    service
      .get(projectId, controller.signal)
      .then((item) => {
        if (!controller.signal.aborted) {
          setSelected(item);
          setDetailError('');
        }
      })
      .catch((caught) => {
        if (!controller.signal.aborted)
          setDetailError(
            errorText(caught, 'No se pudo cargar la investigación.'),
          );
      });
    return () => controller.abort();
  }, [service, projectId, refresh]);

  function goList() {
    setNotice('');
    setDetailError('');
    setSelected(null);
    setDeleting(null);
    setLoading(true);
    setRefresh((n) => n + 1);
    navigateProject();
  }
  function open(id: string) {
    setNotice('');
    setDetailError('');
    navigateProject(id);
  }
  async function save(draft: ProjectDraft) {
    const edited = form === 'edit' && project;
    const savedRoute = activeRoute.current;
    const saved = edited
      ? await service.update(edited.id, draft)
      : await service.create(draft);
    setProjects((items) => [saved, ...items.filter((p) => p.id !== saved.id)]);
    if (
      activeRoute.current.projectId !== savedRoute.projectId ||
      activeRoute.current.form !== savedRoute.form
    )
      return;
    setSelected(saved);
    setDetailError('');
    setError('');
    setNotice(edited ? 'Investigación actualizada.' : 'Investigación creada.');
    navigateProject(saved.id, 'home', null, true);
  }
  async function remove() {
    if (!deleting) return;
    const target = deleting;
    await service.delete(target.id);
    setProjects((items) => items.filter((p) => p.id !== target.id));
    setDeleting((current) => (current?.id === target.id ? null : current));
    const currentProject = activeRoute.current.projectId;
    if (currentProject === target.id) {
      setSelected(null);
      setDetailError('');
      navigateProject(null, 'assistant', null, true);
    }
    if (!currentProject || currentProject === target.id)
      setNotice('Investigación eliminada.');
  }

  return (
    <ProjectShell
      project={project}
      section={section}
      homeHref={homeHref}
      assistant={!!project && !form && section === 'assistant'}
      listing={!projectId && !form}
    >
      {notice && (
        <p role="status" className="rp-success rp-toast">
          {notice}
        </p>
      )}
      {form === 'create' ? (
        <>
          <p className="rp-eyebrow">UN NUEVO COMIENZO</p>
          <div className="rp-heading">
            <div>
              <h1>Nueva investigación</h1>
              <p>
                Elige un nombre provisional y comienza el recorrido de tu
                proyecto.
              </p>
            </div>
          </div>
          <ProjectForm key="create" onSave={save} onCancel={goList} />
        </>
      ) : !projectId ? (
        <>
          <p className="rp-eyebrow">ESPACIO DE INVESTIGACIÓN</p>
          <div className="rp-heading">
            <div>
              <h1>Tu investigación, con claridad.</h1>
              <p className="rp-intro">
                Selecciona tu proyecto para continuar el recorrido, organizar
                tus materiales y comprender tus análisis.
              </p>
            </div>
          </div>
          <div className="rp-entry-row">
            <section className="rp-feature-card">
              <h2>Comienza una nueva investigación</h2>
              <p>
                Crea el espacio de tu tesis. El asistente te acompañará desde la
                metodología hasta la interpretación de resultados.
              </p>
              <button
                disabled={loading}
                onClick={() => {
                  setNotice('');
                  navigateProject(null, 'assistant', 'create');
                }}
              >
                <UiIcon name="plus" /> Nueva investigación
              </button>
            </section>
            <aside className="rp-info-card">
              <span className="rp-info-icon">
                <UiIcon name="message" />
              </span>
              <strong>El asistente trabaja dentro de cada proyecto</strong>
              <p>
                Los documentos, instrumentos y datos permanecen vinculados a la
                investigación que selecciones.
              </p>
            </aside>
          </div>
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
            ) : (
              <ProjectList
                projects={projects}
                onOpen={open}
                onEdit={(target) => {
                  setSelected(target);
                  setNotice('');
                  navigateProject(target.id, 'assistant', 'edit');
                }}
                onDelete={(target, trigger) => {
                  deleteButton.current = trigger;
                  setDeleting(target);
                }}
              />
            )}
          </section>
        </>
      ) : !project ? (
        <section className="rp-state">
          {detailError ? (
            <>
              <p role="alert" className="rp-error">
                {detailError}
              </p>
              <button
                onClick={() => {
                  setDetailError('');
                  setRefresh((n) => n + 1);
                }}
              >
                Reintentar detalle
              </button>
            </>
          ) : (
            <p role="status">Cargando detalle…</p>
          )}
          <button className="rp-secondary" onClick={goList}>
            Volver al listado
          </button>
        </section>
      ) : form === 'edit' ? (
        <>
          <h1>Editar investigación</h1>
          <ProjectForm
            key={project.id}
            initial={project}
            onSave={save}
            onCancel={goList}
          />
        </>
      ) : (
        <section aria-label="Información de la investigación" key={project.id}>
          {section !== 'assistant' && (
            <ProjectHeader project={project} section={section} />
          )}
          <ProjectWorkspace
            key={project.id}
            projectId={project.id}
            projectTitle={project.title}
            projectDescription={project.description}
            section={section}
            view={route.view}
            item={route.item}
          />
          {section !== 'assistant' && (
            <details className="rp-project-details">
              <summary>Información académica del proyecto</summary>
              <p className="rp-description">
                {project.description || 'Sin descripción todavía.'}
              </p>
              <dl>
                <div>
                  <dt>Universidad</dt>
                  <dd>{project.university || 'Sin especificar'}</dd>
                </div>
                <div>
                  <dt>Facultad</dt>
                  <dd>{project.faculty || 'Sin especificar'}</dd>
                </div>
                <div>
                  <dt>Programa</dt>
                  <dd>{project.program || 'Sin especificar'}</dd>
                </div>
                <div>
                  <dt>Año académico</dt>
                  <dd>{project.academic_year ?? 'Sin especificar'}</dd>
                </div>
                <div>
                  <dt>Grado académico</dt>
                  <dd>
                    {project.degree
                      ? degreeLabels[project.degree]
                      : 'Sin especificar'}
                  </dd>
                </div>
                <div>
                  <dt>Creada</dt>
                  <dd>
                    {new Date(project.created_at).toLocaleString('es-PE')}
                  </dd>
                </div>
                <div>
                  <dt>Última actualización</dt>
                  <dd>
                    {new Date(project.updated_at).toLocaleString('es-PE')}
                  </dd>
                </div>
              </dl>
            </details>
          )}
        </section>
      )}
      {deleting && (
        <DeleteProjectDialog
          title={deleting.title}
          onConfirm={remove}
          onCancel={() => {
            setDeleting(null);
            deleteButton.current?.focus();
          }}
        />
      )}
      {!(project && !form && section === 'assistant') && (
        <footer className="rp-footer">
          TesisStat AI · {integrated ? 'Research + Statistics' : 'Research'} ·
          Entorno local sin autenticación. Utiliza únicamente información
          ficticia.
        </footer>
      )}
    </ProjectShell>
  );
}
