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
  return (
    <section className="rp-result-detail" aria-label="Resultado estadístico">
      <p>
        Resultado:{' '}
        {record.result.status === 'completed'
          ? 'Completado'
          : record.result.status === 'failed'
            ? 'Fallido'
            : record.result.status}
        {stale ? ' · histórico, fuentes desactualizadas o sin verificar' : ''}
      </p>
      {record.result.interpretation && <p>{record.result.interpretation}</p>}
      {!!record.result.metrics?.length && (
        <>
          <table>
            <caption>Métricas calculadas sobre el dataset Research</caption>
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
          <PersistedResultCharts metrics={record.result.metrics} />
          {!stale &&
            record.result.status === 'completed' &&
            ['pearson', 'spearman'].includes(record.plan.technique ?? '') && (
              <AuthorizedScatterPlot
                load={() => api.scatter(projectId, record)}
              />
            )}
          {!stale &&
            record.result.status === 'completed' &&
            ['t_paired', 'wilcoxon'].includes(record.plan.technique ?? '') && (
              <AuthorizedPairedPlot load={() => api.pairs(projectId, record)} />
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
              <AuthorizedGroupPlot load={() => api.groups(projectId, record)} />
            )}
        </>
      )}
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
    </section>
  );
}
