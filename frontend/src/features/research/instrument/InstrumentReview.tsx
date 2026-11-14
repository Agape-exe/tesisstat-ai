import type { Instrument } from './api';

export function InstrumentReview({ value: i }: { value: Instrument }) {
  const items = new Map(i.items.map((item) => [item.item_id, item.text]));
  return (
    <div>
      <p>
        Constructos:{' '}
        {i.variables
          .map((v) => `${v.name} (${v.scale ?? 'unknown'})`)
          .join(' · ')}
      </p>
      <p>Dimensiones: {i.dimensions.map((d) => d.name).join(' · ')}</p>
      <p>Indicadores: {i.indicators.map((ind) => ind.name).join(' · ')}</p>
      <ul>
        {i.items.map((item) => (
          <li key={item.item_id}>
            {item.text} ·{' '}
            {item.response_type === 'numeric'
              ? 'Respuesta numérica'
              : 'Opción única'}
            {item.valid_min != null &&
              ` · límites ${item.valid_min} a ${item.valid_max}`}
            {item.reverse_scored && ' · inversión: mínimo + máximo − valor'}
            {!!item.response_options?.length && (
              <ul>
                {item.response_options.map((o) => (
                  <li key={o.code}>
                    {o.code}: {o.label} → {o.numeric_value}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
      <ul>
        {i.scoring_rules.map((r, n) => (
          <li key={r.scoring_rule_id}>
            Regla {n + 1}: {r.aggregation === 'sum' ? 'suma' : 'promedio'} de{' '}
            {r.item_ids
              .map((id) => items.get(id) ?? 'ítem ausente')
              .join(' · ')}
            . Todos sus ítems son requeridos.
          </li>
        ))}
      </ul>
    </div>
  );
}
