import { afterEach, describe, expect, it, vi } from 'vitest';
import { createMethodologyApi } from './api';

afterEach(() => vi.unstubAllGlobals());
describe('methodology HTTP API', () => {
  it('reads status and sends consent only on POST, with no credentials', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}'));
    vi.stubGlobal('fetch', fetchMock);
    const api = createMethodologyApi('http://localhost:8001');
    await api.status('project', 'document');
    expect(fetchMock.mock.calls[0][0]).toContain('/methodology/status');
    expect(fetchMock.mock.calls[0][1].method).toBe('GET');
    fetchMock.mockResolvedValue(new Response('{}'));
    await api.analyze('project', 'document');
    expect(fetchMock.mock.calls[1][1].body).toBe(
      '{"send_to_external_ai":true}',
    );
    expect(fetchMock.mock.calls[1][1].headers).toEqual({
      'Content-Type': 'application/json',
    });
  });
  it('shows public backend and connection errors', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response('{"detail":"Cuota agotada"}', { status: 503 }),
      );
    vi.stubGlobal('fetch', fetchMock);
    const api = createMethodologyApi();
    await expect(api.analyze('p', 'd')).rejects.toThrow('Cuota agotada');
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api.status('p', 'd')).rejects.toThrow('Consulta el estado');
  });
});
