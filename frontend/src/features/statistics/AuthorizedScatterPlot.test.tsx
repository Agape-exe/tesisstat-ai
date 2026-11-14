import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import { AuthorizedScatterPlot } from './AuthorizedScatterPlot';

it('loads and renders only explicitly requested authorized pairs', async () => {
  const load = vi.fn(async () => ({
    x_label: 'horas',
    y_label: 'nota',
    points: [
      { x: 1, y: 2 },
      { x: 2, y: 4 },
    ],
    complete_pair_count: 2,
    sampled: false,
  }));
  render(<AuthorizedScatterPlot load={load} />);

  expect(load).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Mostrar pares autorizados' }),
  );

  expect(
    await screen.findByLabelText('Dispersión de observaciones autorizadas'),
  ).toBeInTheDocument();
  expect(load).toHaveBeenCalledOnce();
  expect(screen.getByText('2 pares completos.')).toBeInTheDocument();
});
