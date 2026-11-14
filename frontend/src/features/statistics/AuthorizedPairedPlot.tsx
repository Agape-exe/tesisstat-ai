import { useState } from 'react';

export interface AuthorizedPairedData {
  before_label: string;
  after_label: string;
  points: { before: number; after: number }[];
  complete_pair_count: number;
  sampled: boolean;
}

export function AuthorizedPairedPlot({
  load,
}: {
  load: () => Promise<AuthorizedPairedData>;
}) {
  const [data, setData] = useState<AuthorizedPairedData | null>(null);
  const [error, setError] = useState('');
  async function show() {
    setError('');
    try {
      setData(await load());
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo cargar los pares.',
      );
    }
  }
  if (!data)
    return (
      <section className="authorized-pairs" aria-label="Pares autorizados">
        <button onClick={() => void show()}>Mostrar pares autorizados</button>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  const values = data.points.flatMap((point) => [point.before, point.after]);
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const y = (value: number) => 180 - ((value - min) / span) * 150;
  return (
    <figure
      className="authorized-pairs"
      aria-label="Cambios de pares autorizados"
    >
      <figcaption>
        Pares: {data.before_label} y {data.after_label}
      </figcaption>
      <svg
        viewBox="0 0 320 220"
        role="img"
        aria-label={`${data.points.length} pares autorizados`}
      >
        <line x1="70" y1="180" x2="250" y2="180" />
        {data.points.map((point, index) => (
          <line
            key={`${point.before}-${point.after}-${index}`}
            x1="100"
            y1={y(point.before)}
            x2="220"
            y2={y(point.after)}
          />
        ))}
        <text x="100" y="205" textAnchor="middle">
          {data.before_label}
        </text>
        <text x="220" y="205" textAnchor="middle">
          {data.after_label}
        </text>
      </svg>
      <p>
        {data.complete_pair_count} pares completos
        {data.sampled
          ? `; se muestran ${data.points.length} de forma determinista.`
          : '.'}
      </p>
    </figure>
  );
}
