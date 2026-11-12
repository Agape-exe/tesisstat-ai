import { useRef, useState } from 'react';
import type { Selection, TutorStatus, createTutorApi } from './tutorApi';
import { navigateWorkspace } from '../research/projects/navigation';
import { TutorApiError } from './tutorApi';
import type { GuidedDescriptiveRequestV2 } from '../../shared/contracts/generated/v2/GuidedDescriptiveRequestV2';

export function GuidedReview({
  projectId,
  status,
  selection,
  api,
}: {
  projectId: string;
  status: TutorStatus;
  selection: Selection;
  api: ReturnType<typeof createTutorApi>;
}) {
  const variables = status.guidance?.variables ?? [];
  const storageKey = `tesisstat:guided-descriptive:v1:${projectId}:${selection.dataset_id}`;
  const [recovered] = useState<GuidedDescriptiveRequestV2 | null>(() => {
    try {
      const saved = JSON.parse(
        sessionStorage.getItem(storageKey) ?? 'null',
      ) as GuidedDescriptiveRequestV2 | null;
      return saved &&
        saved.selection?.dataset_id === selection.dataset_id &&
        Array.isArray(saved.variables)
        ? saved
        : null;
    } catch {
      return null;
    }
  });
  const [selected, setSelected] = useState(() =>
    Object.fromEntries(
      variables.map((v) => [
        v.variable_id,
        recovered
          ? recovered.variables.some((n) => n.variable_id === v.variable_id)
          : v.selected,
      ]),
    ),
  );
  const [scales, setScales] = useState(() =>
    Object.fromEntries(
      variables.map((v) => [
        v.variable_id,
        recovered?.variables.find((n) => n.variable_id === v.variable_id)
          ?.measurement_scale ?? v.suggested_scale,
      ]),
    ),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const attempt = useRef<GuidedDescriptiveRequestV2 | null>(recovered);
  const gate = useRef(false);
  async function prepare() {
    if (gate.current) return;
    gate.current = true;
    setBusy(true);
    setError('');
    const chosen = variables
      .filter((v) => selected[v.variable_id])
      .map((v) => ({
        variable_id: v.variable_id,
        measurement_scale: scales[v.variable_id],
      }));
    if (JSON.stringify(attempt.current?.variables) !== JSON.stringify(chosen))
      attempt.current = {
        kind: 'prepare_descriptive',
        selection,
        context_fingerprint: status.context.context_fingerprint,
        request_id: crypto.randomUUID(),
        variables: chosen as GuidedDescriptiveRequestV2['variables'],
        confirm: true,
      };
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(attempt.current));
    } catch {
      /* Server receipt still protects retries in this view. */
    }
    try {
      const result = await api.prepareDescriptive(projectId, attempt.current!);
      try {
        sessionStorage.removeItem(storageKey);
      } catch {
        /* Resource is persisted. */
      }
      navigateWorkspace(projectId, 'analysis', 'diagnostics', result.intent_id);
    } catch (cause) {
      if (cause instanceof TutorApiError && cause.status === 409) {
        attempt.current = null;
        try {
          sessionStorage.removeItem(storageKey);
        } catch {
          /* Rebuild after explicit review. */
        }
      }
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo preparar el análisis.',
      );
    } finally {
      gate.current = false;
      setBusy(false);
    }
  }
  return (
    <section aria-label="Revisión breve del descriptivo">
      <h3>Revisa solo las variables que analizarás</h3>
      <p>
        Los tipos detectados son sugerencias. Un número puede ser un código:
        elige categorías para obtener frecuencias, o una medida para obtener
        promedios. No necesitas configurar las demás columnas.
      </p>
      <fieldset disabled={busy}>
        {variables.map((v) => (
          <div className="tutor-variable" key={v.variable_id}>
            <label>
              <input
                type="checkbox"
                checked={!!selected[v.variable_id]}
                disabled={v.formula_errors > 0}
                onChange={(e) =>
                  setSelected((old) => ({
                    ...old,
                    [v.variable_id]: e.target.checked,
                  }))
                }
              />{' '}
              {v.name}
            </label>
            {v.possible_identifier && (
              <small>Posible identificador: revisa antes de incluir.</small>
            )}
            {v.formula_errors > 0 && (
              <small>Contiene errores de fórmulas; corrige y reimporta.</small>
            )}
            {selected[v.variable_id] && (
              <label className="rp-field">
                Cómo resumir {v.name}
                <select
                  value={scales[v.variable_id]}
                  onChange={(e) =>
                    setScales((old) => ({
                      ...old,
                      [v.variable_id]: e.target
                        .value as typeof v.suggested_scale,
                    }))
                  }
                >
                  <option value="nominal">
                    Categorías: frecuencias, sin promediar códigos
                  </option>
                  <option value="ordinal">
                    Categorías ordenadas: revisa su orden en Datos
                  </option>
                  <option value="interval">
                    Medida cuantitativa: intervalos comparables
                  </option>
                  <option value="ratio">
                    Medida cuantitativa: cero absoluto
                  </option>
                </select>
              </label>
            )}
          </div>
        ))}
      </fieldset>
      <p>
        Al continuar confirmas las escalas elegidas, guardas una intención y
        calculas el perfil local. A continuación revisarás los casos y la
        propuesta. Esto no aprueba ni ejecuta el análisis final.
      </p>
      {error && <p role="alert">{error}</p>}
      <button
        disabled={busy || !Object.values(selected).some(Boolean)}
        onClick={() => void prepare()}
      >
        {busy
          ? 'Preparando…'
          : 'Guardar variables revisadas y preparar descriptivo'}
      </button>
    </section>
  );
}
