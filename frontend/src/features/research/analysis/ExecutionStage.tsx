import { PlanDetails } from './PlanDetails';
import { useAnalysisPlans } from './useAnalysisPlans';
import { createAnalysisApi } from './api';
import { techniqueName, dateLabel } from './analysisPresentation';
import type { ResearchPackageSummary } from '../packages/api';
import { navigateWorkspace, navigateProject } from '../projects/navigation';
import { EmptyState } from '../projects/ProjectShell';
const api = createAnalysisApi();
export function ExecutionStage({
  projectId,
  researchPackage,
  item,
  authorized,
  onRejected,
}: {
  projectId: string;
  researchPackage: ResearchPackageSummary | null;
  item?: string | null;
  authorized: boolean;
  onRejected: () => void;
}) {
  const plans = useAnalysisPlans(projectId, researchPackage?.id);
  const executable = plans.records.filter(
    (r) =>
      r.plan.research_package_id === researchPackage?.id &&
      !r.invalidated_at &&
      r.plan.status === 'approved' &&
      !!r.approved_at &&
      r.executable &&
      !r.result,
  );
  const selected = executable.find((r) => r.plan.id === item) ?? executable[0];
  async function execute() {
    if (!selected || !authorized || !plans.ready || plans.busy) return;
    if (
      await plans.work(
        () => api.execute(projectId, selected.plan.id),
        onRejected,
      )
    )
      navigateProject(projectId, 'results');
  }
  return (
    <section aria-label="Ejecución de planes aprobados">
      <h3>Ejecutar un plan aprobado</h3>
      <p>
        Solo aparecen planes aprobados y vigentes que todavía no tienen
        resultado.
      </p>
      {plans.error && (
        <p role="alert" className="rp-error">
          {plans.error}
        </p>
      )}
      {!plans.ready && !plans.error && <p role="status">Verificando planes…</p>}
      {!!plans.error && (
        <button className="rp-secondary" onClick={() => void plans.reload()}>
          Reintentar planes
        </button>
      )}
      {plans.ready && !selected && (
        <>
          <EmptyState title="No hay planes listos para ejecutar">
            Revisa y aprueba una propuesta en Plan estadístico. Si ya se
            ejecutó, su resultado está en Resultados.
          </EmptyState>
          <button
            className="rp-secondary"
            onClick={() => navigateWorkspace(projectId, 'analysis', 'plan')}
          >
            Revisar planes
          </button>
        </>
      )}
      {selected && (
        <div className="rp-surface">
          <label className="rp-field">
            Plan aprobado
            <select
              value={selected.plan.id}
              disabled={plans.busy}
              onChange={(e) =>
                navigateWorkspace(
                  projectId,
                  'analysis',
                  'execution',
                  e.target.value,
                )
              }
            >
              {executable.map((r) => (
                <option key={r.plan.id} value={r.plan.id}>
                  {techniqueName(r)} · {dateLabel(r.created_at)}
                </option>
              ))}
            </select>
          </label>
          <PlanDetails record={selected} />
          <p className="rp-success">
            Aprobación humana registrada: {dateLabel(selected.approved_at!)}
          </p>
          {!authorized && (
            <p className="rp-warning">
              Autoriza el dataset no sintético antes de ejecutar. El servidor
              vuelve a verificar las fuentes y permisos.
            </p>
          )}
          <button
            disabled={!plans.ready || plans.busy || !authorized}
            onClick={() => void execute()}
          >
            {plans.busy ? 'Ejecutando…' : 'Ejecutar análisis'}
          </button>
        </div>
      )}
    </section>
  );
}
