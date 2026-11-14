import { useState } from 'react';

export interface AuthorizedResidualData {
  outcome_label: string;
  points: { fitted: number; residual: number }[];
  complete_observation_count: number;
  sampled: boolean;
}

function xCoordinate(value: number, minimum: number, span: number) {
  return 40 + ((value - minimum) / span) * 240;
}

function yCoordinate(value: number, minimum: number, span: number) {
  return 180 - ((value - minimum) / span) * 150;
}

export function AuthorizedResidualPlot({
  load,
}: {
  load: () => Promise<AuthorizedResidualData>;
}) {
  const [data, setData] = useState<AuthorizedResidualData | null>(null);
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
          : 'No se pudo cargar el diagnóstico.',
      );
    } finally {
      setLoading(false);
    }
  }

  if (!data) {
    return (
      <section
        className="authorized-residuals"
        aria-label="Residuos autorizados"
      >
        <button disabled={loading} onClick={() => void show()}>
          {loading ? 'Cargando residuos…' : 'Mostrar residuos autorizados'}
        </button>
        <p>
          Carga solo los valores ajustados y residuos del modelo aprobado. En
          datos no sintéticos exige la autorización local vigente.
        </p>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  }

  const fitted = data.points.map((point) => point.fitted);
  const residuals = data.points.map((point) => point.residual);
  const minimumFitted = Math.min(...fitted);
  const maximumFitted = Math.max(...fitted);
  const minimumResidual = Math.min(...residuals, 0);
  const maximumResidual = Math.max(...residuals, 0);
  const fittedSpan = maximumFitted - minimumFitted || 1;
  const residualSpan = maximumResidual - minimumResidual || 1;
  const zeroY = yCoordinate(0, minimumResidual, residualSpan);
  return (
    <figure
      className="authorized-residuals"
      aria-label="Residuos de observaciones autorizadas"
    >
      <figcaption>
        Residuos vs. valores ajustados: {data.outcome_label}
      </figcaption>
      <svg
        viewBox="0 0 320 220"
        role="img"
        aria-label={`${data.points.length} residuos autorizados`}
      >
        <line x1="40" y1="180" x2="280" y2="180" />
        <line x1="40" y1="30" x2="40" y2="180" />
        <line
          className="authorized-residual-zero"
          x1="40"
          y1={zeroY}
          x2="280"
          y2={zeroY}
        />
        {data.points.map((point, index) => (
          <circle
            key={`${point.fitted}-${point.residual}-${index}`}
            cx={xCoordinate(point.fitted, minimumFitted, fittedSpan)}
            cy={yCoordinate(point.residual, minimumResidual, residualSpan)}
            r="3"
          />
        ))}
        <text x="160" y="210" textAnchor="middle">
          Valores ajustados
        </text>
        <text transform="translate(14 105) rotate(-90)" textAnchor="middle">
          Residuo
        </text>
      </svg>
      <p>
        {data.complete_observation_count} observaciones completas
        {data.sampled
          ? `; se muestran ${data.points.length} de forma determinista.`
          : '.'}
      </p>
    </figure>
  );
}
