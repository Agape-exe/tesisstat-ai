import { useCallback, useEffect, useRef, useState } from 'react';
import { useReadResource } from '../projects/useReadResource';
import { TableContextEditor } from './TableContextEditor';
import {
  createSourcesApi,
  type Sheet,
  type SourceFile,
  type SourcesApi,
  type Table,
  type TableContext,
} from './api';
import './sources.css';

const defaultApi = createSourcesApi();
const stateNames = {
  ready: 'Lista',
  pending: 'Pendiente',
  excluded: 'Excluida',
  error: 'Error',
};

export function ProjectSources({
  projectId,
  api = defaultApi,
  active = true,
  item,
  onSelect,
  onReview,
}: {
  projectId: string;
  api?: SourcesApi;
  active?: boolean;
  item?: string | null;
  onSelect?: (id: string) => void;
  onReview?: (id: string) => void;
}) {
  const load = useCallback(async () => {
    const [files, contexts] = await Promise.all([
      api.files(projectId),
      api.contexts(projectId),
    ]);
    return { files, contexts };
  }, [api, projectId]);
  const resource = useReadResource(load, active);
  const files = resource.data?.files ?? [];
  const [queue, setQueue] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [localSelected, setSelected] = useState<string | null>(null);
  const selected = item ?? localSelected;
  const [editedNames, setNames] = useState<Record<string, string>>({});
  const names = {
    ...Object.fromEntries(
      (resource.data?.contexts ?? []).map((context) => [
        context.table_id,
        context.name.value ?? '',
      ]),
    ),
    ...editedNames,
  };
  const input = useRef<HTMLInputElement>(null);
  const ready = files.flatMap((file) =>
    file.sheets.filter((sheet) => sheet.state === 'ready'),
  );
  const pending = files.flatMap((file) =>
    file.sheets.filter(
      (sheet) => sheet.state === 'pending' || sheet.state === 'error',
    ),
  );
  const chosen = ready.find((sheet) => sheet.table_id === selected);
  const source = files.find((file) => file.id === chosen?.file_id);
  const [pendingOnly, setPendingOnly] = useState(false);

  async function upload() {
    setBusy(true);
    setError('');
    setNotice('');
    const remaining = [];
    const messages = [];
    let imported = 0;
    for (const file of queue) {
      try {
        if (!/\.(csv|xlsx)$/i.test(file.name))
          throw new Error(`${file.name}: adjunta CSV o XLSX.`);
        if (!file.size || file.size > 10 * 1024 * 1024)
          throw new Error(`${file.name}: usa un archivo de 1 byte a 10 MiB.`);
        await api.upload(projectId, file);
        imported += 1;
      } catch (cause) {
        remaining.push(file);
        messages.push(
          `${file.name}: ${cause instanceof Error ? cause.message : 'No se pudo importar.'}`,
        );
      }
    }
    setQueue(remaining);
    if (input.current) input.current.value = '';
    setError(messages.join(' '));
    if (imported)
      setNotice(
        `${imported} archivo(s) guardado(s). Revisa las hojas pendientes; los anteriores se conservan.`,
      );
    resource.reload();
    setBusy(false);
  }
  function update(file: SourceFile) {
    resource.setData({
      files: files.map((previous) =>
        previous.id === file.id && previous.revision < file.revision
          ? file
          : previous,
      ),
      contexts: resource.data?.contexts ?? [],
    });
  }
  return (
    <section
      className="rp-documents source-workspace"
      aria-label="Tus datos"
      aria-busy={busy || resource.loading}
    >
      <div className="rp-section-heading">
        <h2>Tus datos</h2>
      </div>
      <div className="rp-surface source-upload">
        <h3>Archivos y tablas de tu investigación</h3>
        <p>
          Sube el libro completo. Incorporamos las hojas tabulares claras y te
          pedimos revisar solo las que necesitan aclaración.
        </p>
        <label className="rp-field">
          Seleccionar archivos CSV o Excel
          <input
            ref={input}
            type="file"
            multiple
            accept=".csv,.xlsx"
            disabled={busy}
            onChange={(event) => setQueue(Array.from(event.target.files ?? []))}
          />
        </label>
        {queue.length > 0 && (
          <ul>
            {queue.map((file, index) => (
              <li key={`${file.name}-${index}`}>{file.name}</li>
            ))}
          </ul>
        )}
        <button disabled={busy || !queue.length} onClick={() => void upload()}>
          {busy ? 'Importando…' : 'Importar archivos'}
        </button>
        <details className="rp-technical">
          <summary>Formatos y límites</summary>
          <p>
            CSV UTF-8 o XLSX sin macros ni cifrado, hasta 10 MiB por archivo; 50
            MiB descomprimidos y 1000 entradas ZIP. Hasta 30 hojas, 50 000 filas
            por tabla y 200 columnas; 150 000 filas físicas, 2 000 000 celdas y
            30 MiB de tablas extraídas por libro. Los límites rechazan la carga
            completa: no truncamos datos.
          </p>
          <p>
            Conservamos los originales. No rellenamos faltantes con cero ni
            convertimos códigos en cantidades. Las fórmulas se guardan como
            texto, sin calcular ni usar resultados en caché. Los archivos y
            filas permanecen en este servidor local.
          </p>
        </details>
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
      {resource.error ? (
        <div role="alert" className="rp-error">
          <p>{resource.error}</p>
          <button onClick={resource.reload}>Reintentar archivos</button>
        </div>
      ) : resource.loading ? (
        <p role="status">Consultando archivos…</p>
      ) : (
        <>
          <div className="source-summary">
            <p>
              <strong>{files.length}</strong> archivos ·{' '}
              <strong>{ready.length}</strong> tablas listas ·{' '}
              <strong>{pending.length}</strong> hojas pendientes
            </p>
            <label>
              <input
                type="checkbox"
                checked={pendingOnly}
                onChange={(e) => setPendingOnly(e.target.checked)}
              />{' '}
              Ver solo hojas pendientes
            </label>
          </div>
          {!files.length && (
            <p>
              Aún no hay archivos importados. Puedes empezar sin documentos ni
              hipótesis.
            </p>
          )}
          {files.map((file) => (
            <article
              key={file.id}
              className="rp-surface source-file"
              aria-label={`Archivo ${file.name}`}
            >
              <div className="source-file-heading">
                <div>
                  <h3>{file.name}</h3>
                  <p>
                    {file.format.toUpperCase()} · {file.sheets.length} hoja(s) ·{' '}
                    {file.state === 'complete'
                      ? 'Importación completa'
                      : 'Importación con hojas pendientes'}
                  </p>
                </div>
                <a
                  className="rp-link"
                  href={api.originalUrl(projectId, file.id)}
                  download
                >
                  Descargar original
                </a>
              </div>
              <ul className="source-sheet-list">
                {file.sheets
                  .filter(
                    (sheet) =>
                      !pendingOnly ||
                      sheet.state === 'pending' ||
                      sheet.state === 'error',
                  )
                  .map((sheet) => (
                    <SheetRow
                      key={`${sheet.id}:${sheet.revision}`}
                      sheet={sheet}
                      file={file}
                      projectId={projectId}
                      api={api}
                      onUpdate={update}
                      selected={chosen?.id === sheet.id}
                      tableName={
                        sheet.table_id ? names[sheet.table_id] : undefined
                      }
                      onOpen={(id) => {
                        setSelected(id);
                        onSelect?.(id);
                      }}
                    />
                  ))}
              </ul>
              <details className="rp-technical">
                <summary>Procedencia del archivo</summary>
                <p className="source-hash">SHA-256: {file.hash}</p>
                <p>
                  Revisión {file.revision} · Original guardado el{' '}
                  {new Date(file.created_at).toLocaleString('es-PE')}
                </p>
              </details>
            </article>
          ))}
        </>
      )}
      {chosen?.table_id && source && (
        <TablePanel
          key={chosen.table_id}
          projectId={projectId}
          tableId={chosen.table_id}
          fileName={source.name}
          sheetName={chosen.name}
          api={api}
          onReview={onReview ? () => onReview(chosen.table_id!) : undefined}
          onSaved={(context) =>
            setNames((previous) => ({
              ...previous,
              [context.table_id]: context.name.value ?? '',
            }))
          }
        />
      )}
    </section>
  );
}

