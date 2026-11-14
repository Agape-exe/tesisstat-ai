import { useState } from 'react';
import {
  SourcesError,
  type ContextChanges,
  type ContextField,
  type SourcesApi,
  type Table,
  type TableContext,
} from './api';

const contextFields: [ContextField, string][] = [
  ['name', 'Nombre comprensible'],
  ['description', 'Qué contiene'],
  ['purpose', 'Para qué se utilizará'],
  ['row_meaning', 'Qué representa cada fila'],
  ['measurement_moment', 'Momento de medición'],
  ['population', 'Grupo o población descrita'],
  ['identifier_column_id', 'Columna identificadora'],
  ['related_tables_notes', 'Relación con otras tablas'],
];

export function TableContextEditor({
  initial,
  table,
  api,
  onSaved,
}: {
  initial: TableContext;
  table: Table;
  api: SourcesApi;
  onSaved: (context: TableContext) => void;
}) {
  const [saved, setSaved] = useState(initial);
  const [changes, setChanges] = useState<ContextChanges>({});
  const [confirm, setConfirm] = useState<ContextField[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [remote, setRemote] = useState<TableContext | null>(null);
  const dirty = Object.keys(changes).length > 0 || confirm.length > 0;

  function edit(name: ContextField, value: string) {
    setChanges((previous) => ({ ...previous, [name]: value || null }));
    if (!value.trim() || value === 'unknown')
      setConfirm((fields) => fields.filter((field) => field !== name));
    setNotice('');
  }
  async function save() {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const updated = await api.patchContext(table.project_id, table.id, {
        expected_revision: saved.revision,
        changes,
        confirm_fields: confirm.map((name) => `/${name}`),
      });
      setSaved(updated);
      setChanges({});
      setConfirm([]);
      setRemote(null);
      setNotice('Contexto guardado en el servidor.');
      onSaved(updated);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar.');
      if (cause instanceof SourcesError && cause.status === 409) {
        try {
          setRemote(await api.context(table.project_id, table.id));
        } catch {
          setError(
            'Hay un conflicto. Tu borrador se conserva; reintenta para comparar.',
          );
        }
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Contexto de la tabla" className="source-context">
      <h3>Contexto de esta tabla</h3>
      <p className="rp-hint">
        Opcional. Puedes inspeccionar los datos sin completarlo. Los nombres
        «Antes» y «Después» no confirman emparejamiento. Las relaciones que
        describas aquí no combinan tablas.
      </p>
      <p>
        Revisión {saved.revision} ·{' '}
        {dirty ? 'Borrador sin guardar' : 'Sin cambios pendientes'}
      </p>
      {remote && (
        <div role="alert" className="source-conflict">
          <h4>Otra edición guardó la revisión {remote.revision}</h4>
          <p>Tu borrador sigue aquí. Compara antes de volver a guardar.</p>
          <dl>
            {contextFields
              .filter(([name]) => name in changes || confirm.includes(name))
              .map(([name, label]) => (
                <div key={name}>
                  <dt>{label}</dt>
                  <dd>Servidor: {remote[name].value ?? 'Sin especificar'}</dd>
                  <dd>
                    Tu borrador:{' '}
                    {name in changes
                      ? (changes[name] ?? 'Sin especificar')
                      : (saved[name].value ?? 'Sin especificar')}
                  </dd>
                </div>
              ))}
          </dl>
          <div className="rp-actions">
            <button
              type="button"
              className="rp-secondary"
              onClick={() => {
                setChanges((draft) => ({
                  ...Object.fromEntries(
                    confirm
                      .filter((name) => !(name in draft))
                      .map((name) => [name, saved[name].value ?? null]),
                  ),
                  ...draft,
                }));
                setSaved(remote);
                setRemote(null);
                setError('');
                setNotice(
                  'Revisión actual cargada. Tu borrador conserva solo los campos editados; pulsa Guardar cuando termines de comparar.',
                );
              }}
            >
              Conservar borrador sobre revisión actual
            </button>
            <button
              type="button"
              className="rp-secondary"
              onClick={() => {
                setSaved(remote);
                setChanges({});
                setConfirm([]);
                setRemote(null);
                setError('');
              }}
            >
              Descartar borrador y cargar servidor
            </button>
          </div>
        </div>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <div className="source-context-grid">
          {contextFields.map(([name, label]) => {
            const value =
              name in changes
                ? (changes[name] ?? '')
                : (saved[name].value ?? '');
            const known = !!value && value !== 'unknown';
            const changed =
              name in changes && changes[name] !== saved[name].value;
            return (
              <div key={name} className="source-context-field">
                <label
                  className="rp-field"
                  htmlFor={`table-${table.id}-${name}`}
                >
                  {label}
                  {name === 'measurement_moment' ? (
                    <select
                      id={`table-${table.id}-${name}`}
                      value={value || 'unknown'}
                      disabled={busy}
                      onChange={(e) => edit(name, e.target.value)}
                    >
                      <option value="unknown">Sin especificar</option>
                      <option value="before">Antes</option>
                      <option value="after">Después</option>
                      <option value="other">Otro</option>
                    </select>
                  ) : name === 'identifier_column_id' ? (
                    <select
                      id={`table-${table.id}-${name}`}
                      value={value}
                      disabled={busy}
                      onChange={(e) => edit(name, e.target.value)}
                    >
                      <option value="">Sin identificar / desconocida</option>
                      {table.columns.map((column) => (
                        <option key={column.id} value={column.id}>
                          {column.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <textarea
                      id={`table-${table.id}-${name}`}
                      rows={name === 'name' ? 1 : 2}
                      maxLength={name === 'name' ? 200 : 2000}
                      value={value}
                      disabled={busy}
                      onChange={(e) => edit(name, e.target.value)}
                    />
                  )}
                </label>
                <span
                  className={`rp-field-status ${
                    !changed && saved[name].confirmation
                      ? 'status-confirmed'
                      : known
                        ? 'status-unconfirmed'
                        : 'status-empty'
                  }`}
                >
                  {!changed && saved[name].confirmation
                    ? '✓ Confirmado por ti'
                    : known
                      ? '● Sin confirmar'
                      : '○ Sin especificar'}
                </span>
                <label className="source-confirm">
                  <input
                    type="checkbox"
                    checked={confirm.includes(name)}
                    disabled={busy || !known}
                    onChange={(e) =>
                      setConfirm((fields) =>
                        e.target.checked
                          ? [...fields, name]
                          : fields.filter((field) => field !== name),
                      )
                    }
                  />
                  Confirmar {label.toLowerCase()}
                </label>
              </div>
            );
          })}
        </div>
        <p className="rp-hint">
          Guardar conserva lo no modificado. Marca únicamente los campos que has
          revisado. Este contexto describe esta tabla; las relaciones y
          comparaciones se revisan por separado en cada análisis.
        </p>
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
        <button type="submit" disabled={busy || !dirty || !!remote}>
          {busy ? 'Guardando…' : 'Guardar contexto de tabla'}
        </button>
      </form>
    </section>
  );
}
