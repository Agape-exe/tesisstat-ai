import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { ConversationChat } from './ConversationChat';
import { ConversationApiError } from './api';
import type {
  Conversation,
  ConversationApi,
  ConversationDetail,
  Message,
  ProviderStatus,
} from './api';

const conversation: Conversation = {
  id: 'c1',
  project_id: 'p1',
  title: 'Consulta de prueba',
  created_at: '2026-11-02T12:00:00Z',
  updated_at: '2026-11-02T12:00:00Z',
};
const user: Message = {
  id: 'u1',
  conversation_id: 'c1',
  role: 'user',
  content: '¿Qué es una variable?',
  sequence: 1,
  created_at: conversation.created_at,
};
const assistant: Message = {
  ...user,
  id: 'a1',
  role: 'assistant',
  content: 'Respuesta sintética del proveedor simulado.',
  sequence: 2,
};
const detail = (messages: Message[] = []): ConversationDetail => ({
  conversation,
  messages,
  has_more: false,
});

function service(): ConversationApi {
  return {
    status: vi.fn().mockResolvedValue({
      provider_configured: true,
      model: '@cf/qwen/qwen3-30b-a3b-fp8',
      max_message_characters: 2000,
      timeout_seconds: 45,
      context: 'Solo título',
    }),
    list: vi.fn().mockResolvedValue([conversation]),
    create: vi.fn().mockResolvedValue({
      ...conversation,
      id: 'c2',
      title: 'Nueva conversación',
    }),
    get: vi.fn().mockResolvedValue(detail()),
    send: vi.fn().mockResolvedValue({ messages: [user, assistant] }),
    delete: vi.fn().mockResolvedValue(undefined),
  };
}

function researchStatus(states: Record<string, string> = {}): ProviderStatus {
  return {
    provider_configured: true,
    model: 'mock',
    max_message_characters: 2000,
    timeout_seconds: 45,
    context: 'Contexto persistido',
    project_title: 'Investigación sintética activa',
    consent_scope: 'research_context_v2',
    research_context: {
      project_id: 'p1',
      snapshot: 'snapshot-v2',
      sources: Object.entries({
        methodology: 'confirmed',
        dataset: 'current',
        eda: 'missing',
        package: 'stale',
        result: 'historical',
        ...states,
      }).map(([kind, status]) => ({
        kind,
        status,
        id: `source-${kind}`,
        version: '2',
      })),
    },
  };
}

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
});
beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

async function ready(api = service()) {
  const result = render(<ConversationChat projectId="p1" api={api} />);
  await screen.findByLabelText('Tu mensaje');
  await waitFor(() =>
    expect(
      screen.queryByText('Cargando conversaciones…'),
    ).not.toBeInTheDocument(),
  );
  return { api, ...result };
}
function authorize() {
  fireEvent.click(screen.getByRole('checkbox'));
}
function write(value = user.content) {
  fireEvent.change(screen.getByLabelText('Tu mensaje'), { target: { value } });
}

it.each([
  [['conversation'], 'Conversación'],
  [['research', 'conversation'], 'Investigación → Conversación'],
  [
    ['research', 'planning', 'conversation'],
    'Investigación → Planificación estadística → Conversación',
  ],
])('muestra solo los agentes persistidos: %s', async (agents, label) => {
  const api = service();
  vi.mocked(api.get).mockResolvedValue(
    detail([
      user,
      {
        ...assistant,
        context: {
          snapshot: 'snapshot-v2',
          sources: [],
          omitted_facts: 0,
          history_changed: false,
          history_turns: 0,
          multiagent: {
            flow_version: '17a.1',
            request_type: 'planning',
            nodes: ['router', ...agents],
            agents,
            provider_calls: 1,
            planning_status: 'proposed',
            errors: [],
          },
        },
      },
    ]),
  );
  await ready(api);
  expect(screen.getByText(`Agentes utilizados: ${label}`)).toBeInTheDocument();
  if (!agents.includes('planning'))
    expect(
      screen.queryByText(/Planificación estadística/),
    ).not.toBeInTheDocument();
});

