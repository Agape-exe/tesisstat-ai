import { useState } from 'react';
import { ProjectPackage } from './ProjectPackage';
import { useResearchPackage } from './useResearchPackage';
import { createPackageApi } from './api';
import { ProjectAnalysis } from '../analysis/ProjectAnalysis';
import { ExecutionStage } from '../analysis/ExecutionStage';
import { createAnalysisApi } from '../analysis/api';
import { navigateWorkspace } from '../projects/navigation';
const api = createPackageApi();
const analyses = createAnalysisApi();
const linkCount = (count: number) =>
  `${count} ${count === 1 ? 'vinculación' : 'vinculaciones'}`;
const stageNames = [
  ['preparation', 'Preparación'],
  ['plan', 'Plan estadístico'],
  ['execution', 'Ejecución'],
] as const;
export function AnalysisWorkspace({
  projectId,
  view,
  item,
  active = true,
}: {
  projectId: string;
  view?: string | null;
  item?: string | null;
  active?: boolean;
}) {
  const context = useResearchPackage(projectId, active);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [grant, setGrant] = useState<string | null>(null);
  const stage = ['links', 'plan', 'execution'].includes(view ?? '')
    ? view!
    : 'preparation';
  const status = context.status;
  const current = context.current;
  const real = !!current?.dataset && !current.dataset.synthetic;
  const authorized = !real || grant === current?.id;
  async function prepare() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const checked = await api.validate(projectId);
      if (checked.errors.length) throw new Error(checked.errors.join(' '));
      await api.build(projectId);
      await context.reload();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo preparar la investigación.',
      );
      await context.reload();
    } finally {
      setBusy(false);
    }
  }
  async function authorize() {
    if (!current || busy) return;
    setBusy(true);
    setError('');
    try {
      await analyses.authorizeRealDataset(
        projectId,
        current.id,
        current.dataset.id,
      );
      setGrant(current.id);
    } catch (cause) {
      setGrant(null);
      setError(
        cause instanceof Error ? cause.message : 'No se pudo autorizar.',
      );
    } finally {
      setBusy(false);
    }
  }
  const checks = status
    ? [
        [
          'Metodología',
          status.review?.review_status === 'reviewed'
            ? 'Confirmada'
            : 'Pendiente de revisión',
          status.review?.content.general_objective.value ??
            'Revisa objetivos e hipótesis en Metodología.',
        ],
        [
          'Dataset',
          status.dataset?.active ? 'Activo' : 'Pendiente',
          status.dataset
            ? `${status.dataset.name} · ${status.dataset.row_count} filas`
            : 'Selecciona un dataset en Datos.',
        ],
        [
          'Variables y columnas',
          linkCount(
            status.configuration.variables.filter((v) => v.columns.length > 0)
              .length,
          ),
          `${status.review?.content.variables.length ?? 0} variables revisadas. Las escalas se declaran manualmente.`,
        ],
        [
          'Hipótesis y objetivos',
          linkCount(status.configuration.hypotheses.length),
          'Cada hipótesis necesita su objetivo y sus variables.',
        ],
      ]
    : [];
  return (
    <section aria-label="Espacio de análisis">
      <p className="rp-eyebrow">DE LAS FUENTES A LA EVIDENCIA</p>
      <h2>Análisis</h2>
      <p>Prepara, revisa y ejecuta. Cada etapa tiene una decisión distinta.</p>
      <nav className="rp-stage-nav" aria-label="Etapas del análisis">
        {stageNames.map(([id, label], i) => (
          <button
            key={id}
            className="rp-secondary"
            aria-current={
              (stage === 'links' ? 'preparation' : stage) === id
                ? 'step'
                : undefined
            }
            onClick={() => navigateWorkspace(projectId, 'analysis', id)}
          >
            <span>{i + 1}</span>
            {label}
          </button>
        ))}
      </nav>
      {(context.error || error) && (
        <p role="alert" className="rp-error">
          {error || context.error}
        </p>
      )}
      {context.error && (
        <button className="rp-secondary" onClick={() => void context.reload()}>
          Reintentar preparación
        </button>
      )}
      {stage === 'preparation' && (
        <>
          <div className="rp-section-heading">
            <div>
              <h3>Preparación de investigación</h3>
              <p>
                Comprueba las fuentes y completa lo pendiente antes de solicitar
                un plan.
              </p>
            </div>
            <span className="rp-badge">
              {status?.state === 'generated'
                ? 'Preparación vigente'
                : status?.state === 'stale'
                  ? 'Requiere actualización'
                  : 'En preparación'}
            </span>
          </div>
          {context.loading && <p role="status">Verificando fuentes…</p>}
          <div className="rp-requirement-grid">
            {checks.map(([label, state, description]) => (
              <article className="rp-surface" key={label}>
                <p className="rp-eyebrow">{label}</p>
                <h4>{state}</h4>
                <p>{description}</p>
              </article>
            ))}
          </div>
          {status?.errors.map((message) => (
            <p key={message} className="rp-error">
              {message}
            </p>
          ))}
          {status?.warnings.map((message) => (
            <p key={message} className="rp-warning">
              {message}
            </p>
          ))}
          {status?.state === 'stale' && (
            <p className="rp-warning">
              Las fuentes cambiaron. Actualiza las vinculaciones y vuelve a
              preparar la investigación. Los resultados guardados permanecen
              disponibles.
            </p>
          )}
          <div className="rp-actions">
            <button
              className="rp-secondary"
              onClick={() => navigateWorkspace(projectId, 'analysis', 'links')}
            >
              Editar vinculaciones
            </button>
            {current ? (
              <button
                onClick={() => navigateWorkspace(projectId, 'analysis', 'plan')}
              >
                Continuar al plan estadístico
              </button>
            ) : (
              <button
                disabled={busy || context.loading || !status}
                onClick={() => void prepare()}
              >
                {busy ? 'Validando…' : 'Validar y preparar investigación'}
              </button>
            )}
          </div>
          <details className="rp-technical">
            <summary>Estado avanzado</summary>
            <p>Estado del paquete: {status?.state ?? 'Sin verificar'}</p>
            <p>Referencia: {status?.package_id ?? 'Sin generar'}</p>
          </details>
        </>
      )}
      {stage === 'links' && (
        <>
          <button
            className="rp-link"
            onClick={() => {
              void context.reload();
              navigateWorkspace(projectId, 'analysis', 'preparation');
            }}
          >
            ← Volver al resumen
          </button>
          <ProjectPackage
            projectId={projectId}
            onChanged={() => void context.reload()}
          />
        </>
      )}
      {['plan', 'execution'].includes(stage) && (
        <>
          {context.loading && <p role="status">Verificando vigencia…</p>}
          {real && (
            <aside className="rp-warning">
              <h3>Autorización del dataset</h3>
              <p>
                Este dataset no es sintético. La autorización es explícita,
                temporal y se revoca al reiniciar el servidor o cambiar sus
                fuentes.
              </p>
              <button
                className={authorized ? 'rp-secondary' : ''}
                disabled={busy || context.loading}
                onClick={() => void authorize()}
              >
                {authorized
                  ? 'Renovar autorización local'
                  : 'Autorizar datos reales para esta sesión'}
              </button>
            </aside>
          )}
          {stage === 'plan' ? (
            <ProjectAnalysis
              projectId={projectId}
              researchPackage={!context.loading ? current : null}
              item={item}
              authorized={authorized && !busy}
              onRejected={() => setGrant(null)}
            />
          ) : (
            <ExecutionStage
              projectId={projectId}
              researchPackage={!context.loading ? current : null}
              item={item}
              authorized={authorized && !busy}
              onRejected={() => setGrant(null)}
            />
          )}
        </>
      )}
    </section>
  );
}
