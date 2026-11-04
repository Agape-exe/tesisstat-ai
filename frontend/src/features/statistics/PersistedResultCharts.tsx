import type { Metric } from '../../shared/contracts/generated/AnalysisResult';
import './persisted-result-charts.css';

type CategoryBar = { label: string; count: number; percentage: number | null };
type Interval = { label: string; low: number; high: number };
type Estimate = { label: string; value: number };

const boundedAssociationMetrics = new Set([
  'r',
  'rho',
  'r_squared',
  'eta_squared',
  'omega_squared',
  'cramers_v',
  'rank_biserial_effect',
  'rank_effect',
  'epsilon_squared',
]);

const format = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 3 });

function categoryBars(metrics: Metric[]): CategoryBar[] {
  const values = new Map<string, CategoryBar>();
  for (const metric of metrics) {
    const match = /^(.*)\.category\.(.*)\.(count|percentage)$/.exec(
      metric.name,
    );
    if (!match) continue;
    const [, column, category, kind] = match;
    const key = `${column}\u0000${category}`;
    const current = values.get(key) ?? {
      label: `${column}: ${category}`,
      count: 0,
      percentage: null,
    };
    if (kind === 'count') current.count = metric.value;
    else current.percentage = metric.value;
    values.set(key, current);
  }
  return [...values.values()].filter(
    (item) => item.percentage !== null || item.count > 0,
  );
}

function intervals(metrics: Metric[]): Interval[] {
  const values = new Map<string, { low?: number; high?: number }>();
  for (const metric of metrics) {
    const match = /^(.*)_ci_95_(low|high)$/.exec(metric.name);
    if (!match) continue;
    const [, label, bound] = match;
    values.set(label, { ...values.get(label), [bound]: metric.value });
  }
  return [...values.entries()]
    .filter(
      ([, interval]) =>
        interval.low !== undefined && interval.high !== undefined,
    )
    .map(([label, interval]) => ({
      label,
      low: interval.low as number,
      high: interval.high as number,
    }));
}

function estimates(metrics: Metric[]): Estimate[] {
  return metrics
    .filter(
      (metric) =>
        metric.name.endsWith('.mean_difference') ||
        /^group_.+_effect$/.test(metric.name) ||
        /^(slope|beta_\d+|covariate_beta)$/.test(metric.name),
    )
    .map((metric) => ({ label: metric.name, value: metric.value }));
}

function CategoryChart({ items }: { items: CategoryBar[] }) {
  const maximum = Math.max(
    ...items.map((item) => item.percentage ?? item.count),
    1,
  );
  return (
    <figure
      className="persisted-chart"
      aria-label="Frecuencias categóricas persistidas"
    >
      <figcaption>Frecuencias categóricas calculadas</figcaption>
      {items.map((item) => {
        const magnitude = item.percentage ?? item.count;
        return (
          <div className="persisted-frequency" key={item.label}>
            <span>{item.label}</span>
            <i style={{ width: `${(magnitude / maximum) * 100}%` }} />
            <small>
              {format.format(item.count)}
              {item.percentage === null
                ? ''
                : ` (${format.format(item.percentage)}%)`}
            </small>
          </div>
        );
      })}
    </figure>
  );
}

function AssociationChart({ metrics }: { metrics: Metric[] }) {
  const items = metrics.filter((metric) =>
    boundedAssociationMetrics.has(metric.name),
  );
  if (!items.length) return null;
  return (
    <figure
      className="persisted-chart"
      aria-label="Magnitudes de asociación persistidas"
    >
      <figcaption>Magnitud de asociación o efecto</figcaption>
      {items.map((metric) => {
        const value = Math.max(-1, Math.min(1, metric.value));
        return (
          <div className="persisted-scale" key={metric.name}>
            <span>{metric.name}</span>
            <div aria-label={`${metric.name}: ${format.format(metric.value)}`}>
              <i style={{ left: `${(value + 1) * 50}%` }} />
            </div>
            <small>{format.format(metric.value)}</small>
          </div>
        );
      })}
    </figure>
  );
}

function IntervalChart({ items }: { items: Interval[] }) {
  if (!items.length) return null;
  const bounds = items.flatMap((item) => [item.low, item.high]);
  const minimum = Math.min(...bounds);
  const maximum = Math.max(...bounds);
  const range = maximum - minimum || 1;
  return (
    <figure
      className="persisted-chart"
      aria-label="Intervalos de confianza persistidos"
    >
      <figcaption>Intervalos de confianza al 95 %</figcaption>
      {items.map((item) => (
        <div className="persisted-interval" key={item.label}>
          <span>{item.label}</span>
          <div
            aria-label={`${item.label}: ${format.format(item.low)} a ${format.format(item.high)}`}
          >
            <i
              style={{
                left: `${((item.low - minimum) / range) * 100}%`,
                width: `${((item.high - item.low) / range) * 100}%`,
              }}
            />
          </div>
          <small>
            {format.format(item.low)} a {format.format(item.high)}
          </small>
        </div>
      ))}
    </figure>
  );
}

function EstimateChart({ items }: { items: Estimate[] }) {
  if (!items.length) return null;
  const maximum = Math.max(...items.map((item) => Math.abs(item.value)), 1);
  return (
    <figure
      className="persisted-chart"
      aria-label="Estimaciones persistidas de modelos y comparaciones"
    >
      <figcaption>Estimaciones de modelo y diferencias entre grupos</figcaption>
      {items.map((item) => {
        const width = (Math.abs(item.value) / maximum) * 50;
        const left = item.value < 0 ? 50 - width : 50;
        return (
          <div className="persisted-estimate" key={item.label}>
            <span>{item.label}</span>
            <div aria-label={`${item.label}: ${format.format(item.value)}`}>
              <i style={{ left: `${left}%`, width: `${width}%` }} />
            </div>
            <small>{format.format(item.value)}</small>
          </div>
        );
      })}
    </figure>
  );
}

export function PersistedResultCharts({ metrics }: { metrics: Metric[] }) {
  const categories = categoryBars(metrics);
  const confidenceIntervals = intervals(metrics);
  const associations = metrics.filter((metric) =>
    boundedAssociationMetrics.has(metric.name),
  );
  const modelEstimates = estimates(metrics);
  if (
    !categories.length &&
    !confidenceIntervals.length &&
    !associations.length &&
    !modelEstimates.length
  ) {
    return (
      <p className="persisted-chart-empty">
        Este resultado persistido no incluye métricas aptas para una
        visualización válida.
      </p>
    );
  }
  return (
    <section
      className="persisted-charts"
      aria-label="Gráficos de resultados persistidos"
    >
      <h5>Gráficos de resultados persistidos</h5>
      {categories.length > 0 && <CategoryChart items={categories} />}
      <AssociationChart metrics={metrics} />
      <IntervalChart items={confidenceIntervals} />
      <EstimateChart items={modelEstimates} />
    </section>
  );
}
