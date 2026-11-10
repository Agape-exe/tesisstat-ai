import type { Diagnostic } from './api';
import type { DiagnosticFigureV2 } from '../../../shared/contracts/generated/v2/DiagnosticV2';

import { checkLabels } from './labels';
const format = (v: number) =>
  new Intl.NumberFormat('es', { maximumSignificantDigits: 5 }).format(v);

function Figure({ figure }: { figure: DiagnosticFigureV2 }) {
  const xmin = Math.min(...figure.x),
    xmax = Math.max(...figure.x);
  const ymin = figure.kind === 'histogram' ? 0 : Math.min(...figure.y),
    ymax = Math.max(...figure.y);
  const position = (v: number, min: number, max: number) =>
    max === min ? 0.5 : (v / 2 - min / 2) / (max / 2 - min / 2);
  return (
    <figure className="diagnostic-figure">
      <figcaption>
        {figure.kind === 'qq'
          ? 'Q–Q normal'
          : figure.kind === 'scatter'
            ? 'Dispersión'
            : 'Histograma'}{' '}
        · {figure.target}
      </figcaption>
      <svg
        viewBox="0 0 360 230"
        role="img"
        aria-label={`${figure.target}: ${figure.x_label} frente a ${figure.y_label}`}
      >
        <path d="M40 15V190H345" fill="none" stroke="currentColor" />
        {figure.x.map((x, i) => {
          const px = 45 + 290 * position(x, xmin, xmax),
            py = 185 - 160 * position(figure.y[i], ymin, ymax);
          return figure.kind === 'histogram' ? (
            <rect
              key={i}
              x={px - Math.min(12, 130 / figure.x.length)}
              y={py}
              width={Math.min(24, 260 / figure.x.length)}
              height={185 - py}
              fill="#376d8c"
            />
          ) : (
            <circle key={i} cx={px} cy={py} r={2.5} fill="#376d8c" />
          );
        })}
        <text x="42" y="205" fontSize="10">
          {format(xmin)}
        </text>
        <text x="310" y="205" fontSize="10">
          {format(xmax)}
        </text>
        <text x="2" y="25" fontSize="10">
          {format(ymax)}
        </text>
        <text x="2" y="190" fontSize="10">
          {format(ymin)}
        </text>
        <text x="180" y="225" textAnchor="middle" fontSize="11">
          {figure.x_label}
        </text>
      </svg>
      <p>
        {figure.y_label}. {figure.details}
      </p>
    </figure>
  );
}

export function DiagnosticEvidence({ value }: { value: Diagnostic }) {
  const p = value.profile;
  return (
    <article className="rp-surface diagnostic-evidence">
      <h4>Diagnóstico · {new Date(value.created_at).toLocaleString('es')}</h4>
      <p>
        <strong>
          {value.state === 'stale' ? 'Desactualizado' : 'Vigente'}
        </strong>{' '}
        ·{' '}
        {value.status === 'not_calculable'
          ? 'No calculable'
          : value.status === 'failed'
            ? 'Falló'
            : 'Completado'}
      </p>
      {value.stale_reason && (
        <p className="rp-warning">
          {value.stale_reason} Conservamos esta evidencia como historial.
        </p>
      )}
      <p>
        {p.total_rows} filas ·{' '}
        <strong>{p.complete_case_count} casos completos</strong> ·{' '}
        {p.excluded_count} excluidos ({p.excluded_missing_count} por faltantes;{' '}
        {p.excluded_invalid_count} por valores inválidos).
      </p>
      {p.complete_pair_count != null && (
        <p>
          {p.complete_pair_count} pares completos ·{' '}
          {p.zero_difference_count ?? '—'} diferencias cero. Diferencia =
          primera − segunda medición.
        </p>
      )}
      {!!p.group_counts?.length && (
        <ul>
          {p.group_counts.map((g) => (
            <li key={g.label}>
              Grupo {g.label}: {g.count} casos completos
            </li>
          ))}
        </ul>
      )}
      <ul>
        {value.warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
      {value.checks.map((check, i) => (
        <section key={i} className="diagnostic-check">
          <h5>
            {checkLabels[check.name]} · {check.target}
          </h5>
          <p>
            {check.status === 'not_checked'
              ? 'No evaluado'
              : check.status === 'incompatible'
                ? 'Señal para revisar'
                : 'Compatible dentro de los límites'}{' '}
            · {check.case_count} casos
          </p>
          <p>
            {check.method} ({check.method_version})
            {check.statistic != null &&
              ` · estadístico ${format(check.statistic)}`}
            {check.p_value != null && ` · p ${format(check.p_value)}`}
          </p>
          <p>{check.details}</p>
        </section>
      ))}
      <div className="diagnostic-figures">
        {value.figures.map((figure, i) => (
          <Figure key={i} figure={figure} />
        ))}
      </div>
      <details>
        <summary>Referencias y versiones de esta evidencia</summary>
        <p>
          {value.algorithm_version} · {value.engine_version}
        </p>
        <ul>
          {value.source_refs.map((r) => (
            <li key={`${r.kind}-${r.id}`}>
              {r.kind}: {r.id} · revisión {r.revision} · hash {r.hash}
            </li>
          ))}
        </ul>
      </details>
    </article>
  );
}
