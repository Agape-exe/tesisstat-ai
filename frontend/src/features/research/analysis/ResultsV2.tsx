import { useCallback } from 'react';
import { useReadResource } from '../projects/useReadResource';
import { createAnalysisV2Api, techniqueLabels } from './v2api';
const api = createAnalysisV2Api();
function number(value: number | null, key: string) {
  if (value === null) return 'No calculable';
  if (key === 'p_value' && value === 0) return '< límite de precisión';
  return new Intl.NumberFormat('es-PE', { maximumSignificantDigits: 7 }).format(
    value,
  );
}
export function ResultsV2({
  projectId,
  active,
}: {
  projectId: string;
  active: boolean;
}) {
  const load = useCallback(() => api.results(projectId), [projectId]);
  const resource = useReadResource(load, active);
  return (
    <section aria-label="Resultados por análisis" className="analysis-v2">
      <h3>Resultados por análisis</h3>
      <button
        className="rp-secondary"
        disabled={resource.loading}
        onClick={resource.reload}
      >
        Actualizar resultados por análisis
      </button>
      {resource.error && (
        <p role="alert">No se pudieron consultar los resultados guardados.</p>
      )}
      {resource.loading && <p role="status">Consultando resultados…</p>}
      {!resource.loading && !resource.error && !resource.data?.length && (
        <p>
          Todavía no hay resultados v2. Solicita, aprueba y ejecuta una
          propuesta en Análisis.
        </p>
      )}
      {[...(resource.data ?? [])].reverse().map((r) => (
        <details key={r.id} className="rp-surface" open>
          <summary>
            {r.question} ·{' '}
            {r.validity === 'current' ? 'Vigente' : 'Histórico desactualizado'}{' '}
            · {r.status === 'completed' ? 'Completado' : 'Fallido'}
          </summary>
          <h4>{techniqueLabels[r.technique] ?? r.technique}</h4>
          <p>Variables: {r.variable_names.join(', ')}.</p>
          <p>
            {r.case_counts.used} casos utilizados y {r.case_counts.excluded}{' '}
            excluidos de {r.case_counts.total}.{' '}
            {r.case_counts.groups
              ?.map((g) => `${g.label}: ${g.count}`)
              .join(' · ')}{' '}
            {r.case_counts.pairs != null && `Pares: ${r.case_counts.pairs}.`}
          </p>
          {r.validity === 'stale' && (
            <p className="rp-warning">
              {r.stale_reasons.join(' ')} Se conserva la salida histórica; no
              acredita vigencia.
            </p>
          )}
          {r.metrics.length > 0 && (
            <div className="analysis-table-scroll">
              <table>
                <caption>Resultados numéricos guardados</caption>
                <thead>
                  <tr>
                    <th>Métrica</th>
                    <th>Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {r.metrics.map((m) => (
                    <tr key={m.key}>
                      <th scope="row">{m.label}</th>
                      <td>
                        {number(m.value, m.key)}
                        {m.reason && ` · ${m.reason}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {r.tables.map((t) => (
            <div className="analysis-table-scroll" key={t.id}>
              <table>
                <caption>{t.title}</caption>
                <thead>
                  <tr>
                    {t.columns.map((c) => (
                      <th key={c.key}>{c.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {t.rows.map((row, n) => (
                    <tr key={n}>
                      {t.columns.map((c) => (
                        <td key={c.key}>
                          {typeof row[c.key] === 'number'
                            ? number(row[c.key] as number, c.key)
                            : String(row[c.key] ?? 'No disponible')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          {r.interpretation && <p>{r.interpretation.text}</p>}
          <ul>
            {[...r.warnings, ...r.limitations].map((w, n) => (
              <li key={n}>{w}</li>
            ))}
          </ul>
          <details>
            <summary>Método y referencias</summary>
            <p>
              {r.engine_version} · {r.method_version}
            </p>
            <p>
              Plan: {r.analysis_plan_id}. Resultado: {r.id}.
            </p>
            <p>{new Date(r.created_at).toLocaleString()}</p>
          </details>
        </details>
      ))}
    </section>
  );
}
