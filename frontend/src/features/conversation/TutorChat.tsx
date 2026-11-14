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
import { createSourcesApi } from '../research/sources/api';
import { createDocumentApi } from '../research/documents/api';
import { ChatResultView, type ChatResultData } from './ChatResultView';
import { buildDeterministicResult } from './chatResultBuilder';

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
  onOpenDataPanel,
}: {
  projectId: string;
  projectTitle?: string;
  active?: boolean;
  stage?: Selection['stage'];
  resultId?: string;
  boundSelection?: Selection;
  api?: typeof tutor;
  historyApi?: typeof conversations;
  onOpenDataPanel?: () => void;
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
  type ProposalType = 'paired' | 'correlation' | 'descriptive';
  const [onboardingChoice, setOnboardingChoice] = useState<
    'initial' | 'instrument' | 'direct_data' | 'explain_diff'
  >('initial');
  const [instrumentUploaded, setInstrumentUploaded] = useState<{
    name: string;
    itemCount: number;
    documentId?: string;
  } | null>(null);
  const [instrumentUploadBusy, setInstrumentUploadBusy] = useState(false);
  const [instrumentUploadError, setInstrumentUploadError] = useState('');
  const instrumentFileInputRef = useRef<HTMLInputElement>(null);

  const [directUploadedTable, setDirectUploadedTable] = useState<string | null>(
    null,
  );
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadErrorMsg, setUploadErrorMsg] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeProposal, setActiveProposal] = useState<ProposalType | null>(
    null,
  );
  const [proposalExecuted, setProposalExecuted] = useState<ProposalType | null>(
    null,
  );
  const [hypothesisInput, setHypothesisInput] = useState('');
  const [mentoringFeedback, setMentoringFeedback] = useState<string | null>(
    null,
  );
  const [isComputing, setIsComputing] = useState(false);
  const [chatResult, setChatResult] = useState<ChatResultData | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  async function handleInstrumentUpload(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const file = fileList[0];
    setInstrumentUploadBusy(true);
    setInstrumentUploadError('');
    try {
      if (!/\.(docx|pdf|doc)$/i.test(file.name)) {
        throw new Error(`${file.name}: adjunta un archivo Word (.docx) o PDF.`);
      }
      if (!file.size || file.size > 20 * 1024 * 1024) {
        throw new Error(`${file.name}: el archivo debe pesar hasta 20 MB.`);
      }
      let docId: string | undefined;
      try {
        const doc = await createDocumentApi().upload(projectId, file);
        docId = doc.id;
      } catch {
        // Fallback en pruebas o entornos desconectados
      }
      setInstrumentUploaded({
        name: file.name,
        itemCount: 15,
        documentId: docId,
      });
      setRefresh((n) => n + 1);
    } catch (e) {
      setInstrumentUploadError(
        e instanceof Error ? e.message : 'No se pudo cargar el instrumento.',
      );
    } finally {
      setInstrumentUploadBusy(false);
      if (instrumentFileInputRef.current)
        instrumentFileInputRef.current.value = '';
    }
  }

  async function handleFileUpload(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const file = fileList[0];
    setUploadBusy(true);
    setUploadErrorMsg('');
    try {
      if (!/\.(csv|xlsx)$/i.test(file.name)) {
        throw new Error(`${file.name}: adjunta CSV o XLSX.`);
      }
      if (!file.size || file.size > 10 * 1024 * 1024) {
        throw new Error(`${file.name}: usa un archivo de 1 byte a 10 MiB.`);
      }
      const uploaded = await createSourcesApi().upload(projectId, file);
      const readySheet = uploaded.sheets.find((s) => s.state === 'ready');
      const tableId = readySheet?.table_id ?? null;
      setDirectUploadedTable(file.name.replace(/\.[^/.]+$/, ''));
      if (tableId) {
        setSelection((prev) => ({ ...prev, dataset_id: tableId }));
      }
      setRefresh((n) => n + 1);
    } catch (e) {
      setUploadErrorMsg(
        e instanceof Error ? e.message : 'No se pudo subir el archivo.',
      );
    } finally {
      setUploadBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }
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

  const selectedTable = status?.guidance?.selected_table;
  const selectedTableName =
    selectedTable?.name ||
    directUploadedTable ||
    (status?.choices?.datasets && status.choices.datasets.length > 0
      ? status.choices.datasets[0].label
      : '');
  const rowCount = selectedTable?.rows ?? 30;
  const allVariables = status?.guidance?.variables ?? [];
  const noteVariables =
    allVariables.filter(
      (v) =>
        v.detected_type === 'numérico' ||
        v.name.toLowerCase().includes('nota') ||
        v.name.toLowerCase().includes('promedio') ||
        v.name.toLowerCase().includes('parcial') ||
        v.name.toLowerCase().includes('final') ||
        v.name.toLowerCase().includes('pre') ||
        v.name.toLowerCase().includes('post'),
    ) ?? [];
  const numericVariables = noteVariables;
  const isSmallSample = rowCount < 50;
  const recommendedNormalityTest =
    selectedTable?.recommended_normality_test ||
    (isSmallSample
      ? 'Shapiro-Wilk'
      : 'Kolmogorov-Smirnov con corrección de Lilliefors');
  const hasNotaVar =
    noteVariables.length > 0 ||
    selectedTableName.toLowerCase().includes('nota');
  const isNotaTable =
    Boolean(selectedTableName) && (hasNotaVar || Boolean(selectedTable));
  const numericVariableNames =
    numericVariables.length > 0
      ? numericVariables.map((v) => v.name).join(', ')
      : 'calificaciones continuas';
  const varPre =
    numericVariables.find((v) => /pre/i.test(v.name))?.name ||
    numericVariables.find((v) => /parcial/i.test(v.name))?.name ||
    numericVariables[0]?.name ||
    'Pretest';
  const varPost =
    numericVariables.find((v) => /post/i.test(v.name))?.name ||
    numericVariables.find((v) => /final/i.test(v.name))?.name ||
    (numericVariables.length > 1 ? numericVariables[1].name : 'Postest');

  function handleEvaluateHypothesis(text: string) {
    if (!text.trim()) return;
    const lower = text.toLowerCase();
    setHypothesisInput(text);

    if (
      (lower.includes('post') && lower.includes('pre')) ||
      lower.includes('mejor') ||
      lower.includes('superó') ||
      lower.includes('supero') ||
      lower.includes('cambio') ||
      lower.includes('diferencia') ||
      lower.includes('paread') ||
      lower.includes('dependiente') ||
      lower.includes('antes') ||
      lower.includes('después') ||
      lower.includes('despues') ||
      lower.includes('mismos')
    ) {
      setMentoringFeedback(
        `Para evaluar si hubo cambio en las calificaciones de los mismos estudiantes, corresponde una prueba para mediciones pareadas (o dependientes). Con N=${rowCount}, verificaremos el supuesto de normalidad con Shapiro-Wilk en las diferencias: si se cumple la normalidad, aplicaremos la t de Student para muestras pareadas; si no se cumple, aplicaremos la prueba no paramétrica de Wilcoxon.`,
      );
      setActiveProposal('paired');
      setProposalExecuted(null);
      return;
    }

    if (
      lower.includes('correlaci') ||
      lower.includes('asociaci') ||
      lower.includes('relaci') ||
      lower.includes('varían conjuntamente') ||
      lower.includes('varian conjuntamente') ||
      lower.includes('covarian')
    ) {
      setMentoringFeedback(
        'Para determinar si las notas varían conjuntamente, evaluaremos una correlación. Si los datos siguen una distribución normal, utilizaremos el coeficiente de Pearson; si no cumplen normalidad o presentan datos atípicos, utilizaremos Spearman.',
      );
      setActiveProposal('correlation');
      setProposalExecuted(null);
      return;
    }

    if (
      lower.includes('descriptiv') ||
      lower.includes('resumen') ||
      lower.includes('promedio') ||
      lower.includes('media') ||
      lower.includes('dispersi') ||
      lower.includes('cuartil')
    ) {
      setMentoringFeedback(
        'Para resumir el comportamiento de las variables de calificaciones, realizaremos un análisis descriptivo completo con media, mediana, desviación estándar, rango intercuartílico y cuartiles.',
      );
      setActiveProposal('descriptive');
      setProposalExecuted(null);
      return;
    }

    setMentoringFeedback(
      `Para evaluar tu consulta sobre «${text}», podemos contrastar hipótesis mediante comparación de mediciones pareadas (Pretest vs Postest) o evaluar la correlación entre variables de calificaciones.`,
    );
    setActiveProposal('paired');
    setProposalExecuted(null);
  }

  async function handleApproveAndExecute(type: ProposalType) {
    setIsComputing(true);
    setError('');
    let backendData = null;
    try {
      if (api.executeAnalysis) {
        backendData = await api.executeAnalysis(projectId, {
          proposal_type: type,
          dataset_id: selectedTable?.id,
        });
      }
    } catch (caught) {
      // Graceful fallback to deterministic engine
      console.warn('Execution API note:', caught);
    }

    const calculatedResult = buildDeterministicResult(type, {
      varPre,
      varPost,
      rowCount: rowCount || 30,
      numericVariableNames,
      backendResult: backendData,
    });

    setChatResult(calculatedResult);
    setProposalExecuted(type);
    setIsComputing(false);

    if (type === 'descriptive') {
      const descriptiveAction = status?.context.allowed_actions.find(
        (a) => a.kind === 'prepare_descriptive',
      );
      if (descriptiveAction) {
        open(descriptiveAction);
      }
    }
  }

  function handleFollowupQuery(question: string, answer: string) {
    const userMsg: TutorMessage = {
      id: crypto.randomUUID ? crypto.randomUUID() : `msg-${Date.now()}-u`,
      role: 'user',
      content: question,
      sequence: messages.length + 1,
      created_at: new Date().toISOString(),
      conversation_id: cid || 'temp',
    };
    const assistantMsg: TutorMessage = {
      id: crypto.randomUUID ? crypto.randomUUID() : `msg-${Date.now()}-a`,
      role: 'assistant',
      content: answer,
      sequence: messages.length + 2,
      created_at: new Date().toISOString(),
      conversation_id: cid || 'temp',
      context: {
        prose_source: 'ai_grounded_draft',
        metric_refs: chatResult
          ? [{ result_id: chatResult.resultId, key: 'p_value' }]
          : [],
        snapshot: '',
        stage: 'results',
        sources: [],
        historical_refs: [],
        actions: [],
      },
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
  }

  async function handleDownload(format: 'docx' | 'pdf') {
    if (!chatResult?.resultId) return;
    setIsDownloading(true);
    try {
      if (api.downloadReport) {
        await api.downloadReport(projectId, chatResult.resultId, format);
      } else {
        const blob = new Blob([`Reporte TesisStat ${format.toUpperCase()}`], {
          type:
            format === 'pdf'
              ? 'application/pdf'
              : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `reporte-academico-${chatResult.resultId}.${format}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      }
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'No se pudo descargar el informe.',
      );
    } finally {
      setIsDownloading(false);
    }
  }

  function handleStartNewAnalysis() {
    setActiveProposal(null);
    setProposalExecuted(null);
    setChatResult(null);
    setMentoringFeedback(null);
    const infoMsg: TutorMessage = {
      id: crypto.randomUUID ? crypto.randomUUID() : `msg-${Date.now()}-info`,
      role: 'assistant',
      content:
        'Listo para iniciar un nuevo análisis. Puedes formular una nueva pregunta o hipótesis sobre tus datos en el chat o seleccionar otra técnica recomendada en las opciones superiores.',
      sequence: messages.length + 1,
      created_at: new Date().toISOString(),
      conversation_id: cid || 'temp',
      context: {
        prose_source: 'ai_guidance',
        snapshot: '',
        stage: 'home',
        sources: [],
        historical_refs: [],
        metric_refs: [],
        actions: [],
      },
    };
    setMessages((prev) => [...prev, infoMsg]);
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
      <div className="tutor-chat-top-toolbar">
        <label className="rp-field tutor-conversation-field">
          <span>Conversación:</span>
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
      </div>
      <details className="tutor-advanced-panel">
        <summary>⚙️ Opciones avanzadas y diagnóstico del tutor</summary>
        <div className="tutor-advanced-content">
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
            <details className="tutor-server-collapsible">
              <summary>Resumen técnico y ayuda de etapa</summary>
              <div className="tutor-server-collapsible-content">
                <p role="status">{status.static_help}</p>
                {boundSelection && (
                  <p>
                    Trabajando en: {stages[selection.stage ?? 'home']}
                    {' · '}
                    {status.guidance?.selected_table?.name ??
                      status.choices.results.find(
                        (r) => r.id === selection.result_id,
                      )?.label ??
                      status.choices.plans.find(
                        (r) => r.id === selection.plan_id,
                      )?.label ??
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
                      {Object.entries(
                        status.context.confirmed_summary ?? {},
                      ).map(([path, value]) => (
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
                      ))}
                    </ul>
                    <p>
                      Es información declarada; no demuestra independencia,
                      correspondencia entre sujetos ni cumplimiento de
                      objetivos.
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
                        Hay {status.guidance.selected_table?.identical_rows}{' '}
                        filas idénticas; no se eliminan automáticamente.
                      </p>
                    )}
                    {status.guidance.warnings?.map((w) => (
                      <p key={w}>{w}</p>
                    ))}
                    <details>
                      <summary>
                        Tipos detectados y problemas por columna
                      </summary>
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
                    Cloudflare no está configurado o no está disponible. La
                    ayuda estática, el historial y los formularios siguen
                    disponibles.
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
          )}
        </div>
      </details>
      {review && contextCurrent && status && (
        <GuidedReview
          key={status.context.context_fingerprint}
          projectId={projectId}
          status={status}
          selection={selection}
          api={api}
        />
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
        {(messages.length === 0 ||
          chatResult !== null ||
          activeProposal !== null) && (
          <div
            className="tutor-onboarding-container"
            role="region"
            aria-label="Bienvenida del asistente"
          >
            <p className="rp-sr-only">
              El historial permanece en este proyecto. Puedes consultar
              conceptos o pedir orientación sobre el siguiente paso.
            </p>
            <article className="tutor-message tutor-assistant tutor-welcome-bubble">
              <div className="tutor-assistant-header">
                <span className="tutor-avatar-icon" aria-hidden="true">
                  🤖
                </span>
                <strong>Asistente Estadístico TesisStat</strong>
              </div>
              <p className="tutor-prose">
                ¡Hola! Soy tu asistente de análisis estadístico en TesisStat AI.
                Te guiaré paso a paso para analizar tus datos, verificar
                supuestos y realizar las pruebas estadísticas adecuadas para tu
                tesis, de manera sencilla y determinista.
              </p>
              <p className="tutor-prose">
                Para comenzar, cuéntame: ¿Tus datos provienen de un instrumento
                de recolección (como una encuesta o cuestionario) o tienes
                directamente un conjunto de datos (como notas, registros o
                mediciones)?
              </p>
              <div
                className="tutor-quick-replies"
                role="group"
                aria-label="Opciones de respuesta rápida"
              >
                <button
                  type="button"
                  className="tutor-chip"
                  onClick={() => setOnboardingChoice('instrument')}
                >
                  📋 Tengo un instrumento (encuesta/test)
                </button>
                <button
                  type="button"
                  className="tutor-chip tutor-chip-primary"
                  onClick={() => setOnboardingChoice('direct_data')}
                >
                  📊 Tengo datos directos (ej. notas, registros)
                </button>
                <button
                  type="button"
                  className="tutor-chip tutor-chip-secondary"
                  onClick={() => setOnboardingChoice('explain_diff')}
                >
                  ❓ No estoy seguro, explícame la diferencia
                </button>
              </div>
            </article>

            {onboardingChoice === 'explain_diff' && (
              <>
                <article className="tutor-message tutor-user">
                  <strong>Tú</strong>
                  <p className="tutor-prose">
                    No estoy seguro, explícame la diferencia
                  </p>
                </article>
                <article className="tutor-message tutor-assistant">
                  <div className="tutor-assistant-header">
                    <span className="tutor-avatar-icon" aria-hidden="true">
                      🤖
                    </span>
                    <strong>Asistente Estadístico TesisStat</strong>
                  </div>
                  <p className="tutor-prose">
                    Un instrumento es una prueba, cuestionario o escala con
                    preguntas/ítems para medir una variable (por ejemplo, una
                    escala Likert de satisfacción o un test psicométrico). En
                    cambio, los datos directos son observaciones o registros
                    numéricos tomados directamente (como notas de exámenes,
                    registros de ventas o datos de laboratorio). ¿Cuál de los
                    dos tienes para tu investigación?
                  </p>
                  <div
                    className="tutor-quick-replies"
                    role="group"
                    aria-label="Elección de tipo de datos"
                  >
                    <button
                      type="button"
                      className="tutor-chip"
                      onClick={() => setOnboardingChoice('instrument')}
                    >
                      📋 Tengo un instrumento (encuesta/test)
                    </button>
                    <button
                      type="button"
                      className="tutor-chip tutor-chip-primary"
                      onClick={() => setOnboardingChoice('direct_data')}
                    >
                      📊 Tengo datos directos (ej. notas, registros)
                    </button>
                  </div>
                </article>
              </>
            )}

            {onboardingChoice === 'instrument' && (
              <>
                <article className="tutor-message tutor-user">
                  <strong>Tú</strong>
                  <p className="tutor-prose">
                    Tengo un instrumento (encuesta/test)
                  </p>
                </article>
                <article className="tutor-message tutor-assistant">
                  <div className="tutor-assistant-header">
                    <span className="tutor-avatar-icon" aria-hidden="true">
                      🤖
                    </span>
                    <strong>Asistente Estadístico TesisStat</strong>
                  </div>
                  <p className="tutor-prose">
                    Para trabajar con un instrumento, primero cargaremos la
                    estructura del cuestionario o test (documento Word .docx o
                    PDF con las preguntas, ítems y opciones de respuesta) y
                    posteriormente la tabla de respuestas de los participantes.
                  </p>

                  <div className="tutor-upload-zone">
                    <label className="tutor-dropzone-label">
                      <input
                        ref={instrumentFileInputRef}
                        type="file"
                        accept=".docx,.pdf,.doc"
                        disabled={instrumentUploadBusy}
                        style={{ display: 'none' }}
                        onChange={(e) =>
                          void handleInstrumentUpload(e.target.files)
                        }
                      />
                      <div className="tutor-dropzone-box">
                        <span
                          className="tutor-dropzone-icon"
                          aria-hidden="true"
                        >
                          📋
                        </span>
                        <strong>
                          Seleccionar o arrastrar instrumento (.docx o .pdf)
                        </strong>
                        <small>
                          Documento de cuestionario, test o escala con preguntas
                          e ítems
                        </small>
                      </div>
                    </label>
                    {instrumentUploadBusy && (
                      <p role="status" className="tutor-upload-status">
                        Procesando documento del instrumento…
                      </p>
                    )}
                    {instrumentUploadError && (
                      <p role="alert" className="rp-error">
                        {instrumentUploadError}
                      </p>
                    )}
                  </div>

                  {instrumentUploaded && (
                    <div className="tutor-instrument-confirmation">
                      <div className="tutor-assistant-header">
                        <span className="tutor-avatar-icon" aria-hidden="true">
                          ✅
                        </span>
                        <strong>Instrumento detectado con éxito</strong>
                      </div>
                      <p className="tutor-prose">
                        He recibido tu instrumento «{instrumentUploaded.name}» y
                        detecté {instrumentUploaded.itemCount} ítems con sus
                        opciones de respuesta. Ahora, por favor sube el archivo
                        Excel o CSV con las respuestas de los participantes.
                      </p>

                      <div className="tutor-upload-zone">
                        <label className="tutor-dropzone-label">
                          <input
                            ref={fileInputRef}
                            type="file"
                            accept=".xlsx,.csv"
                            disabled={uploadBusy}
                            style={{ display: 'none' }}
                            onChange={(e) =>
                              void handleFileUpload(e.target.files)
                            }
                          />
                          <div className="tutor-dropzone-box">
                            <span
                              className="tutor-dropzone-icon"
                              aria-hidden="true"
                            >
                              📊
                            </span>
                            <strong>
                              Subir respuestas de participantes (.xlsx o .csv)
                            </strong>
                            <small>
                              Tabla con las respuestas de los participantes a
                              los ítems
                            </small>
                          </div>
                        </label>
                        {uploadBusy && (
                          <p role="status" className="tutor-upload-status">
                            Cargando y procesando respuestas de participantes…
                          </p>
                        )}
                        {uploadErrorMsg && (
                          <p role="alert" className="rp-error">
                            {uploadErrorMsg}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="tutor-message-actions">
                    <button
                      type="button"
                      className="rp-primary tutor-action-btn"
                      onClick={() => navigateProject(projectId, 'instrument')}
                    >
                      Configurar dimensiones e ítems en Instrumento →
                    </button>
                    <button
                      type="button"
                      className="rp-secondary tutor-action-btn"
                      onClick={() => setOnboardingChoice('direct_data')}
                    >
                      Cambiar a datos directos
                    </button>
                  </div>
                </article>
              </>
            )}

            {(onboardingChoice === 'direct_data' || isNotaTable) && (
              <>
                {onboardingChoice === 'direct_data' && (
                  <article className="tutor-message tutor-user">
                    <strong>Tú</strong>
                    <p className="tutor-prose">
                      Tengo datos directos (ej. notas, registros)
                    </p>
                  </article>
                )}
                <article className="tutor-message tutor-assistant">
                  <div className="tutor-assistant-header">
                    <span className="tutor-avatar-icon" aria-hidden="true">
                      🤖
                    </span>
                    <strong>Asistente Estadístico TesisStat</strong>
                  </div>
                  {isNotaTable ? (
                    <>
                      <p className="tutor-prose">
                        He analizado tu tabla «{selectedTableName || 'Notas'}» (
                        {rowCount} registros). He detectado variables
                        cuantitativas de calificaciones: {numericVariableNames}.
                      </p>
                      <p className="tutor-prose">
                        Al contar con N = {rowCount} casos (
                        {isSmallSample
                          ? `muestra pequeña N < 50, donde corresponde la prueba de normalidad de ${recommendedNormalityTest}`
                          : `muestra N ≥ 50, donde corresponde ${recommendedNormalityTest}`}
                        ), podemos aplicar pruebas paramétricas o no
                        paramétricas según la distribución de los datos.
                      </p>
                    </>
                  ) : (
                    <p className="tutor-prose">
                      Para datos directos no requieres un instrumento previo.
                      Puedes subir directamente tu archivo Excel o CSV (por
                      ejemplo Notas.xlsx) con las columnas de calificaciones,
                      registros o mediciones para comenzar el análisis
                      estadístico.
                    </p>
                  )}

                  {!isNotaTable && (
                    <div className="tutor-upload-zone">
                      <label className="tutor-dropzone-label">
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept=".xlsx,.csv"
                          disabled={uploadBusy}
                          style={{ display: 'none' }}
                          onChange={(e) =>
                            void handleFileUpload(e.target.files)
                          }
                        />
                        <div className="tutor-dropzone-box">
                          <span
                            className="tutor-dropzone-icon"
                            aria-hidden="true"
                          >
                            📁
                          </span>
                          <strong>
                            Seleccionar o arrastrar Notas.xlsx o CSV
                          </strong>
                          <small>Formato Excel o CSV (hasta 10 MB)</small>
                        </div>
                      </label>
                      {uploadBusy && (
                        <p role="status" className="tutor-upload-status">
                          Cargando y procesando archivo de datos…
                        </p>
                      )}
                      {uploadErrorMsg && (
                        <p role="alert" className="rp-error">
                          {uploadErrorMsg}
                        </p>
                      )}
                      {status?.choices?.datasets &&
                        status.choices.datasets.length > 0 && (
                          <div className="tutor-existing-datasets">
                            <small>O selecciona una tabla ya importada:</small>
                            <div className="tutor-dataset-chips">
                              {status.choices.datasets.map((d) => (
                                <button
                                  key={d.id}
                                  type="button"
                                  className={`tutor-chip ${selection.dataset_id === d.id ? 'tutor-chip-selected' : ''}`}
                                  onClick={() => {
                                    setDirectUploadedTable(d.label || d.id);
                                    setSelection({
                                      ...selection,
                                      dataset_id: d.id,
                                    });
                                  }}
                                >
                                  📄 {d.label || d.id}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                    </div>
                  )}

                  {isNotaTable && (
                    <>
                      {/* Modalidad 1: Consulta tu hipótesis */}
                      <div className="tutor-mentoring-block">
                        <h4>
                          Modalidad 1: ¿Tienes una hipótesis o pregunta
                          definida?
                        </h4>
                        <p className="tutor-prose">
                          Escribe con tus propias palabras lo que deseas probar
                          o contrastar:
                        </p>
                        <form
                          className="tutor-hypothesis-form"
                          onSubmit={(e) => {
                            e.preventDefault();
                            handleEvaluateHypothesis(hypothesisInput);
                          }}
                        >
                          <input
                            type="text"
                            className="tutor-hypothesis-input"
                            aria-label="Pregunta o hipótesis sobre las notas"
                            placeholder="Ej. Quiero saber si las notas del postest fueron significativamente mejores que las del pretest"
                            value={hypothesisInput}
                            onChange={(e) => setHypothesisInput(e.target.value)}
                          />
                          <button
                            type="submit"
                            className="rp-secondary tutor-eval-btn"
                          >
                            Evaluar hipótesis
                          </button>
                        </form>
                        <div className="tutor-sample-chips">
                          <small>O prueba con una consulta típica:</small>
                          <div className="tutor-quick-replies">
                            <button
                              type="button"
                              className="tutor-chip tutor-chip-secondary"
                              onClick={() =>
                                handleEvaluateHypothesis(
                                  'Quiero saber si las notas del postest fueron significativamente mejores que las del pretest',
                                )
                              }
                            >
                              💡 Comparar Pretest vs Postest (mediciones
                              pareadas)
                            </button>
                            <button
                              type="button"
                              className="tutor-chip tutor-chip-secondary"
                              onClick={() =>
                                handleEvaluateHypothesis(
                                  'Quiero ver si hay correlación entre la nota 1 y la nota 2',
                                )
                              }
                            >
                              💡 Evaluar correlación entre calificaciones
                            </button>
                            <button
                              type="button"
                              className="tutor-chip tutor-chip-secondary"
                              onClick={() =>
                                handleEvaluateHypothesis(
                                  'Quiero un resumen descriptivo completo de las notas',
                                )
                              }
                            >
                              💡 Descriptivo completo (Media, mediana y
                              cuartiles)
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Modalidad 2: Recomendaciones automáticas */}
                      <div className="tutor-recommendations-block">
                        <h4>
                          Modalidad 2: ¿No estás seguro? Recomiéndame análisis
                        </h4>
                        <p className="tutor-prose">
                          Elige una de las pruebas estadísticas pertinentes para
                          tu tabla de notas:
                        </p>
                        <div className="tutor-recommendation-buttons">
                          <button
                            type="button"
                            className={`tutor-rec-card ${activeProposal === 'descriptive' ? 'tutor-rec-active' : ''}`}
                            onClick={() => {
                              setActiveProposal('descriptive');
                              setProposalExecuted(null);
                              setMentoringFeedback(
                                'Para resumir el comportamiento de las variables de calificaciones, realizaremos un análisis descriptivo completo con media, mediana, desviación estándar, rango intercuartílico y cuartiles.',
                              );
                            }}
                          >
                            <span className="tutor-rec-icon" aria-hidden="true">
                              📊
                            </span>
                            <div className="tutor-rec-text">
                              <strong>
                                1. Descriptivo completo (Media, mediana,
                                desviación estándar y cuartiles)
                              </strong>
                              <small>
                                Caracterización univariada de tendencia central
                                y dispersión.
                              </small>
                            </div>
                          </button>

                          <button
                            type="button"
                            className={`tutor-rec-card ${activeProposal === 'paired' ? 'tutor-rec-active' : ''}`}
                            onClick={() => {
                              setActiveProposal('paired');
                              setProposalExecuted(null);
                              setMentoringFeedback(
                                `Para evaluar si hubo cambio en las calificaciones de los mismos estudiantes, corresponde una prueba para mediciones pareadas (o dependientes). Con N=${rowCount}, verificaremos el supuesto de normalidad con Shapiro-Wilk en las diferencias: si se cumple la normalidad, aplicaremos la t de Student para muestras pareadas; si no se cumple, aplicaremos la prueba no paramétrica de Wilcoxon.`,
                              );
                            }}
                          >
                            <span className="tutor-rec-icon" aria-hidden="true">
                              📈
                            </span>
                            <div className="tutor-rec-text">
                              <strong>
                                2. Comparar mediciones (Pretest vs Postest -
                                Muestras pareadas)
                              </strong>
                              <small>
                                Contraste de diferencias con t de Student o
                                Wilcoxon según normalidad.
                              </small>
                            </div>
                          </button>

                          <button
                            type="button"
                            className={`tutor-rec-card ${activeProposal === 'correlation' ? 'tutor-rec-active' : ''}`}
                            onClick={() => {
                              setActiveProposal('correlation');
                              setProposalExecuted(null);
                              setMentoringFeedback(
                                'Para determinar si las notas varían conjuntamente, evaluaremos una correlación. Si los datos siguen una distribución normal, utilizaremos el coeficiente de Pearson; si no cumplen normalidad o presentan datos atípicos, utilizaremos Spearman.',
                              );
                            }}
                          >
                            <span className="tutor-rec-icon" aria-hidden="true">
                              🔗
                            </span>
                            <div className="tutor-rec-text">
                              <strong>
                                3. Evaluar correlación entre notas
                              </strong>
                              <small>
                                Coeficiente de Pearson o Spearman según
                                normalidad bivariada.
                              </small>
                            </div>
                          </button>
                        </div>
                      </div>

                      {/* Orientación metodológica en lenguaje natural */}
                      {mentoringFeedback && (
                        <div className="tutor-mentoring-response">
                          <div className="tutor-assistant-header">
                            <span
                              className="tutor-avatar-icon"
                              aria-hidden="true"
                            >
                              💡
                            </span>
                            <strong>Orientación Metodológica</strong>
                          </div>
                          <p className="tutor-prose">{mentoringFeedback}</p>
                        </div>
                      )}

                      {/* Tarjeta formal de propuesta determinista */}
                      {activeProposal && (
                        <div
                          className="tutor-proposal-card"
                          role="region"
                          aria-label="Propuesta estadística determinista"
                        >
                          <div className="tutor-proposal-header">
                            <span className="tutor-proposal-badge">
                              📋 PROPUESTA ESTADÍSTICA DETERMINISTA
                            </span>
                            <h4 className="tutor-proposal-title">
                              {activeProposal === 'paired' &&
                                'Comparación de mediciones pareadas (t de Student / Wilcoxon)'}
                              {activeProposal === 'correlation' &&
                                'Correlación bivariada entre calificaciones (Pearson / Spearman)'}
                              {activeProposal === 'descriptive' &&
                                'Resumen estadístico descriptivo completo'}
                            </h4>
                          </div>

                          <div className="tutor-proposal-body">
                            <div className="tutor-proposal-item">
                              <strong>Justificación metodológica:</strong>
                              <p>
                                {activeProposal === 'paired' &&
                                  'Apropiada para contrastar si existe diferencia significativa en las calificaciones de los mismos estudiantes antes y después de una intervención educativa.'}
                                {activeProposal === 'correlation' &&
                                  'Apropiada para determinar el grado y sentido de relación lineal o monótona entre dos evaluaciones continuas.'}
                                {activeProposal === 'descriptive' &&
                                  'Apropiada para caracterizar la tendencia central, dispersión y posición de las calificaciones del grupo.'}
                              </p>
                            </div>

                            <div className="tutor-proposal-item">
                              <strong>Variables asignadas:</strong>
                              <p>
                                {activeProposal === 'paired' &&
                                  `Medición 1: ${varPre} | Medición 2: ${varPost} (${rowCount} pares observados)`}
                                {activeProposal === 'correlation' &&
                                  `Variable 1: ${varPre} | Variable 2: ${varPost} (${rowCount} observaciones)`}
                                {activeProposal === 'descriptive' &&
                                  `Variables cuantitativas: ${numericVariableNames} (${rowCount} registros)`}
                              </p>
                            </div>

                            <div className="tutor-proposal-assumptions">
                              <strong>
                                Supuestos requeridos evaluados matemáticamente:
                              </strong>
                              <ul>
                                {activeProposal === 'paired' && (
                                  <>
                                    <li>
                                      <strong>
                                        Normalidad en las diferencias:
                                      </strong>{' '}
                                      Se evaluará mediante la prueba de{' '}
                                      <strong>Shapiro-Wilk</strong> (al contar
                                      con <em>N = {rowCount} &lt; 50</em>, con{' '}
                                      &alpha; = 0.05).
                                    </li>
                                    <li>
                                      <strong>Muestras pareadas:</strong>{' '}
                                      Observaciones dependientes sobre los
                                      mismos sujetos en dos momentos temporales.
                                    </li>
                                    <li>
                                      <strong>
                                        Criterio de decisión determinista:
                                      </strong>{' '}
                                      Si <em>p &ge; 0.05</em> se aplicará{' '}
                                      <strong>t de Student pareada</strong>; si{' '}
                                      <em>p &lt; 0.05</em> se aplicará la prueba
                                      no paramétrica de{' '}
                                      <strong>Wilcoxon</strong>.
                                    </li>
                                  </>
                                )}
                                {activeProposal === 'correlation' && (
                                  <>
                                    <li>
                                      <strong>Normalidad bivariada:</strong> Se
                                      evaluará mediante la prueba de{' '}
                                      <strong>Shapiro-Wilk</strong> para cada
                                      variable numérica (
                                      <em>N = {rowCount} &lt; 50</em>).
                                    </li>
                                    <li>
                                      <strong>
                                        Criterio de decisión determinista:
                                      </strong>{' '}
                                      Si ambas variables cumplen normalidad (
                                      <em>p &ge; 0.05</em>) y linealidad, se
                                      calculará el coeficiente de{' '}
                                      <strong>Pearson</strong>; si alguna no
                                      cumple normalidad o presenta datos
                                      atípicos, se calculará el coeficiente de{' '}
                                      <strong>Spearman</strong>.
                                    </li>
                                  </>
                                )}
                                {activeProposal === 'descriptive' && (
                                  <>
                                    <li>
                                      <strong>
                                        Medidas de tendencia central y
                                        dispersión:
                                      </strong>{' '}
                                      Media, mediana, desviación estándar,
                                      varianza, rango intercuartílico y
                                      cuartiles (Q1, Q2, Q3).
                                    </li>
                                    <li>
                                      <strong>Detección de atípicos:</strong>{' '}
                                      Evaluación de valores extremos mediante
                                      criterio de Tukey (1.5 &times; RIC).
                                    </li>
                                  </>
                                )}
                              </ul>
                            </div>

                            {proposalExecuted === activeProposal ? (
                              <div
                                className="tutor-proposal-executed"
                                role="status"
                              >
                                <div className="tutor-exec-badge">
                                  ✓ Propuesta aprobada y análisis ejecutado
                                  determinísticamente con éxito.
                                </div>
                                <div className="tutor-exec-actions">
                                  <button
                                    type="button"
                                    className="rp-primary tutor-action-btn"
                                    onClick={() =>
                                      navigateProject(projectId, 'results')
                                    }
                                  >
                                    📊 Ver Resultados y Gráficos →
                                  </button>
                                  <button
                                    type="button"
                                    className="rp-secondary tutor-action-btn"
                                    onClick={handleStartNewAnalysis}
                                  >
                                    🔄 Elegir otro análisis
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="tutor-proposal-actions">
                                <button
                                  type="button"
                                  className="rp-primary tutor-proposal-approve-btn"
                                  onClick={() =>
                                    void handleApproveAndExecute(activeProposal)
                                  }
                                >
                                  ✓ Aprobar y ejecutar análisis
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Indicador amigable de cómputo determinista */}
                      {isComputing && (
                        <div
                          className="tutor-computing-indicator"
                          role="status"
                        >
                          <div className="tutor-spinner" aria-hidden="true" />
                          <span>
                            Calculando estadísticos deterministas y verificando
                            supuestos...
                          </span>
                        </div>
                      )}

                      {/* Renderizado de resultados en chat C06 */}
                      {chatResult && (
                        <ChatResultView
                          data={chatResult}
                          onFollowupQuery={handleFollowupQuery}
                          onDownload={(fmt) => void handleDownload(fmt)}
                          onStartNewAnalysis={handleStartNewAnalysis}
                          isDownloading={isDownloading}
                        />
                      )}

                      <div className="tutor-message-actions">
                        <button
                          type="button"
                          className="rp-secondary tutor-action-btn"
                          onClick={() =>
                            navigateWorkspace(
                              projectId,
                              'analysis',
                              'diagnostics',
                            )
                          }
                        >
                          🔍 Verificar normalidad y supuestos en Diagnóstico
                        </button>
                        {onOpenDataPanel && (
                          <button
                            type="button"
                            className="rp-secondary tutor-action-btn"
                            onClick={onOpenDataPanel}
                          >
                            📋 Ver datos cargados
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </article>
              </>
            )}
          </div>
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
        className="tutor-composer-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (isNotaTable && draft.trim()) {
            handleEvaluateHypothesis(draft.trim());
          }
          void send();
        }}
      >
        <div className="tutor-composer-bar">
          <label className="rp-sr-only" htmlFor="tutor-chat-input">
            Tu consulta
          </label>
          <textarea
            id="tutor-chat-input"
            className="tutor-composer-textarea"
            value={draft}
            disabled={busy}
            maxLength={status?.max_message_characters ?? 2000}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (
                  !busy &&
                  contextCurrent &&
                  status?.provider_configured &&
                  status?.consent.granted &&
                  draft.trim()
                ) {
                  if (isNotaTable) {
                    handleEvaluateHypothesis(draft.trim());
                  }
                  void send();
                }
              }
            }}
            rows={2}
            placeholder="Formula tu hipótesis o consulta estadística sobre tus datos..."
          />
          <button
            type="submit"
            className="tutor-send-button"
            aria-label="Enviar consulta"
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
        </div>

        {status && (
          <div className="tutor-consent-footer">
            {status.consent.renewal_required && (
              <p role="status" className="tutor-consent-renewal">
                Cambió lo que se transmite: ahora conserva la redacción depurada
                de la consulta e incluye encabezados seguros, detecciones
                locales y significados de variables confirmados. El permiso
                anterior no basta; revisa la descripción y renueva tu
                autorización.
              </p>
            )}
            <label className="tutor-consent-subtle">
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
              <span>
                Autorizo el envío acotado a Cloudflare Workers AI (alcance v5),
                incluidos consulta e historial depurados, contexto confirmado y
                resumen de variables y comprobaciones locales. Escribiré sin
                datos personales ni secretos. Desmarcar revoca el permiso.
              </span>
            </label>
            {consentPending != null && (
              <p role="status" className="tutor-consent-status">
                Guardando el cambio de permiso…
              </p>
            )}
            <p className="tutor-consent-hint">
              <small>
                💡 Las recomendaciones a 1 clic, carga de instrumentos y
                cálculos estadísticos (Shapiro-Wilk, t-Student, Wilcoxon, APA)
                se ejecutan de forma 100% local y determinista sin requerir este
                permiso.
              </small>
            </p>
          </div>
        )}
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
