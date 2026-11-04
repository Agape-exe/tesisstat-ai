import type { Metric } from '../../shared/contracts/generated/AnalysisResult';
import './persisted-result-charts.css';
import {
  buildPersistedResultChartData,
  type CategoryBar,
  type Completeness,
  type ConfidenceInterval,
  type Estimate,
  type PValue,
} from './resultChartData';

const format = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 3 });

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

function AssociationChart({ items }: { items: Metric[] }) {
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

function IntervalChart({ items }: { items: ConfidenceInterval[] }) {
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

function PValueChart({ items }: { items: PValue[] }) {
  if (!items.length) return null;
  const alpha = 0.05;
  return (
    <figure className="persisted-chart" aria-label="P-valores persistidos">
      <figcaption>P-valores reportados (referencia α = 0.05)</figcaption>
      {items.map((item) => (
        <div className="persisted-p-value" key={item.label}>
          <span>{item.label}</span>
          <div aria-label={`${item.label}: ${format.format(item.value)}`}>
            <i style={{ left: `${item.value * 100}%` }} />
            <b style={{ left: `${alpha * 100}%` }} title="alfa 0.05" />
          </div>
          <small>{format.format(item.value)}</small>
        </div>
      ))}
      <p className="persisted-chart-note">
        Referencia visual solamente; no determina significancia ni sustituye la
        revisión metodológica.
      </p>
    </figure>
  );
}

function CompletenessChart({ items }: { items: Completeness[] }) {
  if (!items.length) return null;
  return (
    <figure
      className="persisted-chart"
      aria-label="Calidad de datos persistida"
    >
      <figcaption>Registros válidos y faltantes</figcaption>
      {items.map((item) => {
        const total = item.valid + item.missing;
        const validWidth = total === 0 ? 0 : (item.valid / total) * 100;
        return (
          <div className="persisted-completeness" key={item.label}>
            <span>{item.label}</span>
            <div
              aria-label={`${item.label}: ${item.valid} válidos, ${item.missing} faltantes`}
            >
              <i style={{ width: `${validWidth}%` }} />
            </div>
            <small>
              {format.format(item.valid)} válidos ·{' '}
              {format.format(item.missing)} faltantes
            </small>
          </div>
        );
      })}
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
  const data = buildPersistedResultChartData(metrics);
  if (
    !data.categories.length &&
    !data.confidenceIntervals.length &&
    !data.associations.length &&
    !data.estimates.length &&
    !data.pValues.length &&
    !data.completeness.length
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
      {data.categories.length > 0 && <CategoryChart items={data.categories} />}
      <AssociationChart items={data.associations} />
      <IntervalChart items={data.confidenceIntervals} />
      <EstimateChart items={data.estimates} />
      <PValueChart items={data.pValues} />
      <CompletenessChart items={data.completeness} />
    </section>
  );
}
