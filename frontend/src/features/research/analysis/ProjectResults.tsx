import { EmptyState } from '../projects/ProjectShell';
import { navigateWorkspace, navigateProject } from '../projects/navigation';
import { useAnalysisHistory } from './useAnalysisHistory';
import {
  dateLabel,
  recordIsCurrent,
  recordState,
  techniqueName,
} from './analysisPresentation';
import { ResultDetail } from './ResultDetail';

export function ProjectResults({
  projectId,
  item,
  active = true,
}: {
  projectId: string;
  item?: string | null;
  active?: boolean;
}) {
  const history = useAnalysisHistory(projectId, active);
  const selected =
    history.records.find((r) => r.plan.id === item) ?? history.records[0];
  return (
    <section aria-label="Resultados de investigación">
      <div className="rp-section-heading">
        <div>
          <h2>Resultados de la investigación</h2>
          <p>
            Consulta lo que ya se calculó, sin volver a ejecutar el análisis.
          </p>
        </div>
        <button
          className="rp-secondary"
          disabled={history.loading}
          onClick={() => void history.reload()}
        >
          Actualizar resultados
        </button>
      </div>
      {history.loading && <p role="status">Cargando resultados…</p>}
      {history.error && (
        <p className="rp-error" role="alert">
          {history.error}
        </p>
      )}
      {history.sourceError && (
        <p className="rp-warning" role="status">
          {history.sourceError}
        </p>
      )}
      {!history.loading && !history.error && !history.records.length && (
        <EmptyState title="Todavía no hay resultados">
          Prepara tu investigación y aprueba un plan en Análisis. Los resultados
          aparecerán aquí cuando termine la ejecución.
        </EmptyState>
      )}
      {!history.loading && !history.records.length && (
        <button onClick={() => navigateProject(projectId, 'analysis')}>
          Ir a Análisis
        </button>
      )}
      {!!history.records.length && (
        <div className="rp-results-layout">
          <nav
            aria-label="Resultados disponibles"
            className="rp-record-list rp-history-strip"
          >
            {history.records.map((record) => (
              <button
                className="rp-secondary"
                key={record.plan.id}
                aria-current={
                  selected?.plan.id === record.plan.id ? 'true' : undefined
                }
                onClick={() =>
                  navigateWorkspace(
                    projectId,
                    'results',
                    'detail',
                    record.plan.id,
                  )
                }
              >
                <strong>{techniqueName(record)}</strong>
                <small>{dateLabel(record.created_at)}</small>
                <span className="rp-badge">
                  {recordState(record, history.status)}
                </span>
              </button>
            ))}
          </nav>
          {selected && (
            <div className="rp-selected-result" key={selected.plan.id}>
              <div className="rp-selected-result-heading">
                <h3>{techniqueName(selected)}</h3>
                <p className="rp-hint">
                  {dateLabel(selected.created_at)} ·{' '}
                  {recordState(selected, history.status)} ·{' '}
                  {selected.result?.status === 'completed'
                    ? 'Completado'
                    : 'Fallido'}
                </p>
              </div>
              {!recordIsCurrent(selected, history.status) && (
                <p className="rp-warning">
                  {selected.stale_reason ??
                    'Este resultado es histórico o su vigencia no está confirmada.'}{' '}
                  Puedes consultar sus métricas guardadas; los gráficos que
                  acceden a observaciones requieren fuentes vigentes.
                </p>
              )}
              <ResultDetail
                projectId={projectId}
                record={selected}
                current={
                  !history.error &&
                  !history.loading &&
                  recordIsCurrent(selected, history.status)
                }
              />
              <details className="rp-technical">
                <summary>Referencias del resultado</summary>
                <p>Plan: {selected.plan.id}</p>
                <p>Resultado: {selected.result?.id}</p>
                <p>Paquete: {selected.plan.research_package_id}</p>
              </details>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
