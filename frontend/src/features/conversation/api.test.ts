import { afterEach, expect, it, vi } from 'vitest';
import { createConversationApi } from './api';

afterEach(() => vi.unstubAllGlobals());

it('sends only content, idempotency key and explicit consent to the project API', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{"messages":[]}'));
  vi.stubGlobal('fetch', fetch);
  await createConversationApi('http://127.0.0.1:8001/').send(
    'p1',
    'c1',
    'Pregunta',
    'r1',
  );
  expect(fetch).toHaveBeenCalledWith(
    'http://127.0.0.1:8001/api/research/projects/p1/conversations/c1/messages',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({
        content: 'Pregunta',
        request_id: 'r1',
        external_ai_consent: true,
      }),
    }),
  );
  expect(fetch.mock.calls[0][1].body).not.toContain('assistant');
});

it('handles provider, validation and connection errors without fake responses', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      new Response('{"detail":"Cuota agotada"}', { status: 503 }),
    )
    .mockResolvedValueOnce(new Response('{}', { status: 422 }))
    .mockRejectedValueOnce(new TypeError('Network'));
  vi.stubGlobal('fetch', fetch);
  const api = createConversationApi();
  await expect(api.status('p')).rejects.toThrow('Cuota agotada');
  await expect(api.status('p')).rejects.toThrow('No se pudo completar');
  await expect(api.status('p')).rejects.toThrow('Consulta el historial');
});

it('supports paginated history, listing, creation and deletion', async () => {
  const fetch = vi.fn().mockImplementation(
    async (_url: string, options: RequestInit) =>
      new Response(options.method === 'DELETE' ? null : '[]', {
        status: options.method === 'DELETE' ? 204 : 200,
      }),
  );
  vi.stubGlobal('fetch', fetch);
  const api = createConversationApi('http://127.0.0.1:8001');
  await api.get('p', 'c', 21);
  await api.list('p', 50);
  await api.create('p');
  await api.delete('p', 'c');
  expect(fetch.mock.calls[0][0]).toContain('/p/conversations/c?before=21');
  expect(fetch.mock.calls[1][0]).toContain('/p/conversations?offset=50');
  expect(fetch.mock.calls[2][1].method).toBe('POST');
  expect(fetch.mock.calls[3][1].method).toBe('DELETE');
});
