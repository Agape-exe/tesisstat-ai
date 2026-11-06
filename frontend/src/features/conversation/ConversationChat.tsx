import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import { createConversationApi, ConversationApiError } from './api';
import type {
  Conversation,
  ConversationApi,
  ConversationDetail,
  ProviderStatus,
} from './api';
import './conversation.css';

const defaultApi = createConversationApi();
const agentNames: Record<string, string> = {
  research: 'Investigación',
  planning: 'Planificación estadística',
  conversation: 'Conversación',
};
const errorText = (error: unknown) =>
  error instanceof ConversationApiError
    ? error.message
    : 'No se pudo completar la operación del chat.';
const sourceNames: Record<string, string> = {
  project: 'Proyecto',
  methodology: 'Metodología',
  dataset: 'Dataset',
  eda: 'Perfil EDA',
  preparation: 'Preparación',
  package: 'ResearchPackage',
  plan: 'Plan estadístico',
  result: 'Resultado',
  sources: 'Fuentes',
};
const sourceStates: Record<string, string> = {
  current: 'Vigente',
  confirmed: 'Confirmada',
  draft: 'Borrador: requiere confirmación',
  missing: 'No disponible',
  stale: 'Desactualizado: requiere actualización',
  incomplete: 'Incompleto: revisa las fuentes y vinculaciones',
  ready: 'Listo para generar; aún sin paquete',
  warnings: 'Pendiente de generar con advertencias',
  historical: 'Histórico: corresponde a fuentes anteriores',
  proposed: 'Propuesto: pendiente de aprobación',
  approved: 'Aprobado',
  needs_clarification: 'Requiere aclaraciones',
  completed: 'Ejecutado y completado',
  failed: 'Fallido: sin resultados utilizables',
  not_executed: 'No ejecutado',
  original: 'Dataset original',
  prepared: 'Preparación aplicada',
  unverified: 'No se pudo verificar; actualiza las fuentes',
};