function SheetRow({
  sheet,
  file,
  projectId,
  api,
  selected,
  tableName,
  onUpdate,
  onOpen,
}: {
  sheet: Sheet;
  file: SourceFile;
  projectId: string;
  api: SourcesApi;
  selected: boolean;
  tableName?: string;
  onUpdate: (file: SourceFile) => void;
  onOpen: (id: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [header, setHeader] = useState('1');
  const [range, setRange] = useState('');
  async function change(action: 'include' | 'exclude' | 'extract') {
    setBusy(true);
    setError('');
    try {
      const updated = await api.sheet(projectId, file.id, sheet.id, {
        expected_revision: sheet.revision,
        action,
        ...(action === 'extract'
          ? { header_row: Number(header), range: range.trim().toUpperCase() }
          : {}),
      });
      onUpdate(updated);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'No se guardó la selección.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <li className="source-sheet">
      <div className="source-sheet-heading">
        <div>
          <h4>Hoja: {sheet.name}</h4>
          <span className={`rp-badge source-state-${sheet.state}`}>
            {stateNames[sheet.state]}
          </span>
          {sheet.visibility !== 'visible' && (
            <span className="rp-badge">
              Oculta{sheet.visibility === 'veryHidden' ? ' (veryHidden)' : ''}
            </span>
          )}
          <p>{sheet.explanation}</p>
          {sheet.table_id && (
            <p>
              Tabla: <strong>{tableName || sheet.name}</strong>
              {sheet.extraction ? ` · ${sheet.extraction.range}` : ''}
            </p>
          )}
        </div>
        <div className="rp-actions">
          {sheet.state === 'ready' && sheet.table_id && (
            <button
              aria-pressed={selected}
              disabled={busy}
              onClick={() => onOpen(sheet.table_id!)}
            >
              Abrir {tableName || sheet.name}
            </button>
          )}
          <button
            className="rp-secondary"
            disabled={busy}
            onClick={() =>
              void change(sheet.state === 'excluded' ? 'include' : 'exclude')
            }
          >
            {sheet.state === 'excluded' ? 'Volver a incluir' : 'Excluir hoja'}
          </button>
        </div>
      </div>
      {(sheet.state === 'pending' || sheet.state === 'error') && (
        <details className="source-extraction">
          <summary>Confirmar encabezado y rango</summary>
          <p>
            Dimensiones detectadas: {sheet.row_count} filas ×{' '}
            {sheet.column_count} columnas. El rango incluye la fila de
            encabezados, por ejemplo A3:D20. Consulta el original si necesitas
            ubicarlo.
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void change('extract');
            }}
          >
            <div className="source-range-fields">
              <label className="rp-field">
                Fila de encabezados
                <input
                  type="number"
                  min="1"
                  max={sheet.row_count || 1}
                  required
                  value={header}
                  onChange={(e) => setHeader(e.target.value)}
                />
              </label>
              <label className="rp-field">
                Rango tabular
                <input
                  placeholder="A3:D20"
                  required
                  maxLength={40}
                  value={range}
                  onChange={(e) => setRange(e.target.value)}
                />
              </label>
            </div>
            <button disabled={busy || !range || !sheet.row_count}>
              Confirmar e importar tabla
            </button>
          </form>
        </details>
      )}
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
    </li>
  );
}

function TablePanel({
  projectId,
  tableId,
  fileName,
  sheetName,
  api,
  onSaved,
  onReview,
}: {
  projectId: string;
  tableId: string;
  fileName: string;
  sheetName: string;
  api: SourcesApi;
  onSaved: (context: TableContext) => void;
  onReview?: () => void;
}) {
  const load = useCallback(async () => {
    const [preview, context] = await Promise.all([
      api.preview(projectId, tableId),
      api.context(projectId, tableId),
    ]);
    return { preview, context };
  }, [api, projectId, tableId]);
  const resource = useReadResource(load);
  const data = resource.data;
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    panel.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, []);
  return (
    <section
      ref={panel}
      className="rp-surface source-table"
      aria-label={`Tabla ${sheetName}`}
    >
      {resource.loading ? (
        <p role="status">Abriendo tabla…</p>
      ) : resource.error ? (
        <div role="alert">
          <p className="rp-error">{resource.error}</p>
          <button onClick={resource.reload}>Reintentar tabla</button>
        </div>
      ) : (
        data && (
          <>
            <h3>{data.context.name.value || sheetName}</h3>
            <p>
              Archivo: {fileName} · Hoja: {sheetName}
            </p>
            <p>
              <strong>
                {data.preview.table.row_count} filas de datos ·{' '}
                {data.preview.table.column_count} columnas
              </strong>{' '}
              · Rango {data.preview.table.extraction.range}
            </p>
            <div
              className="rp-dataset-scroll"
              tabIndex={0}
              role="region"
              aria-label="Vista previa de la tabla"
            >
              <table>
                <thead>
                  <tr>
                    {data.preview.table.columns.map((c) => (
                      <th key={c.id} scope="col">
                        {c.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.preview.rows.map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j}>
                          {cell ?? <span className="rp-hint">Sin valor</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="rp-hint">
              Vista previa: {data.preview.rows.length} filas, de{' '}
              {data.preview.table.row_count} procesadas completamente. Abrir
              esta tabla conserva el dataset activo de las herramientas
              anteriores.
            </p>
            {data.preview.table.warnings?.map((warning) => (
              <p key={warning} className="rp-hint">
                {warning}
              </p>
            ))}
            <details className="rp-technical">
              <summary>Procedencia de la tabla</summary>
              <p>
                Extracción{' '}
                {data.preview.table.extraction.confirmation
                  ? 'confirmada por ti'
                  : 'automática'}{' '}
                · encabezado en fila {data.preview.table.extraction.header_row}{' '}
                · algoritmo {data.preview.table.extraction.algorithm_version}
              </p>
              <p className="source-hash">
                Contenido: {data.preview.table.content_hash}
              </p>
            </details>
            <TableContextEditor
              initial={data.context}
              table={data.preview.table as Table}
              api={api}
              onSaved={(context) => {
                resource.setData({ ...data, context });
                onSaved(context);
              }}
            />
            {onReview && (
              <button onClick={onReview}>
                Revisar datos y definir variables de esta tabla
              </button>
            )}
          </>
        )
      )}
    </section>
  );
}
