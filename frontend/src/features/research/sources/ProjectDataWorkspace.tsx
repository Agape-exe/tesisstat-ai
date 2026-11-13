import { useCallback, useRef, useState } from 'react';
import { useReadResource } from '../projects/useReadResource';
import { ProjectDatasets } from '../datasets/ProjectDatasets';
import { createSourcesApi, type SourcesApi, type TablePreview } from './api';
import './sources.css';

const defaultSourcesApi = createSourcesApi();

function detectColumnType(
  rows: (string | null)[][],
  colIndex: number,
): 'numérico' | 'fecha' | 'texto' {
  let hasValue = false;
  let isNumber = true;
  let isDate = true;

  for (const row of rows) {
    const raw = row[colIndex];
    if (raw !== null && raw !== undefined) {
      const val = String(raw).trim();
      if (val !== '') {
        hasValue = true;
        const normalized = val.replace(',', '.');
        if (isNaN(Number(normalized))) {
          isNumber = false;
        }
        if (
          isNaN(Date.parse(val)) ||
          !/[-/]/.test(val) ||
          val.length < 8 ||
          !isNaN(Number(val))
        ) {
          isDate = false;
        }
      }
    }
  }

  if (!hasValue) return 'texto';
  if (isNumber) return 'numérico';
  if (isDate) return 'fecha';
  return 'texto';
}

export function ProjectDataWorkspace({
  projectId,
  view = null,
  item = null,
  active = true,
  onNavigate,
  sourcesApi = defaultSourcesApi,
}: {
  projectId: string;
  view?: string | null;
  item?: string | null;
  active?: boolean;
  onNavigate?: (view: string, item?: string) => void;
  sourcesApi?: SourcesApi;
}) {
  if (['legacy', 'quality', 'preparation'].includes(view ?? '')) {
    return (
      <ProjectDatasets
        projectId={projectId}
        view={view === 'legacy' ? 'preview' : view}
        item={item}
        active={active}
        onNavigate={onNavigate ?? (() => {})}
      />
    );
  }

  return (
    <CleanDataViewer
      projectId={projectId}
      item={item}
      active={active}
      onNavigate={onNavigate}
      sourcesApi={sourcesApi}
    />
  );
}

