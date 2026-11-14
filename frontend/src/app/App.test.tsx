import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from './App';

afterEach(() => vi.unstubAllGlobals());

it('opens the real project application at the main entry point', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[]')));
  render(<App />);
  expect(
    await screen.findByText('Tu próxima investigación empieza aquí'),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: 'Nueva investigación' }),
  ).toBeEnabled();
  expect(
    screen.getByRole('link', { name: 'TesisStat AI, investigaciones' }),
  ).toHaveAttribute('href', '/');
  expect(fetch).toHaveBeenCalledWith(
    'http://127.0.0.1:8001/api/research/projects',
    expect.any(Object),
  );
});
