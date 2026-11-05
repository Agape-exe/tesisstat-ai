import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import { AuthorizedResidualPlot } from './AuthorizedResidualPlot';

it('loads a residual diagnostic only after an explicit request', async () => {
  const load = vi.fn(async () => ({
    outcome_label: 'nota',
    points: [
      { fitted: 2, residual: -0.5 },
      { fitted: 4, residual: 0.5 },
    ],
    complete_observation_count: 2,
    sampled: false,
  }));
  render(<AuthorizedResidualPlot load={load} />);

  expect(load).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Mostrar residuos autorizados' }),
  );

  expect(
    await screen.findByLabelText('Residuos de observaciones autorizadas'),
  ).toBeInTheDocument();
  expect(load).toHaveBeenCalledOnce();
  expect(screen.getByText('2 observaciones completas.')).toBeInTheDocument();
});
