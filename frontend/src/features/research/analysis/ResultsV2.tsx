import { useCallback, useEffect, useRef, useState } from 'react';
import { useReadResource } from '../projects/useReadResource';
import { navigateWorkspace } from '../projects/navigation';
import { createAnalysisV2Api, techniqueLabels, type Result } from './v2api';
import type { ResultPresentationV2 } from '../../../shared/contracts/generated/v2/ResultPresentationV2';
import type {
  ResultFiguresV2,
  ResultFigureDataV2,
} from '../../../shared/contracts/generated/v2/ResultFiguresV2';
import type { ResultExplanationV2 } from '../../../shared/contracts/generated/v2/ResultExplanationV2';
import '../../conversation/tutor.css';

const api = createAnalysisV2Api();
const states = {
  completed: 'Completado',
  failed: 'Fallido',
  not_executed: 'No ejecutado: no calculable',
};
const errorText = (e: unknown) =>
  e instanceof Error ? e.message : 'No se pudo completar la operación.';

export function ResultsV2({
  projectId,
  active,
  selectedId,
}: {
  projectId: string;
  active: boolean;
  selectedId?: string | null;
}) {
  const load = useCallback(() => api.results(projectId), [projectId]);
  const resource = useReadResource(load, active);
  return (
    <section aria-label="Resultados por análisis" className="analysis-v2">
      <h3>Resultados por análisis</h3>
      <p>
        Selecciona una salida para comprenderla y descargar su informe. El
        historial conserva las fuentes y versiones; disponer de un resultado no
        completa toda la investigación.
      </p>
      <button
        className="rp-secondary"
        disabled={resource.loading}
        onClick={resource.reload}
      >
        Actualizar resultados por análisis
      </button>
      {resource.error && (
        <p role="alert">No se pudieron consultar los resultados guardados.</p>
      )}
      {resource.loading && <p role="status">Consultando resultados…</p>}
      {!resource.loading && !resource.error && !resource.data?.length && (
        <p>
          Todavía no hay resultados v2. Solicita, aprueba y ejecuta una
          propuesta en Análisis.
        </p>
      )}
      {[...(resource.data ?? [])].reverse().map((r) => (
        <ResultCard
          key={`${r.id}:${r.validity}`}
          projectId={projectId}
          result={r}
          active={active}
          initiallyOpen={r.id === selectedId}
        />
      ))}
    </section>
  );
}

