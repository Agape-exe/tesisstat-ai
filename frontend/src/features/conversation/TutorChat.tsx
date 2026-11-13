import { useEffect, useRef, useState } from 'react';
import { createConversationApi, type Conversation } from './api';
import {
  createTutorApi,
  type Action,
  type Selection,
  type TutorMessage,
  type TutorStatus,
} from './tutorApi';
import {
  navigateProject,
  navigateWorkspace,
} from '../research/projects/navigation';
import './tutor.css';
import { GuidedReview } from './GuidedReview';

const conversations = createConversationApi();
const tutor = createTutorApi();
const stages = {
  home: 'Inicio',
  context: 'Contexto',
  data: 'Datos',
  analysis: 'Análisis',
  results: 'Resultados',
} as const;
const selectionLabels = {
  datasets: 'Tabla pertinente',
  intents: 'Análisis pertinente',
  plans: 'Propuesta pertinente',
  results: 'Resultado pertinente',
} as const;
const errorText = (e: unknown) =>
  e instanceof Error ? e.message : 'No se pudo consultar el tutor.';

export function TutorChat({
  projectId,
  projectTitle,
  active = true,
  stage = 'home',
  resultId,
  boundSelection,
  api = tutor,
  historyApi = conversations,
}: {
  projectId: string;
  projectTitle?: string;
  active?: boolean;
  stage?: Selection['stage'];
  resultId?: string;
  boundSelection?: Selection;
  api?: typeof tutor;
  historyApi?: typeof conversations;
}) {
  const [manualSelection, setSelection] = useState<Selection>({
    stage,
    result_id: resultId,
  });
  const selection = boundSelection ?? manualSelection;
  const [review, setReview] = useState(false);
  const [status, setStatus] = useState<TutorStatus | null>(null);
  const [statusSelectionKey, setStatusSelectionKey] = useState('');
  const [items, setItems] = useState<Conversation[]>([]);
  const [cid, setCid] = useState('');
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [moreConversations, setMoreConversations] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [consentPending, setConsentPending] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const gate = useRef(false);
  const pending = useRef<{ body: string; requestId: string } | null>(null);
  const storageKey = `tesisstat:tutor-conversation:v2:${projectId}`;
  const selectionKey = JSON.stringify(selection);
  const contextCurrent = statusSelectionKey === selectionKey;
  const workingTable = status?.choices.datasets.find(
    (d) =>
      d.id ===
      (selection.dataset_id ?? status.context.intent_summary?.dataset_id),
  );
  useEffect(() => {
    const update = (event: Event) => {
      if ((event as CustomEvent<string>).detail !== projectId) return;
      setStatusSelectionKey('');
      setRefresh((n) => n + 1);
    };
    window.addEventListener('tesisstat:resources-changed', update);
    return () =>
      window.removeEventListener('tesisstat:resources-changed', update);
  }, [projectId]);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    api
      .status(
        projectId,
        JSON.parse(selectionKey) as Selection,
        controller.signal,
      )
      .then((s) => {
        if (!controller.signal.aborted) {
          setStatus(s);
          setStatusSelectionKey(selectionKey);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setStatus(null);
          setError(errorText(e));
        }
      });
    return () => controller.abort();
  }, [projectId, api, selectionKey, refresh, active]);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    historyApi
      .list(projectId, 0, controller.signal)
      .then(async (list) => {
        if (controller.signal.aborted) return;
        setItems(list);
        setMoreConversations(list.length > 0);
        let saved = '';
        try {
          saved = sessionStorage.getItem(storageKey) ?? '';
        } catch {
          /* Server history is authoritative. */
        }
        const id = list.find((c) => c.id === saved)?.id ?? '';
        if (id) {
          const detail = await historyApi.get(
            projectId,
            id,
            undefined,
            controller.signal,
          );
          if (!controller.signal.aborted) {
            setCid(id);
            setMessages(detail.messages as TutorMessage[]);
            setHasMore(detail.has_more);
          }
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      });
    return () => controller.abort();
  }, [projectId, historyApi, storageKey, active]);
  async function work(action: () => Promise<void>) {
    if (gate.current) return;
    gate.current = true;
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (e) {
      setError(errorText(e));
    } finally {
      gate.current = false;
      setBusy(false);
    }
  }
  function remember(id: string) {
    try {
      sessionStorage.setItem(storageKey, id);
    } catch {
      /* Local navigation still works. */
    }
  }
  async function choose(id: string) {
    await work(async () => {
      if (!id) {
        setCid('');
        setMessages([]);
        setHasMore(false);
        remember('');
        return;
      }
      const detail = await historyApi.get(projectId, id);
      setCid(id);
      setMessages(detail.messages as TutorMessage[]);
      setHasMore(detail.has_more);
      remember(id);
    });
  }
  async function send() {
    if (
      !contextCurrent ||
      !status?.provider_configured ||
      !status.consent.granted ||
      !draft.trim()
    )
      return;
    await work(async () => {
      let id = cid;
      if (!id) {
        const conversation = await historyApi.create(projectId);
        id = conversation.id;
        setCid(id);
        remember(id);
        setItems((old) => [conversation, ...old]);
      }
      const content = draft.trim();
      const signature = JSON.stringify([
        content,
        selection,
        status.consent.revision,
        id,
      ]);
      if (pending.current?.body !== signature)
        pending.current = { body: signature, requestId: crypto.randomUUID() };
      try {
        const response = await api.send(projectId, id, {
          ...selection,
          stage: selection.stage ?? 'home',
          content,
          request_id: pending.current.requestId,
          consent_revision: status.consent.revision,
          external_ai_consent: true,
          consent_scope: 'tutor_context_v5',
        });
        setMessages((old) => [
          ...old.filter((m) => !response.messages.some((n) => n.id === m.id)),
          ...response.messages,
        ]);
        setDraft('');
        pending.current = null;
      } catch (e) {
        const history = await historyApi.get(projectId, id).catch(() => null);
        if (history) {
          setMessages(history.messages as TutorMessage[]);
          setHasMore(history.has_more);
        }
        throw e;
      }
    });
  }
  function open(action: Action, fingerprint?: string) {
    if (!contextCurrent) return;
    if (fingerprint && fingerprint !== status?.context.context_fingerprint)
      return;
    if (action.kind === 'prepare_descriptive') {
      setReview(true);
      return;
    }
    if (
      action.kind === 'start_association' ||
      action.kind === 'start_comparison'
    ) {
      navigateWorkspace(
        projectId,
        'analysis',
        action.kind === 'start_association' ? 'association' : 'comparison',
        action.resource_id ?? undefined,
      );
      return;
    }
    if (
      action.kind === 'request_proposal' ||
      action.kind === 'request_diagnostic'
    ) {
      navigateWorkspace(
        projectId,
        'analysis',
        'diagnostics',
        action.resource_id ?? undefined,
      );
    } else if (action.kind === 'propose_update' && action.resource_id) {
      navigateWorkspace(projectId, 'context', 'suggestion', action.resource_id);
    } else navigateProject(projectId, action.destination);
  }
  return (
    <section
      className="tutor-v2 rp-surface"
      aria-label={
        projectTitle && !boundSelection ? 'Asistente IA' : 'Tutor contextual'
      }
    >
      {projectTitle && (
        <div className="chat-breadcrumb">
          <span>{projectTitle}</span>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      <button
        className="rp-secondary"
        disabled={busy}
        onClick={() => {
          setError('');
          setRefresh((n) => n + 1);
        }}
      >
        Actualizar fuentes y permiso
      </button>
      {!boundSelection && (
        <details>
          <summary>Cambiar la selección de la consulta</summary>
          <div className="tutor-selection">
            <label className="rp-field">
              Etapa de la consulta
              <select
                aria-label="Etapa de la consulta"
                disabled={busy}
                value={selection.stage}
                onChange={(e) =>
                  setSelection({
                    ...selection,
                    stage: e.target.value as Selection['stage'],
                  })
                }
              >
                {Object.entries(stages).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            {status &&
              (['datasets', 'intents', 'plans', 'results'] as const).map(
                (kind) => {
                  const field = {
                    datasets: 'dataset_id',
                    intents: 'intent_id',
                    plans: 'plan_id',
                    results: 'result_id',
                  } as const;
                  return (
                    <label className="rp-field" key={kind}>
                      {
                        {
                          datasets: 'Tabla pertinente',
                          intents: 'Análisis pertinente',
                          plans: 'Propuesta pertinente',
                          results: 'Resultado pertinente',
                        }[kind]
                      }
                      <select
                        aria-label={selectionLabels[kind]}
                        disabled={busy}
                        value={selection[field[kind]] ?? ''}
                        onChange={(e) =>
                          setSelection({
                            stage: selection.stage,
                            [field[kind]]: e.target.value || null,
                          })
                        }
                      >
                        <option value="">Seleccionar explícitamente</option>
                        {status.choices[kind].map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.label || item.id}
                            {item.validity === 'stale'
                              ? ' · histórico desactualizado'
                              : item.validity === 'unverified'
                                ? ' · vigencia al seleccionar'
                                : ''}
                          </option>
                        ))}
                      </select>
                    </label>
                  );
                },
              )}
          </div>
        </details>
      )}
      {status && (
        <>
          <details className="tutor-server-collapsible">
            <summary>Resumen técnico y ayuda de etapa</summary>
            <div className="tutor-server-collapsible-content">
              <p>
                <small>Ayuda estática por etapa · sin proveedor IA</small>
              </p>
              <p role="status">{status.static_help}</p>
              {boundSelection && (
                <p>
                  Trabajando en: {stages[selection.stage ?? 'home']}
                  {' · '}
                  {status.guidance?.selected_table?.name ??
                    status.choices.results.find(
                      (r) => r.id === selection.result_id,
                    )?.label ??
                    status.choices.plans.find((r) => r.id === selection.plan_id)
                      ?.label ??
                    status.choices.intents.find(
                      (r) => r.id === selection.intent_id,
                    )?.label ??
                    'sin recurso seleccionado'}
                </p>
              )}
              {boundSelection &&
                workingTable &&
                !status.guidance?.selected_table && (
                  <p>Tabla de este análisis: {workingTable.label}.</p>
                )}
              {Object.keys(status.context.confirmed_summary ?? {}).length >
                0 && (
                <details>
                  <summary>Contexto confirmado utilizado</summary>
                  <ul>
                    {Object.entries(status.context.confirmed_summary ?? {}).map(
                      ([path, value]) => (
                        <li key={path}>
                          {(
                            {
                              '/main_objective': 'Objetivo principal',
                              '/research_question': 'Pregunta de investigación',
                              '/study_description': 'Descripción del estudio',
                              '/data_description': 'Descripción de datos',
                              '/sampling_notes': 'Población y muestreo',
                            } as Record<string, string>
                          )[path] ?? 'Información confirmada'}
                          : {value}
                        </li>
                      ),
                    )}
                  </ul>
                  <p>
                    Es información declarada; no demuestra independencia,
                    correspondencia entre sujetos ni cumplimiento de objetivos.
                  </p>
                </details>
              )}
              {status.guidance && (
                <section aria-label="Resumen local de datos">
                  <h3>Resumen del servidor · sin IA</h3>
                  <p>
                    {status.guidance.table_count} tablas disponibles.
                    {status.guidance.selected_table &&
                      ` Tabla seleccionada: ${status.guidance.selected_table.name}. ${status.guidance.selected_table.rows} registros y ${status.guidance.selected_table.columns} columnas.`}
                  </p>
                  {(status.guidance.selected_table?.identical_rows ?? 0) >
                    0 && (
                    <p>
                      Hay {status.guidance.selected_table?.identical_rows} filas
                      idénticas; no se eliminan automáticamente.
                    </p>
                  )}
                  {status.guidance.warnings?.map((w) => (
                    <p key={w}>{w}</p>
                  ))}
                  <details>
                    <summary>Tipos detectados y problemas por columna</summary>
                    <ul>
                      {status.guidance.variables.map((v) => (
                        <li key={v.variable_id}>
                          {v.name}: {v.detected_type}; {v.missing} faltantes
                          {v.formula_errors
                            ? `; ${v.formula_errors} errores de fórmula`
                            : ''}
                          {v.possible_identifier
                            ? '; posible identificador'
                            : ''}
                          .{' '}
                          {v.constant
                            ? 'Sin variación entre los valores presentes. '
                            : ''}
                          {v.scale_confirmed
                            ? 'Escala confirmada.'
                            : 'Significado y escala por revisar.'}
                        </li>
                      ))}
                    </ul>
                  </details>
                  {status.guidance.selected_table && (
                    <button
                      className="rp-secondary"
                      onClick={() => setReview(true)}
                    >
                      No sé por dónde empezar
                    </button>
                  )}
                </section>
              )}
              {status.provider_kind === 'controlled_test' && (
                <p className="rp-warning">
                  Proveedor controlado de verificación, sin llamadas externas.
                  Esta respuesta no acredita una conexión real con IA.
                </p>
              )}
              {!status.provider_configured && (
                <p className="rp-warning">
                  Cloudflare no está configurado o no está disponible. La ayuda
                  estática, el historial y los formularios siguen disponibles.
                </p>
              )}
              {status.context.pending_questions.length > 0 && (
                <ul>
                  {status.context.pending_questions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              )}
              {status.context.warnings.map((w) => (
                <p className="rp-warning" key={w}>
                  {w}
                </p>
              ))}
              <div className="rp-actions">
                {status.context.allowed_actions.map((action, index) => (
                  <div key={index}>
                    <button
                      className="rp-secondary"
                      disabled={busy || !contextCurrent}
                      onClick={() => open(action)}
                    >
                      {action.label}
                    </button>
                    {action.scope && <small>{action.scope}</small>}
                  </div>
                ))}
              </div>
              <details>
                <summary>Qué información utiliza el tutor</summary>
                <p>{status.privacy}</p>
                <p>
                  Huella del contexto:{' '}
                  <code>{status.context.context_fingerprint}</code>
                </p>
                <p>
                  {status.context.source_refs.length} referencias vigentes y{' '}
                  {status.context.historical_refs.length} históricas.
                </p>
              </details>
            </div>
          </details>
          {review && contextCurrent && (
            <GuidedReview
              key={status.context.context_fingerprint}
              projectId={projectId}
              status={status}
              selection={selection}
              api={api}
            />
          )}
          {status.consent.renewal_required && (
            <p role="status">
              Cambió lo que se transmite: ahora conserva la redacción depurada
              de la consulta e incluye encabezados seguros, detecciones locales
              y significados de variables confirmados. El permiso anterior no
              basta; revisa la descripción y renueva tu autorización.
            </p>
          )}
          <label className="tutor-consent">
            <input
              type="checkbox"
              checked={consentPending ?? status.consent.granted}
              disabled={busy}
              onChange={(e) => {
                const granted = e.target.checked;
                if (gate.current) return;
                setConsentPending(granted);
                void work(async () => {
                  const consent = await api.consent(
                    projectId,
                    status.consent.revision,
                    granted,
                  );
                  setStatus({ ...status, consent });
                }).finally(() => setConsentPending(null));
              }}
            />
            Autorizo el envío acotado a Cloudflare Workers AI (alcance v5),
            incluidos consulta e historial depurados, contexto confirmado y
            resumen de variables y comprobaciones locales. Escribiré sin datos
            personales ni secretos. Desmarcar revoca el permiso.
          </label>
          {consentPending != null && (
            <p role="status">Guardando el cambio de permiso…</p>
          )}
          <p>
            <small>
              Este permiso es independiente de la extracción documental y del
              cálculo local. Puedes revisar el alcance en «Qué información
              utiliza el tutor».
            </small>
          </p>
        </>
      )}
      <label className="rp-field">
        Conversación
        <select
          aria-label="Conversación"
          disabled={busy}
          value={cid}
          onChange={(e) => void choose(e.target.value)}
        >
          <option value="">Nueva conversación</option>
          {items.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title} · {new Date(c.created_at).toLocaleString('es-PE')}
            </option>
          ))}
        </select>
      </label>
      {moreConversations && (
        <button
          className="rp-secondary"
          disabled={busy}
          onClick={() =>
            void work(async () => {
              const next = await historyApi.list(projectId, items.length);
              setItems((old) => [...old, ...next]);
              setMoreConversations(next.length > 0);
            })
          }
        >
          Más conversaciones
        </button>
      )}
      {hasMore && (
        <button
          className="rp-secondary"
          disabled={busy}
          onClick={() =>
            void work(async () => {
              const history = await historyApi.get(
                projectId,
                cid,
                messages[0]?.sequence,
              );
              setMessages((old) => [
                ...(history.messages as TutorMessage[]),
                ...old,
              ]);
              setHasMore(history.has_more);
            })
          }
        >
          Mensajes anteriores
        </button>
      )}
      <div
        className="tutor-messages"
        role="log"
        aria-label="Historial del tutor"
        aria-live="polite"
      >
        {messages.length === 0 && (
          <p>
            El historial permanece en este proyecto. Puedes consultar conceptos
            o pedir orientación sobre el siguiente paso.
          </p>
        )}
        {messages.map((message) => (
          <article
            key={message.id}
            className={`tutor-message tutor-${message.role}`}
          >
            <strong>
              {message.role === 'user'
                ? 'Tú'
                : message.context?.prose_source === 'template'
                  ? 'Orientación básica · acciones sugeridas por IA'
                  : message.context?.prose_source === 'ai_guidance'
                    ? 'Orientación de IA · revisa antes de avanzar'
                    : message.context?.prose_source === 'ai_concepts'
                      ? 'Conceptos generales de IA · no son hallazgos del estudio'
                      : 'Borrador IA · revisa su alcance'}
            </strong>
            <p className="tutor-prose">{message.content}</p>
            {message.context?.error && (
              <p role="status">
                Envío sin respuesta confirmada: {message.context.error}.
              </p>
            )}
            {message.role === 'assistant' &&
              message.context?.actions &&
              message.context.actions.length > 0 && (
                <div className="tutor-message-actions">
                  {message.context.actions.map((action, n) => (
                    <div key={n} className="tutor-action-item">
                      <button
                        type="button"
                        className="rp-secondary tutor-action-btn"
                        disabled={
                          !contextCurrent ||
                          message.context?.snapshot !==
                            status?.context.context_fingerprint
                        }
                        onClick={() => open(action, message.context?.snapshot)}
                      >
                        {action.label}
                      </button>
                      {action.scope && (
                        <small className="tutor-action-scope">
                          {action.scope}
                        </small>
                      )}
                    </div>
                  ))}
                </div>
              )}
            {message.context?.snapshot && (
              <details>
                <summary>Referencias de este mensaje</summary>
                <p>
                  Etapa: {message.context.stage ?? 'recorrido anterior'}.
                  Huella: <code>{message.context.snapshot}</code>
                </p>
                {status &&
                  message.context.snapshot !==
                    status.context.context_fingerprint && (
                    <p>
                      Este mensaje utilizó otras fuentes o selección. No
                      sustituye el contexto actual.
                    </p>
                  )}
                <ul>
                  {[
                    ...(message.context.sources ?? []),
                    ...(message.context.historical_refs ?? []),
                  ].map((s, n) => (
                    <li key={n}>
                      {s.kind} · {s.id} · versión{' '}
                      {'revision' in s && s.revision != null
                        ? s.revision
                        : 'version' in s
                          ? s.version
                          : 'histórica'}
                    </li>
                  ))}
                </ul>
                <ul>
                  {message.context.evidence_refs?.map((fact) => (
                    <li key={fact.key}>
                      {fact.kind === 'confirmed'
                        ? 'Declaración confirmada'
                        : fact.kind === 'detected'
                          ? 'Detección local'
                          : 'Cálculo local'}
                      : {fact.text}
                      {' · '}
                      {fact.source_ref.kind} · {fact.source_ref.id} · revisión{' '}
                      {fact.source_ref.revision}
                    </li>
                  ))}
                </ul>
                <ul>
                  {message.context.metric_refs?.map((m) => (
                    <li key={`${m.result_id}:${m.key}`}>
                      Resultado {m.result_id} · métrica {m.key}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </article>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <label className="rp-field">
          Tu consulta
          <textarea
            value={draft}
            disabled={busy}
            maxLength={status?.max_message_characters ?? 2000}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
          />
        </label>
        <button
          disabled={
            busy ||
            !contextCurrent ||
            !status?.provider_configured ||
            !status.consent.granted ||
            !draft.trim()
          }
        >
          {busy ? 'Procesando…' : 'Enviar consulta'}
        </button>
        {error && (
          <button
            type="button"
            className="rp-secondary"
            disabled={busy}
            onClick={() => {
              pending.current = null;
              setError(
                'Nuevo intento preparado explícitamente; revisa antes el historial.',
              );
            }}
          >
            Preparar otro intento explícito
          </button>
        )}
      </form>
    </section>
  );
}
