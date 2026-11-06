import { useEffect, useState } from 'react';
import { PersistedResultCharts } from '../../statistics/PersistedResultCharts';
import { AuthorizedScatterPlot } from '../../statistics/AuthorizedScatterPlot';
import { AuthorizedResidualPlot } from '../../statistics/AuthorizedResidualPlot';
import { AuthorizedGroupPlot } from '../../statistics/AuthorizedGroupPlot';
import { AuthorizedPairedPlot } from '../../statistics/AuthorizedPairedPlot';
import type { ResearchPackageSummary } from '../packages/api';
import { createAnalysisApi, type AnalysisRecord } from './api';

const api = createAnalysisApi();

export function ProjectAnalysis({
  projectId,
  researchPackage,
}: {
  projectId: string;
  researchPackage:
    | (Pick<ResearchPackageSummary, 'id' | 'hypotheses'> &
        Partial<Pick<ResearchPackageSummary, 'dataset'>>)
    | null;
}) {
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const realDataset =
    researchPackage?.dataset && !researchPackage.dataset.synthetic
      ? researchPackage.dataset
      : null;

  useEffect(() => {
    let cancelled = false;
    api
      .plans(projectId)
      .then((items) => {
        if (!cancelled) {
          setRecords(items);
          setReady(true);
        }
      })
      .catch((caught) => {
        if (!cancelled) setError(String(caught));
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, researchPackage?.id]);

  async function work(action: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    try {
      await action();
      setRecords(await api.plans(projectId));
      setReady(true);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo completar el análisis.',
      );
      // Invalidation and a completed network retry are reflected before another action.
      try {
        setRecords(await api.plans(projectId));
      } catch {
        setReady(false);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rp-analysis" aria-label="Análisis estadístico Research">
      <h3>Análisis estadístico</h3>
      <p>
        Revisa la técnica, su justificación y los supuestos antes de aprobar.
        Los datos sintéticos están disponibles de inmediato. Los datos reales
        requieren una autorización explícita, temporal y vinculada a este
        paquete vigente.
      </p>
      <p>
        Integración disponible: resumen descriptivo, Pearson y Spearman. Las
        demás técnicas requieren un adaptador de integración.
      </p>
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      {busy && <p role="status">Procesando análisis…</p>}
      <button
        className="rp-secondary"
        disabled={busy}
        onClick={() => void work(() => api.plans(projectId))}
      >
        Recargar análisis
      </button>
      {researchPackage && realDataset && (
        <aside className="rp-analysis-authorization">
          <p>
            Este dataset no es sintético. Autorízalo solo si confirmas que es
            adecuado para esta sesión local; la autorización se revoca al
            reiniciar el servidor o cambiar sus fuentes.
          </p>
          <button
            disabled={busy}
            onClick={() =>
              void work(() =>
                api.authorizeRealDataset(
                  projectId,
                  researchPackage.id,
                  realDataset.id,
                ),
              )
            }
          >
            Autorizar datos reales para esta sesión
          </button>
        </aside>
      )}
      {!researchPackage && (
        <p>
          Genera un paquete vigente para proponer análisis. Los resultados
          anteriores se conservan como históricos.
        </p>
      )}
      {[
        ...(researchPackage?.hypotheses ?? []),
        ...Array.from(
          new Set(records.map((record) => record.plan.hypothesis_id)),
        )
          .filter(
            (id) => !researchPackage?.hypotheses.some((item) => item.id === id),
          )
          .map((id) => ({
            id,
            statement: `Hipótesis histórica: ${id}`,
            variable_ids: [],
          })),
      ].map((hypothesis) => (
        <fieldset key={hypothesis.id}>
          <legend>{hypothesis.statement}</legend>
          {researchPackage?.hypotheses.some(
            (item) => item.id === hypothesis.id,
          ) && (
            <button
              disabled={busy || !ready}
              onClick={() =>
                void work(() =>
                  api.propose(projectId, researchPackage.id, hypothesis.id),
                )
              }
            >
              Proponer análisis
            </button>
          )}
          {records
            .filter((record) => record.plan.hypothesis_id === hypothesis.id)
            .reverse()
            .map((record) => {
              const stale =
                !!record.invalidated_at ||
                record.plan.research_package_id !== researchPackage?.id;
              return (
                <article
                  key={record.plan.id}
                  aria-label={`Plan ${record.plan.id}`}
                >
                  <p>
                    Plan: {record.plan.id} · Estado: {record.plan.status}
                  </p>
                  <p>
                    Técnica recomendada:{' '}
                    {record.plan.technique ?? 'Por aclarar'}
                  </p>
                  <p>Justificación: {record.plan.rationale}</p>
                  <h4>Supuestos que deben comprobarse</h4>
                  {record.plan.assumptions_to_check?.length ? (
                    <ul>
                      {record.plan.assumptions_to_check.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>
                      Sin supuestos adicionales declarados por el planificador.
                    </p>
                  )}
                  {record.plan.pending_questions?.map((item) => (
                    <p key={item}>Aclaración: {item}</p>
                  ))}
                  {record.limitation && <p>{record.limitation}</p>}
                  {stale && (
                    <p className="rp-error">
                      Plan desactualizado:{' '}
                      {record.stale_reason ?? 'El paquete cambió'}. Genera una
                      nueva propuesta.
                    </p>
                  )}
                  {record.plan.status === 'proposed' &&
                    record.executable &&
                    !stale && (
                      <button
                        disabled={busy || !ready}
                        onClick={() =>
                          void work(() => api.approve(projectId, record))
                        }
                      >
                        Aprobar análisis
                      </button>
                    )}
                  {record.approved_at && !stale && (
                    <p>Aprobación explícita: {record.approved_at}</p>
                  )}
                  {record.plan.status === 'approved' &&
                    !stale &&
                    !record.result && (
                      <button
                        disabled={busy || !ready}
                        onClick={() =>
                          void work(() =>
                            api.execute(projectId, record.plan.id),
                          )
                        }
                      >
                        Ejecutar análisis
                      </button>
                    )}
                  {record.result && (
                    <div aria-label="Resultado estadístico">
                      <p>
                        Resultado: {record.result.status}
                        {stale ? ' · histórico, fuentes desactualizadas' : ''}
                      </p>
                      {record.result.interpretation && (
                        <p>{record.result.interpretation}</p>
                      )}
                      {!!record.result.metrics?.length && (
                        <>
                          <table>
                            <caption>
                              Métricas calculadas sobre el dataset Research
                            </caption>
                            <thead>
                              <tr>
                                <th scope="col">Métrica</th>
                                <th scope="col">Valor</th>
                              </tr>
                            </thead>
                            <tbody>
                              {record.result.metrics.map((metric) => (
                                <tr key={metric.name}>
                                  <th scope="row">{metric.name}</th>
                                  <td>{metric.value}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          <PersistedResultCharts
                            metrics={record.result.metrics}
                          />
                          {!stale &&
                            ['pearson', 'spearman'].includes(
                              record.plan.technique ?? '',
                            ) && (
                              <AuthorizedScatterPlot
                                load={() => api.scatter(projectId, record)}
                              />
                            )}
                          {!stale &&
                            ['t_paired', 'wilcoxon'].includes(
                              record.plan.technique ?? '',
                            ) && (
                              <AuthorizedPairedPlot
                                load={() => api.pairs(projectId, record)}
                              />
                            )}
                          {!stale &&
                            [
                              'linear_regression_simple',
                              'linear_regression_multiple',
                              'ancova',
                            ].includes(record.plan.technique ?? '') && (
                              <AuthorizedResidualPlot
                                load={() => api.residuals(projectId, record)}
                              />
                            )}
                          {!stale &&
                            [
                              't_independent',
                              't_welch',
                              'mann_whitney',
                              'anova',
                              'anova_welch',
                              'kruskal_wallis',
                              'tukey',
                              'games_howell',
                            ].includes(record.plan.technique ?? '') && (
                              <AuthorizedGroupPlot
                                load={() => api.groups(projectId, record)}
                              />
                            )}
                        </>
                      )}
                      {record.result.assumptions?.map((item) => (
                        <p key={item.name}>
                          Comprobación {item.name}: {item.status}.{' '}
                          {item.details}
                        </p>
                      ))}
                      {record.result.warnings?.map((item) => (
                        <p key={item}>Advertencia: {item}</p>
                      ))}
                      {record.result.status === 'completed' && (
                        <>
                          <div className="rp-actions">
                            {(['docx', 'pdf'] as const).map((format) => (
                              <button
                                key={format}
                                disabled={busy || !ready || stale}
                                onClick={() =>
                                  void work(() =>
                                    api.download(projectId, record, format),
                                  )
                                }
                              >
                                Descargar {format.toUpperCase()}
                              </button>
                            ))}
                          </div>
                          <p className="rp-hint">
                            PDF de texto paginado con caracteres españoles. Para
                            caracteres fuera de WinAnsi utiliza DOCX. Las
                            descargas usan el resultado almacenado; no repiten
                            el cálculo.
                          </p>
                          {stale && (
                            <p>
                              La exportación está bloqueada porque las fuentes
                              cambiaron. Genera y aprueba un nuevo análisis.
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </article>
              );
            })}
        </fieldset>
      ))}
    </section>
  );
}
