import { useState } from 'react';

export interface AuthorizedScatterData {
  x_label: string;
  y_label: string;
  points: { x: number; y: number }[];
  complete_pair_count: number;
  sampled: boolean;
}

function coordinate(
  value: number,
  minimum: number,
  span: number,
  invert = false,
) {
  const percentage = (value - minimum) / span;
  return invert ? 180 - percentage * 150 : 40 + percentage * 240;
}

export function AuthorizedScatterPlot({
  load,
}: {
  load: () => Promise<AuthorizedScatterData>;
}) {
  const [data, setData] = useState<AuthorizedScatterData | null>(null);
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
          : 'No se pudo cargar el gráfico.',
      );
    } finally {
      setLoading(false);
    }
  }

  if (!data) {
    return (
      <section
        className="authorized-scatter"
        aria-label="Observaciones autorizadas"
      >
        <button disabled={loading} onClick={() => void show()}>
          {loading ? 'Cargando observaciones…' : 'Mostrar pares autorizados'}
        </button>
        <p>
          Carga únicamente los pares numéricos de las variables aprobadas. En
          datos no sintéticos exige la autorización local vigente.
        </p>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  }

  const xs = data.points.map((point) => point.x);
  const ys = data.points.map((point) => point.y);
  const minimumX = Math.min(...xs);
  const maximumX = Math.max(...xs);
  const minimumY = Math.min(...ys);
  const maximumY = Math.max(...ys);
  const spanX = maximumX - minimumX || 1;
  const spanY = maximumY - minimumY || 1;
  return (
    <figure
      className="authorized-scatter"
      aria-label="Dispersión de observaciones autorizadas"
    >
      <figcaption>
        Dispersión: {data.x_label} y {data.y_label}
      </figcaption>
      <svg
        viewBox="0 0 320 220"
        role="img"
        aria-label={`${data.points.length} pares autorizados`}
      >
        <line x1="40" y1="180" x2="280" y2="180" />
        <line x1="40" y1="30" x2="40" y2="180" />
        {data.points.map((point, index) => (
          <circle
            key={`${point.x}-${point.y}-${index}`}
            cx={coordinate(point.x, minimumX, spanX)}
            cy={coordinate(point.y, minimumY, spanY, true)}
            r="3"
          />
        ))}
        <text x="160" y="210" textAnchor="middle">
          {data.x_label}
        </text>
        <text transform="translate(14 105) rotate(-90)" textAnchor="middle">
          {data.y_label}
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
