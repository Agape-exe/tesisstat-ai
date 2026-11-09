import type { Context } from './api';
import type { Draft } from './draft';
import { directionHelp, directionLabels } from './semantics';

export function ContextLists({
  draft,
  saved,
  update,
}: {
  draft: Draft;
  saved: Context;
  update: <K extends keyof Draft>(key: K, value: Draft[K]) => void;
}) {
  return (
    <details>
      <summary>Objetivos específicos e hipótesis (opcionales)</summary>
      <h3>Objetivos específicos</h3>
      <p className="rp-hint">
        Pasos concretos que ayudan a responder el objetivo general. Cada
        elemento conserva su identificador al editarlo.
      </p>
      {draft.specific_objectives.map((o, i) => (
        <div className="rc-item" key={o.key}>
          <label htmlFor={`objective-${o.key}`}>
            Objetivo específico {i + 1}
          </label>
          <textarea
            id={`objective-${o.key}`}
            rows={2}
            maxLength={2000}
            value={o.text}
            onChange={(e) =>
              update(
                'specific_objectives',
                draft.specific_objectives.map((x) =>
                  x.key === o.key ? { ...x, text: e.target.value } : x,
                ),
              )
            }
          />
          <p className="rc-field-status">
            {!o.id ||
            o.text !==
              (saved.specific_objectives.find((x) => x.id === o.id)?.text
                .value ?? '')
              ? 'Sin guardar'
              : saved.specific_objectives.find((x) => x.id === o.id)?.text
                    .confirmation
                ? 'Confirmado por ti'
                : 'Guardado · sin confirmar'}
          </p>
          <button
            className="rp-link"
            type="button"
            onClick={() => {
              update(
                'specific_objectives',
                draft.specific_objectives.filter((x) => x.key !== o.key),
              );
              if (o.id)
                update(
                  'hypotheses',
                  draft.hypotheses.map((h) =>
                    h.objective_id === o.id ? { ...h, objective_id: null } : h,
                  ),
                );
            }}
          >
            Retirar objetivo {i + 1}
          </button>
        </div>
      ))}
      <button
        className="rp-secondary"
        type="button"
        disabled={draft.specific_objectives.length >= 40}
        onClick={() =>
          update('specific_objectives', [
            ...draft.specific_objectives,
            { key: crypto.randomUUID(), text: '' },
          ])
        }
      >
        Añadir objetivo específico
      </button>
      <h3>Hipótesis, si existen</h3>
      <p className="rp-hint">
        Una respuesta que esperas contrastar. No es necesaria para explorar o
        describir datos. Puedes conservar H0 y H1 como texto, sin completar una
        dirección.
      </p>
      {draft.hypotheses.map((h, i) => (
        <div className="rc-item" key={h.key}>
          <label htmlFor={`hypothesis-${h.key}`}>Hipótesis {i + 1}</label>
          <textarea
            id={`hypothesis-${h.key}`}
            rows={2}
            maxLength={2000}
            value={h.statement}
            onChange={(e) =>
              update(
                'hypotheses',
                draft.hypotheses.map((x) =>
                  x.key === h.key ? { ...x, statement: e.target.value } : x,
                ),
              )
            }
          />
          <label htmlFor={`hypothesis-objective-${h.key}`}>
            Objetivo relacionado
          </label>
          <select
            id={`hypothesis-objective-${h.key}`}
            value={h.objective_id ?? ''}
            onChange={(e) =>
              update(
                'hypotheses',
                draft.hypotheses.map((x) =>
                  x.key === h.key
                    ? { ...x, objective_id: e.target.value || null }
                    : x,
                ),
              )
            }
          >
            <option value="">Sin vínculo por ahora</option>
            {draft.specific_objectives
              .filter((o) => o.id)
              .map((o) => (
                <option key={o.key} value={o.id}>
                  {o.text || 'Objetivo sin texto'}
                </option>
              ))}
          </select>
          <p className="rp-hint">
            Guarda los objetivos nuevos para poder vincularlos.
          </p>
          <label htmlFor={`hypothesis-alternative-${h.key}`}>
            Dirección de la hipótesis (opcional)
          </label>
          <select
            id={`hypothesis-alternative-${h.key}`}
            value={h.alternative}
            onChange={(e) =>
              update(
                'hypotheses',
                draft.hypotheses.map((x) =>
                  x.key === h.key
                    ? {
                        ...x,
                        alternative: e.target.value as typeof h.alternative,
                      }
                    : x,
                ),
              )
            }
          >
            {Object.entries(directionLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <p className="rp-hint">{directionHelp}</p>
          <p className="rc-field-status">
            {!h.id ||
            h.statement !==
              (saved.hypotheses.find((x) => x.id === h.id)?.statement.value ??
                '') ||
            h.objective_id !==
              (saved.hypotheses.find((x) => x.id === h.id)?.objective_id ??
                null) ||
            h.alternative !==
              (saved.hypotheses.find((x) => x.id === h.id)?.alternative ??
                'unspecified')
              ? 'Sin guardar'
              : saved.hypotheses.find((x) => x.id === h.id)?.statement
                    .confirmation
                ? 'Confirmado por ti'
                : 'Guardado · sin confirmar'}
          </p>
          <button
            className="rp-link"
            type="button"
            onClick={() =>
              update(
                'hypotheses',
                draft.hypotheses.filter((x) => x.key !== h.key),
              )
            }
          >
            Retirar hipótesis {i + 1}
          </button>
        </div>
      ))}
      <button
        className="rp-secondary"
        type="button"
        disabled={draft.hypotheses.length >= 40}
        onClick={() =>
          update('hypotheses', [
            ...draft.hypotheses,
            {
              key: crypto.randomUUID(),
              statement: '',
              objective_id: null,
              alternative: 'unspecified',
            },
          ])
        }
      >
        Añadir hipótesis
      </button>
    </details>
  );
}
