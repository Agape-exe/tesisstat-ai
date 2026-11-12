import { useCallback } from 'react';
import { loadJourney, nextJourneyStep, type JourneyStep } from './journey';
import { useReadResource } from './useReadResource';
import { navigateProject, navigateWorkspace } from './navigation';

export function ProjectHome({
  projectId,
  title,
  description,
  active,
}: {
  projectId: string;
  title: string;
  description: string;
  active: boolean;
}) {
  const load = useCallback(() => loadJourney(projectId), [projectId]);
  const resource = useReadResource(load, active);
  const steps = resource.loading || resource.error ? null : resource.data;
  const next = steps ? nextJourneyStep(steps) : undefined;
  function open(step: JourneyStep) {
    if (step.view) navigateWorkspace(projectId, step.section, step.view);
    else navigateProject(projectId, step.section);
  }
  return (
    <section aria-label="Inicio del proyecto" className="rp-home">
      <div className="rp-home-intro">
        <p className="rp-eyebrow">TU INVESTIGACIÓN</p>
        <h2>{title}</h2>
        <p>
          {description || 'Puedes añadir una descripción cuando lo necesites.'}
        </p>
        <p>
          Sube tus datos, conoce qué puedes analizar, aclara lo necesario y
          revisa una propuesta. Después podrás aprobarla, ejecutarla y
          comprender sus resultados. El contexto de la tesis es opcional.
        </p>
      </div>
      <div className="rp-home-next">
        <h3>Siguiente paso</h3>
        {resource.loading ? (
          <p role="status">Comprobando recursos del proyecto…</p>
        ) : resource.error ? (
          <p role="alert">No se pudo comprobar el recorrido. Reintenta.</p>
        ) : (
          <p>
            {next?.state === 'No verificable'
              ? 'Reintenta la comprobación antes de decidir cómo continuar.'
              : next
                ? `${next.name}: ${next.evidence}`
                : 'Consulta el recorrido recomendado.'}
          </p>
        )}
        <div className="rp-actions">
          <button onClick={() => navigateProject(projectId, 'datasets')}>
            Subir datos
          </button>
          {next && next.state !== 'No verificable' && (
            <button className="rp-secondary" onClick={() => open(next)}>
              Continuar: {next.name}
            </button>
          )}
          <button
            className="rp-secondary"
            onClick={() => navigateProject(projectId, 'datasets')}
          >
            Revisar datos
          </button>
          <button
            className="rp-secondary"
            onClick={() => navigateProject(projectId, 'assistant')}
          >
            Solicitar ayuda
          </button>
          <button
            className="rp-secondary"
            disabled={resource.loading}
            onClick={resource.reload}
          >
            Actualizar estado
          </button>
        </div>
      </div>
      <h3>Recorrido recomendado</h3>
      <p className="rp-hint">
        El estado refleja contexto, archivos, perfiles, propuestas y resultados
        guardados por análisis; puedes explorar Datos sin completar Contexto.
      </p>
      <ol className="rp-journey">
        {steps?.map((step, index) => (
          <li key={step.name}>
            <span className="rp-journey-number" aria-hidden="true">
              {index + 1}
            </span>
            <div>
              <h4>{step.name}</h4>
              <span className="rp-badge">{step.state}</span>
              <p>{step.evidence}</p>
              <button className="rp-link" onClick={() => open(step)}>
                Ir a {step.name}
              </button>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