it('abre mensajes anteriores sin inventar agentes', async () => {
  const api = service();
  vi.mocked(api.get).mockResolvedValue(detail([user, assistant]));
  await ready(api);
  expect(screen.getByText(assistant.content)).toBeInTheDocument();
  expect(screen.queryByText(/Agentes utilizados:/)).not.toBeInTheDocument();
});

it('no presenta la consulta general sin snapshot como una respuesta desactualizada', async () => {
  const api = service();
  vi.mocked(api.get).mockResolvedValue(
    detail([
      {
        ...assistant,
        context: {
          snapshot: null,
          sources: [],
          omitted_facts: 0,
          history_changed: false,
          history_turns: 0,
        },
      },
    ]),
  );
  await ready(api);
  fireEvent.click(
    screen.getByText('Fuentes proporcionadas para esta respuesta'),
  );
  expect(
    screen.queryByText(/Esta respuesta corresponde a una consulta anterior/),
  ).not.toBeInTheDocument();
});
function send() {
  fireEvent.click(screen.getByRole('button', { name: 'Enviar mensaje' }));
}

it('shows source states and explains historical results and incomplete sources', async () => {
  const api = service();
  vi.mocked(api.status).mockResolvedValue(researchStatus());
  await ready(api);
  const panel = screen.getByRole('region', {
    name: 'Contexto de investigación',
  });
  expect(
    within(panel).getByText('Investigación sintética activa'),
  ).toBeInTheDocument();
  expect(within(panel).getByText('Confirmada')).toBeInTheDocument();
  expect(within(panel).getByText('Vigente')).toBeInTheDocument();
  expect(within(panel).getByText('No disponible')).toBeInTheDocument();
  expect(
    within(panel).getByText('Desactualizado: requiere actualización'),
  ).toBeInTheDocument();
  expect(
    within(panel).getByText('Histórico: corresponde a fuentes anteriores'),
  ).toBeInTheDocument();
});

it('refreshes changed sources without losing history or consent', async () => {
  const api = service();
  vi.mocked(api.status)
    .mockResolvedValueOnce(researchStatus({ methodology: 'draft' }))
    .mockResolvedValue(researchStatus());
  vi.mocked(api.get).mockResolvedValue(detail([user, assistant]));
  await ready(api);
  expect(
    screen.getByText('Borrador: requiere confirmación'),
  ).toBeInTheDocument();
  authorize();
  fireEvent.click(screen.getByRole('button', { name: 'Actualizar contexto' }));
  expect(await screen.findByText('Confirmada')).toBeInTheDocument();
  expect(screen.getByText(assistant.content)).toBeInTheDocument();
  expect(screen.getByRole('checkbox')).toBeChecked();
  expect(api.send).not.toHaveBeenCalled();
});

it('keeps local history readable if source status fails and no consent is given', async () => {
  const api = service();
  vi.mocked(api.status).mockRejectedValue(new Error('Sources unavailable'));
  vi.mocked(api.get).mockResolvedValue(detail([user, assistant]));
  await ready(api);
  expect(screen.getByText(assistant.content)).toBeInTheDocument();
  expect(
    screen.getByText(/No se pudo actualizar el contexto/),
  ).toBeInTheDocument();
  expect(screen.getByLabelText('Tu mensaje')).toBeDisabled();
  expect(api.send).not.toHaveBeenCalled();
});

it('describes the expanded consent scope without reusing old session storage', async () => {
  sessionStorage.setItem('tesisstat:consent:v1:p1', 'true');
  await ready();
  const checkbox = screen.getByRole('checkbox');
  expect(checkbox).not.toBeChecked();
  expect(checkbox).toHaveAccessibleName(
    /información metodológica seleccionada/,
  );
  expect(checkbox).toHaveAccessibleName(
    /metadatos del dataset y métricas estadísticas verificadas/,
  );
  expect(checkbox).toHaveAccessibleName(
    /No se envían documentos completos ni datos individuales/,
  );
});

