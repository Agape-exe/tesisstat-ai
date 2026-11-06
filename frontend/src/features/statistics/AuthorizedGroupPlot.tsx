import { useState } from 'react';

export interface AuthorizedGroupData {
  group_label: string;
  outcome_label: string;
  points: { group: string; value: number }[];
  complete_observation_count: number;
  sampled: boolean;
}

function yCoordinate(value: number, minimum: number, span: number) {
  return 180 - ((value - minimum) / span) * 150;
}

export function AuthorizedGroupPlot({
  load,
}: {
  load: () => Promise<AuthorizedGroupData>;
}) {
  const [data, setData] = useState<AuthorizedGroupData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function show() {
    setLoading(true);
    setError('');
    try {
      setData(await load());
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo cargar la distribución.',
      );
    } finally {
      setLoading(false);
    }
  }

  if (!data) {
    return (
      <section
        className="authorized-groups"
        aria-label="Distribución autorizada por grupo"
      >
        <button disabled={loading} onClick={() => void show()}>
          {loading
            ? 'Cargando distribución…'
            : 'Mostrar distribución por grupo'}
        </button>
        <p>
          Carga únicamente los resultados numéricos y grupos del plan aprobado.
          En datos no sintéticos exige la autorización local vigente.
        </p>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  }

  const groups = [...new Set(data.points.map((point) => point.group))];
  const values = data.points.map((point) => point.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || 1;
  const xCoordinate = (group: string) => {
    const index = groups.indexOf(group);
    return 40 + ((index + 0.5) / groups.length) * 240;
  };

  return (
    <figure
      className="authorized-groups"
      aria-label="Distribución de grupos autorizados"
    >
      <figcaption>
        Distribución: {data.outcome_label} por {data.group_label}
      </figcaption>
      <svg
        viewBox="0 0 320 220"
        role="img"
        aria-label={`${data.points.length} observaciones autorizadas por grupo`}
      >
        <line x1="40" y1="180" x2="280" y2="180" />
        <line x1="40" y1="30" x2="40" y2="180" />
        {data.points.map((point, index) => (
          <circle
            key={`${point.group}-${point.value}-${index}`}
            cx={xCoordinate(point.group)}
            cy={yCoordinate(point.value, minimum, span)}
            r="3"
          />
        ))}
        {groups.map((group) => (
          <text key={group} x={xCoordinate(group)} y="198" textAnchor="middle">
            {group}
          </text>
        ))}
        <text transform="translate(14 105) rotate(-90)" textAnchor="middle">
          {data.outcome_label}
        </text>
      </svg>
      <p>
        {data.complete_observation_count} observaciones completas
        {data.sampled
          ? `; se muestran ${data.points.length} de forma estratificada y determinista.`
          : '.'}
      </p>
    </figure>
  );
}
