import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import { AuthorizedGroupPlot } from './AuthorizedGroupPlot';

it('loads the approved group distribution only after an explicit request', async () => {
  const load = vi.fn(async () => ({
    group_label: 'tratamiento',
    outcome_label: 'nota',
    points: [
      { group: 'A', value: 2 },
      { group: 'B', value: 4 },
    ],
    complete_observation_count: 2,
    sampled: false,
  }));
  render(<AuthorizedGroupPlot load={load} />);

  expect(load).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Mostrar distribución por grupo' }),
  );

  expect(
    await screen.findByLabelText('Distribución de grupos autorizados'),
  ).toBeInTheDocument();
  expect(load).toHaveBeenCalledOnce();
  expect(screen.getByText('2 observaciones completas.')).toBeInTheDocument();
});