export function ConversationChat({
  projectId,
  api = defaultApi,
  onOpenResource,
}: {
  projectId: string;
  api?: ConversationApi;
  onOpenResource?: (section: 'documents' | 'datasets' | 'instrument') => void;
}) {
  // The parent keys this component by project: no state or requests cross projects.
  const [items, setItems] = useState<Conversation[]>([]);
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState('');
  const [consent, setConsent] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [more, setMore] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [contextError, setContextError] = useState('');
  const [contextBusy, setContextBusy] = useState(false);
  const locked = useRef(false);
  const active = useRef(true);
  const selection = useRef(0);
  const messagesViewport = useRef<HTMLDivElement>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const deleteButton = useRef<HTMLButtonElement>(null);
  const selectedKey = `tesisstat:conversation:v1:${projectId}`;

  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    // Source failures must not block access to local conversation history.
    api
      .status(projectId, controller.signal)
      .then((provider) => {
        if (!controller.signal.aborted) {
          setStatus(provider);
          setContextError('');
        }
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setContextError(
            'No se pudo actualizar el contexto. Puedes consultar tu historial.',
          );
      });
    api
      .list(projectId, 0, controller.signal)
      .then(async (conversations) => {
        if (controller.signal.aborted) return;
        setItems(conversations);
        setMore(conversations.length > 0);
        let saved: string | null = null;
        try {
          saved = sessionStorage.getItem(selectedKey);
        } catch {
          /* Storage can be disabled. */
        }
        const id = saved ?? conversations[0]?.id;
        if (id) {
          try {
            const history = await api.get(
              projectId,
              id,
              undefined,
              controller.signal,
            );
            if (!controller.signal.aborted) setDetail(history);
          } catch (caught) {
            if (!controller.signal.aborted) setError(errorText(caught));
          }
        }
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorText(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      active.current = false;
      controller.abort();
    };
  }, [api, projectId, selectedKey, refresh]);

  async function refreshContext() {
    setContextBusy(true);
    try {
      const provider = await api.status(projectId);
      if (active.current) {
        setStatus(provider);
        setContextError('');
      }
    } catch {
      if (active.current)
        setContextError(
          'No se pudo actualizar el contexto. Puedes consultar tu historial.',
        );
    } finally {
      if (active.current) setContextBusy(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    const update = () => {
      api
        .status(projectId, controller.signal)
        .then((provider) => {
          if (!controller.signal.aborted) {
            setStatus(provider);
            setContextError('');
          }
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setContextError(
              'No se pudo actualizar el contexto. Puedes consultar tu historial.',
            );
        });
    };
    window.addEventListener('focus', update);
    return () => {
      controller.abort();
      window.removeEventListener('focus', update);
    };
  }, [api, projectId]);

  useEffect(() => {
    // Scroll the history pane only; opening a project must not move the page
    // past its heading or the mobile navigation.
    const viewport = messagesViewport.current;
    if (viewport) viewport.scrollTop = viewport.scrollHeight;
  }, [detail?.messages.length, sending]);
  useEffect(() => {
    if (deleting) deleteDialog.current?.showModal();
  }, [deleting]);

  function remember(id: string | null) {
    try {
      if (id) sessionStorage.setItem(selectedKey, id);
      else sessionStorage.removeItem(selectedKey);
    } catch {
      /* History still lives on the server. */
    }
  }

  async function choose(id: string) {
    if (locked.current) return;
    const version = ++selection.current;
    setBusy(true);
    setError('');
    setDraft('');
    try {
      const history = await api.get(projectId, id);
      if (active.current && version === selection.current) {
        setDetail(history);
        remember(id);
      }
    } catch (caught) {
      if (active.current && version === selection.current) {
        setDetail(null);
        setError(errorText(caught));
      }
    } finally {
      if (active.current && version === selection.current) setBusy(false);
    }
  }

  async function create() {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError('');
    try {
      const conversation = await api.create(projectId);
      if (!active.current) return;
      setItems((old) => [conversation, ...old]);
      setDetail({ conversation, messages: [], has_more: false });
      setDraft('');
      remember(conversation.id);
    } catch (caught) {
      if (active.current) setError(errorText(caught));
    } finally {
      locked.current = false;
      if (active.current) setBusy(false);
    }
  }

  async function send() {
    if (
      locked.current ||
      busy ||
      !detail ||
      !consent ||
      !status?.provider_configured ||
      !draft.trim()
    )
      return;
    locked.current = true;
    setSending(true);
    setError('');
    const content = draft.trim();
    const id = detail.conversation.id;
    try {
      const result = await api.send(
        projectId,
        id,
        content,
        crypto.randomUUID(),
      );
      if (!active.current) return;
      setDetail(
        (old) =>
          old && {
            ...old,
            messages: [
              ...old.messages.filter(
                (m) => !result.messages.some((n) => n.id === m.id),
              ),
              ...result.messages,
            ],
          },
      );
      setDraft('');
      void refreshContext();
    } catch (caught) {
      if (!active.current) return;
      setError(errorText(caught));
      // A lost HTTP response may have committed. Reload before a deliberate new send.
      try {
        const history = await api.get(projectId, id);
        if (active.current) {
          setDetail(history);
          setDraft('');
        }
      } catch {
        if (active.current) setStatus(null);
      }
    } finally {
      locked.current = false;
      if (active.current) setSending(false);
    }
  }

  async function remove() {
    if (!detail || locked.current) return;
    locked.current = true;
    setBusy(true);
    setError('');
    try {
      await api.delete(projectId, detail.conversation.id);
      if (!active.current) return;
      setItems((old) => old.filter((c) => c.id !== detail.conversation.id));
      setDetail(null);
      setDraft('');
      remember(null);
      setDeleting(false);
    } catch (caught) {
      if (active.current) setError(errorText(caught));
    } finally {
      locked.current = false;
      if (active.current) setBusy(false);
    }
  }

  async function olderMessages() {
    if (!detail || busy || locked.current) return;
    setBusy(true);
    setError('');
    try {
      const older = await api.get(
        projectId,
        detail.conversation.id,
        detail.messages[0]?.sequence,
      );
      if (active.current)
        setDetail(
          (old) =>
            old && {
              ...old,
              has_more: older.has_more,
              messages: [...older.messages, ...old.messages],
            },
        );
    } catch (caught) {
      if (active.current) setError(errorText(caught));
    } finally {
      if (active.current) setBusy(false);
    }
  }

  async function moreConversations() {
    setBusy(true);
    setError('');
    try {
      const next = await api.list(projectId, items.length);
      if (active.current) {
        setItems((old) => [
          ...old,
          ...next.filter((n) => !old.some((c) => c.id === n.id)),
        ]);
        setMore(next.length > 0);
      }
    } catch (caught) {
      if (active.current) setError(errorText(caught));
    } finally {
      if (active.current) setBusy(false);
    }
  }

  return (
    <section className="chat" aria-label="Asistente IA" aria-busy={loading}>
      <header className="chat-header">
        <div>
          <p className="rp-eyebrow">ORIENTACIÓN ACADÉMICA</p>
          <h2>Asistente IA</h2>
          <p>Una pregunta a la vez, avanza con tu investigación.</p>
        </div>
        <span className="rp-badge">
          {status?.model === 'simulado-local-sin-red'
            ? 'Proveedor simulado · Sin red'
            : 'Qwen3 · Cloudflare'}
        </span>
      </header>
      <p className="rp-hint">
        El contexto se verifica para cada pregunta. El historial puede referirse
        a versiones anteriores. Revisa las respuestas con criterio académico.
        Demostración local sin autenticación: usa únicamente información
        ficticia.
      </p>
      <details className="chat-context-disclosure">
        <summary>Fuentes y contexto de investigación</summary>
        <section
          className="chat-context"
          aria-label="Contexto de investigación"
        >
          <div className="chat-toolbar">
            <h3>Contexto de investigación</h3>
            <button
              className="rp-secondary"
              disabled={sending || contextBusy}
              onClick={() => void refreshContext()}
            >
              {contextBusy ? 'Actualizando contexto…' : 'Actualizar contexto'}
            </button>
          </div>
          <p>
            <strong>Proyecto activo:</strong>{' '}
            {status?.project_title ?? projectId}
          </p>
          {status?.research_context ? (
            <dl className="chat-source-grid">
              {status.research_context.sources
                .filter((s) => s.kind !== 'project')
                .map((s) => (
                  <div key={`${s.kind}:${s.id}`}>
                    <dt>{sourceNames[s.kind] ?? s.kind}</dt>
                    <dd>{sourceStates[s.status] ?? s.status}</dd>
                  </div>
                ))}
            </dl>
          ) : (
            <p>Los estados de las fuentes aún no se han verificado.</p>
          )}
          <small>
            Un borrador no confirma la metodología. Generar un paquete y
            ejecutar análisis requieren los pasos de revisión del sistema.
          </small>
        </section>
      </details>
      {contextError && (
        <p role="status" className="chat-warning">
          {contextError}
        </p>
      )}
      {status?.research_context?.sources.some((source) =>
        ['stale', 'unverified'].includes(source.status),
      ) && (
        <p className="chat-warning" role="status">
          Hay fuentes desactualizadas o sin verificar. Revisa «Fuentes y
          contexto de investigación» antes de interpretar las respuestas.
        </p>
      )}
      {loading && <p role="status">Cargando conversaciones…</p>}
      {error && (
        <div role="alert" className="rp-error">
          <p>{error}</p>
          <button
            className="rp-secondary"
            disabled={busy || sending}
            onClick={() => {
              setLoading(true);
              setError('');
              setRefresh((n) => n + 1);
            }}
          >
            Actualizar historial y configuración
          </button>
        </div>
      )}
      {status && !status.provider_configured && (
        <p role="status" className="chat-warning">
          Cloudflare no está configurado. El envío está deshabilitado; puedes
          consultar y organizar tu historial.
        </p>
      )}
      <div className="chat-layout">
        <aside
          className="chat-sidebar"
          aria-label="Conversaciones del proyecto"
        >
          <button
            onClick={() => void create()}
            disabled={loading || busy || sending}
          >
            ＋ Nueva conversación
          </button>
          {!loading && items.length === 0 && <p>Aún no hay conversaciones.</p>}
          <ul>
            {items.map((c) => (
              <li key={c.id}>
                <button
                  className="rp-secondary"
                  aria-pressed={detail?.conversation.id === c.id}
                  disabled={busy || sending}
                  onClick={() => void choose(c.id)}
                >
                  {c.title}
                  <small>
                    {new Date(c.created_at).toLocaleString('es-PE')}
                  </small>
                </button>
              </li>
            ))}
          </ul>
          {items.length > 0 && more && (
            <button
              className="rp-link"
              disabled={busy || sending}
              onClick={() => void moreConversations()}
            >
              Más conversaciones
            </button>
          )}
        </aside>
        <div className="chat-main">
          {detail ? (
            <>
              <div className="chat-toolbar">
                <strong>{detail.conversation.title}</strong>
                <button
                  ref={deleteButton}
                  className="rp-delete"
                  disabled={busy || sending}
                  onClick={() => setDeleting(true)}
                >
                  Eliminar conversación
                </button>
              </div>
              {detail.has_more && (
                <button
                  className="rp-link"
                  disabled={busy || sending}
                  onClick={() => void olderMessages()}
                >
                  Cargar mensajes anteriores
                </button>
              )}
              <div
                className="chat-messages"
                ref={messagesViewport}
                role="log"
                aria-label="Historial de mensajes"
                aria-live="polite"
              >
                {detail.messages.length === 0 && (
                  <div className="chat-empty">
                    <h3>¿Qué te gustaría comprender?</h3>
                    <p>
                      Puedes preguntar sobre conceptos, hipótesis o métodos
                      estadísticos. Este chat no ejecuta análisis.
                    </p>
                    <ResourceWelcome onOpenResource={onOpenResource} />
                  </div>
                )}
                {detail.messages.map((m) => (
                  <article key={m.id} className={`chat-message chat-${m.role}`}>
                    <strong>{m.role === 'user' ? 'Tú' : 'Asistente IA'}</strong>
                    {m.role === 'assistant' ? (
                      <div className="chat-markdown">
                        <ReactMarkdown
                          remarkPlugins={[remarkBreaks]}
                          components={{ img: ({ alt }) => <>{alt}</> }}
                        >
                          {m.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <p>{m.content}</p>
                    )}
                    {m.role === 'assistant' && m.context && (
                      <details className="chat-provenance">
                        <summary>
                          Fuentes proporcionadas para esta respuesta
                        </summary>
                        {m.context.history_changed && (
                          <p>
                            El historial contiene referencias a fuentes
                            anteriores o sin trazabilidad.
                          </p>
                        )}
                        {m.context.snapshot !== null &&
                          m.context.snapshot !==
                            status?.research_context?.snapshot && (
                            <p>
                              Esta respuesta corresponde a una consulta
                              anterior; comprueba las fuentes actuales.
                            </p>
                          )}
                        {m.context.omitted_facts > 0 && (
                          <p>
                            Se omitieron {m.context.omitted_facts} datos
                            completos por el límite de contexto. Haz una
                            pregunta más específica.
                          </p>
                        )}
                        {m.context.sources.map((s) => (
                          <p key={`${s.kind}:${s.id}`}>
                            {sourceNames[s.kind] ?? s.kind}:{' '}
                            {sourceStates[s.status] ?? s.status}
                            <small>
                              Referencia: {s.id} · Versión: {s.version}
                            </small>
                          </p>
                        ))}
                      </details>
                    )}
                    {m.role === 'assistant' &&
                      !!m.context?.multiagent?.agents.length && (
                        <small className="chat-agents">
                          Agentes utilizados:{' '}
                          {m.context.multiagent.agents
                            .map((agent) => agentNames[agent] ?? agent)
                            .join(' → ')}
                        </small>
                      )}
                    <time dateTime={m.created_at}>
                      {new Date(m.created_at).toLocaleTimeString('es-PE', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </time>
                  </article>
                ))}
                {sending && (
                  <p role="status" className="chat-thinking">
                    Generando respuesta…
                  </p>
                )}
              </div>
              <div className="chat-consent">
                <label>
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    disabled={sending}
                  />{' '}
                  Autorizo enviar mi mensaje, el título, el historial reciente,
                  información metodológica seleccionada, metadatos del dataset y
                  métricas estadísticas verificadas a Cloudflare Workers AI. No
                  se envían documentos completos ni datos individuales del
                  dataset. Usaré solo información ficticia. Sin aceptar puedo
                  consultar mi historial local.
                </label>
              </div>
              <form
                className="chat-composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  void send();
                }}
              >
                <label htmlFor={`chat-input-${projectId}`}>Tu mensaje</label>
                <textarea
                  id={`chat-input-${projectId}`}
                  rows={3}
                  value={draft}
                  maxLength={status?.max_message_characters ?? 2000}
                  disabled={
                    sending || busy || !status?.provider_configured || !consent
                  }
                  placeholder="Escribe tu pregunta académica…"
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (
                      e.key === 'Enter' &&
                      !e.shiftKey &&
                      !e.nativeEvent.isComposing
                    ) {
                      e.preventDefault();
                      void send();
                    }
                  }}
                />
                <div>
                  <small>
                    Enter para enviar · Shift+Enter para nueva línea ·{' '}
                    {draft.length}/{status?.max_message_characters ?? 2000}
                  </small>
                  <button
                    disabled={
                      sending ||
                      busy ||
                      !consent ||
                      !status?.provider_configured ||
                      !draft.trim()
                    }
                  >
                    Enviar mensaje
                  </button>
                </div>
              </form>
            </>
          ) : (
            <div className="chat-empty">
              <h3>Tu espacio de consulta</h3>
              <p>Crea o selecciona una conversación de esta investigación.</p>
              <ResourceWelcome onOpenResource={onOpenResource} />
            </div>
          )}
        </div>
      </div>
      {deleting && (
        <dialog
          ref={deleteDialog}
          className="rp-dialog"
          aria-labelledby="delete-chat-title"
          onCancel={(e) => {
            e.preventDefault();
            if (!busy) {
              setDeleting(false);
              deleteButton.current?.focus();
            }
          }}
        >
          <h3 id="delete-chat-title">Eliminar conversación</h3>
          <p>Se eliminarán todos sus mensajes de forma permanente.</p>
          <div className="rp-actions">
            <button
              className="rp-secondary"
              disabled={busy}
              onClick={() => {
                setDeleting(false);
                deleteButton.current?.focus();
              }}
            >
              Cancelar
            </button>
            <button
              className="rp-delete"
              disabled={busy}
              onClick={() => void remove()}
            >
              Confirmar eliminación
            </button>
          </div>
        </dialog>
      )}
    </section>
  );
}

function ResourceWelcome({
  onOpenResource,
}: {
  onOpenResource?: (section: 'documents' | 'datasets' | 'instrument') => void;
}) {
  if (!onOpenResource) return null;
  return (
    <div className="chat-resource-welcome">
      <p>
        Puedes empezar con una pregunta general. Cuando lo necesites, añade
        documentos y datos para aportar contexto verificado.
      </p>
      <div className="chat-resource-links">
        <button
          className="rp-secondary"
          onClick={() => onOpenResource('documents')}
        >
          Cargar documentos<small>PDF o DOCX</small>
        </button>
        <button
          className="rp-secondary"
          onClick={() => onOpenResource('datasets')}
        >
          Cargar datos<small>CSV o XLSX</small>
        </button>
        <button
          className="rp-secondary"
          onClick={() => onOpenResource('instrument')}
        >
          Instrumento<small>Funcionalidad pendiente</small>
        </button>
      </div>
    </div>
  );
}
