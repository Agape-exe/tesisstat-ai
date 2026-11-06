import { useEffect, useMemo, useState } from 'react';
import {
  createDescriptiveApi,
  type DescriptiveApi,
  type AnalysisPlan,
  type AnalysisResult,
  type DescriptiveResult,
  type ReportFormat,
} from './descriptiveApi';
import './descriptive-demo.css';

const number = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 3 });
const defaultApi = createDescriptiveApi();

function value(input: number | null) {
  return input === null ? '—' : number.format(input);
}

function NumericChart({ result }: { result: DescriptiveResult }) {
  const summary = result.numeric;
  if (
    !summary?.quantiles ||
    summary.minimum === null ||
    summary.maximum === null
  )
    return null;
  const { p0, p25, p50, p75, p100 } = summary.quantiles;
  const range = p100 - p0 || 1;
  const position = (item: number) => `${((item - p0) / range) * 100}%`;
  return (
    <figure
      className="descriptive-chart"
      aria-label={`Resumen de cuantiles de ${result.column}`}
    >
      <figcaption>{result.column}: mínimo, cuartiles y máximo</figcaption>
      <div className="boxplot" aria-hidden="true">
        <i
          style={{
            left: position(p0),
            width: `${((p100 - p0) / range) * 100}%`,
          }}
        />
        <b
          style={{
            left: position(p25),
            width: `${((p75 - p25) / range) * 100}%`,
          }}
        />
        <em style={{ left: position(p50) }} />
      </div>
      <small>
        {value(p0)} · {value(p25)} · {value(p50)} · {value(p75)} · {value(p100)}
      </small>
    </figure>
  );
}

function CategoricalChart({ result }: { result: DescriptiveResult }) {
  if (!result.categorical) return null;
  return (
    <figure
      className="descriptive-chart"
      aria-label={`Frecuencias de ${result.column}`}
    >
      <figcaption>{result.column}: frecuencias</figcaption>
      {result.categorical.frequencies.map((frequency) => (
        <div className="frequency-bar" key={frequency.value}>
          <span>{frequency.value}</span>
          <i style={{ width: `${frequency.percentage}%` }} />
          <small>
            {frequency.count} ({number.format(frequency.percentage)}%)
          </small>
        </div>
      ))}
    </figure>
  );
}

