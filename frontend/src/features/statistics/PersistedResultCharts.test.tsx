import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { PersistedResultCharts } from './PersistedResultCharts';

it('renders category bars from persisted frequency metrics', () => {
  render(
    <PersistedResultCharts
      metrics={[
        { name: 'sexo.category.Mujer.count', value: 6 },
        { name: 'sexo.category.Mujer.percentage', value: 60 },
        { name: 'sexo.category.Hombre.count', value: 4 },
        { name: 'sexo.category.Hombre.percentage', value: 40 },
      ]}
    />,
  );

  expect(
    screen.getByLabelText('Frecuencias categóricas persistidas'),
  ).toBeInTheDocument();
  expect(screen.getByText('sexo: Mujer')).toBeInTheDocument();
  expect(screen.getByText('6 (60%)')).toBeInTheDocument();
});

it('renders effect and confidence interval charts from persisted metrics', () => {
  render(
    <PersistedResultCharts
      metrics={[
        { name: 'r', value: 0.8 },
        { name: 'r_ci_95_low', value: 0.2 },
        { name: 'r_ci_95_high', value: 0.95 },
      ]}
    />,
  );

  expect(
    screen.getByLabelText('Magnitudes de asociación persistidas'),
  ).toBeInTheDocument();
  expect(
    screen.getByLabelText('Intervalos de confianza persistidos'),
  ).toBeInTheDocument();
  expect(screen.getByLabelText('r: 0.2 a 0.95')).toBeInTheDocument();
});

it('does not fabricate a chart for unsupported persisted metrics', () => {
  render(<PersistedResultCharts metrics={[{ name: 'n', value: 12 }]} />);

  expect(
    screen.getByText(
      /no incluye métricas aptas para una visualización válida/i,
    ),
  ).toBeInTheDocument();
});
