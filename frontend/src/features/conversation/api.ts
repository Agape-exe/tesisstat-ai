export interface Conversation {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}
export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  sequence: number;
  context?: ContextTrace | null;
}
export interface ContextSource {
  kind: string;
  id: string;
  status: string;
  version: string;
}
export interface ContextTrace {
  snapshot: string | null;
  sources: ContextSource[];
  omitted_facts: number;
  history_changed: boolean;
  history_turns: number;
  multiagent?: {
    flow_version: string;
    request_type: string;
    nodes: string[];
    agents: string[];
    provider_calls: number;
    planning_status: string;
    errors: string[];
  };
}
export interface ResearchContextStatus {
  project_id: string;
  snapshot: string;
  sources: ContextSource[];
}
export interface ConversationDetail {
  conversation: Conversation;
  messages: Message[];
  has_more: boolean;
}
export interface ProviderStatus {
  provider_configured: boolean;
  model: string;
  max_message_characters: number;
  timeout_seconds: number;
  context: string;
  project_title?: string;
  consent_scope?: string;
  research_context?: ResearchContextStatus | null;
}
export class ConversationApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function createConversationApi(
  baseUrl = import.meta.env.VITE_RESEARCH_API_BASE_URL ??
    'http://127.0.0.1:8001',
) {
  async function request<T>(
    projectId: string,
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(
        `${baseUrl.replace(/\/$/, '')}/api/research/projects/${encodeURIComponent(projectId)}/conversations${path}`,
        {
          ...options,
          headers: options.body
            ? { 'Content-Type': 'application/json' }
            : undefined,
          signal: options.signal
            ? AbortSignal.any([options.signal, AbortSignal.timeout(135000)])
            : AbortSignal.timeout(135000),
        },
      );
    } catch {
      throw new ConversationApiError(
        'No se pudo contactar con el chat. Consulta el historial antes de volver a enviar.',
        0,
      );
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ConversationApiError(
        typeof body?.detail === 'string'
          ? body.detail
          : 'No se pudo completar la operación del chat.',
        response.status,
      );
    }
    return response.status === 204
      ? (undefined as T)
      : (response.json() as Promise<T>);
  }
  return {
    status: (p: string, signal?: AbortSignal) =>
      request<ProviderStatus>(p, '/status', { signal }),
    list: (p: string, offset = 0, signal?: AbortSignal) =>
      request<Conversation[]>(p, `?offset=${offset}`, { signal }),
    create: (p: string) =>
      request<Conversation>(p, '', {
        method: 'POST',
        body: JSON.stringify({ title: 'Nueva conversación' }),
      }),
    get: (p: string, c: string, before?: number, signal?: AbortSignal) =>
      request<ConversationDetail>(
        p,
        `/${encodeURIComponent(c)}${before ? `?before=${before}` : ''}`,
        { signal },
      ),
    send: (p: string, c: string, content: string, requestId: string) =>
      request<{ messages: Message[] }>(
        p,
        `/${encodeURIComponent(c)}/messages`,
        {
          method: 'POST',
          body: JSON.stringify({
            content,
            request_id: requestId,
            external_ai_consent: true,
            consent_scope: 'research_context_v2',
          }),
        },
      ),
    delete: (p: string, c: string) =>
      request<void>(p, `/${encodeURIComponent(c)}`, { method: 'DELETE' }),
  };
}
export type ConversationApi = ReturnType<typeof createConversationApi>;