export function DescriptiveDemo({
  api = defaultApi,
}: {
  api?: DescriptiveApi;
}) {
  const [datasets, setDatasets] = useState<
    Awaited<ReturnType<DescriptiveApi['getDatasets']>>
  >([]);
  const [datasetId, setDatasetId] = useState('');
  const [columns, setColumns] = useState<
    Awaited<ReturnType<DescriptiveApi['getColumns']>>
  >([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [results, setResults] = useState<DescriptiveResult[]>([]);
  const [plan, setPlan] = useState<AnalysisPlan | null>(null);
  const [execution, setExecution] = useState<AnalysisResult | null>(null);
  const [state, setState] = useState<
    'loading' | 'ready' | 'error' | 'analyzing'
  >('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    api
      .getDatasets()
      .then((items) => {
        setDatasets(items);
        setDatasetId(items[0]?.id ?? '');
        setMessage('');
        setState('ready');
      })
      .catch((error: unknown) => {
        setMessage(
          error instanceof Error ? error.message : 'Error desconocido',
        );
        setState('error');
      });
  }, [api]);

  useEffect(() => {
    if (!datasetId) return;
    api
      .getColumns(datasetId)
      .then((items) => {
        setColumns(items);
        setSelected(
          items
            .filter((item) => item.kind !== 'identifier')
            .map((item) => item.name),
        );
        setMessage('');
        setState('ready');
      })
      .catch((error: unknown) => {
        setMessage(
          error instanceof Error ? error.message : 'Error desconocido',
        );
        setState('error');
      });
  }, [api, datasetId]);

  const selectable = useMemo(
    () => columns.filter((column) => column.kind !== 'identifier'),
    [columns],
  );
  async function analyze() {
    if (!selected.length) {
      setMessage('Selecciona al menos una variable no identificadora.');
      return;
    }
    setState('analyzing');
    setMessage('');
    try {
      const [descriptive, nextPlan, nextExecution] = await Promise.all([
        api.describe(datasetId, selected),
        api.getPlan ? api.getPlan(datasetId) : Promise.resolve(null),
        api.execute ? api.execute(datasetId) : Promise.resolve(null),
      ]);
      setResults(descriptive);
      setPlan(nextPlan);
      setExecution(nextExecution);
      setState('ready');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Error desconocido');
      setState('error');
    }
  }
  async function downloadReport(format: ReportFormat) {
    if (!api.getReport) return;
    try {
      const blob = await api.getReport(datasetId, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${datasetId}-report.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Error desconocido');
    }
  }
  return (
    <main className="descriptive-demo">
      <p className="eyebrow">TESISSTAT AI · DEMOSTRACIÓN</p>
      <h1>Análisis descriptivo</h1>
      <p>
        Motor determinista: media, mediana, moda, dispersión, cuantiles y
        frecuencias.
      </p>
      {state === 'error' && (
        <p className="demo-error" role="alert">
          {message}
        </p>
      )}
      <label>
        Dataset de prueba
        <select
          value={datasetId}
          onChange={(event) => {
            setState('loading');
            setResults([]);
            setDatasetId(event.target.value);
          }}
          disabled={state === 'loading'}
        >
          {datasets.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <section aria-label="Columnas disponibles">
        <h2>Variables</h2>
        {state === 'loading' ? (
          <p role="status">Cargando columnas…</p>
        ) : (
          <div className="column-picker">
            {columns.map((column) => (
              <label key={column.name}>
                <input
                  type="checkbox"
                  checked={selected.includes(column.name)}
                  disabled={column.kind === 'identifier'}
                  onChange={() =>
                    setSelected((current) =>
                      current.includes(column.name)
                        ? current.filter((name) => name !== column.name)
                        : [...current, column.name],
                    )
                  }
                />
                {column.name}{' '}
                <small>
                  ({column.kind}; válidos {column.valid_count}, faltantes{' '}
                  {column.missing_count})
                </small>
              </label>
            ))}
          </div>
        )}
      </section>
      <button
        onClick={analyze}
        disabled={
          state === 'loading' || state === 'analyzing' || !selectable.length
        }
      >
        {state === 'analyzing' ? 'Calculando…' : 'Calcular descriptivos'}
      </button>
      {message && state !== 'error' && (
        <p className="demo-error" role="alert">
          {message}
        </p>
      )}
      {results.length > 0 && (
        <section>
          <h2>Resultados</h2>
          <div className="result-grid">
            {results.map((result) => (
              <article key={result.column}>
                <h3>{result.column}</h3>
                {result.numeric ? (
                  <>
                    <table>
                      <tbody>
                        {[
                          ['Válidos', result.numeric.valid_count],
                          ['Faltantes', result.numeric.missing_count],
                          ['Media', value(result.numeric.mean)],
                          ['Mediana', value(result.numeric.median)],
                          [
                            'Moda',
                            result.numeric.modes.length
                              ? result.numeric.modes
                                  .map((item) => value(item))
                                  .join(', ')
                              : 'Sin moda',
                          ],
                          ['Mínimo', value(result.numeric.minimum)],
                          ['Máximo', value(result.numeric.maximum)],
                          [
                            'Desv. estándar muestral',
                            value(result.numeric.sample_standard_deviation),
                          ],
                          [
                            'Varianza muestral',
                            value(result.numeric.sample_variance),
                          ],
                        ].map(([label, metric]) => (
                          <tr key={label as string}>
                            <th>{label}</th>
                            <td>{metric}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <NumericChart result={result} />
                  </>
                ) : (
                  <>
                    <p>
                      Válidos: {result.categorical?.valid_count} · Faltantes:{' '}
                      {result.categorical?.missing_count}
                    </p>
                    <CategoricalChart result={result} />
                  </>
                )}
                {[
                  ...(result.numeric?.warnings ?? []),
                  ...(result.categorical?.warnings ?? []),
                ].map((warning) => (
                  <p className="warning" key={warning}>
                    {warning}
                  </p>
                ))}
              </article>
            ))}
          </div>
        </section>
      )}
      {plan && (
        <section className="analysis-plan" aria-label="Plan estadístico">
          <h2>Plan estadístico</h2>
          <p>
            <strong>{plan.technique ?? 'Pendiente de aclaración'}</strong> ·{' '}
            estado: {plan.status}
          </p>
          <p>{plan.rationale}</p>
          {plan.assumptions_to_check.length > 0 && (
            <p>Supuestos a comprobar: {plan.assumptions_to_check.join(', ')}</p>
          )}
        </section>
      )}
      {execution && (
        <section className="analysis-result" aria-label="Resultado del motor">
          <h2>Resultado del motor</h2>
          <p>{execution.interpretation ?? `Estado: ${execution.status}`}</p>
          {execution.metrics.length > 0 && (
            <table>
              <tbody>
                {execution.metrics.map((metric) => (
                  <tr key={metric.name}>
                    <th>{metric.name}</th>
                    <td>{value(metric.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {execution.assumptions.map((assumption) => (
            <p className="assumption" key={assumption.name}>
              {assumption.name}: {assumption.status} — {assumption.details}
            </p>
          ))}
          {execution.warnings.map((warning) => (
            <p className="warning" key={warning}>
              {warning}
            </p>
          ))}
          {api.getReport && execution.status === 'completed' && (
            <div className="report-actions" aria-label="Exportar reporte">
              <span>Exportar:</span>
              {(['txt', 'docx', 'pdf'] as ReportFormat[]).map((format) => (
                <button
                  key={format}
                  type="button"
                  onClick={() => downloadReport(format)}
                >
                  {format.toUpperCase()}
                </button>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