function ResultCard({
  projectId,
  result: r,
  active,
  initiallyOpen,
}: {
  projectId: string;
  result: Result;
  active: boolean;
  initiallyOpen: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  const [linked, setLinked] = useState(initiallyOpen);
  if (linked !== initiallyOpen) {
    setLinked(initiallyOpen);
    if (initiallyOpen) setOpen(true);
  }
  const [display, setDisplay] = useState<ResultPresentationV2 | null>(null);
  const [figures, setFigures] = useState<ResultFiguresV2 | null>(null);
  const [explanations, setExplanations] = useState<ResultExplanationV2[]>([]);
  const [interpretationHistory, setInterpretationHistory] = useState<
    ResultExplanationV2[]
  >([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const gate = useRef(false);
  const allowed = r.validity === 'current' && r.status === 'completed';
  useEffect(() => {
    if (!active || !open) return;
    let live = true;
    Promise.all([
      api.presentation(projectId, r.id),
      api.interpretations(projectId, r.id),
    ])
      .then(([d, e]) => {
        if (live) {
          setDisplay(d);
          setExplanations(e);
        }
      })
      .catch((e) => {
        if (live) setError(errorText(e));
      });
    return () => {
      live = false;
    };
  }, [projectId, r.id, active, open]);
  async function work(action: () => Promise<void>) {
    if (gate.current) return;
    gate.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      setError(errorText(e));
    } finally {
      gate.current = false;
      setBusy(false);
    }
  }
  return (
    <details
      className="rp-surface result-v2-card"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>
        {r.question} ·{' '}
        {r.validity === 'current' ? 'Vigente' : 'Histórico desactualizado'} ·{' '}
        {states[r.status]}
      </summary>
      <h4>{techniqueLabels[r.technique] ?? r.technique}</h4>
      <p>
        Variables: {r.variable_names.join(', ')}. Fuente: tabla {r.dataset_id}.
      </p>
      <p>
        {r.case_counts.used} casos utilizados y {r.case_counts.excluded}{' '}
        excluidos de {r.case_counts.total}.{' '}
        {r.case_counts.groups?.map((g) => `${g.label}: ${g.count}`).join(' · ')}{' '}
        {r.case_counts.pairs != null &&
          `Pares completos: ${r.case_counts.pairs}.`}
      </p>
      {r.validity === 'stale' && (
        <p className="rp-warning">
          {r.stale_reasons.join(' ')} Se conserva la salida histórica. Sus
          figuras y exportaciones están bloqueadas.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {open && !display && !error && (
        <p role="status">Preparando presentación guardada…</p>
      )}
      {display && (
        <>
          <p>{display.status_label}</p>
          {display.metrics.length > 0 && (
            <div className="analysis-table-scroll">
              <table>
                <caption>Métricas guardadas del resultado {r.id}</caption>
                <thead>
                  <tr>
                    <th>Métrica</th>
                    <th>Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {display.metrics.map((m) => (
                    <tr key={m.key}>
                      <th scope="row">{m.label}</th>
                      <td>
                        {m.formatted}
                        {m.unit && ` ${m.unit}`}
                        {m.reason && ` · ${m.reason}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {display.tables.map((t) => (
            <div key={t.id} className="analysis-table-scroll">
              <table>
                <caption>{t.title}</caption>
                <thead>
                  <tr>
                    {t.columns.map((c, n) => (
                      <th key={n}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {t.rows.map((row, n) => (
                    <tr key={n}>
                      {row.map((v, i) => (
                        <td key={i}>{v}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          {display.interpretation && (
            <>
              <h4>Cómo comprender esta salida</h4>
              <p>{display.interpretation}</p>
              <small>{display.interpretation_label}</small>
            </>
          )}
        </>
      )}
      <div className="rp-actions">
        <button
          className="rp-secondary"
          disabled={busy || !allowed}
          onClick={() =>
            void work(async () => {
              setFigures(await api.figures(projectId, r.id));
            })
          }
        >
          Mostrar figuras autorizadas
        </button>
        {(['txt', 'docx', 'pdf'] as const).map((format) => (
          <button
            key={format}
            className="rp-secondary"
            disabled={busy || !allowed}
            onClick={() =>
              void work(async () => {
                await api.download(projectId, r.id, format);
                setNotice(
                  'Informe generado con cifras guardadas y fuentes revalidadas.',
                );
              })
            }
          >
            Descargar {format.toUpperCase()}
          </button>
        ))}
        <button
          className="rp-secondary"
          onClick={() =>
            navigateWorkspace(projectId, 'assistant', 'results', r.id)
          }
        >
          Comprender este resultado con el tutor
        </button>
      </div>
      {figures?.figures.map((figure) => (
        <ResultFigure key={figure.id} figure={figure} />
      ))}
      {figures?.warnings.map((w) => (
        <p key={w}>{w}</p>
      ))}
      <button
        className="rp-secondary"
        disabled={busy}
        onClick={() =>
          void work(async () =>
            setExplanations(await api.interpretations(projectId, r.id)),
          )
        }
      >
        Consultar interpretaciones actuales
      </button>
      {explanations.map((e) => (
        <div key={e.id}>
          <Explanation
            key={`${e.id}:${e.revision}`}
            explanation={e}
            disabled={busy || !allowed}
            onReview={(text) =>
              void work(async () => {
                const updated = await api.review(projectId, r.id, e, text);
                try {
                  sessionStorage.removeItem(
                    `tesisstat:interpretation:v2:${e.id}`,
                  );
                } catch {
                  /* Review remains persisted on the server. */
                }
                setExplanations((old) =>
                  old.map((item) => (item.id === updated.id ? updated : item)),
                );
                setNotice(
                  'Revisión guardada. El resultado numérico permanece intacto.',
                );
              })
            }
          />
          <button
            className="rp-secondary"
            disabled={busy}
            onClick={() =>
              void work(async () =>
                setInterpretationHistory(
                  await api.interpretationHistory(projectId, r.id, e.id),
                ),
              )
            }
          >
            Consultar historial de esta interpretación
          </button>
        </div>
      ))}
      {interpretationHistory.length > 0 && (
        <details open>
          <summary>Historial de interpretación IA</summary>
          {interpretationHistory.map((e) => (
            <article key={`${e.id}:${e.revision}`}>
              <h5>
                Revisión {e.revision} ·{' '}
                {e.review_status === 'draft' ? 'Borrador' : 'Revisada'}
              </h5>
              {e.evidence_policy !== 'structured-findings-v1' && (
                <p>
                  Histórico sin respaldo verificado; no se exporta esta prosa.
                </p>
              )}
              <p>{e.text}</p>
              {e.grounded_text && <p>{e.grounded_text}</p>}
              <small>
                Resultado {e.result_ref.id}; métricas {e.metric_keys.join(', ')}
                .
              </small>
            </article>
          ))}
        </details>
      )}
      <h4>Advertencias y limitaciones</h4>
      <ul>
        {[...r.warnings, ...r.limitations].map((w, n) => (
          <li key={n}>{w}</li>
        ))}
      </ul>
      <details>
        <summary>Supuestos, método e historial</summary>
        <p>
          {r.engine_version} · {r.method_version}
        </p>
        <p>
          Plan: {r.analysis_plan_id}. Resultado: {r.id}.
        </p>
        <p>{new Date(r.created_at).toLocaleString('es-PE')}</p>
        {display?.assumptions?.map((text, n) => (
          <p key={n}>{text}</p>
        ))}
        <ul>
          {r.source_refs.map((s, n) => (
            <li key={n}>
              {s.kind} · {s.id} · revisión {s.revision} · hash {s.hash}
            </li>
          ))}
        </ul>
      </details>
    </details>
  );
}

function Explanation({
  explanation: e,
  disabled,
  onReview,
}: {
  explanation: ResultExplanationV2;
  disabled: boolean;
  onReview: (text: string) => void;
}) {
  const key = `tesisstat:interpretation:v2:${e.id}`;
  const [text, setText] = useState(() => {
    try {
      return sessionStorage.getItem(key) ?? e.text;
    } catch {
      return e.text;
    }
  });
  return (
    <section className="rp-surface" aria-label="Interpretación IA revisable">
      <h4>
        {e.review_status === 'draft'
          ? 'Borrador IA pendiente de revisión'
          : 'Interpretación IA revisada'}
      </h4>
      <p>
        Resultado {e.result_ref.id}. Referencias: {e.metric_keys.join(', ')}.
        Revisar no certifica validez científica.
      </p>
      {e.evidence_policy !== 'structured-findings-v1' ? (
        <p role="status">
          Interpretación histórica sin respaldo verificado de sus afirmaciones.
          Se conserva para consulta, no se exporta ni puede validarse con esta
          versión. Solicita una nueva explicación.
        </p>
      ) : (
        <div>
          <h5>Hallazgos reproducidos por el servidor</h5>
          <p className="tutor-prose">{e.grounded_text}</p>
        </div>
      )}
      <label className="rp-field">
        Explicación editable
        <textarea
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            try {
              sessionStorage.setItem(key, event.target.value);
            } catch {
              /* The editable draft remains on this page. */
            }
          }}
          maxLength={3500}
          rows={4}
        />
      </label>
      <p>
        <small>
          Este texto contiene conceptos y comentarios generales. Los hallazgos y
          cifras guardados se muestran separados y no cambian al editarlo.
        </small>
      </p>
      <details>
        <summary>Versión guardada para comparar</summary>
        <p>{e.text}</p>
        <p>Revisión {e.revision}.</p>
      </details>
      <button
        disabled={
          disabled ||
          !text.trim() ||
          e.evidence_policy !== 'structured-findings-v1'
        }
        onClick={() => onReview(text)}
      >
        Guardar revisión de interpretación
      </button>
    </section>
  );
}

export function ResultFigure({ figure: f }: { figure: ResultFigureDataV2 }) {
  if (!f.x.length || !f.y.length) return null;
  const minX = Math.min(...f.x),
    maxX = Math.max(...f.x);
  const minY = Math.min(0, ...f.y),
    maxY = Math.max(0, ...f.y);
  const position = (v: number, min: number, max: number) =>
    max === min ? 0.5 : (v / 2 - min / 2) / (max / 2 - min / 2);
  const py = (v: number) => 220 - 190 * position(v, minY, maxY);
  return (
    <figure className="result-v2-figure">
      <svg
        viewBox="0 0 520 300"
        role="img"
        aria-label={`${f.x_label} frente a ${f.y_label}`}
      >
        <path d="M60 20V230H500" stroke="currentColor" fill="none" />
        {f.x.map((x, n) => {
          const px = 75 + 400 * position(x, minX, maxX),
            y = f.y[n];
          return f.kind === 'bars' || f.kind === 'metric' ? (
            <rect
              key={n}
              x={px - 10}
              y={Math.min(py(0), py(y))}
              width={20}
              height={Math.max(1, Math.abs(py(y) - py(0)))}
              fill="#376d8c"
            />
          ) : (
            <circle
              key={n}
              cx={px}
              cy={py(y)}
              r={3}
              fill="#376d8c"
              opacity={0.65}
            />
          );
        })}
        <text x={8} y={30} fontSize={11}>
          {maxY.toPrecision(4)}
        </text>
        <text x={8} y={220} fontSize={11}>
          {minY.toPrecision(4)}
        </text>
        <text x={65} y={248} fontSize={11}>
          {minX.toPrecision(4)}
        </text>
        <text x={460} y={248} fontSize={11}>
          {maxX.toPrecision(4)}
        </text>
        <text x={265} y={270} textAnchor="middle" fontSize={11}>
          {f.x_label.slice(0, 65)}
        </text>
      </svg>
      <figcaption>
        {f.x_label} / {f.y_label}. {f.caption}
      </figcaption>
    </figure>
  );
}
