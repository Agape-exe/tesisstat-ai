import { PlanDetails } from './PlanDetails';
import { useState } from 'react';
import type { ResearchPackageSummary } from '../packages/api';
import { createAnalysisApi } from './api';
import { useAnalysisPlans } from './useAnalysisPlans';
import { techniqueName, dateLabel } from './analysisPresentation';
import { navigateProject, navigateWorkspace } from '../projects/navigation';
const api = createAnalysisApi();
export function ProjectAnalysis({
  projectId,
  researchPackage,
  item,
  authorized = true,
  onRejected = () => {},
}: {
  projectId: string;
  researchPackage:
    | (Pick<ResearchPackageSummary, 'id' | 'hypotheses'> &
        Partial<Pick<ResearchPackageSummary, 'dataset'>>)
    | null;
  item?: string | null;
  authorized?: boolean;
  onRejected?: () => void;
}) {
  const plans = useAnalysisPlans(projectId, researchPackage?.id);
  const [localHypothesis, setLocalHypothesis] = useState('');
  const hypothesis =
    researchPackage?.hypotheses.find(
      (h) => h.id === (item === undefined ? localHypothesis : item),
    ) ?? researchPackage?.hypotheses[0];
  const matching = plans.records.filter(
    (r) =>
      r.plan.research_package_id === researchPackage?.id &&
      r.plan.hypothesis_id === hypothesis?.id,
  );
  const [chosen, setChosen] = useState('');
  const selected = matching.find((r) => r.plan.id === chosen) ?? matching[0];
  const current =
    !!selected &&
    !selected.invalidated_at &&
    selected.plan.research_package_id === researchPackage?.id;
  const canApprove =
    current &&
    selected.plan.status === 'proposed' &&
    selected.executable &&
    authorized &&
    plans.ready;
  return (
    <section aria-label="Análisis estadístico Research">
      <h3>Plan estadístico</h3>
      <p>Elige una hipótesis y revisa la propuesta antes de aprobarla.</p>
      {plans.error && (
        <p role="alert" className="rp-error">
          {plans.error}
        </p>
      )}
      {!plans.ready && !plans.error && <p role="status">Cargando planes…</p>}
      {plans.error && (
        <button className="rp-secondary" onClick={() => void plans.reload()}>
          Reintentar planes
        </button>
      )}
      {!researchPackage && (
        <p className="rp-warning">
          Genera un paquete vigente en Preparación para proponer análisis. Los
          resultados anteriores se conservan en Resultados.
        </p>
      )}
      {hypothesis && (
        <>
          <label className="rp-field">
            Hipótesis seleccionada
            <select
              value={hypothesis.id}
              disabled={plans.busy}
              onChange={(e) => {
                setLocalHypothesis(e.target.value);
                setChosen('');
                navigateWorkspace(
                  projectId,
                  'analysis',
                  'plan',
                  e.target.value,
                );
              }}
            >
              {researchPackage?.hypotheses.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.statement}
                </option>
              ))}
            </select>
          </label>
          {!selected ? (
            <div className="rp-surface">
              <p>Aún no hay un plan para esta hipótesis.</p>
              <button
                disabled={plans.busy || !plans.ready || !authorized}
                onClick={() =>
                  void plans.work(
                    () =>
                      api.propose(
                        projectId,
                        researchPackage!.id,
                        hypothesis.id,
                      ),
                    onRejected,
                  )
                }
              >
                Proponer análisis
              </button>
            </div>
          ) : (
            <div className="rp-surface">
              <label className="rp-field">
                Propuesta a revisar
                <select
                  value={selected.plan.id}
                  disabled={plans.busy}
                  onChange={(e) => setChosen(e.target.value)}
                >
                  {matching.map((r) => (
                    <option key={r.plan.id} value={r.plan.id}>
                      {techniqueName(r)} · {dateLabel(r.created_at)} ·{' '}
                      {r.plan.status === 'approved'
                        ? 'Aprobado'
                        : r.plan.status === 'needs_clarification'
                          ? 'Requiere aclaraciones'
                          : 'Propuesto'}
                    </option>
                  ))}
                </select>
              </label>
              <PlanDetails record={selected} />
              {canApprove && (
                <button
                  disabled={plans.busy}
                  onClick={() =>
                    void plans.work(
                      () => api.approve(projectId, selected),
                      onRejected,
                    )
                  }
                >
                  Aprobar análisis
                </button>
              )}
              {current &&
                selected.plan.status === 'approved' &&
                !selected.result && (
                  <>
                    <p className="rp-success">
                      El plan está aprobado. Ejecutarlo requiere una acción
                      separada.
                    </p>
                    <button
                      onClick={() =>
                        navigateWorkspace(
                          projectId,
                          'analysis',
                          'execution',
                          selected.plan.id,
                        )
                      }
                    >
                      Continuar a ejecución
                    </button>
                  </>
                )}
              {selected.result && (
                <>
                  <p>Este plan ya tiene un resultado guardado.</p>
                  <button onClick={() => navigateProject(projectId, 'results')}>
                    Consultar resultados
                  </button>
                </>
              )}
              <button
                className="rp-secondary"
                disabled={plans.busy || !plans.ready || !authorized}
                onClick={() => {
                  setChosen('');
                  void plans.work(
                    () =>
                      api.propose(
                        projectId,
                        researchPackage!.id,
                        hypothesis.id,
                      ),
                    onRejected,
                  );
                }}
              >
                Nueva propuesta
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
