import { useState } from 'react';
import type { DataApi, Dataset, Preview, Recipe } from './api';
import { DataPreview } from './DataPreview';

const operations = {
  rename_column: 'Renombrar columna',
  drop_columns: 'Eliminar columnas',
  drop_missing: 'Eliminar filas con faltantes',
  replace_missing: 'Reemplazar faltantes por un valor explícito',
  drop_duplicates: 'Eliminar filas duplicadas exactas',
} as const;
export function PreparationEditor({
  projectId,
  dataset,
  tables,
  api,
  onCreated,
}: {
  projectId: string;
  dataset: Dataset;
  tables: Dataset[];
  api: DataApi;
  onCreated: (id: string) => void;
}) {
  const [mode, setMode] = useState<'prepare' | 'join'>('join');
  const [rightId, setRightId] = useState('');
  const [leftKey, setLeftKey] = useState('');
  const [rightKey, setRightKey] = useState('');
  const [policy, setPolicy] = useState<'matches_only' | 'all_cases' | ''>('');
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<
    Record<string, { include: boolean; name: string }>
  >({});
  const [operation, setOperation] =
    useState<keyof typeof operations>('rename_column');
  const [column, setColumn] = useState('');
  const [newName, setNewName] = useState('');
  const [value, setValue] = useState('');
  const [steps, setSteps] = useState<
    NonNullable<Recipe['operations']>[number][]
  >([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [resultId, setResultId] = useState('');
  const right = tables.find((t) => t.id === rightId);
  function invalidate() {
    setPreview(null);
    setError('');
    setResultId('');
  }
  function choice(
    id: string,
    columnId: string,
    original: string,
    side: string,
  ) {
    return (
      selected[`${id}:${columnId}`] ?? {
        include: true,
        name: `${original}_${side}`,
      }
    );
  }
  function recipe(): Recipe {
    if (mode === 'prepare')
      return {
        kind: mode,
        name,
        left_table_id: dataset.id,
        operations: steps as Recipe['operations'],
      };
    return {
      kind: mode,
      name,
      left_table_id: dataset.id,
      right_table_id: rightId,
      left_key: leftKey,
      right_key: rightKey,
      unmatched_policy: policy || null,
      columns: [dataset, ...(right ? [right] : [])].flatMap((table, index) =>
        table.columns
          .filter(
            (c) =>
              choice(table.id, c.id, c.name, index ? 'derecha' : 'izquierda')
                .include,
          )
          .map((c) => ({
            table_id: table.id,
            column_id: c.id,
            name: choice(
              table.id,
              c.id,
              c.name,
              index ? 'derecha' : 'izquierda',
            ).name,
          })),
      ),
    };
  }
  async function calculate() {
    setBusy(true);
    invalidate();
    try {
      setPreview(await api.prepare(projectId, recipe()));
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'No se pudo previsualizar.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function apply() {
    if (!preview) return;
    setBusy(true);
    setError('');
    try {
      const result = await api.apply(projectId, preview);
      setResultId(result.id);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo guardar. Reintenta la misma confirmación.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Preparación opcional">
      <h3>Preparar o combinar, solo si hace falta</h3>
      <p>
        Si tus datos ya están listos, continúa a Análisis. Cada cambio crea otra
        tabla; los originales permanecen intactos.
      </p>
      <fieldset
        disabled={busy || !!resultId}
        className="data-dictionary-fields"
      >
        <div className="data-form-grid">
          <label className="rp-field">
            Operación
            <select
              value={mode}
              onChange={(e) => {
                setMode(e.target.value as typeof mode);
                invalidate();
              }}
            >
              <option value="join">
                Combinar por identificador (uno a uno)
              </option>
              <option value="prepare">Preparar una tabla</option>
            </select>
          </label>
          <label className="rp-field">
            Nombre de la nueva tabla
            <input
              maxLength={200}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                invalidate();
              }}
            />
          </label>
        </div>
        {mode === 'join' ? (
          <>
            <p>
              Tabla izquierda: <strong>{dataset.name}</strong>
            </p>
            <div className="data-form-grid">
              <label className="rp-field">
                Tabla derecha
                <select
                  value={rightId}
                  onChange={(e) => {
                    setRightId(e.target.value);
                    setRightKey('');
                    invalidate();
                  }}
                >
                  <option value="">Elegir otra tabla</option>
                  {tables
                    .filter((t) => t.id !== dataset.id)
                    .map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                </select>
              </label>
              <label className="rp-field">
                Identificador izquierdo
                <select
                  value={leftKey}
                  onChange={(e) => {
                    setLeftKey(e.target.value);
                    invalidate();
                  }}
                >
                  <option value="">Elegir columna</option>
                  {dataset.columns.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="rp-field">
                Identificador derecho
                <select
                  value={rightKey}
                  onChange={(e) => {
                    setRightKey(e.target.value);
                    invalidate();
                  }}
                >
                  <option value="">Elegir columna</option>
                  {right?.columns.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="rp-field">
                Casos sin correspondencia
                <select
                  value={policy}
                  onChange={(e) => {
                    setPolicy(e.target.value as typeof policy);
                    invalidate();
                  }}
                >
                  <option value="">Elegir política</option>
                  <option value="matches_only">Solo coincidencias</option>
                  <option value="all_cases">Conservar todos los casos</option>
                </select>
              </label>
            </div>
            <p className="rp-hint">
              Se compara el texto exacto: 001 y 1 son distintos, igual que A y a
              o espacios exteriores. Los marcadores de faltantes del diccionario
              se excluyen de las claves. Nunca se empareja por posición ni se
              rellenan notas con cero.
            </p>
            {[dataset, ...(right ? [right] : [])].map((table, index) => (
              <div key={table.id}>
                <h4>Columnas de {index ? 'la derecha' : 'la izquierda'}</h4>
                {table.columns.map((c) => {
                  const key = `${table.id}:${c.id}`;
                  const current = choice(
                    table.id,
                    c.id,
                    c.name,
                    index ? 'derecha' : 'izquierda',
                  );
                  return (
                    <div className="data-output" key={c.id}>
                      <label>
                        <input
                          type="checkbox"
                          checked={current.include}
                          onChange={(e) => {
                            setSelected((s) => ({
                              ...s,
                              [key]: { ...current, include: e.target.checked },
                            }));
                            invalidate();
                          }}
                        />
                        Conservar {c.name}
                      </label>
                      <label className="rp-field">
                        Nombre de salida de {c.name} (
                        {index ? 'derecha' : 'izquierda'})
                        <input
                          disabled={!current.include}
                          value={current.name}
                          maxLength={200}
                          onChange={(e) => {
                            setSelected((s) => ({
                              ...s,
                              [key]: { ...current, name: e.target.value },
                            }));
                            invalidate();
                          }}
                        />
                      </label>
                    </div>
                  );
                })}
              </div>
            ))}
          </>
        ) : (
          <>
            <p>
              Los marcadores de faltantes se toman del diccionario de esta
              tabla. Revisa la vista previa antes de confirmar una eliminación o
              reemplazo.
            </p>
            <div className="data-form-grid">
              <label className="rp-field">
                Transformación
                <select
                  value={operation}
                  onChange={(e) =>
                    setOperation(e.target.value as typeof operation)
                  }
                >
                  {Object.entries(operations).map(([id, title]) => (
                    <option value={id} key={id}>
                      {title}
                    </option>
                  ))}
                </select>
              </label>
              {operation !== 'drop_duplicates' && (
                <label className="rp-field">
                  Columna a preparar
                  <select
                    value={column}
                    onChange={(e) => setColumn(e.target.value)}
                  >
                    <option value="">Elegir columna</option>
                    {dataset.columns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {operation === 'rename_column' && (
                <label className="rp-field">
                  Nuevo nombre
                  <input
                    value={newName}
                    maxLength={200}
                    onChange={(e) => setNewName(e.target.value)}
                  />
                </label>
              )}
              {operation === 'replace_missing' && (
                <label className="rp-field">
                  Valor de reemplazo
                  <input
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                  />
                </label>
              )}
            </div>
            <button
              className="rp-secondary"
              disabled={
                steps.length >= 20 ||
                (operation !== 'drop_duplicates' && !column)
              }
              onClick={() => {
                setSteps((s) => [
                  ...s,
                  {
                    type: operation,
                    ...(operation !== 'drop_duplicates'
                      ? { column_ids: [column] }
                      : {}),
                    ...(operation === 'rename_column'
                      ? { new_name: newName }
                      : {}),
                    ...(operation === 'replace_missing' ? { value } : {}),
                  },
                ]);
                invalidate();
              }}
            >
              Añadir paso a la receta
            </button>
            <ol>
              {steps.map((s, i) => (
                <li key={i}>
                  {operations[s.type]} {s.new_name ?? ''}
                  <button
                    className="rp-link"
                    onClick={() => {
                      setSteps((list) => list.filter((_, n) => n !== i));
                      invalidate();
                    }}
                  >
                    Quitar paso {i + 1}
                  </button>
                </li>
              ))}
            </ol>
          </>
        )}
        <button
          disabled={
            !name.trim() ||
            (mode === 'join'
              ? !rightId || !leftKey || !rightKey || !policy
              : !steps.length)
          }
          onClick={() => void calculate()}
        >
          {busy ? 'Calculando…' : 'Ver vista previa y conteos'}
        </button>
      </fieldset>
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      {preview && (
        <section className="rp-surface" aria-label="Resultado previsto">
          <h4>Revisar antes de confirmar</h4>
          <dl className="data-counts">
            {Object.entries(preview.counts).map(([key, value]) => (
              <div key={key}>
                <dt>{countLabels[key] ?? key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          {!!preview.unmatched_left.length && (
            <p>
              Sin pareja en la izquierda: filas de datos{' '}
              {preview.unmatched_left.slice(0, 20).join(', ')}
              {preview.unmatched_left.length > 20 ? '…' : ''}.
            </p>
          )}
          {!!preview.unmatched_right.length && (
            <p>
              Sin pareja en la derecha: filas de datos{' '}
              {preview.unmatched_right.slice(0, 20).join(', ')}
              {preview.unmatched_right.length > 20 ? '…' : ''}.
            </p>
          )}
          {preview.warnings.map((w) => (
            <p className="rp-hint" key={w}>
              {w}
            </p>
          ))}
          {preview.blockers.map((w) => (
            <p className="rp-error" role="alert" key={w}>
              {w}
            </p>
          ))}
          <DataPreview names={preview.result_columns} rows={preview.rows} />
          <details>
            <summary>Receta y fuentes de la vista previa</summary>
            <pre>
              {JSON.stringify(
                { recipe: preview.recipe, source_refs: preview.source_refs },
                null,
                2,
              )}
            </pre>
          </details>
          <p>
            La vista previa vence en 30 minutos y se valida otra vez al
            confirmar. Combinar no confirma la población, el diseño ni una
            mejora.
          </p>
          <button
            disabled={busy || !!preview.blockers.length || !!resultId}
            onClick={() => void apply()}
          >
            {busy ? 'Guardando…' : 'Confirmar y crear nueva tabla'}
          </button>
        </section>
      )}
      {preview && !!preview.unmatched_left_rows?.length && (
        <details>
          <summary>Ver casos sin pareja de la izquierda (hasta 20)</summary>
          <DataPreview
            names={dataset.columns.map((c) => c.name)}
            rows={preview.unmatched_left_rows}
          />
        </details>
      )}
      {preview && !!preview.unmatched_right_rows?.length && right && (
        <details>
          <summary>Ver casos sin pareja de la derecha (hasta 20)</summary>
          <DataPreview
            names={right.columns.map((c) => c.name)}
            rows={preview.unmatched_right_rows}
          />
        </details>
      )}
      {resultId && (
        <div role="status" className="rp-success">
          <p>
            Nueva tabla guardada. Revisa sus variables y vínculos; las
            confirmaciones de las fuentes no se heredan.
          </p>
          <button onClick={() => onCreated(resultId)}>
            Abrir tabla derivada
          </button>
        </div>
      )}
    </section>
  );
}
const countLabels: Record<string, string> = {
  left_rows: 'Filas izquierda',
  right_rows: 'Filas derecha',
  matches: 'Coincidencias',
  left_only: 'Exclusivos izquierda',
  right_only: 'Exclusivos derecha',
  left_missing_keys: 'Claves faltantes izquierda',
  right_missing_keys: 'Claves faltantes derecha',
  left_duplicate_keys: 'Claves duplicadas izquierda',
  right_duplicate_keys: 'Claves duplicadas derecha',
  result_rows: 'Filas del resultado',
  result_columns: 'Columnas del resultado',
  rows_removed: 'Filas eliminadas',
};
