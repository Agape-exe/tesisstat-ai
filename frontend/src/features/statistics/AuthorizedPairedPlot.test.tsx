import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import { AuthorizedPairedPlot } from './AuthorizedPairedPlot';

it('loads approved pairs only after an explicit request', async () => {
  const load = vi.fn(async () => ({
    before_label: 'pre',
    after_label: 'post',
    points: [{ before: 2, after: 4 }],
    complete_pair_count: 1,
    sampled: false,
  }));
  render(<AuthorizedPairedPlot load={load} />);

  expect(load).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Mostrar pares autorizados' }),
  );

  expect(
    await screen.findByLabelText('Cambios de pares autorizados'),
  ).toBeInTheDocument();
  expect(load).toHaveBeenCalledOnce();
  expect(screen.getByText('1 pares completos.')).toBeInTheDocument();
});