it('shows backend provenance, source changes and context omissions after reload', async () => {
  const api = service();
  vi.mocked(api.status).mockResolvedValue(researchStatus());
  vi.mocked(api.get).mockResolvedValue(
    detail([
      user,
      {
        ...assistant,
        context: {
          snapshot: 'previous-snapshot',
          history_changed: true,
          omitted_facts: 3,
          history_turns: 1,
          sources: [
            {
              kind: 'methodology',
              id: 'verified-review-id',
              status: 'confirmed',
              version: '2',
            },
          ],
        },
      },
    ]),
  );
  await ready(api);
  fireEvent.click(
    screen.getByText('Fuentes proporcionadas para esta respuesta'),
  );
  expect(screen.getByText(/verified-review-id/)).toBeInTheDocument();
  expect(
    screen.getByText(/Se omitieron 3 datos completos/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Esta respuesta corresponde a una consulta anterior/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/El historial contiene referencias a fuentes anteriores/),
  ).toBeInTheDocument();
});

it('rechecks sources when returning focus to the chat', async () => {
  const api = service();
  vi.mocked(api.status)
    .mockResolvedValueOnce(researchStatus())
    .mockResolvedValue(researchStatus({ dataset: 'missing' }));
  await ready(api);
  fireEvent(window, new Event('focus'));
  await waitFor(() => expect(api.status).toHaveBeenCalledTimes(2));
  const panel = screen.getByRole('region', {
    name: 'Contexto de investigación',
  });
  await waitFor(() =>
    expect(within(panel).queryByText('Vigente')).not.toBeInTheDocument(),
  );
});

it('renders assistant Markdown safely while keeping user messages as text', async () => {
  const api = service();
  vi.mocked(api.get).mockResolvedValue(
    detail([
      { ...user, content: '**Pregunta literal**' },
      {
        ...assistant,
        content:
          '### Ejemplo de **variable cuantitativa**\n\nUna *medida*.\nSegunda línea.\n\n- Primer elemento\n- Segundo elemento\n\n<script>alert(1)</script>\n\n[enlace](javascript:alert(1))',
      },
    ]),
  );
  await ready(api);
  expect(screen.getByText('**Pregunta literal**').tagName).toBe('P');
  const heading = screen.getByRole('heading', {
    name: 'Ejemplo de variable cuantitativa',
  });
  expect(within(heading).getByText('variable cuantitativa').tagName).toBe(
    'STRONG',
  );
  expect(screen.getByText('medida').tagName).toBe('EM');
  expect(screen.getAllByRole('listitem')).toHaveLength(3);
  expect(
    screen.getByText('medida').closest('p')?.querySelector('br'),
  ).not.toBeNull();
  expect(document.querySelector('.chat-markdown script')).toBeNull();
  expect(screen.getByText('enlace')).not.toHaveAttribute(
    'href',
    'javascript:alert(1)',
  );
});

it('loads only the current project and requires explicit external consent', async () => {
  const { api } = await ready();
  expect(api.list).toHaveBeenCalledWith('p1', 0, expect.any(AbortSignal));
  expect(api.get).toHaveBeenCalledWith(
    'p1',
    'c1',
    undefined,
    expect.any(AbortSignal),
  );
  expect(screen.getByLabelText('Tu mensaje')).toBeDisabled();
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  authorize();
  write();
  send();
  expect(await screen.findByText(assistant.content)).toBeInTheDocument();
  expect(api.send).toHaveBeenCalledWith(
    'p1',
    'c1',
    user.content,
    expect.any(String),
  );
  expect(screen.getByLabelText('Tu mensaje')).toHaveValue('');
});

it('shows processing and blocks repeated clicks and Enter submissions', async () => {
  const api = service();
  let finish!: (value: { messages: Message[] }) => void;
  vi.mocked(api.send).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  await ready(api);
  authorize();
  write();
  send();
  expect(screen.getByText('Generando respuesta…')).toBeInTheDocument();
  send();
  fireEvent.keyDown(screen.getByLabelText('Tu mensaje'), { key: 'Enter' });
  expect(api.send).toHaveBeenCalledTimes(1);
  expect(
    screen.getByRole('button', { name: '＋ Nueva conversación' }),
  ).toBeDisabled();
  await act(async () => finish({ messages: [user, assistant] }));
  expect(screen.queryByText('Generando respuesta…')).not.toBeInTheDocument();
});

