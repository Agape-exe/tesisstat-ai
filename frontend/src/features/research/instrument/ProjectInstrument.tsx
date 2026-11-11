import { useEffect, useState, useRef } from 'react';
import { createDataApi, type Dataset } from '../data/api';
import { navigateProject } from '../projects/navigation';
import { SourcesError } from '../sources/api';
import { InstrumentEditor } from './InstrumentEditor';
import { InstrumentReview } from './InstrumentReview';
import {
  blank,
  createInstrumentApi,
  fromInstrument,
  type Instrument,
  type Mapping,
  type Structure,
  type ScorePreview,
  type Score,
  type Edit,
} from './api';
import './instrument.css';
const api = createInstrumentApi(),
  data = createDataApi();
export function ProjectInstrument({
  projectId,
  active = true,
}: {
  projectId: string;
  active?: boolean;
}) {
  const [instruments, setInstruments] = useState<Instrument[]>([]),
    [current, setCurrent] = useState<Instrument | null>(null);
  const initial = useState(blank)[0];
  const [draft, setDraft] = useState<Structure>(initial),
    [baseline, setBaseline] = useState(() =>
      JSON.stringify({ draft: initial, contextField: 'study_description' }),
    );
  const [contextField, setContextField] =
    useState<Edit['context_field']>('study_description');
  const [tables, setTables] = useState<Dataset[]>([]),
    [tableId, setTableId] = useState('');
  const [mapping, setMapping] = useState<Mapping | null>(null),
    [links, setLinks] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<Instrument[]>([]),
    [scores, setScores] = useState<Score[]>([]);
  const [preview, setPreview] = useState<ScorePreview | null>(null),
    [ruleId, setRuleId] = useState(''),
    [columnName, setColumnName] = useState('puntuacion');
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [message, setMessage] = useState('');
  const [conflict, setConflict] = useState<Instrument | null>(null);
  const key = `s05:${projectId}:${current?.instrument_id ?? 'new'}`;
  const dirty = JSON.stringify({ draft, contextField }) !== baseline;
  const mappingDirty =
    tableId !== mapping?.dataset_ref.id ||
    JSON.stringify(links) !==
      JSON.stringify(
        Object.fromEntries(
          (mapping?.item_columns ?? []).map((m) => [m.item_id, m.column_id]),
        ),
      );
  const selectedTable = tables.find((t) => t.id === tableId);
  useEffect(() => {
    if (!active) return;
    let live = true;
    Promise.all([api.list(projectId), data.tables(projectId)])
      .then(([items, ts]) => {
        if (live) {
          setInstruments(items);
          setTables(ts);
        }
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [projectId, active]);
  useEffect(() => {
    if (dirty)
      sessionStorage.setItem(key, JSON.stringify({ draft, contextField }));
  }, [key, draft, contextField, dirty]);
  const gate = useRef(false);
  async function run(action: () => Promise<void>) {
    if (gate.current) return;
    gate.current = true;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await action();
    } catch (cause) {
      setError(String(cause));
      if (cause instanceof SourcesError && cause.status === 409 && current)
        setConflict(await api.get(projectId, current.instrument_id));
    } finally {
      gate.current = false;
      setBusy(false);
    }
  }
  function apply(i: Instrument | null) {
    const value = i ? fromInstrument(i) : blank(),
      field = i?.context_field ?? 'study_description';
    setCurrent(i);
    setDraft(value);
    setContextField(field);
    setBaseline(JSON.stringify({ draft: value, contextField: field }));
    setPreview(null);
    setConflict(null);
    setHistory([]);
    setScores([]);
    setMapping(null);
    setTableId('');
    setLinks({});
    setRuleId(i?.scoring_rules?.[0]?.scoring_rule_id ?? '');
  }
  async function load(i: Instrument) {
    apply(i);
    const [h, s, m] = await Promise.all([
      api.history(projectId, i.instrument_id),
      api.scores(projectId, i.instrument_id),
      api.mapping(projectId, i.instrument_id).catch((e) => {
        if (e instanceof SourcesError && e.status === 404) return null;
        throw e;
      }),
    ]);
    setHistory(h);
    setScores(s);
    setMapping(m);
    if (m) {
      setTableId(m.dataset_ref.id);
      setLinks(
        Object.fromEntries(m.item_columns.map((x) => [x.item_id, x.column_id])),
      );
    }
  }
  return (
    <section
      aria-label="Instrumento de investigación"
      className="instrument-workspace"
    >
      <h2>Instrumento y puntuaciones</h2>
      <p>
        Este recorrido es opcional. Puedes describir, relacionar o comparar
        otros datos sin definir un instrumento.
      </p>
      <p>
        Define y revisa → relaciona respuestas → previsualiza → confirma datos
        derivados → solicita confiabilidad en Análisis.
      </p>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <div className="instrument-row">
        <label className="rp-field">
          Instrumento guardado
          <select
            value={current?.instrument_id ?? ''}
            disabled={busy}
            onChange={(e) => {
              const i = instruments.find(
                (i) => i.instrument_id === e.target.value,
              );
              if (i) void run(() => load(i));
              else apply(null);
            }}
          >
            <option value="">Nuevo instrumento</option>
            {instruments.map((i) => (
              <option key={i.instrument_id} value={i.instrument_id}>
                {i.variables[0]?.name} · revisión {i.revision} ·{' '}
                {i.status === 'reviewed'
                  ? 'revisado'
                  : i.status === 'stale'
                    ? 'desactualizado'
                    : 'borrador'}
              </option>
            ))}
          </select>
        </label>
        <button disabled={busy} onClick={() => apply(null)}>
          Nuevo instrumento
        </button>
        <button
          disabled={busy}
          onClick={() => {
            try {
              const saved = sessionStorage.getItem(key);
              if (saved) {
                const s = JSON.parse(saved);
                setDraft(s.draft);
                setContextField(s.contextField);
                setMessage(
                  'Borrador local recuperado. Revísalo antes de guardar.',
                );
              } else setMessage('No hay borrador local pendiente.');
            } catch {
              setError('No se pudo recuperar el borrador.');
            }
          }}
        >
          Recuperar borrador local
        </button>
      </div>
      {current && (
        <button
          disabled={busy}
          onClick={() =>
            void run(async () => {
              await load(await api.get(projectId, current.instrument_id));
              setInstruments(await api.list(projectId));
              setTables(await data.tables(projectId));
            })
          }
        >
          Actualizar revisión guardada (conservar borrador local)
        </button>
      )}
      {conflict && (
        <div role="alert">
          <p>
            Hay una revisión más reciente ({conflict.revision}). Tu borrador
            sigue disponible; cargar la revisión no sobrescribe el borrador
            guardado en este navegador.
          </p>
          <details>
            <summary>Comparar revisión del servidor</summary>
            <InstrumentReview value={conflict} />
          </details>
          <button onClick={() => void run(() => load(conflict))}>
            Cargar revisión del servidor
          </button>
          <button
            onClick={() => {
              setCurrent(conflict);
              setConflict(null);
              setMessage(
                'Base actualizada. Compara tu borrador con el historial antes de guardarlo.',
              );
            }}
          >
            Conservar mi borrador sobre la nueva revisión
          </button>
        </div>
      )}
      <details open={!current || current.status !== 'reviewed'}>
        <summary>
          1. Definir o revisar el instrumento
          {current ? ` · revisión ${current.revision}` : ''}
        </summary>
        <fieldset disabled={busy}>
          <InstrumentEditor
            value={draft}
            change={(s) => {
              setDraft(s);
              setPreview(null);
            }}
          />
          <label className="rp-field">
            Contexto pertinente que revisarás
            <select
              value={contextField}
              onChange={(e) =>
                setContextField(e.target.value as Edit['context_field'])
              }
            >
              <option value="study_description">Descripción del estudio</option>
              <option value="data_description">Descripción de los datos</option>
              <option value="research_question">
                Pregunta de investigación
              </option>
              <option value="main_objective">Objetivo principal</option>
            </select>
          </label>
          <p>
            Para revisar, confirma únicamente ese campo pertinente en Contexto.
            No se requiere documento, hipótesis ni completar todo el contexto.
            Editar un instrumento revisado deja una nueva revisión pendiente.
          </p>
          <button
            onClick={() =>
              void run(async () => {
                const i = await api.save(
                  projectId,
                  current?.instrument_id ?? null,
                  {
                    expected_revision: current?.revision ?? 0,
                    structure: draft,
                    context_field: contextField,
                  },
                );
                sessionStorage.removeItem(key);
                await load(i);
                setInstruments(await api.list(projectId));
                setMessage(
                  'Borrador guardado; falta revisarlo explícitamente.',
                );
              })
            }
          >
            Guardar borrador del instrumento
          </button>
          <button
            disabled={!current || dirty || current.status === 'reviewed'}
            onClick={() =>
              void run(async () => {
                const i = await api.confirm(projectId, current!);
                await load(i);
                setInstruments(await api.list(projectId));
                setMessage(
                  'Estructura y reglas revisadas. Confirma la correspondencia aparte.',
                );
              })
            }
          >
            Confirmar revisión de estructura y reglas
          </button>
          <button
            className="rp-secondary"
            onClick={() => navigateProject(projectId, 'context')}
          >
            Revisar contexto pertinente
          </button>
        </fieldset>
      </details>
      {current && (
        <>
          <fieldset disabled={busy || dirty}>
            <legend>2. Relacionar ítems con columnas</legend>
            <p>
              Elige cada correspondencia. No se asocia por parecido de nombres.
              Debes cubrir todos los ítems, con columnas distintas y sin
              identificadores.
            </p>
            <label className="rp-field">
              Tabla de respuestas
              <select
                aria-label="Tabla de respuestas"
                value={tableId}
                onChange={(e) => {
                  setTableId(e.target.value);
                  setLinks({});
                  setPreview(null);
                }}
              >
                <option value="">Elegir tabla</option>
                {tables.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} · {t.row_count} filas
                  </option>
                ))}
              </select>
            </label>
            {current.items.map((i) => (
              <label className="rp-field" key={i.item_id}>
                {i.text}
                <select
                  aria-label={i.text}
                  value={links[i.item_id] ?? ''}
                  onChange={(e) => {
                    setLinks({ ...links, [i.item_id]: e.target.value });
                    setPreview(null);
                  }}
                >
                  <option value="">Sin relacionar</option>
                  {selectedTable?.columns.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <p>
              Correspondencia:{' '}
              {mapping?.status === 'confirmed' && !mappingDirty
                ? 'confirmada'
                : mapping?.status === 'stale'
                  ? 'desactualizada'
                  : 'pendiente'}
            </p>
            {([false, true] as const).map((confirm) => (
              <button
                key={String(confirm)}
                disabled={
                  !selectedTable || (confirm && current.status !== 'reviewed')
                }
                onClick={() =>
                  void run(async () => {
                    const m = await api.map(projectId, current.instrument_id, {
                      expected_revision: mapping?.revision ?? 0,
                      instrument_revision: current.revision,
                      dataset_id: selectedTable!.id,
                      dataset_revision: selectedTable!.revision,
                      item_columns: Object.entries(links)
                        .filter(([, c]) => c)
                        .map(([item_id, column_id]) => ({
                          item_id,
                          column_id,
                        })),
                      confirm,
                    });
                    setMapping(m);
                    setPreview(null);
                    setMessage(
                      confirm
                        ? 'Correspondencia confirmada.'
                        : 'Correspondencia guardada como borrador.',
                    );
                  })
                }
              >
                {confirm
                  ? 'Confirmar correspondencia completa'
                  : 'Guardar correspondencia pendiente'}
              </button>
            ))}
          </fieldset>
          <fieldset
            disabled={
              busy ||
              dirty ||
              mappingDirty ||
              mapping?.status !== 'confirmed' ||
              current.status !== 'reviewed'
            }
          >
            <legend>3. Previsualizar puntuación</legend>
            <label className="rp-field">
              Regla y conjunto de ítems
              <select
                value={ruleId}
                onChange={(e) => {
                  setRuleId(e.target.value);
                  setPreview(null);
                }}
              >
                <option value="">Elegir regla</option>
                {current.scoring_rules.map((r, n) => (
                  <option key={r.scoring_rule_id} value={r.scoring_rule_id}>
                    Regla {n + 1} ·{' '}
                    {r.aggregation === 'sum' ? 'Suma' : 'Promedio'} ·{' '}
                    {r.item_ids.length} ítems
                  </option>
                ))}
              </select>
            </label>
            <label className="rp-field">
              Nombre de la nueva columna
              <input
                value={columnName}
                maxLength={128}
                onChange={(e) => {
                  setColumnName(e.target.value);
                  setPreview(null);
                }}
              />
            </label>
            <button
              disabled={!ruleId || !columnName}
              onClick={() =>
                void run(async () =>
                  setPreview(
                    await api.preview(projectId, current.instrument_id, {
                      expected_revision: current.revision,
                      mapping_revision: mapping!.revision,
                      scoring_rule_id: ruleId,
                      column_name: columnName,
                      confirm: true,
                    }),
                  ),
                )
              }
            >
              Solicitar vista previa de puntuación
            </button>
          </fieldset>
          {preview && (
            <div aria-label="Vista previa de puntuación">
              <h3>4. Revisar y confirmar datos derivados</h3>
              <p>
                {preview.counts.total} filas; {preview.counts.valid} puntuadas;{' '}
                {preview.counts.missing} con faltantes; {preview.counts.unknown}{' '}
                con respuestas desconocidas; {preview.counts.out_of_range} fuera
                de rango. Los conteos de problemas pueden coincidir en una fila.
              </p>
              <p>
                Primeras {preview.bounded_preview.length} filas:{' '}
                {preview.bounded_preview
                  .map((v) => (v === null ? 'sin puntuación' : String(v)))
                  .join(' · ')}
              </p>
              <ul>
                {[...preview.warnings, ...preview.exclusions].map((w, n) => (
                  <li key={n}>{w}</li>
                ))}
              </ul>
              <p>
                Vence: {new Date(preview.expires_at).toLocaleString()}. Se
                conservarán todas las filas y originales. El derivado requiere
                selección y revisión de diccionario antes de otros análisis.
              </p>
              <button
                disabled={busy || dirty || mappingDirty}
                onClick={() =>
                  void run(async () => {
                    const requestKey = `s05-score:${preview.id}`,
                      requestId =
                        sessionStorage.getItem(requestKey) ??
                        crypto.randomUUID();
                    sessionStorage.setItem(requestKey, requestId);
                    await api.score(
                      projectId,
                      current.instrument_id,
                      preview,
                      requestId,
                    );
                    setScores(
                      await api.scores(projectId, current.instrument_id),
                    );
                    setTables(await data.tables(projectId));
                    setMessage(
                      'Datos derivados publicados. Puedes seleccionarlos y revisar su diccionario en Datos.',
                    );
                  })
                }
              >
                Confirmar creación de datos derivados
              </button>
            </div>
          )}
          {!!scores.length && (
            <div>
              <h3>Puntuaciones publicadas</h3>
              <ul>
                {scores.map((s) => (
                  <li key={s.id}>
                    {s.derived_dataset_ref.name} · {s.counts.total} filas ·{' '}
                    {s.counts.valid} puntuadas ·{' '}
                    {new Date(s.confirmed_at).toLocaleString()} (histórico;
                    vigencia comprobada al usar)
                  </li>
                ))}
              </ul>
              <button onClick={() => navigateProject(projectId, 'datasets')}>
                Seleccionar derivado y revisar diccionario
              </button>
            </div>
          )}
          <h3>5. Solicitar confiabilidad desde Análisis</h3>
          <p>
            Elige el constructo y la regla pertinentes en Análisis, revisa los
            casos completos, solicita propuesta y aprueba antes de ejecutar.
            Alfa se calcula sobre ítems recodificados, nunca sobre la columna
            total. No demuestra validez ni unidimensionalidad.
          </p>
          <button onClick={() => navigateProject(projectId, 'analysis')}>
            Ir a Análisis
          </button>
          <details>
            <summary>Historial del instrumento ({history.length})</summary>
            <ul>
              {history.map((i) => (
                <li key={i.revision}>
                  <details>
                    <summary>
                      Revisión {i.revision} · {i.status} ·{' '}
                      {new Date(i.updated_at).toLocaleString()}
                    </summary>
                    <InstrumentReview value={i} />
                  </details>
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
    </section>
  );
}
