import { useCallback, useEffect, useRef, useState } from 'react';
import type { PlanRequest } from '../../../shared/contracts/generated/v2/PlanRequest';
import type { Intent, Diagnostic } from '../diagnostics/api';
import { createAnalysisV2Api, techniqueLabels, type Plan } from './v2api';
import { navigateProject, navigateWorkspace } from '../projects/navigation';
const api = createAnalysisV2Api();
export function AnalysisProposals({
  projectId,
  intent,
  diagnostics,
  dirty,
  active,
}: {
  projectId: string;
  intent: Intent;
  diagnostics: Diagnostic[];
  dirty: boolean;
  active: boolean;
}) {
  const [plans, setPlans] = useState<Plan[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [message, setMessage] = useState('');
  const [confirmed, setConfirmed] = useState<string | null>(null);
  const gate = useRef(false);
  const load = useCallback(
    async () =>
      setPlans(
        (await api.plans(projectId))
          .filter((p) => p.intent_id === intent.id)
          .reverse(),
      ),
    [projectId, intent.id],
  );
  useEffect(() => {
    if (!active) return;
    let live = true;
    api
      .plans(projectId)
      .then((p) => {
        if (live)
          setPlans(p.filter((x) => x.intent_id === intent.id).reverse());
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [projectId, intent.id, intent.revision, active]);
  async function work(action: () => Promise<void>) {
    if (gate.current) return;
    gate.current = true;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await action();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      await load().catch(() => {});
    } finally {
      gate.current = false;
      setBusy(false);
    }
  }
  return (
    <section aria-label="Propuestas y ejecución" className="analysis-v2">
      <h3>4. Revisar propuesta, aprobar y ejecutar</h3>
      <p>
        La propuesta se explica antes de aprobarla. Aprobar y ejecutar son
        acciones separadas. Cada propuesta conserva su evidencia.
      </p>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <button
        disabled={busy || dirty}
        onClick={() =>
          void work(async () => {
            await api.propose(projectId, {
              intent_id: intent.id,
              intent_revision: intent.revision,
              dataset_id: intent.dataset_id,
              dataset_revision: intent.dataset_id ? 1 : null,
              diagnostic_ids: diagnostics
                .filter((d) => d.state === 'current')
                .slice(-20)
                .map((d) => d.id) as PlanRequest['diagnostic_ids'],
            });
            setConfirmed(null);
          })
        }
      >
        Solicitar nueva propuesta
      </button>
      <button
        className="rp-secondary"
        disabled={busy}
        onClick={() => void work(load)}
      >
        Actualizar propuestas
      </button>
      {dirty && (
        <p>Guarda la intención para proponer o aprobar su versión exacta.</p>
      )}
      {plans.map((p, index) => (
        <details key={p.id} open={index === 0} className="rp-surface">
          <summary>
            {techniqueLabels[p.technique ?? ''] ?? 'Requiere aclaraciones'} ·{' '}
            {p.validity === 'stale'
              ? 'Desactualizada'
              : p.status === 'approved'
                ? 'Aprobada'
                : p.status === 'proposed'
                  ? 'Propuesta'
                  : 'Pendiente'}{' '}
            · {new Date(p.created_at).toLocaleString()}
          </summary>
          <h4>{p.question}</h4>
          <p>Variables: {p.variable_names.join(', ') || 'por revisar'}.</p>
          <p>{p.rationale}</p>
          {p.case_counts && (
            <p>
              Casos: {p.case_counts.used} utilizados, {p.case_counts.excluded}{' '}
              excluidos, de {p.case_counts.total}.{' '}
              {p.case_counts.groups
                ?.map((g) => `${g.label}: ${g.count}`)
                .join(' · ')}{' '}
              {p.case_counts.pairs != null &&
                `Pares completos: ${p.case_counts.pairs}.`}
            </p>
          )}
          <p>
            Método: {p.parameters.calculation_method} ·{' '}
            {p.parameters.alternative === 'two-sided'
              ? 'bilateral'
              : 'dirección por revisar'}{' '}
            · alfa {p.parameters.alpha}. IC disponibles: 95 %.
          </p>
          <ul>
            {p.limitations.map((l, n) => (
              <li key={n}>{l}</li>
            ))}
          </ul>
          {p.pending_questions.length > 0 && (
            <ul>
              {p.pending_questions.map((q) => (
                <li key={q.code}>
                  {q.question}{' '}
                  <button
                    className="rp-link"
                    onClick={() =>
                      q.destination === 'analysis'
                        ? document
                            .getElementById('intent-review')
                            ?.scrollIntoView({ behavior: 'smooth' })
                        : q.destination === 'datasets' && p.dataset_id
                          ? navigateWorkspace(
                              projectId,
                              'datasets',
                              'review',
                              p.dataset_id,
                            )
                          : navigateProject(
                              projectId,
                              q.destination === 'instrument'
                                ? 'instrument'
                                : q.destination,
                            )
                    }
                  >
                    Responder en{' '}
                    {q.destination === 'datasets'
                      ? 'Datos'
                      : q.destination === 'context'
                        ? 'Contexto'
                        : q.destination === 'instrument'
                          ? 'Instrumento'
                          : 'esta intención'}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {p.validity === 'stale' && (
            <p className="rp-warning">
              {p.stale_reasons.join(' ')} Solicita otra propuesta; esta conserva
              su historial.
            </p>
          )}
          {p.validity === 'current' && p.status === 'proposed' && (
            <>
              {p.data_authorization_required && !p.data_authorized && (
                <div>
                  <p>
                    Estas fuentes no están declaradas como sintéticas. Confirma
                    que tienes autorización para su cálculo local; no se
                    enviarán a IA.
                  </p>
                  <button
                    disabled={busy || dirty}
                    onClick={() =>
                      void work(async () => {
                        await api.authorize(projectId, p);
                      })
                    }
                  >
                    Autorizar cálculo local de estas fuentes
                  </button>
                </div>
              )}
              <label>
                <input
                  type="checkbox"
                  checked={confirmed === p.id}
                  disabled={busy || dirty}
                  onChange={(e) => setConfirmed(e.target.checked ? p.id : null)}
                />
                He revisado pregunta, técnica, casos, método y limitaciones de
                esta propuesta exacta.
              </label>
              <button
                disabled={
                  busy ||
                  dirty ||
                  confirmed !== p.id ||
                  (p.data_authorization_required && !p.data_authorized)
                }
                onClick={() =>
                  void work(async () => {
                    await api.approve(projectId, p);
                    setConfirmed(null);
                    setMessage(
                      'Propuesta aprobada. Ejecutarla requiere otra acción.',
                    );
                  })
                }
              >
                Aprobar esta propuesta
              </button>
            </>
          )}
          {p.validity === 'current' &&
            p.status === 'approved' &&
            p.execution_status !== 'completed' && (
              <>
                <p>
                  {p.execution_status === 'running'
                    ? 'Cálculo en curso. Actualiza el estado para recuperar el resultado. Si se interrumpe, la reserva vence en dos minutos.'
                    : p.execution_status === 'failed'
                      ? 'El intento anterior falló o se interrumpió. Puedes iniciar un nuevo intento explícito.'
                      : 'La aprobación está guardada.'}
                </p>
                <button
                  disabled={busy || dirty || p.execution_status === 'running'}
                  onClick={() =>
                    void work(async () => {
                      const key = `s04b-attempt:${projectId}:${p.id}`;
                      const requestId =
                        p.execution_status === 'failed'
                          ? crypto.randomUUID()
                          : (sessionStorage.getItem(key) ??
                            crypto.randomUUID());
                      sessionStorage.setItem(key, requestId);
                      const result = await api.execute(projectId, p, requestId);
                      sessionStorage.removeItem(key);
                      setMessage(
                        result.status === 'completed'
                          ? `Resultado guardado (${result.validity === 'current' ? 'vigente' : 'histórico desactualizado'}).`
                          : 'El cálculo no terminó; consulta el resultado del intento.',
                      );
                    })
                  }
                >
                  {p.execution_status === 'failed'
                    ? 'Reintentar cálculo'
                    : 'Ejecutar propuesta aprobada'}
                </button>
              </>
            )}
          {p.execution_status === 'completed' && (
            <button onClick={() => navigateProject(projectId, 'results')}>
              Consultar resultado guardado
            </button>
          )}
        </details>
      ))}
    </section>
  );
}
