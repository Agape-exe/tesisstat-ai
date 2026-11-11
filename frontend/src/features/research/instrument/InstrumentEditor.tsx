import type { Structure } from './api';

export function InstrumentEditor({
  value: s,
  change,
}: {
  value: Structure;
  change: (s: Structure) => void;
}) {
  const set = <K extends keyof Structure>(key: K, value: Structure[K]) =>
    change({ ...s, [key]: value });
  const updateItem = (
    index: number,
    patch: Partial<Structure['items'][number]>,
  ) =>
    set(
      'items',
      s.items.map((i, n) => (n === index ? { ...i, ...patch } : i)),
    );
  return (
    <div className="instrument-editor">
      <p>
        Define tu instrumento sin documento. Nombra únicamente los componentes
        que hayas acordado. Para uno sencillo puedes declarar expresamente un
        conjunto sin desglose.
      </p>
      <button
        type="button"
        className="rp-secondary"
        onClick={() =>
          change({
            ...s,
            dimensions: s.dimensions.map((d) => ({
              ...d,
              name: 'Sin desglose dimensional (declarado)',
            })),
            indicators: s.indicators.map((i) => ({
              ...i,
              name: 'Sin indicadores diferenciados (declarado)',
            })),
          })
        }
      >
        Declarar estructura mínima sin desglose
      </button>
      <fieldset>
        <legend>Variables o constructos</legend>
        {s.variables.map((v, n) => (
          <div className="instrument-row" key={v.variable_id}>
            <label className="rp-field">
              Nombre del constructo {n + 1}
              <input
                value={v.name}
                maxLength={200}
                onChange={(e) =>
                  set(
                    'variables',
                    s.variables.map((x, j) =>
                      j === n ? { ...x, name: e.target.value } : x,
                    ),
                  )
                }
              />
            </label>
            <label className="rp-field">
              Escala declarada del constructo {n + 1}
              <select
                value={v.scale ?? 'unknown'}
                onChange={(e) =>
                  set(
                    'variables',
                    s.variables.map((x, j) =>
                      j === n
                        ? { ...x, scale: e.target.value as typeof v.scale }
                        : x,
                    ),
                  )
                }
              >
                <option value="unknown">Pendiente de revisar</option>
                <option value="nominal">Nominal</option>
                <option value="ordinal">Ordinal</option>
                <option value="interval">Intervalar</option>
                <option value="ratio">Razón</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() =>
                set(
                  'variables',
                  s.variables.filter((_, j) => j !== n),
                )
              }
            >
              Quitar constructo {n + 1}
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            set('variables', [
              ...s.variables,
              { variable_id: crypto.randomUUID(), name: '', scale: 'unknown' },
            ])
          }
        >
          Añadir constructo
        </button>
      </fieldset>
      <fieldset>
        <legend>Dimensiones</legend>
        {s.dimensions.map((d, n) => (
          <div className="instrument-row" key={d.dimension_id}>
            <label className="rp-field">
              Dimensión {n + 1}
              <input
                value={d.name}
                onChange={(e) =>
                  set(
                    'dimensions',
                    s.dimensions.map((x, j) =>
                      j === n ? { ...x, name: e.target.value } : x,
                    ),
                  )
                }
              />
            </label>
            <label className="rp-field">
              Constructo de dimensión {n + 1}
              <select
                value={d.variable_id}
                onChange={(e) =>
                  set(
                    'dimensions',
                    s.dimensions.map((x, j) =>
                      j === n ? { ...x, variable_id: e.target.value } : x,
                    ),
                  )
                }
              >
                {s.variables.map((v) => (
                  <option key={v.variable_id} value={v.variable_id}>
                    {v.name || 'Sin nombre'}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() =>
                set(
                  'dimensions',
                  s.dimensions.filter((_, j) => j !== n),
                )
              }
            >
              Quitar dimensión {n + 1}
            </button>
          </div>
        ))}
        <button
          type="button"
          disabled={!s.variables.length}
          onClick={() =>
            set('dimensions', [
              ...s.dimensions,
              {
                dimension_id: crypto.randomUUID(),
                variable_id: s.variables[0].variable_id,
                name: '',
              },
            ])
          }
        >
          Añadir dimensión
        </button>
      </fieldset>
      <fieldset>
        <legend>Indicadores</legend>
        {s.indicators.map((i, n) => (
          <div className="instrument-row" key={i.indicator_id}>
            <label className="rp-field">
              Indicador {n + 1}
              <input
                value={i.name}
                onChange={(e) =>
                  set(
                    'indicators',
                    s.indicators.map((x, j) =>
                      j === n ? { ...x, name: e.target.value } : x,
                    ),
                  )
                }
              />
            </label>
            <label className="rp-field">
              Dimensión de indicador {n + 1}
              <select
                value={i.dimension_id}
                onChange={(e) =>
                  set(
                    'indicators',
                    s.indicators.map((x, j) =>
                      j === n ? { ...x, dimension_id: e.target.value } : x,
                    ),
                  )
                }
              >
                {s.dimensions.map((d) => (
                  <option key={d.dimension_id} value={d.dimension_id}>
                    {d.name || 'Sin nombre'}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() =>
                set(
                  'indicators',
                  s.indicators.filter((_, j) => j !== n),
                )
              }
            >
              Quitar indicador {n + 1}
            </button>
          </div>
        ))}
        <button
          type="button"
          disabled={!s.dimensions.length}
          onClick={() =>
            set('indicators', [
              ...s.indicators,
              {
                indicator_id: crypto.randomUUID(),
                dimension_id: s.dimensions[0].dimension_id,
                name: '',
              },
            ])
          }
        >
          Añadir indicador
        </button>
      </fieldset>
      <fieldset>
        <legend>Ítems y respuestas</legend>
        {s.items.map((item, n) => (
          <fieldset key={item.item_id}>
            <legend>Ítem {n + 1}</legend>
            <label className="rp-field">
              Texto del ítem {n + 1}
              <textarea
                value={item.text}
                maxLength={1000}
                onChange={(e) => updateItem(n, { text: e.target.value })}
              />
            </label>
            <label className="rp-field">
              Indicador del ítem {n + 1}
              <select
                value={item.indicator_id}
                onChange={(e) => {
                  const i = s.indicators.find(
                    (i) => i.indicator_id === e.target.value,
                  )!;
                  const d = s.dimensions.find(
                    (d) => d.dimension_id === i.dimension_id,
                  )!;
                  updateItem(n, {
                    indicator_id: i.indicator_id,
                    dimension_id: d.dimension_id,
                    variable_id: d.variable_id,
                  });
                }}
              >
                {s.indicators.map((i) => (
                  <option key={i.indicator_id} value={i.indicator_id}>
                    {i.name || 'Sin nombre'}
                  </option>
                ))}
              </select>
            </label>
            <label className="rp-field">
              Tipo de respuesta del ítem {n + 1}
              <select
                value={item.response_type}
                onChange={(e) =>
                  updateItem(n, {
                    response_type: e.target.value as typeof item.response_type,
                    response_options: [],
                  })
                }
              >
                <option value="numeric">Numérica con puntuación directa</option>
                <option value="single_choice">
                  Opción única con códigos explícitos
                </option>
              </select>
            </label>
            <div className="instrument-row">
              {(['valid_min', 'valid_max'] as const).map((key) => (
                <label className="rp-field" key={key}>
                  {key === 'valid_min' ? 'Mínimo' : 'Máximo'} del ítem {n + 1}
                  <input
                    type="number"
                    step="any"
                    value={item[key] ?? ''}
                    onChange={(e) =>
                      updateItem(n, {
                        [key]:
                          e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                  />
                </label>
              ))}
            </div>
            <label>
              <input
                type="checkbox"
                checked={item.reverse_scored ?? false}
                onChange={(e) =>
                  updateItem(n, {
                    reverse_scored: e.target.checked,
                    reverse_rule: e.target.checked
                      ? 'min_plus_max_minus_value'
                      : null,
                  })
                }
              />
              Invertir ítem {n + 1}: mínimo + máximo − valor
            </label>
            {item.response_type === 'single_choice' && (
              <div>
                <p>
                  Cada código debe tener etiqueta y puntuación explícitas; no se
                  deducen de su nombre.
                </p>
                {(item.response_options ?? []).map((o, j) => (
                  <div className="instrument-row" key={j}>
                    <label className="rp-field">
                      Código {j + 1} del ítem {n + 1}
                      <input
                        value={o.code}
                        onChange={(e) =>
                          updateItem(n, {
                            response_options: item.response_options!.map(
                              (x, k) =>
                                k === j ? { ...x, code: e.target.value } : x,
                            ),
                          })
                        }
                      />
                    </label>
                    <label className="rp-field">
                      Etiqueta {j + 1} del ítem {n + 1}
                      <input
                        value={o.label}
                        onChange={(e) =>
                          updateItem(n, {
                            response_options: item.response_options!.map(
                              (x, k) =>
                                k === j ? { ...x, label: e.target.value } : x,
                            ),
                          })
                        }
                      />
                    </label>
                    <label className="rp-field">
                      Puntuación {j + 1} del ítem {n + 1}
                      <input
                        type="number"
                        step="any"
                        value={o.numeric_value}
                        onChange={(e) =>
                          updateItem(n, {
                            response_options: item.response_options!.map(
                              (x, k) =>
                                k === j
                                  ? {
                                      ...x,
                                      numeric_value: Number(e.target.value),
                                    }
                                  : x,
                            ),
                          })
                        }
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        updateItem(n, {
                          response_options: item.response_options!.filter(
                            (_, k) => k !== j,
                          ),
                        })
                      }
                    >
                      Quitar opción {j + 1} del ítem {n + 1}
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() =>
                    updateItem(n, {
                      response_options: [
                        ...(item.response_options ?? []),
                        { code: '', label: '', numeric_value: 0 },
                      ],
                    })
                  }
                >
                  Añadir opción al ítem {n + 1}
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={() =>
                set(
                  'items',
                  s.items.filter((_, j) => j !== n),
                )
              }
            >
              Quitar ítem {n + 1}
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          disabled={!s.indicators.length || !s.dimensions.length}
          onClick={() => {
            const i = s.indicators[0],
              d = s.dimensions.find((d) => d.dimension_id === i.dimension_id);
            if (d)
              set('items', [
                ...s.items,
                {
                  item_id: crypto.randomUUID(),
                  indicator_id: i.indicator_id,
                  dimension_id: d.dimension_id,
                  variable_id: d.variable_id,
                  text: '',
                  response_type: 'numeric',
                  response_options: [],
                  reverse_scored: false,
                  reverse_rule: null,
                  valid_min: null,
                  valid_max: null,
                },
              ]);
          }}
        >
          Añadir ítem
        </button>
      </fieldset>
      <fieldset>
        <legend>Reglas de puntuación</legend>
        <p>
          Selecciona los ítems que realmente usa cada regla. Si falta alguno de
          esos ítems la puntuación de esa fila será nula.
        </p>
        {s.scoring_rules.map((r, n) => (
          <fieldset key={r.scoring_rule_id}>
            <legend>Regla {n + 1}</legend>
            <label className="rp-field">
              Ámbito de regla {n + 1}
              <select
                value={
                  r.scope === 'instrument'
                    ? 'instrument'
                    : (r.dimension_id ?? '')
                }
                onChange={(e) =>
                  set(
                    'scoring_rules',
                    s.scoring_rules.map((x, j) =>
                      j === n
                        ? {
                            ...x,
                            scope:
                              e.target.value === 'instrument'
                                ? 'instrument'
                                : 'dimension',
                            dimension_id:
                              e.target.value === 'instrument'
                                ? null
                                : e.target.value,
                            item_ids: [],
                          }
                        : x,
                    ),
                  )
                }
              >
                <option value="instrument">
                  Conjunto del instrumento (elección explícita)
                </option>
                {s.dimensions.map((d) => (
                  <option key={d.dimension_id} value={d.dimension_id}>
                    {d.name || 'Dimensión sin nombre'}
                  </option>
                ))}
              </select>
            </label>
            <label className="rp-field">
              Operación de regla {n + 1}
              <select
                value={r.aggregation}
                onChange={(e) =>
                  set(
                    'scoring_rules',
                    s.scoring_rules.map((x, j) =>
                      j === n
                        ? {
                            ...x,
                            aggregation: e.target.value as 'sum' | 'mean',
                          }
                        : x,
                    ),
                  )
                }
              >
                <option value="sum">Suma</option>
                <option value="mean">Promedio</option>
              </select>
            </label>
            {s.items
              .filter(
                (i) =>
                  r.scope === 'instrument' || i.dimension_id === r.dimension_id,
              )
              .map((i) => (
                <label className="instrument-choice" key={i.item_id}>
                  <input
                    type="checkbox"
                    checked={r.item_ids.includes(i.item_id)}
                    onChange={(e) =>
                      set(
                        'scoring_rules',
                        s.scoring_rules.map((x, j) =>
                          j === n
                            ? {
                                ...x,
                                item_ids: e.target.checked
                                  ? [...x.item_ids, i.item_id]
                                  : x.item_ids.filter((id) => id !== i.item_id),
                              }
                            : x,
                        ),
                      )
                    }
                  />
                  {i.text || 'Ítem sin texto'}
                </label>
              ))}
            <button
              type="button"
              onClick={() =>
                set(
                  'scoring_rules',
                  s.scoring_rules.filter((_, j) => j !== n),
                )
              }
            >
              Quitar regla {n + 1}
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          onClick={() =>
            set('scoring_rules', [
              ...s.scoring_rules,
              {
                scoring_rule_id: crypto.randomUUID(),
                scope: 'dimension',
                dimension_id: s.dimensions[0]?.dimension_id ?? null,
                item_ids: [],
                aggregation: 'sum',
                missing_policy: 'all_required',
              },
            ])
          }
        >
          Añadir regla
        </button>
      </fieldset>
    </div>
  );
}
