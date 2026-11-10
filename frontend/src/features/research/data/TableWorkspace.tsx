import { DataPreview } from './DataPreview';
import { useCallback, useState } from 'react';
import { useReadResource } from '../projects/useReadResource';
import { navigateProject } from '../projects/navigation';
import { createDataApi, type DataApi, type Profile } from './api';
import { DictionaryEditor } from './DictionaryEditor';
import { PreparationEditor } from './PreparationEditor';
import './data.css';

const defaultApi = createDataApi();
export function TableWorkspace({
  projectId,
  tableId,
  active,
  onSelect,
  onContext,
  api = defaultApi,
}: {
  projectId: string;
  tableId: string | null;
  active: boolean;
  onSelect: (id: string) => void;
  onContext: (id: string) => void;
  api?: DataApi;
}) {
  const load = useCallback(async () => {
    const [tables, summary] = await Promise.all([
      api.tables(projectId),
      api.summary(projectId),
    ]);
    return { tables, summary };
  }, [api, projectId]);
  const resource = useReadResource(load, active);
  const dataset = resource.data?.tables.find((t) => t.id === tableId);
  return (
    <section
      className="source-workspace data-workspace"
      aria-label="Revisión de datos y variables"
    >
      <h2>Revisar datos</h2>
      <p>
        Explora y define las variables de cada tabla. Preparar o combinar es
        opcional; no necesitas documentos ni hipótesis.
      </p>
      <label className="rp-field">
        Tabla para revisar
        <select
          value={dataset?.id ?? ''}
          onChange={(e) => onSelect(e.target.value)}
        >
          <option value="">Elegir tabla</option>
          {resource.data?.tables.map((t) => (
            <option key={t.id} value={t.id}>
              {t.kind === 'derived' ? 'Derivado · ' : ''}
              {t.name} · {t.row_count} filas
            </option>
          ))}
        </select>
      </label>
      {resource.loading && <p role="status">Consultando tablas…</p>}
      {resource.error && (
        <p role="alert" className="rp-error">
          {resource.error}{' '}
          <button onClick={resource.reload}>Reintentar tablas</button>
        </p>
      )}
      {resource.data && !resource.data.tables.length && (
        <p>Aún no hay tablas. Importa tus archivos desde Archivos y tablas.</p>
      )}
      {resource.data && (
        <ul className="data-inventory">
          {resource.data.summary.tables.map((t) => (
            <li key={t.id}>
              <button className="rp-link" onClick={() => onSelect(t.id)}>
                {t.name}
              </button>{' '}
              · {t.kind === 'derived' ? 'derivado' : 'importada'} · perfil{' '}
              {t.profile === 'current'
                ? 'vigente'
                : t.profile === 'stale'
                  ? 'desactualizado'
                  : 'pendiente'}{' '}
              · {t.confirmed_variables}/{t.variables} variables confirmadas
              {!t.usable ? ' · fuentes desactualizadas' : ''}
            </li>
          ))}
        </ul>
      )}
      {dataset && (
        <TableReview
          key={`${projectId}:${dataset.id}`}
          projectId={projectId}
          tableId={dataset.id}
          tables={resource.data!.tables}
          api={api}
          onCreated={(id) => {
            resource.reload();
            onSelect(id);
          }}
          onChanged={resource.reload}
          onContext={() => onContext(dataset.id)}
        />
      )}
      <div className="rp-surface data-continue">
        <h3>Continuar a Análisis</h3>
        <p>
          No necesitas transformar datos que ya están listos. Análisis permite
          guardar preguntas y solicitar diagnósticos para estas tablas. Las
          nuevas propuestas y ejecución llegarán en S04B; el análisis actual
          conserva su recorrido documental v1.
        </p>
        <button onClick={() => navigateProject(projectId, 'analysis')}>
          Ir a Análisis
        </button>
      </div>
    </section>
  );
}
function TableReview({
  projectId,
  tableId,
  tables,
  api,
  onCreated,
  onChanged,
  onContext,
}: {
  projectId: string;
  tableId: string;
  tables: Awaited<ReturnType<DataApi['tables']>>;
  api: DataApi;
  onCreated: (id: string) => void;
  onChanged: () => void;
  onContext: () => void;
}) {
  const load = useCallback(async () => {
    const [preview, dictionary, profile] = await Promise.all([
      api.preview(projectId, tableId),
      api.dictionary(projectId, tableId),
      api.profile(projectId, tableId),
    ]);
    return { preview, dictionary, profile };
  }, [api, projectId, tableId]);
  const resource = useReadResource(load);
  const [tab, setTab] = useState<'review' | 'variables'>('review');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function compute() {
    if (!resource.data) return;
    setBusy(true);
    setError('');
    try {
      const profile = await api.compute(
        projectId,
        resource.data.preview.dataset_ref,
      );
      resource.setData({ ...resource.data, profile });
      onChanged();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo calcular el perfil.',
      );
    } finally {
      setBusy(false);
    }
  }
  if (resource.error)
    return (
      <div role="alert" className="rp-error">
        {resource.error}
        <button onClick={resource.reload}>Reintentar revisión</button>
      </div>
    );
  if (!resource.data || resource.loading)
    return <p role="status">Abriendo revisión de la tabla…</p>;
  const { preview, dictionary, profile } = resource.data;
  return (
    <section
      className="rp-surface"
      aria-label={`Revisar ${preview.dataset_ref.name}`}
    >
      <h3>{preview.dataset_ref.name}</h3>
      <p>
        {preview.dataset_ref.row_count} filas ·{' '}
        {preview.dataset_ref.columns.length} columnas
      </p>
      {preview.dataset_ref.kind === 'imported' && (
        <button className="rp-link" onClick={onContext}>
          Ver archivo, hoja y contexto de origen
        </button>
      )}
      <div className="rp-actions data-tabs">
        <button
          aria-pressed={tab === 'review'}
          onClick={() => setTab('review')}
        >
          Revisar datos
        </button>
        <button
          aria-pressed={tab === 'variables'}
          onClick={() => setTab('variables')}
        >
          Definir o confirmar variables
        </button>
      </div>
      <div hidden={tab !== 'review'}>
        <p>
          El perfil cuenta todas las filas. Calcularlo no confirma escalas ni
          completa la revisión.
        </p>
        <button disabled={busy} onClick={() => void compute()}>
          {busy
            ? 'Calculando…'
            : profile
              ? 'Recalcular perfil completo'
              : 'Calcular perfil completo'}
        </button>
        {error && (
          <p role="alert" className="rp-error">
            {error}
          </p>
        )}
        {!profile && <p>No hay perfil guardado para esta tabla.</p>}
        {profile && <ProfileView profile={profile} />}
        <details>
          <summary>
            Vista previa de las primeras {preview.rows.length} filas
          </summary>
          <DataPreview
            names={preview.dataset_ref.columns.map((c) => c.name)}
            rows={preview.rows}
          />
        </details>
      </div>
      <div hidden={tab !== 'variables'}>
        <DictionaryEditor
          initial={dictionary}
          api={api}
          onSaved={(updated) => {
            resource.setData({
              ...resource.data!,
              dictionary: updated,
              profile: profile ? { ...profile, state: 'stale' } : null,
            });
            onChanged();
          }}
        />
      </div>
      <details className="data-advanced">
        <summary>Preparar o combinar (opcional)</summary>
        <PreparationEditor
          projectId={projectId}
          dataset={preview.dataset_ref}
          tables={tables}
          api={api}
          onCreated={onCreated}
        />
      </details>
      {preview.dataset_ref.kind === 'derived' && (
        <DerivedEvidence projectId={projectId} tableId={tableId} api={api} />
      )}
    </section>
  );
}
function ProfileView({ profile: p }: { profile: Profile }) {
  return (
    <section aria-label="Perfil exploratorio completo">
      <h4>Perfil {p.state === 'current' ? 'vigente' : 'desactualizado'}</h4>
      {p.state === 'stale' && (
        <p role="status" className="rp-hint">
          Cambió la configuración o una fuente. Recalcula para disponer de
          evidencia vigente.
        </p>
      )}
      <dl className="data-counts">
        {[
          ['Filas', p.rows],
          ['Columnas', p.columns_count],
          ['Faltantes', p.missing],
          ['Duplicados', p.duplicates],
          ['Constantes', p.constant_columns],
          ['Columnas vacías', p.empty_columns],
        ].map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {p.warnings.map((w) => (
        <p className="rp-hint" key={w}>
          {w}
        </p>
      ))}
      {p.columns.map((c) => (
        <details key={c.column_id} className="data-profile-column">
          <summary>
            {c.name} · {c.present} presentes · {c.missing} faltantes ·
            almacenamiento sugerido:{' '}
            {
              (
                {
                  string: 'texto',
                  integer: 'entero',
                  number: 'número',
                  boolean: 'booleano',
                  date: 'fecha',
                  mixed: 'mixto',
                  unknown: 'desconocido',
                } as Record<string, string>
              )[c.storage_type]
            }
          </summary>
          <p>
            Escala:{' '}
            {
              (
                {
                  unknown: 'desconocida',
                  nominal: 'nominal',
                  ordinal: 'ordinal',
                  interval: 'intervalar',
                  ratio: 'razón',
                } as Record<string, string>
              )[c.measurement_scale ?? 'unknown']
            }
            . {c.distinct} valores distintos.{' '}
            {c.possible_identifier ? 'Posible identificador.' : ''}{' '}
            {c.formula_count ? `${c.formula_count} fórmulas como texto.` : ''}
          </p>
          {c.numeric_summary && (
            <dl className="data-counts">
              {Object.entries(c.numeric_summary).map(([k, v]) => (
                <div key={k}>
                  <dt>
                    {
                      (
                        {
                          min: 'Mínimo',
                          max: 'Máximo',
                          mean: 'Media',
                          median: 'Mediana',
                          sample_stdev: 'Desviación estándar muestral',
                        } as Record<string, string>
                      )[k]
                    }
                  </dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          )}
          <p>
            Frecuencias más comunes, hasta 10 categorías. Porcentaje sobre{' '}
            {c.present} valores presentes.
          </p>
          <ul>
            {c.frequencies?.map((f, i) => (
              <li key={i}>
                <code>{f.value}</code>: {f.count} ({f.percentage.toFixed(1)} %)
              </li>
            ))}
          </ul>
          {c.warnings?.map((w) => (
            <p key={w} className="rp-hint">
              {w}
            </p>
          ))}
        </details>
      ))}
      <details>
        <summary>Método, política y referencias</summary>
        <p>
          {p.method} · {p.engine_version} · revisión {p.revision} ·{' '}
          {new Date(p.created_at).toLocaleString('es-PE')}
        </p>
        <pre>
          {JSON.stringify(
            {
              missing_policy: p.missing_policy,
              source_refs: p.source_refs,
              dictionary_ref: p.dictionary_ref,
              hash: p.hash,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </section>
  );
}
function DerivedEvidence({
  projectId,
  tableId,
  api,
}: {
  projectId: string;
  tableId: string;
  api: DataApi;
}) {
  const load = useCallback(
    () => api.derived(projectId, tableId),
    [api, projectId, tableId],
  );
  const r = useReadResource(load);
  return (
    <details>
      <summary>Receta y trazabilidad del derivado</summary>
      {r.error && <p role="alert">{r.error}</p>}
      {r.data && (
        <>
          <p>
            Preparación confirmada. La interpretación y vínculos del derivado
            requieren revisión propia.
          </p>
          <pre>
            {JSON.stringify(
              {
                recipe: r.data.recipe,
                source_refs: r.data.source_refs,
                counts: r.data.counts,
                column_lineage: r.data.column_lineage,
                row_lineage_sample: r.data.row_lineage.slice(0, 20),
              },
              null,
              2,
            )}
          </pre>
          <p>
            La API conserva la correspondencia completa de las{' '}
            {r.data.row_lineage.length} filas.
          </p>
        </>
      )}
    </details>
  );
}