it('Enter sends, Shift+Enter and IME Enter do not submit', async () => {
  const { api } = await ready();
  authorize();
  write();
  fireEvent.keyDown(screen.getByLabelText('Tu mensaje'), {
    key: 'Enter',
    shiftKey: true,
  });
  fireEvent.keyDown(screen.getByLabelText('Tu mensaje'), {
    key: 'Enter',
    isComposing: true,
  });
  expect(api.send).not.toHaveBeenCalled();
  fireEvent.keyDown(screen.getByLabelText('Tu mensaje'), { key: 'Enter' });
  await screen.findByText(assistant.content);
  expect(api.send).toHaveBeenCalledTimes(1);
});

it('rejects whitespace and enforces the configured input length', async () => {
  const { api } = await ready();
  authorize();
  write('   ');
  expect(screen.getByRole('button', { name: 'Enviar mensaje' })).toBeDisabled();
  fireEvent.keyDown(screen.getByLabelText('Tu mensaje'), { key: 'Enter' });
  expect(api.send).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Tu mensaje')).toHaveAttribute(
    'maxlength',
    '2000',
  );
});

it('shows errors, reloads persisted user messages and never invents answers', async () => {
  const api = service();
  vi.mocked(api.send).mockRejectedValue(
    new ConversationApiError('Cloudflare alcanzó su límite de cuota.', 503),
  );
  await ready(api);
  authorize();
  write();
  vi.mocked(api.get).mockResolvedValue(detail([user]));
  send();
  expect(await screen.findByRole('alert')).toHaveTextContent('límite de cuota');
  expect(await screen.findByText(user.content)).toBeInTheDocument();
  expect(screen.queryByText(assistant.content)).not.toBeInTheDocument();
  expect(api.send).toHaveBeenCalledTimes(1);
});

it('keeps sending disabled if recovery of uncertain delivery fails', async () => {
  const api = service();
  await ready(api);
  authorize();
  write();
  vi.mocked(api.send).mockRejectedValue(
    new ConversationApiError('Conexión perdida.', 0),
  );
  vi.mocked(api.get).mockRejectedValue(
    new ConversationApiError('Sin conexión.', 0),
  );
  send();
  await screen.findByRole('alert');
  await waitFor(() =>
    expect(screen.getByLabelText('Tu mensaje')).toBeDisabled(),
  );
});

it('restores selected history after remount and requests consent again', async () => {
  const api = service();
  vi.mocked(api.get).mockResolvedValue(detail([user, assistant]));
  sessionStorage.setItem('tesisstat:conversation:v1:p1', 'c1');
  const rendered = await ready(api);
  expect(screen.getByText(assistant.content)).toBeInTheDocument();
  authorize();
  rendered.unmount();
  await ready(api);
  expect(screen.getByText(assistant.content)).toBeInTheDocument();
  expect(screen.getByRole('checkbox')).not.toBeChecked();
});

it('creates a second conversation and switches back to stored history', async () => {
  const { api } = await ready();
  fireEvent.click(
    screen.getByRole('button', { name: '＋ Nueva conversación' }),
  );
  await waitFor(() => expect(api.create).toHaveBeenCalledWith('p1'));
  expect(
    await screen.findByText('Nueva conversación', { selector: 'strong' }),
  ).toBeInTheDocument();
  vi.mocked(api.get).mockResolvedValue(detail([user, assistant]));
  fireEvent.click(screen.getByRole('button', { name: /Consulta de prueba/ }));
  await screen.findByText(assistant.content);
  expect(sessionStorage.getItem('tesisstat:conversation:v1:p1')).toBe('c1');
});

it('confirms deletion, supports cancellation and removes the conversation', async () => {
  const { api } = await ready();
  fireEvent.click(
    screen.getByRole('button', { name: 'Eliminar conversación' }),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
  expect(api.delete).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Eliminar conversación' }),
  );
  fireEvent.click(
    within(screen.getByRole('dialog')).getByRole('button', {
      name: 'Confirmar eliminación',
    }),
  );
  await screen.findByText('Aún no hay conversaciones.');
  expect(api.delete).toHaveBeenCalledWith('p1', 'c1');
});

