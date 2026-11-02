import { useEffect, useState } from 'react';
import type {
  DatasetApi,
  PreparationKind,
  PreparationOperation,
  PreparationPreview,
  PreparationRecord,
  ResearchDataset,
} from './api';

const labels: Record<PreparationKind, string> = {
  drop_duplicates: 'Eliminar duplicados exactos',
  drop_missing: 'Eliminar filas con faltantes',
  replace_missing: 'Reemplazar faltantes',
  drop_columns: 'Eliminar columnas',
  rename_column: 'Renombrar columna',
  trim: 'Eliminar espacios externos',
  to_numeric: 'Convertir a numérico',
};
const markers = ['NA', 'N/A', 'null', 'none'] as const;

export function DatasetPreparation({
  projectId,
  dataset,
  api,
  onCreated,
}: {
  projectId: string;
  dataset: ResearchDataset;
  api: DatasetApi;
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<PreparationKind>('drop_duplicates');
  const [operations, setOperations] = useState<PreparationOperation[]>([]);
  const [preview, setPreview] = useState<PreparationPreview | null>(null);
  const [history, setHistory] = useState<PreparationRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!open || !api.listPreparations) return;
    void api
      .listPreparations(projectId, dataset.id)
      .then(setHistory)
      .catch(() => {
        setError('No se pudo cargar el historial.');
      });
  }, [open, api, projectId, dataset.id]);

  function change(index: number, next: PreparationOperation) {
    setOperations((items) =>
      items.map((item, position) => (position === index ? next : item)),
    );
    setPreview(null);
    setNotice('');
  }
  function move(index: number, offset: number) {
    const next = [...operations];
    const target = index + offset;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setOperations(next);
    setPreview(null);
  }
  async function showPreview() {
    if (!api.previewPreparation) return;
    setBusy(true);
    setError('');
    setNotice('');
    setPreview(null);
    try {
      setPreview(
        await api.previewPreparation(projectId, dataset.id, { operations }),
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'No se pudo previsualizar.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function apply() {
    if (!preview || !api.applyPreparation) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const record = await api.applyPreparation(
        projectId,
        dataset.id,
        { operations },
        preview,
      );
      setHistory((items) => [
        record,
        ...items.filter((item) => item.result_id !== record.result_id),
      ]);
      setNotice(
        'Dataset preparado creado. Selecciónalo como activo desde el listado si deseas usarlo.',
      );
      setPreview(null);
      onCreated();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo crear el derivado.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rp-dataset-preparation">
      <button className="rp-secondary" onClick={() => setOpen(!open)}>
        {open ? 'Ocultar preparación' : 'Preparar datos'}
      </button>
      {open && (
        <div>
          <h4>Preparar datos</h4>
          <p>
            Revisa el análisis EDA de este dataset antes de elegir operaciones.
            Los cambios se aplican solo al confirmar.
          </p>
          <label>
            Operación
            <select
              value={kind}
              onChange={(event) =>
                setKind(event.target.value as PreparationKind)
              }
            >
              {Object.entries(labels).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button
            disabled={busy || operations.length >= 20}
            onClick={() => {
              setOperations((items) => [
                ...items,
                {
                  type: kind,
                  columns: [],
                  empty_is_missing: true,
                  missing_markers: [],
                },
              ]);
              setPreview(null);
            }}
          >
            Agregar operación
          </button>
          <ol>
            {operations.map((operation, index) => {
              let available = [...dataset.columns];
              for (const prior of operations.slice(0, index)) {
                if (
                  prior.type === 'rename_column' &&
                  prior.column &&
                  prior.new_name
                ) {
                  available = available.map((name) =>
                    name === prior.column ? prior.new_name!.trim() : name,
                  );
                }
                if (prior.type === 'drop_columns')
                  available = available.filter(
                    (name) => !prior.columns?.includes(name),
                  );
              }
              const multi = ['drop_missing', 'drop_columns', 'trim'].includes(
                operation.type,
              );
              const single = [
                'replace_missing',
                'rename_column',
                'to_numeric',
              ].includes(operation.type);
              const missing = [
                'drop_missing',
                'replace_missing',
                'to_numeric',
              ].includes(operation.type);
              return (
                <li key={index}>
                  <strong>
                    {index + 1}. {labels[operation.type]}
                  </strong>
                  {multi && (
                    <fieldset>
                      <legend>Columnas</legend>
                      {available.map((name) => (
                        <label key={name}>
                          <input
                            type="checkbox"
                            checked={operation.columns?.includes(name) ?? false}
                            onChange={(event) =>
                              change(index, {
                                ...operation,
                                columns: event.target.checked
                                  ? [...(operation.columns ?? []), name]
                                  : operation.columns?.filter(
                                      (item) => item !== name,
                                    ),
                              })
                            }
                          />
                          {name}
                        </label>
                      ))}
                    </fieldset>
                  )}
                  {single && (
                    <label>
                      Columna
                      <select
                        value={operation.column ?? ''}
                        onChange={(event) =>
                          change(index, {
                            ...operation,
                            column: event.target.value,
                          })
                        }
                      >
                        <option value="">Seleccionar</option>
                        {available.map((name) => (
                          <option key={name}>{name}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  {operation.type === 'rename_column' && (
                    <label>
                      Nuevo nombre
                      <input
                        value={operation.new_name ?? ''}
                        onChange={(event) =>
                          change(index, {
                            ...operation,
                            new_name: event.target.value,
                          })
                        }
                      />
                    </label>
                  )}
                  {operation.type === 'replace_missing' && (
                    <label>
                      Valor de reemplazo
                      <input
                        value={operation.value ?? ''}
                        onChange={(event) =>
                          change(index, {
                            ...operation,
                            value: event.target.value,
                          })
                        }
                      />
                    </label>
                  )}
                  {missing && (
                    <fieldset>
                      <legend>Política de faltantes</legend>
                      <label>
                        <input
                          type="checkbox"
                          checked={operation.empty_is_missing ?? true}
                          onChange={(event) =>
                            change(index, {
                              ...operation,
                              empty_is_missing: event.target.checked,
                            })
                          }
                        />
                        Celdas vacías y espacios
                      </label>
                      {markers.map((marker) => (
                        <label key={marker}>
                          <input
                            type="checkbox"
                            checked={
                              operation.missing_markers?.includes(marker) ??
                              false
                            }
                            onChange={(event) =>
                              change(index, {
                                ...operation,
                                missing_markers: event.target.checked
                                  ? [
                                      ...(operation.missing_markers ?? []),
                                      marker,
                                    ]
                                  : operation.missing_markers?.filter(
                                      (item) => item !== marker,
                                    ),
                              })
                            }
                          />
                          {marker}
                        </label>
                      ))}
                    </fieldset>
                  )}
                  <button
                    className="rp-secondary"
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                  >
                    Subir
                  </button>
                  <button
                    className="rp-secondary"
                    disabled={index === operations.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    Bajar
                  </button>
                  <button
                    className="rp-secondary"
                    onClick={() => {
                      setOperations(
                        operations.filter((_, position) => position !== index),
                      );
                      setPreview(null);
                    }}
                  >
                    Quitar
                  </button>
                </li>
              );
            })}
          </ol>
          <button
            disabled={busy || !operations.length}
            onClick={() => void showPreview()}
          >
            {busy ? 'Procesando…' : 'Previsualizar cambios'}
          </button>
          {error && (
            <p role="alert" className="rp-error">
              {error}
            </p>
          )}
          {notice && (
            <p role="status" className="rp-success">
              {notice}
            </p>
          )}
          {preview && (
            <section aria-label="Vista previa de preparación">
              <h5>Vista previa; aún no se creó ningún dataset</h5>
              <p>
                {preview.original_rows} → {preview.result_rows} filas ·{' '}
                {preview.original_columns.length} →{' '}
                {preview.result_columns.length} columnas ·{' '}
                {preview.rows_removed} filas eliminadas ·{' '}
                {preview.cells_changed} celdas modificadas
              </p>
              <ul>
                {preview.operations.map((item, index) => (
                  <li key={index}>
                    {labels[item.type]}: {item.rows_removed} filas,{' '}
                    {item.cells_changed} celdas; columnas eliminadas:{' '}
                    {item.columns_removed.join(', ') || 'ninguna'}
                  </li>
                ))}
              </ul>
              {preview.warnings.map((warning) => (
                <p role="status" key={warning}>
                  {warning}
                </p>
              ))}
              <div className="rp-dataset-scroll">
                <table>
                  <thead>
                    <tr>
                      {preview.result_columns.map((name) => (
                        <th key={name}>{name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, index) => (
                      <tr key={index}>
                        {row.map((value, column) => (
                          <td key={column}>{value ?? ''}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p>Se muestran como máximo 20 filas.</p>
              <button disabled={busy} onClick={() => void apply()}>
                Confirmar y crear dataset preparado
              </button>
            </section>
          )}
          <h5>Historial de transformaciones</h5>
          {history.length ? (
            <ul>
              {history.map((record) => (
                <li key={record.result_id}>
                  {new Date(record.prepared_at).toLocaleString()} · Derivado{' '}
                  {record.result_id} ·{' '}
                  {record.plan.operations
                    .map((item) => labels[item.type])
                    .join(' → ')}
                </li>
              ))}
            </ul>
          ) : (
            <p>Aún no hay preparaciones para este dataset.</p>
          )}
        </div>
      )}
    </div>
  );
}
