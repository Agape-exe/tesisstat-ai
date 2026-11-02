import { afterEach, expect, it, vi } from 'vitest';
import { createAnalysisApi } from './api';

afterEach(() => vi.unstubAllGlobals());

it('encodes project IDs and sends only package and hypothesis references', async () => {
  const fetcher = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
  vi.stubGlobal('fetch', fetcher);
  await createAnalysisApi('http://127.0.0.1:8001/').propose(
    'project/id',
    'p',
    'h',
  );
  expect(fetcher.mock.calls[0]).toEqual([
    'http://127.0.0.1:8001/api/research/projects/project%2Fid/analysis/plan',
    expect.objectContaining({
      method: 'POST',
      body: '{"package_id":"p","hypothesis_id":"h"}',
    }),
  ]);
});

it('translates network failure into a recoverable local message', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new Error('network');
    }),
  );
  await expect(createAnalysisApi().plans('p')).rejects.toThrow(
    'Recarga para recuperar el estado',
  );
});

it('reports download errors and never sends calculated values from the client', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(
        JSON.stringify({ detail: 'El resultado está desactualizado.' }),
        { status: 409 },
      ),
    );
  vi.stubGlobal('fetch', fetcher);
  const record = {
    plan: { id: 'plan/id' },
    result: { id: 'result/id' },
  } as Parameters<ReturnType<typeof createAnalysisApi>['download']>[1];
  await expect(
    createAnalysisApi('http://127.0.0.1:8001').download(
      'project/id',
      record,
      'pdf',
    ),
  ).rejects.toThrow('El resultado está desactualizado.');
  expect(fetcher).toHaveBeenCalledWith(
    'http://127.0.0.1:8001/api/research/projects/project%2Fid/analysis/plans/plan%2Fid/results/result%2Fid/report.pdf',
    { signal: expect.any(AbortSignal) },
  );
});
