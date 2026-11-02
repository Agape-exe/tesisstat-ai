import { useEffect, useState } from 'react';
import { DatasetApiError } from './api';
import type { DatasetApi, EDAReport } from './api';

export function DatasetEDA({
  projectId,
  datasetId,
  api,
}: {
  projectId: string;
  datasetId: string;
  api: DatasetApi;
}) {
  const [report, setReport] = useState<EDAReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [opened, setOpened] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .getEda(projectId, datasetId)
      .then((value) => {
        if (active) setReport(value);
      })
      .catch((caught) => {
        if (
          active &&
          !(caught instanceof DatasetApiError && caught.status === 404)
        ) {
          setError(
            caught instanceof Error
              ? caught.message
              : 'No se pudo consultar el reporte.',
          );
        }
      });
    return () => {
      active = false;
    };
  }, [api, projectId, datasetId]);

  async function analyze(force = false) {
    setBusy(true);
    setError('');
    try {
      setReport(await api.runEda(projectId, datasetId, force));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo analizar el dataset.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rp-dataset-preview" aria-busy={busy}>
      <button
        className="rp-secondary"
        disabled={busy}
        onClick={() => void analyze()}
      >
        Analizar calidad de datos
      </button>
      {report && (
        <button
          className="rp-secondary"
          disabled={busy}
          onClick={() => void analyze(true)}
        >
          Repetir análisis
        </button>
      )}
      {busy && <p role="status">Procesando el dataset completo…</p>}
      {error && (
        <p role="alert" className="rp-error">
          {error} <button onClick={() => void analyze()}>Reintentar</button>
        </p>
      )}
      {!report && !busy && !error && <p>Aún no hay análisis guardado.</p>}
      {report && (
        <>
          <h4>Resumen general</h4>
          <p>
            {report.summary.rows} filas · {report.summary.columns} columnas ·{' '}
            {report.summary.missing} faltantes (
            {report.summary.missing_percentage.toFixed(1)}%) ·{' '}
            {report.summary.duplicates} duplicados ·{' '}
            {report.summary.problem_columns} columnas problemáticas
          </p>
          <small>
            Procesado: {new Date(report.processed_at).toLocaleString()} ·
            Reglas: {report.rule_version}
          </small>
          <h4>Perfil de columnas</h4>
          <div className="rp-dataset-scroll">
            <table>
              <thead>
                <tr>
                  <th>Columna</th>
                  <th>Tipo sugerido</th>
                  <th>Faltantes</th>
                  <th>Valores distintos</th>
                  <th>Advertencias</th>
                  <th>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {report.columns.map((column) => (
                  <tr key={column.name}>
                    <th scope="row">{column.name}</th>
                    <td>{column.suggested_type}</td>
                    <td>
                      {column.missing} ({column.missing_percentage.toFixed(1)}%)
                    </td>
                    <td>{column.distinct}</td>
                    <td>{column.warnings.length}</td>
                    <td>
                      <button
                        className="rp-secondary"
                        onClick={() =>
                          setOpened(opened === column.name ? null : column.name)
                        }
                      >
                        {opened === column.name ? 'Ocultar' : 'Ver detalle'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.columns
            .filter((column) => column.name === opened)
            .map((column) => (
              <div key={column.name}>
                <h5>{column.name}</h5>
                <p>
                  Presentes: {column.present} · Unicidad:{' '}
                  {column.uniqueness_percentage.toFixed(1)}% · Numéricos
                  válidos: {column.numeric_valid}
                </p>
                {column.numeric_min !== null && (
                  <p>
                    Rango numérico: {column.numeric_min} a {column.numeric_max}
                  </p>
                )}
                {column.date_min !== null && (
                  <p>
                    Intervalo temporal sugerido: {column.date_min} a{' '}
                    {column.date_max}
                  </p>
                )}
                {column.incompatible_examples.length > 0 && (
                  <p>
                    Ejemplos no numéricos:{' '}
                    {column.incompatible_examples.join(', ')}
                  </p>
                )}
                {column.frequencies.length > 0 && (
                  <ul>
                    {column.frequencies.map((item, index) => (
                      <li key={index}>
                        {item.value}: {item.count} ({item.percentage.toFixed(1)}
                        %)
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          <h4>Advertencias</h4>
          {report.warnings.length ? (
            <ul>
              {report.warnings.map((warning, index) => (
                <li key={index}>{warning.message}</li>
              ))}
            </ul>
          ) : (
            <p>No se detectaron advertencias.</p>
          )}
        </>
      )}
    </div>
  );
}
