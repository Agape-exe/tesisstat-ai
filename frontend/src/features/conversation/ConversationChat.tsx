import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import { createConversationApi, ConversationApiError } from './api';
import type {
  Conversation,
  ConversationApi,
  ConversationDetail,
  ProviderStatus,
} from './api';
import { ActionMenu } from '../research/projects/ActionMenu';
import { UiIcon } from '../research/projects/UiIcon';
import { navigateProject } from '../research/projects/navigation';
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
  projectTitle,
  api = defaultApi,
  onOpenResource,
}: {
  projectId: string;
  projectTitle?: string;
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
  const [deleting, setDeleting] = useState<Conversation | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [consentInfo, setConsentInfo] = useState(true);
  const simulated = status?.model === 'simulado-local-sin-red';
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
        setHistoryOpen(false);
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
      setHistoryOpen(false);
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
      loading ||
      busy ||
      !consent ||
      !status?.provider_configured ||
      !draft.trim()
    )
      return;
    locked.current = true;
    setSending(true);
    setError('');
    const content = draft.trim();
    let id = detail?.conversation.id;
    try {
      if (!id) {
        const conversation = await api.create(projectId);
        if (!active.current) return;
        id = conversation.id;
        setItems((old) => [conversation, ...old]);
        setDetail({ conversation, messages: [], has_more: false });
        remember(id);
      }
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
        if (!id) return;
        const history = await api.get(projectId, id);
        if (active.current) {
          setDetail(history);
          setHistoryOpen(false);
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
    if (!deleting || locked.current) return;
    locked.current = true;
    setBusy(true);
    setError('');
    try {
      await api.delete(projectId, deleting.id);
      if (!active.current) return;
      setItems((old) => old.filter((c) => c.id !== deleting.id));
      if (detail?.conversation.id === deleting.id) {
        setDetail(null);
        setDraft('');
        remember(null);
      }
      setDeleting(null);
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
      <div className="chat-layout">
        <aside
          id={`history-${projectId}`}
          className={`chat-sidebar ${historyOpen ? 'chat-history-open' : ''}`}
          aria-label="Conversaciones del proyecto"
        >
          <div className="chat-sidebar-heading">
            <strong>Conversaciones</strong>
            <button
              className="rp-secondary chat-history-close"
              aria-label="Cerrar historial"
              onClick={() => setHistoryOpen(false)}
            >
              <UiIcon name="x" />
            </button>
          </div>
          <button
            className="rp-secondary chat-new"
            onClick={() => void create()}
            disabled={loading || busy || sending}
          >
            <UiIcon name="plus" /> Nueva conversación
          </button>
          {!loading && items.length === 0 && <p>Aún no hay conversaciones.</p>}
          <ul>
            {items.map((c) => (
              <li key={c.id}>
                <button
                  className="chat-select"
                  aria-pressed={detail?.conversation.id === c.id}
                  disabled={busy || sending}
                  onClick={() => {
                    void choose(c.id);
                    setHistoryOpen(false);
                  }}
                >
                  <UiIcon name="message" />
                  <span>
                    {c.title}
                    <small>
                      {new Date(c.created_at).toLocaleDateString('es-PE')}
                    </small>
                  </span>
                </button>
                <ActionMenu
                  label={`Opciones de conversación: ${c.title}`}
                  disabled={busy || sending}
                  actions={[
                    {
                      label: 'Eliminar conversación',
                      danger: true,
                      onSelect: () => {
                        deleteButton.current =
                          document.activeElement as HTMLButtonElement;
                        setDeleting(c);
                      },
                    },
                  ]}
                />
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
          <small className="chat-history-note">
            Cada investigación conserva su propio historial.
          </small>
        </aside>
        <div className="chat-stage">
          <header className="chat-header">
            <div className="chat-breadcrumb">
              <button className="rp-link" onClick={() => navigateProject()}>
                Mis investigaciones
              </button>
              <UiIcon name="chevron" />
              <span>
                {projectTitle ?? status?.project_title ?? 'Investigación'}
              </span>
            </div>
            <div className="chat-heading-row">
              <div>
                <h1>Asistente IA</h1>
                <p>Conversación dentro del proyecto seleccionado</p>
              </div>
              <div className="chat-header-actions">
                <button
                  className="rp-secondary chat-history-toggle"
                  aria-label="Abrir historial de conversaciones"
                  aria-expanded={historyOpen}
                  aria-controls={`history-${projectId}`}
                  onClick={() => setHistoryOpen(!historyOpen)}
                >
                  <UiIcon name="message" />
                  <span>Historial</span>
                </button>
                <button
                  className="rp-secondary"
                  aria-expanded={contextOpen}
                  aria-controls={`context-${projectId}`}
                  onClick={() => setContextOpen(!contextOpen)}
                >
                  <UiIcon name="panel" />
                  <span>Fuentes y contexto</span>
                </button>
              </div>
            </div>
          </header>
          <div
            className={`chat-content ${contextOpen ? 'chat-with-context' : ''}`}
          >
            <div className="chat-main">
              <div
                className="chat-messages"
                ref={messagesViewport}
                role="log"
                aria-label="Historial de mensajes"
                aria-live="polite"
              >
                <div className="chat-inner">
                  {loading && <p role="status">Cargando conversaciones…</p>}
                  {contextError && (
                    <p role="status" className="chat-warning">
                      {contextError}
                    </p>
                  )}
                  {status?.research_context?.sources.some((source) =>
                    ['stale', 'unverified'].includes(source.status),
                  ) && (
                    <p className="chat-warning" role="status">
                      Hay fuentes desactualizadas o sin verificar. Revisa
                      «Fuentes y contexto de investigación» antes de interpretar
                      las respuestas.
                    </p>
                  )}
                  {error && !deleting && (
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
                      Cloudflare no está configurado. El envío está
                      deshabilitado; puedes consultar y organizar tu historial.
                    </p>
                  )}
                  {detail?.has_more && (
                    <button
                      className="rp-link"
                      disabled={busy || sending}
                      onClick={() => void olderMessages()}
                    >
                      Cargar mensajes anteriores
                    </button>
                  )}
                  {!loading && !detail?.messages.length && (
                    <div className="chat-empty">
                      <span className="chat-hello">
                        <UiIcon name="spark" />
                      </span>
                      <h2>
                        {status?.research_context?.sources.some(
                          (source) =>
                            source.kind !== 'project' &&
                            ['current', 'confirmed', 'completed'].includes(
                              source.status,
                            ),
                        )
                          ? '¿En qué trabajamos hoy?'
                          : 'Empecemos por tu investigación'}
                      </h2>
                      <p>
                        Puedes comenzar conversando o añadir materiales para
                        aportar contexto verificado.
                      </p>
                      <ResourceWelcome onOpenResource={onOpenResource} />
                      <p className="chat-quick-title">
                        También puedes hacer una pregunta
                      </p>
                      <div className="chat-suggestions">
                        {[
                          '¿Cómo comienzo mi análisis?',
                          '¿Cómo identifico mis variables?',
                          '¿Qué es la confiabilidad?',
                        ].map((question) => (
                          <button
                            className="rp-secondary"
                            key={question}
                            onClick={() => {
                              setDraft(question);
                              document
                                .getElementById(`chat-input-${projectId}`)
                                ?.focus();
                            }}
                          >
                            {question}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {detail?.messages.map((m) => (
                    <article
                      key={m.id}
                      className={`chat-message chat-${m.role}`}
                    >
                      <span className="chat-message-icon">
                        <UiIcon
                          name={m.role === 'user' ? 'message' : 'spark'}
                        />
                      </span>
                      <div className="chat-message-body">
                        <strong>
                          {m.role === 'user' ? 'Tú' : 'Asistente IA'}
                        </strong>
                        {m.role === 'assistant' ? (
                          <div className="chat-markdown">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm, remarkBreaks]}
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
                            <details className="chat-agents">
                              <summary>Agentes utilizados</summary>
                              <small>
                                Agentes utilizados:{' '}
                                {m.context.multiagent.agents
                                  .map((agent) => agentNames[agent] ?? agent)
                                  .join(' → ')}
                              </small>
                            </details>
                          )}
                        {m.role === 'assistant' &&
                          m.content.includes('Simulación local:') && (
                            <small className="chat-simulated">
                              Simulación local · Sin Qwen3 ni transmisión
                              externa
                            </small>
                          )}
                        <time dateTime={m.created_at}>
                          {new Date(m.created_at).toLocaleTimeString('es-PE', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </time>
                      </div>
                    </article>
                  ))}

                  {sending && (
                    <p role="status" className="chat-thinking">
                      Generando respuesta…
                    </p>
                  )}
                </div>
              </div>
              <div className="chat-composer-area">
                <div className="chat-composer-inner">
                  {status && (
                    <div className="chat-permissions">
                      {consent ? (
                        <>
                          <span className="chat-permission-state">
                            <UiIcon name="lock" />
                            {simulated
                              ? 'Demo local autorizada'
                              : 'Envío autorizado para este proyecto'}
                          </span>
                          <button
                            className="rp-link"
                            aria-expanded={consentInfo}
                            onClick={() => setConsentInfo(!consentInfo)}
                          >
                            Consultar permiso
                          </button>
                          <button
                            className="rp-link"
                            disabled={sending}
                            onClick={() => {
                              setConsent(false);
                              setConsentInfo(true);
                            }}
                          >
                            Revocar permiso
                          </button>
                        </>
                      ) : (
                        !consentInfo && (
                          <>
                            <span>Envío bloqueado sin autorización</span>
                            <button
                              className="rp-link"
                              onClick={() => setConsentInfo(true)}
                            >
                              Revisar consentimiento
                            </button>
                          </>
                        )
                      )}
                      {consentInfo && (
                        <div className="chat-consent">
                          <strong>
                            {simulated
                              ? 'Demo local · Sin transmisión externa'
                              : 'Permiso para usar el proveedor externo'}
                          </strong>
                          <p id={`consent-scope-${projectId}`}>
                            {simulated
                              ? 'Esta demo no transmite información a Cloudflare ni realiza inferencia Qwen3 real. Procesa localmente tu mensaje, título, historial reciente, información metodológica seleccionada, metadatos del dataset y métricas estadísticas verificadas. Se exige autorización explícita en cada solicitud.'
                              : 'Se enviarán tu mensaje, el título, el historial reciente, información metodológica seleccionada, metadatos del dataset y métricas estadísticas verificadas a Cloudflare Workers AI. No se envían documentos completos ni datos individuales del dataset.'}{' '}
                            Usaré solo información ficticia. Sin aceptar puedo
                            consultar mi historial local. El permiso se limita a
                            este proyecto y sesión; se solicita de nuevo al
                            recargar.
                          </p>
                          {!consent && (
                            <div className="chat-consent-actions">
                              <label>
                                <input
                                  type="checkbox"
                                  aria-describedby={`consent-scope-${projectId}`}
                                  checked={consent}
                                  disabled={sending}
                                  onChange={(event) => {
                                    setConsent(event.target.checked);
                                    setConsentInfo(false);
                                  }}
                                />
                                {simulated
                                  ? 'Autorizo el procesamiento de la demo local'
                                  : 'Autorizo el envío descrito a Cloudflare Workers AI'}
                              </label>
                              <button
                                className="rp-link"
                                onClick={() => setConsentInfo(false)}
                              >
                                Rechazar
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  <form
                    className="chat-composer"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void send();
                    }}
                  >
                    <label
                      className="rp-sr-only"
                      htmlFor={`chat-input-${projectId}`}
                    >
                      Tu mensaje
                    </label>
                    <textarea
                      id={`chat-input-${projectId}`}
                      rows={1}
                      value={draft}
                      maxLength={status?.max_message_characters ?? 2000}
                      disabled={
                        loading ||
                        sending ||
                        busy ||
                        !status?.provider_configured ||
                        !consent
                      }
                      placeholder="Escribe una pregunta sobre tu tesis..."
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (
                          event.key === 'Enter' &&
                          !event.shiftKey &&
                          !event.nativeEvent.isComposing
                        ) {
                          event.preventDefault();
                          void send();
                        }
                      }}
                    />
                    <button
                      aria-label="Enviar mensaje"
                      disabled={
                        loading ||
                        sending ||
                        busy ||
                        !consent ||
                        !status?.provider_configured ||
                        !draft.trim()
                      }
                    >
                      <UiIcon name="send" />
                    </button>
                  </form>
                  <div className="chat-composer-meta">
                    <span>
                      Enter para enviar · Shift+Enter para nueva línea{' '}
                      <span className="chat-character-count">
                        · {draft.length}/
                        {status?.max_message_characters ?? 2000}
                      </span>
                    </span>
                    <span>
                      {simulated
                        ? 'Simulación local · Sin Qwen3 ni red'
                        : status?.provider_configured
                          ? 'Qwen3 · Cloudflare'
                          : 'Proveedor no disponible'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            {contextOpen && (
              <aside
                className="chat-context"
                id={`context-${projectId}`}
                aria-label="Contexto de investigación"
              >
                <div className="chat-context-heading">
                  <h2>Fuentes y contexto</h2>
                  <button
                    className="rp-secondary"
                    aria-label="Cerrar fuentes y contexto"
                    onClick={() => setContextOpen(false)}
                  >
                    <UiIcon name="x" />
                  </button>
                </div>
                <p>
                  El contexto se verifica para cada pregunta. El historial puede
                  referirse a versiones anteriores. Revisa las respuestas con
                  criterio académico.
                </p>
                <p>
                  <strong>Proyecto activo:</strong>{' '}
                  {projectTitle ?? status?.project_title ?? 'Investigación'}
                </p>
                <button
                  className="rp-secondary"
                  disabled={sending || contextBusy}
                  onClick={() => void refreshContext()}
                >
                  {contextBusy
                    ? 'Actualizando contexto…'
                    : 'Actualizar contexto'}
                </button>
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

                <ResourceWelcome onOpenResource={onOpenResource} />
              </aside>
            )}
          </div>
        </div>
      </div>
      {deleting && (
        <dialog
          ref={deleteDialog}
          className="rp-dialog"
          aria-labelledby="delete-chat-title"
          onCancel={(event) => {
            event.preventDefault();
            if (!busy) {
              setDeleting(null);
              deleteButton.current?.focus();
            }
          }}
        >
          <h3 id="delete-chat-title">Eliminar conversación</h3>
          <p>
            Se eliminará «{deleting.title}» y todos sus mensajes de forma
            permanente.
          </p>
          {error && <p role="alert">{error}</p>}
          <div className="rp-actions">
            <button
              className="rp-secondary"
              disabled={busy}
              onClick={() => {
                deleteDialog.current?.close();
                setDeleting(null);
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
      <div className="chat-resource-links">
        <button
          className="rp-secondary"
          onClick={() => onOpenResource('documents')}
        >
          <UiIcon name="file" />
          Cargar documentos<small>PDF o DOCX</small>
        </button>
        <button
          className="rp-secondary"
          onClick={() => onOpenResource('instrument')}
        >
          <UiIcon name="clipboard" />
          Instrumento<small>Funcionalidad pendiente</small>
        </button>
        <button
          className="rp-secondary"
          onClick={() => onOpenResource('datasets')}
        >
          <UiIcon name="database" />
          Cargar datos<small>CSV o XLSX</small>
        </button>
      </div>
    </div>
  );
}
