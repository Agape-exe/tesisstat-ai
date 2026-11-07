import {
  Guidance,
  SectionColumns,
  SupportPanel,
} from '../projects/SectionLayout';
import { UiIcon } from '../projects/UiIcon';
import { useReadResource } from '../projects/useReadResource';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createDatasetApi } from './api';
import { DatasetEDA } from './DatasetEDA';
import { DatasetPreparation } from './DatasetPreparation';
import type { DatasetApi, ResearchDataset } from './api';

const defaultApi = createDatasetApi();
const MAX_BYTES = 10 * 1024 * 1024;

export function ProjectDatasets({
  projectId,
  api = defaultApi,
  view: requestedView,
  item,
  onNavigate,
  active = true,
}: {
  projectId: string;
  api?: DatasetApi;
  view?: string | null;
  item?: string | null;
  onNavigate?: (view: string, item?: string) => void;
  active?: boolean;
}) {
  const [datasets, setDatasets] = useState<ResearchDataset[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [retry, setRetry] = useState(0);
  const [localSelected, setSelected] = useState<string | null>(null);
  const selected = onNavigate ? (item ?? null) : (item ?? localSelected);
  const [localStage, setLocalStage] = useState('preview');
  const requestedStage = onNavigate
    ? (requestedView ?? 'preview')
    : (requestedView ?? localStage);
  const stage = ['preview', 'quality', 'preparation'].includes(requestedStage)
    ? requestedStage
    : 'preview';
  const chosen =
    datasets.find((d) => d.id === selected) ??
    datasets.find((d) => d.active) ??
    datasets[0];
  const [visited, setVisited] = useState<string[]>([]);
  const pane = chosen && stage !== 'preview' ? `${chosen.id}:${stage}` : null;
  if (pane && !visited.includes(pane)) setVisited([...visited, pane]);
  function go(next: string, id?: string) {
    setLocalStage(next);
    setSelected(id ?? null);
    onNavigate?.(next, id);
  }
  const [previewHidden, setPreviewHidden] = useState(false);
  const previewId = previewHidden ? undefined : chosen?.id;
  const loadPreview = useCallback(
    () =>
      previewId ? api.preview(projectId, previewId) : Promise.resolve(null),
    [api, projectId, previewId],
  );
  const previewResource = useReadResource(
    loadPreview,
    active && stage === 'preview' && !!previewId,
    String(retry),
  );
  const preview = previewResource.data;
  const previewLoading = previewResource.loading;
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!active) return;
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
  }, [api, projectId, retry, active]);

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

  function view(id: string, retry = false) {
    setError('');
    if (retry) {
      previewResource.reload();
      return;
    }
    setPreviewHidden(previewId === id);
    go('preview', id);
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
        go('preview');
        setPreviewHidden(false);
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
      <div className="rp-section-heading">
        <h2>Conjunto de datos</h2>
        <button
          onClick={() => {
            go('preview', chosen?.id);
            input.current?.click();
          }}
        >
          <UiIcon name="upload" /> Seleccionar archivo
        </button>
      </div>
      <SectionColumns
        support={
          <SupportPanel
            title="Antes del análisis"
            projectId={projectId}
            destination="analysis"
            action="Ir a Análisis"
          >
            <Guidance
              items={[
                'Revisa las columnas y sus tipos',
                'Vincula las variables con sus columnas',
                'Confirma la codificación de escalas',
                'Comprueba la calidad de los datos',
              ]}
            />
            <p className="rp-hint">
              Los tipos de columna no determinan escalas de medición.
            </p>
          </SupportPanel>
        }
      >
        <div className="rp-surface rp-data-surface">
          <h3>Archivo de respuestas</h3>
          {chosen && (
            <div className="rp-active-dataset">
              <span className="rp-file-symbol">
                <UiIcon name="database" />
              </span>
              <div>
                <strong>{chosen.name}</strong>
                <small>
                  {chosen.format.toUpperCase()} · {chosen.row_count} filas ·{' '}
                  {chosen.column_count} columnas ·{' '}
                  {chosen.synthetic == null
                    ? 'Origen sin declarar'
                    : chosen.synthetic
                      ? 'Sintético'
                      : 'No sintético'}
                </small>
              </div>
              {chosen.active && <span className="rp-badge">Activo</span>}
            </div>
          )}
          {datasets.length > 1 && (
            <label className="rp-field">
              Dataset de trabajo
              <select
                value={chosen?.id ?? ''}
                onChange={(event) => {
                  setPreviewHidden(false);
                  go(stage, event.target.value);
                }}
              >
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}
                    {dataset.active ? ' · Activo' : ''}
                  </option>
                ))}
              </select>
            </label>
          )}
          <nav className="rp-segment" aria-label="Vistas de datos">
            {[
              ['preview', 'Archivo y vista previa'],
              ['quality', 'Calidad de datos'],
              ['preparation', 'Preparación y transformaciones'],
            ].map(([id, label]) => (
              <button
                key={id}
                aria-current={stage === id ? 'page' : undefined}
                onClick={() => go(id, chosen?.id)}
              >
                {label}
              </button>
            ))}
          </nav>
          <div hidden={stage !== 'preview' || (!!datasets.length && !file)}>
            <p className="rp-hint">
              Adjunta CSV UTF-8 o XLSX de hasta 10 MiB. Usa solo datos ficticios
              en esta demo.
            </p>
            <div className="rp-upload-zone rp-data-upload">
              <label className="rp-file-picker" htmlFor="research-dataset">
                {file?.name || 'Selecciona un CSV o XLSX'}
              </label>
              <div className="rp-documents-upload">
                <input
                  ref={input}
                  id="research-dataset"
                  aria-label="Archivo"
                  type="file"
                  accept=".csv,.xlsx"
                  disabled={busy}
                  onChange={(event) => choose(event.target.files?.[0] ?? null)}
                />
                <button disabled={!file || busy} onClick={() => void upload()}>
                  {busy ? 'Subiendo…' : 'Subir dataset'}
                </button>
              </div>
            </div>
          </div>
          {error && (
            <p role="alert" className="rp-error">
              {error}
            </p>
          )}
          {previewResource.error && (
            <p role="alert" className="rp-error">
              {previewResource.error}
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
          ) : null}
          {stage === 'preview' && chosen && !previewHidden && (
            <div className="rp-dataset-preview">
              {previewLoading ? (
                <p role="status">Cargando vista previa…</p>
              ) : preview ? (
                <>
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
                  <p className="rp-hint">
                    Se muestran como máximo 20 filas.
                    {preview.sheet ? ` Hoja: ${preview.sheet}.` : ''}
                  </p>
                </>
              ) : (
                <button
                  className="rp-secondary"
                  onClick={() => view(chosen.id, true)}
                >
                  Reintentar vista previa
                </button>
              )}
            </div>
          )}
          {chosen && stage === 'preview' && (
            <details className="rp-technical">
              <summary>Procedencia y trazabilidad</summary>
              <p>
                {chosen.format.toUpperCase()} ·{' '}
                {(chosen.size / 1024).toFixed(1)} KB.{' '}
                {new Date(chosen.uploaded_at).toLocaleString('es-PE')}
              </p>
              {chosen.source_dataset_id && (
                <p>Derivado de {chosen.source_dataset_id}</p>
              )}
              {api.setOrigin && (
                <label className="rp-field">
                  Origen de {chosen.name}
                  <select
                    value={
                      chosen.synthetic == null ? '' : String(chosen.synthetic)
                    }
                    disabled={busy || !!chosen.source_dataset_id}
                    onChange={(event) =>
                      void setOrigin(chosen, event.target.value === 'true')
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
              <p className="rp-hint">
                {chosen.source_dataset_id
                  ? 'La procedencia se hereda del original al crear el derivado.'
                  : 'Declara el origen sintético antes de preparar los datos.'}
              </p>
              <div className="rp-actions">
                <button
                  className="rp-secondary"
                  disabled={busy}
                  onClick={() => view(chosen.id)}
                >
                  {previewHidden ? 'Ver datos' : 'Ocultar datos'}
                </button>
                {!chosen.active && (
                  <button
                    className="rp-secondary"
                    disabled={busy}
                    onClick={() => void activate(chosen.id)}
                  >
                    Seleccionar como activo
                  </button>
                )}
                <button
                  className="rp-delete"
                  disabled={busy}
                  onClick={() => void remove(chosen)}
                  aria-label={`Eliminar dataset ${chosen.name}`}
                >
                  Eliminar
                </button>
              </div>
            </details>
          )}
          {chosen?.warnings.map((warning) => (
            <p key={warning} role="status">
              {warning}
            </p>
          ))}
          {visited.map((key) => {
            const [id, kind] = key.split(':');
            const dataset = datasets.find((d) => d.id === id);
            return dataset ? (
              <div key={key} hidden={pane !== key}>
                {kind === 'quality' ? (
                  <DatasetEDA projectId={projectId} datasetId={id} api={api} />
                ) : (
                  <DatasetPreparation
                    projectId={projectId}
                    dataset={dataset}
                    api={api}
                    onCreated={() => setRetry((n) => n + 1)}
                  />
                )}
              </div>
            ) : null;
          })}
        </div>
      </SectionColumns>
    </section>
  );
}