function CleanDataViewer({
  projectId,
  item = null,
  active = true,
  onNavigate,
  sourcesApi = defaultSourcesApi,
}: {
  projectId: string;
  item?: string | null;
  active?: boolean;
  onNavigate?: (view: string, item?: string) => void;
  sourcesApi?: SourcesApi;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(item);
  const [uploadNotice, setUploadNotice] = useState<string>('');
  const [uploadError, setUploadError] = useState<string>('');
  const [uploading, setUploading] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadSources = useCallback(async () => {
    const [files, contexts] = await Promise.all([
      sourcesApi.files(projectId),
      sourcesApi.contexts(projectId).catch(() => []),
    ]);

    const readySheets = files.flatMap((f) =>
      f.sheets
        .filter((s) => s.state === 'ready' && s.table_id)
        .map((s) => {
          const matchedContext = contexts.find(
            (c) => c.table_id === s.table_id,
          );
          const customName = matchedContext?.name?.value;
          return {
            fileId: f.id,
            fileName: f.name,
            sheetId: s.id,
            tableId: s.table_id as string,
            sheetName: s.name,
            displayName: customName || s.name,
            rowCount: s.row_count,
            columnCount: s.column_count,
          };
        }),
    );

    return { files, readySheets };
  }, [projectId, sourcesApi]);

  const sourcesResource = useReadResource(loadSources, active);
  const readySheets = sourcesResource.data?.readySheets ?? [];

  const currentTableId =
    (selectedId && readySheets.some((s) => s.tableId === selectedId)
      ? selectedId
      : readySheets[0]?.tableId) ?? null;

  const currentSheet = readySheets.find((s) => s.tableId === currentTableId);

  const loadPreview = useCallback(async () => {
    if (!currentTableId) return null;
    return sourcesApi.preview(projectId, currentTableId);
  }, [projectId, currentTableId, sourcesApi]);

  const previewResource = useReadResource(
    loadPreview,
    active && Boolean(currentTableId),
  );
  const previewData: TablePreview | null = previewResource.data;

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setUploading(true);
    setUploadNotice('');
    setUploadError('');
    let uploadedCount = 0;
    let firstNewTableId: string | null = null;

    try {
      for (const file of files) {
        if (!/\.(csv|xlsx)$/i.test(file.name)) {
          throw new Error(
            `${file.name}: Por favor adjunta un archivo CSV o Excel (.xlsx).`,
          );
        }
        const uploaded = await sourcesApi.upload(projectId, file);
        uploadedCount += 1;
        const newTable = uploaded.sheets.find(
          (s) => s.state === 'ready',
        )?.table_id;
        if (newTable && !firstNewTableId) {
          firstNewTableId = newTable;
        }
      }
      setUploadNotice(
        `✓ ${uploadedCount} archivo(s) importado(s) exitosamente.`,
      );
      await sourcesResource.reload();
      if (firstNewTableId) {
        setSelectedId(firstNewTableId);
        onNavigate?.('table', firstNewTableId);
      }
    } catch (err) {
      setUploadError(
        err instanceof Error ? err.message : 'Error al subir el archivo.',
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  if (sourcesResource.loading) {
    return (
      <div className="clean-data-viewer" aria-label="Visor de datos">
        <p role="status" className="clean-data-loading">
          Cargando datos del proyecto…
        </p>
      </div>
    );
  }

  if (!readySheets.length) {
    return (
      <section className="clean-data-viewer" aria-label="Visor de datos">
        <div className="clean-data-empty rp-surface">
          <span className="clean-data-empty-icon" aria-hidden="true">
            📊
          </span>
          <h3>No hay datos cargados en esta investigación</h3>
          <p>
            Sube tu archivo de datos en formato Excel (.xlsx) o CSV para
            visualizar las filas y columnas. También puedes adjuntarlo
            directamente en el <strong>Asistente IA</strong> para comenzar a
            analizarlo de inmediato.
          </p>
          <label className="rp-button clean-data-upload-action">
            {uploading
              ? 'Importando archivo…'
              : '+ Subir archivo (Excel o CSV)'}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx"
              multiple
              disabled={uploading}
              style={{ display: 'none' }}
              onChange={(e) => void handleFileSelected(e)}
            />
          </label>
          {uploadError && (
            <p role="alert" className="rp-error clean-data-msg">
              {uploadError}
            </p>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="clean-data-viewer" aria-label="Visor de datos">
      <div className="clean-data-header-bar">
        <div className="clean-data-selector-group">
          {readySheets.length > 1 ? (
            <label className="clean-data-selector-label">
              <strong>Tabla activa:</strong>
              <select
                className="clean-data-select"
                aria-label="Seleccionar tabla activa"
                value={currentTableId ?? ''}
                onChange={(e) => {
                  setSelectedId(e.target.value);
                  onNavigate?.('table', e.target.value);
                }}
              >
                {readySheets.map((s) => (
                  <option key={s.tableId} value={s.tableId}>
                    {s.displayName} ({s.fileName} · {s.sheetName})
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <div className="clean-data-single-title">
              <span className="clean-data-badge-table">Tabla</span>
              <strong>{currentSheet?.displayName}</strong>
              <small className="clean-data-sub-hint">
                ({currentSheet?.fileName} · {currentSheet?.sheetName})
              </small>
            </div>
          )}
        </div>

        <div className="clean-data-actions-group">
          <label className="rp-secondary clean-data-upload-discreet">
            {uploading ? 'Subiendo…' : '+ Subir otro archivo'}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx"
              multiple
              disabled={uploading}
              style={{ display: 'none' }}
              onChange={(e) => void handleFileSelected(e)}
            />
          </label>
        </div>
      </div>

      {uploadNotice && (
        <p role="status" className="clean-data-notice">
          {uploadNotice}
        </p>
      )}
      {uploadError && (
        <p role="alert" className="rp-error clean-data-msg">
          {uploadError}
        </p>
      )}

      {previewResource.loading ? (
        <p role="status" className="clean-data-loading">
          Cargando vista previa de la tabla…
        </p>
      ) : previewData ? (
        <>
          <div className="clean-data-stats-bar">
            <span>
              <strong>{previewData.table.row_count}</strong> registros
            </span>
            <span>·</span>
            <span>
              <strong>{previewData.table.column_count}</strong> columnas
            </span>
            {previewData.table.extraction?.range && (
              <>
                <span>·</span>
                <span className="clean-data-range-info">
                  Rango extraído: {previewData.table.extraction.range}
                </span>
              </>
            )}
          </div>

          <div
            className="rp-dataset-scroll clean-data-grid"
            tabIndex={0}
            role="region"
            aria-label="Vista previa de datos"
          >
            <table>
              <thead>
                <tr>
                  {previewData.table.columns.map((c) => (
                    <th key={c.id} scope="col">
                      {c.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewData.rows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    {row.map((cell, cIdx) => (
                      <td key={cIdx}>
                        {cell === null || cell === undefined ? (
                          <span className="rp-hint">Sin valor</span>
                        ) : cell === '' ? (
                          <span className="rp-hint">Vacío</span>
                        ) : (
                          String(cell)
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="clean-data-variables rp-surface">
            <h4>Variables detectadas ({previewData.table.columns.length})</h4>
            <div className="clean-data-var-list">
              {previewData.table.columns.map((col, idx) => {
                const detected = detectColumnType(previewData.rows, idx);
                return (
                  <div className="clean-data-var-chip" key={col.id}>
                    <span className="clean-data-var-name">{col.name}</span>
                    <span className={`clean-data-var-badge badge-${detected}`}>
                      {detected}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
