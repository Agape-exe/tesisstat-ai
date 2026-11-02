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
const errorText = (error: unknown) =>
  error instanceof ConversationApiError
    ? error.message
    : 'No se pudo completar la operación del chat.';

export function ConversationChat({
  projectId,
  api = defaultApi,
}: {
  projectId: string;
  api?: ConversationApi;
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
  const locked = useRef(false);
  const active = useRef(true);
  const selection = useRef(0);
  const listEnd = useRef<HTMLDivElement>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const deleteButton = useRef<HTMLButtonElement>(null);
  const selectedKey = `tesisstat:conversation:v1:${projectId}`;

  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    Promise.all([
      api.status(projectId, controller.signal),
      api.list(projectId, 0, controller.signal),
    ])
      .then(async ([provider, conversations]) => {
        if (controller.signal.aborted) return;
        setStatus(provider);
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

  useEffect(() => {
    listEnd.current?.scrollIntoView?.({ block: 'nearest' });
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
          <h3>Asistente IA</h3>
          <p>Una pregunta a la vez, avanza con tu investigación.</p>
        </div>
        <span className="rp-badge">Qwen3 · Cloudflare</span>
      </header>
      <p className="rp-hint">
        Solo se utiliza el título del proyecto y el historial reciente. Los
        documentos, datasets y resultados todavía no están conectados. Revisa
        las respuestas con criterio académico.
      </p>
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
                role="log"
                aria-label="Historial de mensajes"
                aria-live="polite"
              >
                {detail.messages.length === 0 && (
                  <div className="chat-empty">
                    <h4>¿Qué te gustaría comprender?</h4>
                    <p>
                      Puedes preguntar sobre conceptos, hipótesis o métodos
                      estadísticos. Este chat no ejecuta análisis.
                    </p>
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
                <div ref={listEnd} />
              </div>
              <div className="chat-consent">
                <label>
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    disabled={sending}
                  />{' '}
                  Autorizo enviar mis mensajes, el título y el historial
                  reciente a Cloudflare Workers AI para su procesamiento. Usaré
                  solo información ficticia.
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
              <h4>Tu espacio de consulta</h4>
              <p>Crea o selecciona una conversación de esta investigación.</p>
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
