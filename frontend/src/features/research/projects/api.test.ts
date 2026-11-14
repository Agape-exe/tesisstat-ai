import { afterEach, describe, expect, it, vi } from 'vitest';
import { createProjectApi, ProjectApiError } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('Research API adapter', () => {
  it('preserves validation errors for form fields', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: 'Revisa los datos.',
            errors: { title: 'Título inválido' },
          }),
          { status: 422 },
        ),
      ),
    );
    await expect(createProjectApi().list()).rejects.toMatchObject({
      status: 422,
      fields: { title: 'Título inválido' },
    });
  });

  it('handles a no-content deletion without parsing JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );
    await expect(
      createProjectApi('http://localhost:8001/').delete('test-id'),
    ).resolves.toBeUndefined();
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8001/api/research/projects/test-id',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('provides a readable network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(createProjectApi().list()).rejects.toBeInstanceOf(
      ProjectApiError,
    );
    await expect(createProjectApi().list()).rejects.toThrow(
      /No se pudo contactar/,
    );
  });
});