it('keeps history if deletion fails', async () => {
  const api = service();
  vi.mocked(api.delete).mockRejectedValue(
    new ConversationApiError('No se pudo eliminar.', 503),
  );
  await ready(api);
  fireEvent.click(
    screen.getByRole('button', { name: 'Eliminar conversación' }),
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Confirmar eliminación' }),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se pudo eliminar.',
  );
  expect(screen.getByRole('dialog')).toBeInTheDocument();
});

it('unconfigured provider still allows reading and creating conversations', async () => {
  const api = service();
  vi.mocked(api.status).mockResolvedValue({
    provider_configured: false,
    model: 'qwen3',
    max_message_characters: 2000,
    timeout_seconds: 45,
    context: '',
  });
  vi.mocked(api.get).mockResolvedValue(detail([user, assistant]));
  await ready(api);
  authorize();
  expect(
    screen.getByText(/Cloudflare no está configurado/),
  ).toBeInTheDocument();
  expect(screen.getByText(assistant.content)).toBeInTheDocument();
  expect(screen.getByLabelText('Tu mensaje')).toBeDisabled();
  expect(
    screen.getByRole('button', { name: '＋ Nueva conversación' }),
  ).toBeEnabled();
  expect(api.send).not.toHaveBeenCalled();
});

it('handles a missing project without enabling send', async () => {
  const api = service();
  vi.mocked(api.list).mockRejectedValue(
    new ConversationApiError('No se encontró el proyecto.', 404),
  );
  render(<ConversationChat projectId="missing" api={api} />);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se encontró el proyecto.',
  );
  expect(api.list).toHaveBeenCalledWith('missing', 0, expect.any(AbortSignal));
  expect(
    screen.queryByRole('button', { name: 'Enviar mensaje' }),
  ).not.toBeInTheDocument();
});

it('handles a deleted saved conversation', async () => {
  const api = service();
  vi.mocked(api.get).mockRejectedValue(
    new ConversationApiError('No se encontró la conversación.', 404),
  );
  sessionStorage.setItem('tesisstat:conversation:v1:p1', 'deleted');
  render(<ConversationChat projectId="p1" api={api} />);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se encontró la conversación.',
  );
  expect(api.get).toHaveBeenCalledWith(
    'p1',
    'deleted',
    undefined,
    expect.any(AbortSignal),
  );
});

it('loads older messages without replacing recent history', async () => {
  const api = service();
  vi.mocked(api.get).mockResolvedValue({
    ...detail([
      { ...user, sequence: 3 },
      { ...assistant, sequence: 4 },
    ]),
    has_more: true,
  });
  await ready(api);
  vi.mocked(api.get).mockResolvedValue(
    detail([{ ...user, id: 'old', content: 'Mensaje anterior' }]),
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Cargar mensajes anteriores' }),
  );
  expect(await screen.findByText('Mensaje anterior')).toBeInTheDocument();
  expect(screen.getByText(assistant.content)).toBeInTheDocument();
  expect(api.get).toHaveBeenLastCalledWith('p1', 'c1', 3);
});

it('renders HTML as text and never executes scripts', async () => {
  const api = service();
  const html = '<script>alert("x")</script><img src=x onerror=alert(1)>';
  vi.mocked(api.get).mockResolvedValue(
    detail([{ ...assistant, content: html }]),
  );
  const { container } = await ready(api);
  expect(screen.getByText(html)).toBeInTheDocument();
  expect(container.querySelector('script, img')).toBeNull();
});

it('discards a late response after leaving the project', async () => {
  const api = service();
  let finish!: (value: { messages: Message[] }) => void;
  vi.mocked(api.send).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { unmount } = await ready(api);
  authorize();
  write();
  send();
  unmount();
  render(<ConversationChat key="p2" projectId="p2" api={service()} />);
  await act(async () => finish({ messages: [user, assistant] }));
  expect(screen.queryByText(assistant.content)).not.toBeInTheDocument();
});
