import { useEffect, useRef, useState } from 'react';
import { createDatasetApi } from './api';
import { DatasetEDA } from './DatasetEDA';
import { DatasetPreparation } from './DatasetPreparation';
import type { DatasetApi, DatasetPreview, ResearchDataset } from './api';

const defaultApi = createDatasetApi();
const MAX_BYTES = 10 * 1024 * 1024;

export function ProjectDatasets({
  projectId,
  api = defaultApi,
}: {
  projectId: string;
  api?: DatasetApi;
}) {
  const [datasets, setDatasets] = useState<ResearchDataset[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .list(projectId, controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) {
          setDatasets(items);
          setLoading(false);
          setError('');
        }
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setError(
            caught instanceof Error
              ? caught.message
              : 'No se pudo cargar el listado.',
          );
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [api, projectId, retry]);

  function choose(chosen: File | null) {
    setFile(chosen);
    setError('');
    if (chosen && !/\.(csv|xlsx)$/i.test(chosen.name))
      setError('Adjunta un archivo CSV o XLSX.');
    else if (chosen && !chosen.size) setError('El archivo está vacío.');
    else if (chosen && chosen.size > MAX_BYTES)
      setError('El archivo supera el límite de 10 MiB.');
  }

  async function upload() {
    if (!file || busy) return;
    if (
      !/\.(csv|xlsx)$/i.test(file.name) ||
      !file.size ||
      file.size > MAX_BYTES
    ) {
      choose(file);
      return;
    }
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const dataset = await api.upload(projectId, file);
      setDatasets((items) => [dataset, ...items]);
      setFile(null);
      if (input.current) input.current.value = '';
      setNotice('Dataset subido.');
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo subir el dataset.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function view(id: string, retry = false) {
    if (selected === id && !retry) {
      setSelected(null);
      setPreview(null);
      return;
    }
    setSelected(id);
    setPreview(null);
    setPreviewLoading(true);
    setError('');
    try {
      setPreview(await api.preview(projectId, id));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo cargar la vista previa.',
      );
    } finally {
      setPreviewLoading(false);
    }
  }

  async function activate(id: string) {
    setBusy(true);
    setError('');
    try {
      await api.activate(projectId, id);
      setDatasets((items) =>
        items.map((item) => ({ ...item, active: item.id === id })),
      );
      setNotice('Dataset activo actualizado.');
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo activar el dataset.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function setOrigin(dataset: ResearchDataset, synthetic: boolean) {
    if (!api.setOrigin) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const updated = await api.setOrigin(projectId, dataset.id, synthetic);
      setDatasets((items) =>
        items.map((item) => (item.id === dataset.id ? updated : item)),
      );
      setNotice(
        'Procedencia guardada. Los nuevos derivados heredarán esta declaración.',
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo guardar la procedencia.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(dataset: ResearchDataset) {
    if (!window.confirm(`¿Eliminar el dataset «${dataset.name}»?`)) return;
    setBusy(true);
    setError('');
    try {
      await api.delete(projectId, dataset.id);
      setDatasets((items) => items.filter((item) => item.id !== dataset.id));
      if (selected === dataset.id) {
        setSelected(null);
        setPreview(null);
      }
      setNotice('Dataset eliminado.');
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo eliminar el dataset.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="rp-documents"
      aria-label="Datasets de investigación"
      aria-busy={loading || busy}
    >
      <h3>Datasets</h3>
      <p className="rp-hint">
        Adjunta CSV UTF-8 o XLSX de hasta 10 MiB. Usa solo datos ficticios en
        esta demo.
      </p>
      <label htmlFor="research-dataset">Archivo</label>
      <div className="rp-documents-upload">
        <input
          ref={input}
          id="research-dataset"
          type="file"
          accept=".csv,.xlsx"
          disabled={busy}
          onChange={(event) => choose(event.target.files?.[0] ?? null)}
        />
        <button disabled={!file || busy} onClick={() => void upload()}>
          {busy ? 'Subiendo…' : 'Subir dataset'}
        </button>
      </div>
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
      {loading ? (
        <p role="status">Cargando datasets…</p>
      ) : error && !datasets.length ? (
        <button
          className="rp-secondary"
          onClick={() => {
            setLoading(true);
            setRetry((value) => value + 1);
          }}
        >
          Reintentar listado
        </button>
      ) : !datasets.length ? (
        <p>Aún no hay datasets en esta investigación.</p>
      ) : (
        <ul className="rp-documents-list">
          {datasets.map((dataset) => (
            <li key={dataset.id}>
              <div>
                <strong>{dataset.name}</strong>{' '}
                {dataset.active && <span className="rp-badge">Activo</span>}
                <small>
                  {dataset.format.toUpperCase()} ·{' '}
                  {(dataset.size / 1024).toFixed(1)} KB · {dataset.row_count}{' '}
                  filas · {dataset.column_count} columnas
                </small>
                {dataset.source_dataset_id && (
                  <small>Derivado de {dataset.source_dataset_id}</small>
                )}
                {api.setOrigin && (
                  <label>
                    Origen de {dataset.name}
                    <select
                      value={
                        dataset.synthetic == null
                          ? ''
                          : String(dataset.synthetic)
                      }
                      disabled={busy || !!dataset.source_dataset_id}
                      onChange={(event) =>
                        void setOrigin(dataset, event.target.value === 'true')
                      }
                    >
                      <option value="" disabled>
                        Sin declarar
                      </option>
                      <option value="true">Sintético</option>
                      <option value="false">No sintético</option>
                    </select>
                  </label>
                )}
                {dataset.source_dataset_id ? (
                  <p className="rp-hint">
                    La procedencia se hereda del original al crear el derivado.
                  </p>
                ) : (
                  <p className="rp-hint">
                    Declara el origen sintético antes de preparar los datos.
                  </p>
                )}
                {dataset.warnings.map((warning) => (
                  <p key={warning} role="status">
                    {warning}
                  </p>
                ))}
              </div>
              <button
                className="rp-secondary"
                disabled={busy}
                onClick={() => void view(dataset.id)}
              >
                {selected === dataset.id ? 'Ocultar datos' : 'Ver datos'}
              </button>
              {!dataset.active && (
                <button
                  className="rp-secondary"
                  disabled={busy}
                  onClick={() => void activate(dataset.id)}
                >
                  Seleccionar como activo
                </button>
              )}
              <button
                className="rp-delete"
                disabled={busy}
                onClick={() => void remove(dataset)}
                aria-label={`Eliminar dataset ${dataset.name}`}
              >
                Eliminar
              </button>
              <DatasetEDA
                projectId={projectId}
                datasetId={dataset.id}
                api={api}
              />
              <DatasetPreparation
                projectId={projectId}
                dataset={dataset}
                api={api}
                onCreated={() => setRetry((value) => value + 1)}
              />
              {selected === dataset.id && (
                <div className="rp-dataset-preview">
                  {previewLoading ? (
                    <p role="status">Cargando vista previa…</p>
                  ) : preview ? (
                    <>
                      <p>
                        {preview.row_count} filas · {preview.column_count}{' '}
                        columnas · {preview.format.toUpperCase()}
                        {preview.sheet ? ` · Hoja: ${preview.sheet}` : ''}
                      </p>
                      <div className="rp-dataset-scroll">
                        <table>
                          <thead>
                            <tr>
                              {preview.columns.map((column) => (
                                <th scope="col" key={column}>
                                  {column}
                                </th>
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
                    </>
                  ) : (
                    <button
                      className="rp-secondary"
                      onClick={() => void view(dataset.id, true)}
                    >
                      Reintentar vista previa
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
