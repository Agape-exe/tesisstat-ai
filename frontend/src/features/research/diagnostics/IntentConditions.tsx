import { useEffect, useState } from 'react';
import { createContextApi, type Context } from '../context/api';
import type { Changes } from './api';
import { techniqueLabels } from '../analysis/v2api';
const contexts = createContextApi();
const conditionLabels = {
  linearity: 'La dispersión es compatible con una relación lineal',
  monotonicity: 'Una relación monótona responde a la pregunta',
  comparable_group_shapes:
    'Las formas de los grupos son comparables (solo afecta interpretación de localización)',
  difference_symmetry: 'La simetría de las diferencias está justificada',
  pooled_variance_justified: 'La varianza agrupada de Student está justificada',
  inference_reviewed:
    'He revisado la adecuación del modelo para medias o correlación',
  influence_reviewed:
    'He revisado extremos, influencia, empates y casos pertinentes',
  sampling_limit_accepted:
    'Acepto que la generalización está limitada por la selección de la muestra',
} as const;
export function IntentConditions({
  projectId,
  draft,
  update,
  variables,
}: {
  projectId: string;
  draft: Changes;
  update: (c: Changes) => void;
  variables: { id: string; name: { value?: string | null } }[];
}) {
  const [context, setContext] = useState<Context | null>(null),
    [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    contexts
      .get(projectId)
      .then((c) => {
        if (live) setContext(c);
      })
      .catch(() => {
        if (live)
          setError(
            'No se pudieron consultar objetivos e hipótesis. Puedes continuar sin vincularlos.',
          );
      });
    return () => {
      live = false;
    };
  }, [projectId]);
  const fields =
    draft.kind === 'descriptive'
      ? []
      : Object.entries(conditionLabels).filter(([key]) => {
          if (key === 'linearity')
            return draft.estimand === 'linear_association';
          if (key === 'monotonicity')
            return draft.estimand === 'monotonic_association';
          if (key === 'difference_symmetry')
            return (
              draft.observations === 'paired' &&
              draft.estimand === 'distribution_difference'
            );
          if (key === 'pooled_variance_justified')
            return draft.requested_technique === 't_independent';
          if (key === 'comparable_group_shapes')
            return (
              draft.observations === 'independent' &&
              draft.estimand === 'distribution_difference'
            );
          if (key === 'inference_reviewed')
            return ['mean_difference', 'linear_association'].includes(
              draft.estimand ?? '',
            );
          return true;
        });
  return (
    <fieldset>
      <legend>Condiciones y vínculos de esta intención</legend>
      {error && <p role="status">{error}</p>}
      <label className="rp-field">
        Objetivo específico (opcional)
        <select
          value={draft.objective_id ?? ''}
          onChange={(e) => update({ objective_id: e.target.value || null })}
        >
          <option value="">Sin vínculo</option>
          {context?.specific_objectives?.map((o) => (
            <option key={o.id} value={o.id}>
              {o.text.value}
            </option>
          ))}
        </select>
      </label>
      <label className="rp-field">
        Hipótesis (opcional)
        <select
          value={draft.hypothesis_id ?? ''}
          onChange={(e) => update({ hypothesis_id: e.target.value || null })}
        >
          <option value="">Sin hipótesis</option>
          {context?.hypotheses?.map((h) => (
            <option key={h.id} value={h.id}>
              {h.statement.value}
            </option>
          ))}
        </select>
      </label>
      <p>Una hipótesis importada no aprueba una dirección ni una técnica.</p>
      {variables.map((v) => (
        <label className="rp-field" key={v.id}>
          Rol de {v.name.value}
          <select
            value={draft.roles?.find((r) => r.variable_id === v.id)?.role ?? ''}
            onChange={(e) =>
              update({
                roles: [
                  ...(draft.roles ?? []).filter((r) => r.variable_id !== v.id),
                  ...(e.target.value
                    ? [
                        {
                          variable_id: v.id,
                          role: e.target.value as NonNullable<
                            Changes['roles']
                          >[number]['role'],
                        },
                      ]
                    : []),
                ],
              })
            }
          >
            <option value="">Sin asignar</option>
            {Object.entries({
              outcome: 'Resultado',
              predictor: 'Predictora',
              group: 'Grupo',
              item: 'Ítem',
              descriptive: 'Descriptiva',
            }).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
      ))}
      {draft.kind !== 'descriptive' && (
        <label className="rp-field">
          Dirección del contraste
          <select
            value={draft.alternative ?? 'unspecified'}
            onChange={(e) =>
              update({ alternative: e.target.value as Changes['alternative'] })
            }
          >
            <option value="unspecified">Pendiente de revisar</option>
            <option value="two-sided">
              Bilateral: cualquiera de los dos sentidos
            </option>
            <option value="greater">Mayor (fuera del alcance validado)</option>
            <option value="less">Menor (fuera del alcance validado)</option>
          </select>
        </label>
      )}
      <label className="rp-field">
        Técnica solicitada (opcional)
        <select
          value={draft.requested_technique ?? ''}
          onChange={(e) =>
            update({ requested_technique: e.target.value || null })
          }
        >
          <option value="">Dejar que el selector evalúe la intención</option>
          {Object.entries(techniqueLabels).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {fields.map(([key, label]) => (
        <label className="rp-field" key={key}>
          {label}
          <select
            value={
              draft.conditions?.[key as keyof typeof conditionLabels] ??
              'unknown'
            }
            onChange={(e) =>
              update({
                conditions: { ...draft.conditions, [key]: e.target.value },
              })
            }
          >
            <option value="unknown">Pendiente de revisar</option>
            <option value="yes">Sí, revisado para este análisis</option>
            <option value="no">No / condición insuficiente</option>
          </select>
        </label>
      ))}
      {draft.kind !== 'descriptive' && (
        <label className="rp-field">
          Justificación de condiciones y límites
          <textarea
            value={draft.conditions?.review_notes ?? ''}
            maxLength={2000}
            onChange={(e) =>
              update({
                conditions: {
                  ...draft.conditions,
                  review_notes: e.target.value,
                },
              })
            }
            placeholder="Revisa diagnósticos, dispersión o diferencias y explica por qué la técnica responde a la pregunta."
          />
        </label>
      )}
    </fieldset>
  );
}
