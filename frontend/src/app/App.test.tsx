import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';

describe('Backend connection', () => {
  it('shows the API version after a successful request', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: 'ok',
            service: 'tesisstat-api',
            version: '0.1.0',
          }),
        ),
      ),
    );
    render(<App />);
    expect(
      await screen.findByText('Backend conectado · API v0.1.0'),
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/health',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('allows retrying a failed request', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockRejectedValueOnce(new Error('offline'))
        .mockResolvedValue(
          new Response(
            JSON.stringify({
              status: 'ok',
              service: 'tesisstat-api',
              version: '0.1.0',
            }),
          ),
        ),
    );
    render(<App />);
    expect(await screen.findByText(/No se pudo conectar/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Verificar conexión' }));
    expect(await screen.findByText(/Backend conectado/)).toBeInTheDocument();
  });

  it.each([
    new Response('{}', { status: 503 }),
    new Response(JSON.stringify({ status: 'invalid' })),
  ])('reports an invalid health response', async (response) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
    render(<App />);
    expect(await screen.findByText(/No se pudo conectar/)).toBeInTheDocument();
  });
});
