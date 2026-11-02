import { useState } from 'react';
import {
  createResearchStatisticsApi,
  type RuntimeHypothesis,
  type RuntimePlan,
  type RuntimeResult,
} from './researchStatisticsApi';

export function ResearchStatisticsPanel({
  projectId,
  packageId,
  hypotheses,
  api = createResearchStatisticsApi(),
}: {
  projectId: string;
  packageId: string;
  hypotheses: RuntimeHypothesis[];
  api?: ReturnType<typeof createResearchStatisticsApi>;
}) {
  const [hypothesisId, setHypothesisId] = useState(hypotheses[0]?.id ?? '');
  const [plan, setPlan] = useState<RuntimePlan | null>(null);
  const [result, setResult] = useState<RuntimeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Error desconocido');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Statistics sobre paquete Research">
      <h2>Statistics</h2>
      <p>Planifica y ejecuta el análisis sobre el paquete vigente.</p>
      {error && <p role="alert">{error}</p>}
      <label>
        Hipótesis
        <select
          value={hypothesisId}
          onChange={(event) => setHypothesisId(event.target.value)}
          disabled={busy}
        >
          {hypotheses.map((hypothesis) => (
            <option key={hypothesis.id} value={hypothesis.id}>
              {hypothesis.statement}
            </option>
          ))}
        </select>
      </label>
      <div>
        <button
          type="button"
          disabled={busy || !hypothesisId}
          onClick={() =>
            run(async () =>
              setPlan(await api.plan(projectId, packageId, hypothesisId)),
            )
          }
        >
          {busy ? 'Procesando…' : 'Proponer plan'}
        </button>
        <button
          type="button"
          disabled={busy || !hypothesisId}
          onClick={() =>
            run(async () =>
              setResult(await api.execute(projectId, packageId, hypothesisId)),
            )
          }
        >
          Ejecutar descriptivos
        </button>
      </div>
      {plan && (
        <article aria-label="Plan Statistics">
          <strong>{plan.technique ?? 'Requiere aclaración'}</strong> ·{' '}
          {plan.status}
          <p>{plan.rationale}</p>
          {plan.pending_questions.map((question) => (
            <p key={question}>{question}</p>
          ))}
        </article>
      )}
      {result && (
        <article aria-label="Resultado Statistics">
          <strong>{result.status}</strong>
          <p>{result.interpretation}</p>
          {result.metrics.map((metric) => (
            <p key={metric.name}>
              {metric.name}: {metric.value}
            </p>
          ))}
          {result.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </article>
      )}
    </section>
  );
}
