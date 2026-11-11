import { useEffect, useState } from 'react';
import { createInstrumentApi, type Instrument, type Mapping } from './api';
import { createDataApi } from '../data/api';
import type { Changes } from '../diagnostics/api';
import { navigateProject } from '../projects/navigation';

const api = createInstrumentApi(),
  data = createDataApi();
export function ReliabilityInputs({
  projectId,
  draft,
  update,
}: {
  projectId: string;
  draft: Changes;
  update: (change: Changes) => void;
}) {
  const [items, setItems] = useState<Instrument[]>([]),
    [mapping, setMapping] = useState<Mapping | null>(null);
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const current = items.find((i) => i.instrument_id === draft.instrument_id);
  useEffect(() => {
    let live = true;
    api
      .list(projectId)
      .then((i) => {
        if (live) setItems(i);
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [projectId]);
  useEffect(() => {
    let live = true;
    if (draft.instrument_id)
      api
        .mapping(projectId, draft.instrument_id)
        .then((m) => {
          if (live) setMapping(m);
        })
        .catch((e) => {
          if (live) setError(String(e));
        });
    return () => {
      live = false;
    };
  }, [projectId, draft.instrument_id]);
  async function applyRule(id: string) {
    if (!current || !mapping) return;
    setBusy(true);
    setError('');
    try {
      const rule = current.scoring_rules.find((r) => r.scoring_rule_id === id)!;
      const dictionary = await data.dictionary(
        projectId,
        mapping.dataset_ref.id,
      );
      const columns = mapping.item_columns
        .filter((m) => rule.item_ids.includes(m.item_id))
        .map((m) => m.column_id);
      const variables = dictionary.variables
        .filter((v) => (v.column_ids ?? []).some((c) => columns.includes(c)))
        .map((v) => v.id);
      update({
        instrument_id: current.instrument_id,
        instrument_revision: current.revision,
        mapping_revision: mapping.revision,
        scoring_rule_id: id,
        dataset_id: mapping.dataset_ref.id,
        variable_ids: variables,
        estimand: 'internal_consistency',
        roles: variables.map((variable_id) => ({ variable_id, role: 'item' })),
        group_column_id: null,
        paired_columns: null,
        alternative: 'unspecified',
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <fieldset disabled={busy}>
      <legend>Conjunto de ítems para confiabilidad</legend>
      <p>
        Elige una regla revisada y explica qué constructo deseas evaluar. No se
        reúnen automáticamente todas las dimensiones. Se utilizarán las
        respuestas recodificadas; el total no es una entrada válida para alfa.
      </p>
      {error && <p role="alert">{error}</p>}
      <label className="rp-field">
        Instrumento para confiabilidad
        <select
          value={draft.instrument_id ?? ''}
          onChange={(e) => {
            setMapping(null);
            setError('');
            update({
              instrument_id: e.target.value || null,
              instrument_revision: null,
              mapping_revision: null,
              scoring_rule_id: null,
            });
          }}
        >
          <option value="">Elegir instrumento</option>
          {items.map((i) => (
            <option key={i.instrument_id} value={i.instrument_id}>
              {i.variables[0]?.name} · revisión {i.revision} · {i.status}
            </option>
          ))}
        </select>
      </label>
      <label className="rp-field">
        Regla y agrupación pertinente
        <select
          disabled={
            !current ||
            !mapping ||
            current.status !== 'reviewed' ||
            mapping.status !== 'confirmed'
          }
          value={draft.scoring_rule_id ?? ''}
          onChange={(e) => {
            if (e.target.value) void applyRule(e.target.value);
          }}
        >
          <option value="">Elegir explícitamente el conjunto</option>
          {current?.scoring_rules.map((r, n) => (
            <option key={r.scoring_rule_id} value={r.scoring_rule_id}>
              Regla {n + 1} ·{' '}
              {r.scope === 'dimension'
                ? current.dimensions.find(
                    (d) => d.dimension_id === r.dimension_id,
                  )?.name
                : 'Conjunto del instrumento'}{' '}
              · {r.item_ids.length} ítems
            </option>
          ))}
        </select>
      </label>
      {current && draft.scoring_rule_id && (
        <ul>
          {current.items
            .filter((i) =>
              current.scoring_rules
                .find((r) => r.scoring_rule_id === draft.scoring_rule_id)
                ?.item_ids.includes(i.item_id),
            )
            .map((i) => (
              <li key={i.item_id}>
                {i.text}
                {i.reverse_scored ? ' · inversión explícita' : ''}
              </li>
            ))}
        </ul>
      )}
      <label className="rp-field">
        Constructo y razón para evaluar juntos estos ítems
        <textarea
          value={draft.reliability_group ?? ''}
          onChange={(e) => update({ reliability_group: e.target.value })}
          maxLength={2000}
        />
      </label>
      <button
        type="button"
        onClick={() => navigateProject(projectId, 'instrument')}
      >
        Revisar instrumento y correspondencia
      </button>
      <p>
        Alfa describe consistencia interna. No demuestra validez ni
        unidimensionalidad y puede ser negativo.
      </p>
    </fieldset>
  );
}
