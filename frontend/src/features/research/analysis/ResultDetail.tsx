import { SectionColumns, SupportPanel } from '../projects/SectionLayout';
import { metricLabel, metricValue } from './analysisPresentation';
import { PersistedResultCharts } from '../../statistics/PersistedResultCharts';
import { AuthorizedScatterPlot } from '../../statistics/AuthorizedScatterPlot';
import { AuthorizedResidualPlot } from '../../statistics/AuthorizedResidualPlot';
import { AuthorizedGroupPlot } from '../../statistics/AuthorizedGroupPlot';
import { AuthorizedPairedPlot } from '../../statistics/AuthorizedPairedPlot';
import { createAnalysisApi, type AnalysisRecord } from './api';
const api = createAnalysisApi();
const assumptionNames: Record<string, string> = {
  normality: 'Normalidad',
  independence: 'Independencia',
  descriptive_input_validation: 'Validación de datos',
  linearity: 'Linealidad',
  homoscedasticity: 'Homogeneidad de varianzas',
};
const assumptionStates: Record<string, string> = {
  passed: 'Comprobado',
  failed: 'No cumplido',
  not_checked: 'Pendiente de comprobación',
  warning: 'Requiere revisión',
};
export function ResultDetail({
  projectId,
  record,
  current,
}: {
  projectId: string;
  record: AnalysisRecord;
  current: boolean;
}) {
  if (!record.result) return null;
  const stale = !current;
  const metrics = record.result.metrics ?? [];
  const featured = metrics
    .filter((m) =>
      ['n', 'r', 'rho', 'p_value', 'statistic', 'r_squared'].includes(m.name),
    )
    .slice(0, 3);
  const summary = featured.length ? featured : metrics.slice(0, 3);
  return (
    <section className="rp-result-detail" aria-label="Resultado estadístico">
      <p className="rp-sr-only">
        Resultado:{' '}
        {record.result.status === 'completed'
          ? 'Completado'
          : record.result.status === 'failed'
            ? 'Fallido'
            : record.result.status}
        {stale ? ' · histórico, fuentes desactualizadas o sin verificar' : ''}
      </p>

      {!!record.result.metrics?.length && (
        <>
          <dl
            className="rp-metric-grid"
            aria-label="Métricas calculadas sobre el dataset Research"
          >
            {summary.map((metric) => (
              <div key={metric.name} title={`${metric.name}: ${metric.value}`}>
                <dd>{metricValue(metric.name, metric.value)}</dd>
                <dt>{metricLabel(metric.name)}</dt>
              </div>
            ))}
          </dl>
          {record.result.metrics.some(
            (m) => /(^|_)p_value($|_)/.test(m.name) && m.value === 0,
          ) && (
            <p className="rp-warning">
              El valor p está registrado como 0 por precisión numérica. No
              representa una probabilidad matemáticamente nula. El valor
              original se conserva en los detalles.
            </p>
          )}
        </>
      )}
      <SectionColumns
        support={
          <SupportPanel
            title="Cómo leer los resultados"
            projectId={projectId}
            destination="reports"
            action="Ver Informes"
          >
            <h4>Interpretación registrada</h4>
            <p>
              {record.result.interpretation ||
                'No hay una interpretación registrada para este resultado.'}
            </p>
            <p className="rp-hint">
              Revisa la técnica ejecutada, el diseño y sus supuestos antes de
              formular conclusiones. Una asociación por sí sola no demuestra
              causalidad.
            </p>
          </SupportPanel>
        }
      >
        <div className="rp-surface rp-result-figures">
          {!!record.result.metrics?.length && (
            <>
              {!stale &&
                record.result.status === 'completed' &&
                ['pearson', 'spearman'].includes(
                  record.plan.technique ?? '',
                ) && (
                  <AuthorizedScatterPlot
                    load={() => api.scatter(projectId, record)}
                  />
                )}
              {!stale &&
                record.result.status === 'completed' &&
                ['t_paired', 'wilcoxon'].includes(
                  record.plan.technique ?? '',
                ) && (
                  <AuthorizedPairedPlot
                    load={() => api.pairs(projectId, record)}
                  />
                )}
              {!stale &&
                record.result.status === 'completed' &&
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
                record.result.status === 'completed' &&
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
          {!!record.result.metrics?.length &&
            (['pearson', 'spearman'].includes(record.plan.technique ?? '') ? (
              <details className="rp-technical">
                <summary>Gráficos de métricas guardadas</summary>
                <PersistedResultCharts metrics={record.result.metrics} />
              </details>
            ) : (
              <PersistedResultCharts metrics={record.result.metrics} />
            ))}
          <h3>Supuestos y comprobaciones</h3>
          {record.result.assumptions?.map((item) => (
            <p key={item.name}>
              Comprobación {assumptionNames[item.name] ?? item.name}:{' '}
              {assumptionStates[item.status] ?? item.status}. {item.details}
            </p>
          ))}
          {record.result.warnings?.map((item) => (
            <p className="rp-warning" key={item}>
              Advertencia: {item}
            </p>
          ))}
        </div>
      </SectionColumns>
      {!!metrics.length && (
        <details className="rp-technical">
          <summary>Valores originales y precisión</summary>
          <table>
            <caption>Métricas sin redondear</caption>
            <thead>
              <tr>
                <th>Métrica</th>
                <th>Valor registrado</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr key={m.name}>
                  <th>{m.name}</th>
                  <td>{String(m.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </section>
  );
}
