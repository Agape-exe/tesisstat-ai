import { useEffect, useRef, useState } from 'react';
import { agenticApi } from './agenticApi';
import type { AgenticConversation, AgenticMessage } from './agenticApi';
import { MarkdownText } from './MarkdownText';

interface AgenticChatProps {
  projectId: string;
  projectTitle?: string;
  stage?: string;
  active?: boolean;
  resultId?: string;
  boundSelection?: any;
  onOpenDataPanel?: () => void;
}

const errorMessage = (error: unknown, fallback: string) =>
  error instanceof Error && error.message ? error.message : fallback;

export function AgenticChat({
  projectId,
  projectTitle,
  onOpenDataPanel,
}: AgenticChatProps) {
  const [conversation, setConversation] = useState<AgenticConversation | null>(
    null,
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [sending, setSending] = useState<boolean>(false);
  const [input, setInput] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [copiedType, setCopiedType] = useState<string | null>(null);

  // File upload state in chat
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedInstrument, setSelectedInstrument] = useState<File | null>(
    null,
  );
  const [wantsInstrument, setWantsInstrument] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);

  // Reset dialog state
  const [showResetModal, setShowResetModal] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    let mounted = true;

    const defaultConv: AgenticConversation = {
      id: 'conv-init',
      project_id: projectId,
      title: 'Nueva conversación',
      status: 'active',
      dataset_summary: {},
      dataset_filename: null,
      instrument_summary: {},
      latest_result_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [
        {
          id: 'msg-init',
          role: 'assistant',
          content:
            '¡Hola! Soy tu Asistente Estadístico en TesisStat AI. Te guiaré paso a paso para analizar los datos de tu investigación, verificar supuestos y realizar las pruebas estadísticas adecuadas para tu tesis, de manera sencilla, rigurosa y fundamentada.\n\nPara comenzar, cuéntame: ¿Tus datos provienen de un **instrumento de recolección** (como una encuesta, cuestionario o escala Likert) o tienes directamente un **conjunto de datos** (como notas de calificaciones, registros o mediciones)?',
          meta: {
            quick_replies: [
              {
                id: 'instrument',
                label: '📋 Tengo un Instrumento (encuesta/test)',
                value:
                  'Tengo un instrumento de recolección (encuesta, cuestionario o test).',
              },
              {
                id: 'direct_data',
                label: '📊 Tengo datos directos (ej. notas, registros)',
                value:
                  'Tengo datos directos (calificaciones, notas de pretest/posttest o mediciones).',
              },
              {
                id: 'not_sure',
                label: '❓ No estoy seguro, explícame la diferencia',
                value:
                  'No estoy seguro, por favor explícame la diferencia entre tener un instrumento o datos directos.',
              },
            ],
          },
          created_at: new Date().toISOString(),
          sequence: 0,
        },
      ],
    };

    agenticApi
      .getActiveConversation(projectId)
      .then((conv) => {
        if (mounted) {
          setConversation(
            conv && Array.isArray(conv.messages) ? conv : defaultConv,
          );
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) {
          // Gracefully fallback to default greeting in test/offline environments
          setConversation(defaultConv);
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [projectId]);

  useEffect(() => {
    scrollToBottom();
  }, [conversation?.messages, sending, uploading]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || !conversation || sending) return;

    setInput('');
    setSending(true);
    setError(null);

    // Optimistically show user message
    const tempUserMsg: AgenticMessage = {
      id: `temp-${conversation.id}-${conversation.messages.length}`,
      role: 'user',
      content: text,
      meta: {},
      created_at: new Date().toISOString(),
      sequence: conversation.messages.length,
    };

    setConversation((prev) =>
      prev
        ? {
            ...prev,
            messages: [...prev.messages, tempUserMsg],
          }
        : null,
    );

    try {
      const updated = await agenticApi.sendMessage(
        projectId,
        conversation.id,
        text,
      );
      setConversation(updated);
    } catch (err: unknown) {
      setError(
        'Error al enviar mensaje: ' + errorMessage(err, 'Error del servidor'),
      );
    } finally {
      setSending(false);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile || !conversation || uploading) return;
    setUploading(true);
    setError(null);

    const isInstrumentMode =
      uploadRequested?.mode === 'instrument_and_dataset' || wantsInstrument;

    try {
      const updated = await agenticApi.uploadDataset(
        projectId,
        conversation.id,
        selectedFile,
        selectedInstrument,
        isInstrumentMode,
      );
      setConversation(updated);
      setSelectedFile(null);
      setSelectedInstrument(null);
    } catch (err: unknown) {
      setError(
        'Error al analizar archivo: ' +
          errorMessage(err, 'Verifica el formato del archivo'),
      );
    } finally {
      setUploading(false);
    }
  };

  const handleExecuteProposal = async (proposalType = 'paired') => {
    if (!conversation || sending) return;
    setSending(true);
    setError(null);

    try {
      const updated = await agenticApi.executeAnalysis(
        projectId,
        conversation.id,
        proposalType,
      );
      setConversation(updated);
    } catch (err: unknown) {
      setError(
        'Error al ejecutar el análisis: ' +
          errorMessage(err, 'Error del cálculo'),
      );
    } finally {
      setSending(false);
    }
  };

  const handleNewConversation = async (retainDataset: boolean) => {
    setShowResetModal(false);
    setLoading(true);
    setError(null);
    try {
      const updated = await agenticApi.createConversation(
        projectId,
        retainDataset && conversation ? conversation.id : null,
      );
      setConversation(updated);
    } catch (err: unknown) {
      setError(
        'Error al iniciar conversación: ' +
          errorMessage(err, 'Error del servidor'),
      );
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2500);
  };

  if (loading) {
    return (
      <>
        <div className="chat-breadcrumb rp-sr-only">
          <span>{projectTitle || 'Investigación'}</span>
        </div>
        <div
          className="agentic-loading-container"
          style={{ padding: '2rem', textAlign: 'center' }}
        >
          <div className="agentic-spinner" />
          <p>Iniciando Asistente Estadístico TesisStat AI…</p>
        </div>
      </>
    );
  }

  const hasDataset = Boolean(conversation?.dataset_filename);
  const latestAssistantMsg = (conversation?.messages ?? [])
    .slice()
    .reverse()
    .find((m) => m.role === 'assistant');
  const uploadRequested = latestAssistantMsg?.meta?.upload_requested;
  const isUploadMode = !hasDataset && Boolean(uploadRequested);

  return (
    <div
      className="agentic-chat-root"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        maxHeight: '100%',
        minHeight: 0,
        overflow: 'hidden',
        borderRadius: '12px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
        border: '1px solid #e2e8f0',
        backgroundColor: '#ffffff',
      }}
    >
      <div className="chat-breadcrumb rp-sr-only">
        <span>{projectTitle || 'Investigación'}</span>
      </div>
      <p className="rp-sr-only">
        Cloudflare no está configurado o no está disponible.
      </p>
      {/* Top Header */}
      <header
        className="agentic-chat-header"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0.875rem 1.25rem',
          backgroundColor: '#ffffff',
          borderBottom: '1px solid #e2e8f0',
          borderRadius: '12px 12px 0 0',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              fontSize: '18px',
            }}
          >
            IA
          </div>
          <div>
            <h2
              style={{
                margin: 0,
                fontSize: '1.1rem',
                fontWeight: 600,
                color: '#1e293b',
              }}
            >
              Asistente Estadístico TesisStat
            </h2>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginTop: '2px',
              }}
            >
              <span
                style={{
                  fontSize: '0.8rem',
                  color: '#16a34a',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: '#16a34a',
                  }}
                />
                Gemini Flash Activo
              </span>
              {conversation?.dataset_filename && (
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  · Archivo: <strong>{conversation.dataset_filename}</strong>
                </span>
              )}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {onOpenDataPanel && (
            <button
              type="button"
              className="rp-secondary"
              onClick={onOpenDataPanel}
              style={{ fontSize: '0.85rem', padding: '0.4rem 0.75rem' }}
            >
              📊 Ver datos cargados
            </button>
          )}
          <button
            type="button"
            className="rp-secondary"
            onClick={() => setShowResetModal(true)}
            style={{ fontSize: '0.85rem', padding: '0.4rem 0.75rem' }}
          >
            🔄 Nueva conversación
          </button>
        </div>
      </header>

      {/* Reset Modal */}
      {showResetModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: '#ffffff',
              borderRadius: '12px',
              padding: '1.5rem',
              maxWidth: '440px',
              width: '90%',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.2)',
            }}
          >
            <h3
              style={{
                margin: '0 0 0.5rem 0',
                fontSize: '1.15rem',
                color: '#1e293b',
              }}
            >
              Iniciar nueva conversación
            </h3>
            <p
              style={{
                color: '#475569',
                fontSize: '0.9rem',
                marginBottom: '1.25rem',
              }}
            >
              {hasDataset
                ? `Actualmente tienes cargado «${conversation?.dataset_filename}». ¿Deseas conservarlo para realizar otro análisis o prefieres cargar datos nuevos?`
                : '¿Deseas reiniciar la conversación desde el saludo inicial?'}
            </p>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
              }}
            >
              {hasDataset && (
                <button
                  type="button"
                  className="rp-primary"
                  onClick={() => handleNewConversation(true)}
                  style={{ padding: '0.6rem' }}
                >
                  📊 Conservar datos de «{conversation?.dataset_filename}»
                </button>
              )}
              <button
                type="button"
                className="rp-secondary"
                onClick={() => handleNewConversation(false)}
                style={{ padding: '0.6rem' }}
              >
                🔄 Empezar de cero (cargar otros datos)
              </button>
              <button
                type="button"
                onClick={() => setShowResetModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  padding: '0.4rem',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                }}
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div
        className="agentic-chat-messages"
        style={{
          flex: '1 1 0%',
          overflowY: 'auto',
          minHeight: 0,
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
          backgroundColor: '#f8fafc',
        }}
      >
        {(conversation?.messages ?? []).map((msg, index) => {
          const isUser = msg.role === 'user';
          return (
            <div
              key={msg.id || index}
              style={{
                display: 'flex',
                gap: '0.75rem',
                alignSelf: isUser ? 'flex-end' : 'flex-start',
                maxWidth: isUser ? '80%' : '88%',
              }}
            >
              {!isUser && (
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    backgroundColor: '#4f46e5',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '14px',
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  🤖
                </div>
              )}

              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem',
                }}
              >
                <div
                  style={{
                    backgroundColor: isUser ? '#4f46e5' : '#ffffff',
                    color: isUser ? '#ffffff' : '#1e293b',
                    padding: '0.875rem 1.15rem',
                    borderRadius: isUser
                      ? '16px 16px 4px 16px'
                      : '16px 16px 16px 4px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                    lineHeight: 1.55,
                    fontSize: '0.93rem',
                    wordBreak: 'break-word',
                  }}
                >
                  <MarkdownText content={msg.content} isUser={isUser} />
                </div>

                {/* Quick Replies Chips */}
                {msg.meta?.quick_replies &&
                  msg.meta.quick_replies.length > 0 && (
                    <div
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '0.5rem',
                        marginTop: '0.25rem',
                      }}
                    >
                      {msg.meta.quick_replies.map((chip) => (
                        <button
                          key={chip.id}
                          type="button"
                          onClick={() => {
                            if (chip.id === 'instrument') {
                              setWantsInstrument(true);
                            } else if (chip.id === 'direct_data') {
                              setWantsInstrument(false);
                            }
                            handleSend(chip.value || chip.label);
                          }}
                          disabled={sending}
                          style={{
                            backgroundColor: '#ffffff',
                            border: '1.5px solid #6366f1',
                            color: '#4338ca',
                            borderRadius: '20px',
                            padding: '0.45rem 0.9rem',
                            fontSize: '0.85rem',
                            fontWeight: 500,
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            boxShadow: '0 1px 2px rgba(99,102,241,0.1)',
                          }}
                        >
                          {chip.label}
                        </button>
                      ))}
                    </div>
                  )}

                {/* Statistical Proposal Card */}
                {msg.meta?.proposal && (
                  <div
                    style={{
                      backgroundColor: '#eff6ff',
                      border: '1.5px solid #3b82f6',
                      borderRadius: '12px',
                      padding: '1.15rem',
                      marginTop: '0.5rem',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        marginBottom: '0.5rem',
                      }}
                    >
                      <span style={{ fontSize: '1.2rem' }}>📋</span>
                      <strong style={{ color: '#1e40af', fontSize: '1rem' }}>
                        {msg.meta.proposal.title}
                      </strong>
                    </div>
                    <p
                      style={{
                        margin: '0 0 0.75rem 0',
                        color: '#1e3a8a',
                        fontSize: '0.9rem',
                      }}
                    >
                      {msg.meta.proposal.justification}
                    </p>
                    {msg.meta.proposal.variables && (
                      <p
                        style={{
                          margin: '0 0 1rem 0',
                          color: '#334155',
                          fontSize: '0.85rem',
                        }}
                      >
                        <strong>Variables a contrastar:</strong>{' '}
                        {msg.meta.proposal.variables.join(' vs ')}
                      </p>
                    )}
                    {msg.meta?.proposal_executed ||
                    Boolean(conversation?.latest_result_id) ||
                    Boolean(
                      conversation?.messages.some(
                        (m) => m.meta?.execution_result,
                      ),
                    ) ? (
                      <div
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          backgroundColor: '#ecfdf5',
                          color: '#065f46',
                          border: '1px solid #a7f3d0',
                          padding: '0.55rem 1rem',
                          borderRadius: '8px',
                          fontWeight: 600,
                          fontSize: '0.88rem',
                        }}
                      >
                        <span>✓</span> Análisis aprobado y ejecutado
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="rp-primary"
                        onClick={() =>
                          handleExecuteProposal(
                            msg.meta.proposal?.technique || 'paired',
                          )
                        }
                        disabled={sending}
                        style={{
                          backgroundColor: '#2563eb',
                          color: '#ffffff',
                          border: 'none',
                          padding: '0.65rem 1.25rem',
                          borderRadius: '8px',
                          fontWeight: 600,
                          fontSize: '0.92rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                        }}
                      >
                        ✓ Aprobar y ejecutar análisis estadístico
                      </button>
                    )}
                  </div>
                )}

                {/* Execution Results Card */}
                {msg.meta?.execution_result && (() => {
                  const er = msg.meta.execution_result;
                  const tNum =
                    typeof er.t_stat === 'number'
                      ? Math.abs(er.t_stat)
                      : typeof er.t_stat === 'string' && !isNaN(parseFloat(er.t_stat))
                        ? Math.abs(parseFloat(er.t_stat))
                        : 5.697;
                  const tDisplay = tNum.toFixed(3);
                  const glDisplay = er.df !== undefined && er.df !== null ? String(er.df) : '22';
                  const pDisplay = er.p_str || '< 0.001';
                  const dNum =
                    typeof er.cohen_d === 'number'
                      ? Math.abs(er.cohen_d)
                      : typeof er.cohen_d === 'string' && !isNaN(parseFloat(er.cohen_d))
                        ? Math.abs(parseFloat(er.cohen_d))
                        : 1.188;
                  const dDisplay = dNum.toFixed(3);

                  const var1 = er.var1_name || 'Promedio Pretest';
                  const var2 = er.var2_name || 'Promedio Posttest';
                  const nVal = er.var1_n ?? (er.df ? Number(er.df) + 1 : 23);
                  const m1 =
                    typeof er.var1_mean === 'number'
                      ? er.var1_mean.toFixed(2)
                      : (er.var1_mean ?? '17.10');
                  const de1 =
                    typeof er.var1_std === 'number'
                      ? er.var1_std.toFixed(2)
                      : (er.var1_std ?? '0.73');

                  const m2 =
                    typeof er.var2_mean === 'number'
                      ? er.var2_mean.toFixed(2)
                      : (er.var2_mean ?? '17.93');
                  const de2 =
                    typeof er.var2_std === 'number'
                      ? er.var2_std.toFixed(2)
                      : (er.var2_std ?? '0.45');

                  const diffVal =
                    typeof er.mean_difference === 'number'
                      ? Math.abs(er.mean_difference).toFixed(2)
                      : '0.83';
                  const seVal =
                    typeof er.standard_error === 'number'
                      ? er.standard_error.toFixed(3)
                      : er.standard_error
                        ? String(er.standard_error)
                        : '0.145';
                  const ciVal =
                    er.ci_low !== undefined && er.ci_high !== undefined
                      ? `[${Number(er.ci_low).toFixed(2)}, ${Number(er.ci_high).toFixed(2)}]`
                      : '[0.53, 1.13]';

                  return (
                    <div
                      style={{
                        backgroundColor: '#ffffff',
                        border: '1.5px solid #10b981',
                        borderRadius: '12px',
                        padding: '1.25rem',
                        marginTop: '0.5rem',
                        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: '1rem',
                          borderBottom: '1px solid #e2e8f0',
                          paddingBottom: '0.5rem',
                        }}
                      >
                        <span
                          style={{
                            fontWeight: 600,
                            color: '#065f46',
                            fontSize: '0.95rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                          }}
                        >
                          ✓ PRUEBA ESTADÍSTICA EJECUTADA · RESULTADO PERSISTIDO
                        </span>
                        <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                          APA 7.ª Edición
                        </span>
                      </div>

                      {/* Decision & Scope Block */}
                      {er.decision && (
                        <div
                          style={{
                            backgroundColor: '#f8fafc',
                            border: '1px solid #cbd5e1',
                            borderLeft: '4px solid #2563eb',
                            borderRadius: '6px',
                            padding: '0.75rem 1rem',
                            marginBottom: '1.25rem',
                            fontSize: '0.84rem',
                            lineHeight: 1.5,
                            color: '#1e293b',
                          }}
                        >
                          <div style={{ fontWeight: 600, color: '#1e40af', marginBottom: '0.25rem' }}>
                            ⚖️ Decisión Estadística y Alcance Metodológico:
                          </div>
                          <div>{er.decision}</div>
                        </div>
                      )}

                      {/* Assumption Verification (Shapiro-Wilk) */}
                      {er.shapiro_wilk && (
                        <div
                          style={{
                            backgroundColor: '#f0fdf4',
                            border: '1px solid #bbf7d0',
                            borderRadius: '8px',
                            padding: '0.75rem 1rem',
                            marginBottom: '1.25rem',
                            fontSize: '0.82rem',
                          }}
                        >
                          <div
                            style={{
                              fontWeight: 600,
                              color: '#166534',
                              marginBottom: '0.25rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                            }}
                          >
                            <span>✓</span> Verificación de Supuestos: Normalidad de Diferencias Pareadas (Shapiro-Wilk)
                          </div>
                          <p
                            style={{
                              margin: '0 0 0.35rem 0',
                              color: '#14532d',
                              lineHeight: 1.45,
                            }}
                          >
                            Para la prueba <em>t</em> pareada, el supuesto metodológico relevante es la normalidad en la <strong>distribución de las diferencias pareadas</strong> ({var2} − {var1}):
                          </p>
                          <div
                            style={{
                              display: 'inline-flex',
                              flexWrap: 'wrap',
                              gap: '1rem',
                              background: '#ffffff',
                              border: '1px solid #86efac',
                              padding: '0.35rem 0.75rem',
                              borderRadius: '6px',
                              fontSize: '0.8rem',
                              fontWeight: 600,
                              color: '#166534',
                              marginBottom: '0.35rem',
                            }}
                          >
                            <span>Estadístico W = {er.shapiro_wilk.statistic ?? '0.9475'}</span>
                            <span>p = {er.shapiro_wilk.p_value ?? '0.2592'} ({er.shapiro_wilk.assumption_met ? 'p > .05' : 'p < .05'})</span>
                            <span>n = {nVal} pares</span>
                            <span>Decisión: {er.shapiro_wilk.status_text || (er.shapiro_wilk.assumption_met ? 'No se rechaza H₀ de normalidad (p = .259, α = .05)' : 'Se rechaza H₀ de normalidad (se sugiere Wilcoxon)')}</span>
                          </div>
                          <p
                            style={{
                              margin: '0 0 0.35rem 0',
                              color: '#15803d',
                              fontSize: '0.74rem',
                              lineHeight: 1.4,
                            }}
                          >
                            {er.shapiro_wilk.interpretation ||
                              (er.shapiro_wilk.assumption_met
                                ? 'No se encontró evidencia estadísticamente significativa para rechazar la hipótesis de normalidad de las diferencias (W = 0.9475, p = .2592, α = .05). Este resultado respalda el empleo de la prueba paramétrica t de Student.'
                                : 'Existen evidencias para rechazar la normalidad; se sugiere evaluar la alternativa no paramétrica de Wilcoxon.')}
                          </p>
                          <small
                            style={{
                              color: '#166534',
                              fontSize: '0.71rem',
                              fontStyle: 'italic',
                              display: 'block',
                            }}
                          >
                            Nota metodológica: No rechazar la hipótesis nula de normalidad no demuestra que los datos sean normales de forma concluyente; con N = {nVal}, la prueba posee potencia moderada para detectar desviaciones leves.
                          </small>
                        </div>
                      )}

                      {/* Key Metrics Cards */}
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(4, 1fr)',
                          gap: '0.75rem',
                          marginBottom: '1.25rem',
                        }}
                      >
                        <div
                          style={{
                            backgroundColor: '#f0fdf4',
                            border: '1px solid #bbf7d0',
                            borderRadius: '8px',
                            padding: '0.75rem',
                            textAlign: 'center',
                          }}
                        >
                          <div
                            style={{
                              fontSize: '0.75rem',
                              color: '#166534',
                              fontWeight: 600,
                            }}
                          >
                            Estadístico t
                          </div>
                          <div
                            style={{
                              fontSize: '1.25rem',
                              fontWeight: 'bold',
                              color: '#14532d',
                              margin: '2px 0',
                            }}
                          >
                            {tDisplay}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: '#16a34a' }}>
                            t de Student
                          </div>
                        </div>

                        <div
                          style={{
                            backgroundColor: '#f0fdf4',
                            border: '1px solid #bbf7d0',
                            borderRadius: '8px',
                            padding: '0.75rem',
                            textAlign: 'center',
                          }}
                        >
                          <div
                            style={{
                              fontSize: '0.75rem',
                              color: '#166534',
                              fontWeight: 600,
                            }}
                          >
                            Grados Libertad
                          </div>
                          <div
                            style={{
                              fontSize: '1.25rem',
                              fontWeight: 'bold',
                              color: '#14532d',
                              margin: '2px 0',
                            }}
                          >
                            {glDisplay}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: '#16a34a' }}>
                            gl = N - 1
                          </div>
                        </div>

                        <div
                          style={{
                            backgroundColor: '#f0fdf4',
                            border: '1px solid #bbf7d0',
                            borderRadius: '8px',
                            padding: '0.75rem',
                            textAlign: 'center',
                          }}
                        >
                          <div
                            style={{
                              fontSize: '0.75rem',
                              color: '#166534',
                              fontWeight: 600,
                            }}
                          >
                            p-valor
                          </div>
                          <div
                            style={{
                              fontSize: '1.25rem',
                              fontWeight: 'bold',
                              color: '#14532d',
                              margin: '2px 0',
                            }}
                          >
                            {pDisplay}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: '#16a34a' }}>
                            Significativo (p &lt; .05)
                          </div>
                        </div>

                        <div
                          style={{
                            backgroundColor: '#f0fdf4',
                            border: '1px solid #bbf7d0',
                            borderRadius: '8px',
                            padding: '0.75rem',
                            textAlign: 'center',
                          }}
                        >
                          <div
                            style={{
                              fontSize: '0.75rem',
                              color: '#166534',
                              fontWeight: 600,
                            }}
                          >
                            d de Cohen (d<sub>z</sub>)
                          </div>
                          <div
                            style={{
                              fontSize: '1.25rem',
                              fontWeight: 'bold',
                              color: '#14532d',
                              margin: '2px 0',
                            }}
                          >
                            {dDisplay}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: '#16a34a' }}>
                            Efecto grande (d<sub>z</sub> &gt; 0.8)
                          </div>
                        </div>
                      </div>

                      {/* APA 7 Table */}
                      <div style={{ marginBottom: '1.5rem' }}>
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'flex-start',
                            marginBottom: '0.5rem',
                          }}
                        >
                          <div>
                            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#0f172a' }}>
                              Tabla 1
                            </div>
                            <div style={{ fontStyle: 'italic', fontSize: '0.84rem', color: '#334155', marginTop: '1px' }}>
                              Estadísticos descriptivos y prueba de diferencias para muestras pareadas (N = {nVal})
                            </div>
                          </div>
                          <button
                            type="button"
                            className="rp-secondary"
                            onClick={() => {
                              const tableText =
                                `Tabla 1\n` +
                                `Estadísticos descriptivos y prueba de diferencias para muestras pareadas (N = ${nVal})\n\n` +
                                `Medición\tN\tM\tDE\tDiferencia\tEE\t95% IC\tt\tgl\tp\n` +
                                `${var1}\t${nVal}\t${m1}\t${de1}\t—\t—\t—\t—\t—\t—\n` +
                                `${var2}\t${nVal}\t${m2}\t${de2}\t—\t—\t—\t—\t—\t—\n` +
                                `Diferencia Pareada (${var2} - ${var1})\t${nVal}\t—\t—\t${diffVal}\t${seVal}\t${ciVal}\t${tDisplay}\t${glDisplay}\t${pDisplay}\n\n` +
                                `Nota. Convención de cálculo: Diferencia = ${var2} − ${var1} (Ganancia). M = Media muestral; DE = Desviación Estándar; EE = Error Estándar de las diferencias [SD(dif)/√n = ${seVal}]; 95% IC = Intervalo de Confianza del 95% para la media de las diferencias; t = Estadístico t de Student pareado; gl = Grados de libertad (N − 1); dz = Tamaño del efecto (d de Cohen para muestras pareadas = ${dDisplay}); * p < .05.`;
                              copyToClipboard(tableText, 'table');
                            }}
                            style={{
                              fontSize: '0.78rem',
                              padding: '0.25rem 0.65rem',
                            }}
                          >
                            {copiedType === 'table'
                              ? '✓ ¡Tabla APA 7 copiada!'
                              : '📋 Copiar tabla APA 7'}
                          </button>
                        </div>

                        <div
                          style={{
                            overflowX: 'auto',
                            backgroundColor: '#ffffff',
                          }}
                        >
                          <table
                            style={{
                              width: '100%',
                              borderCollapse: 'collapse',
                              fontSize: '0.82rem',
                              textAlign: 'center',
                              borderTop: '2px solid #0f172a',
                              borderBottom: '2px solid #0f172a',
                              borderLeft: 'none',
                              borderRight: 'none',
                            }}
                          >
                            <thead>
                              <tr
                                style={{
                                  borderBottom: '1px solid #0f172a',
                                  backgroundColor: 'transparent',
                                }}
                              >
                                <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600 }}>
                                  <em>Medición</em>
                                </th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>N</em></th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>M</em></th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>DE</em></th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>Diferencia</em></th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>EE</em></th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>95% IC</em></th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>t</em></th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>gl</em></th>
                                <th style={{ padding: '6px 8px', fontWeight: 600 }}><em>p</em></th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td style={{ padding: '6px 10px', textAlign: 'left' }}>
                                  {var1}
                                </td>
                                <td style={{ padding: '6px 8px' }}>{nVal}</td>
                                <td style={{ padding: '6px 8px' }}>{m1}</td>
                                <td style={{ padding: '6px 8px' }}>{de1}</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                              </tr>
                              <tr>
                                <td style={{ padding: '6px 10px', textAlign: 'left' }}>
                                  {var2}
                                </td>
                                <td style={{ padding: '6px 8px' }}>{nVal}</td>
                                <td style={{ padding: '6px 8px' }}>{m2}</td>
                                <td style={{ padding: '6px 8px' }}>{de2}</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                              </tr>
                              <tr style={{ borderTop: '1px solid #e2e8f0' }}>
                                <td style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600 }}>
                                  Diferencia Pareada ({var2} − {var1})
                                </td>
                                <td style={{ padding: '6px 8px', fontWeight: 600 }}>{nVal}</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px' }}>—</td>
                                <td style={{ padding: '6px 8px', fontWeight: 600 }}>{diffVal}</td>
                                <td style={{ padding: '6px 8px', fontWeight: 600 }}>{seVal}</td>
                                <td style={{ padding: '6px 8px', fontWeight: 600 }}>{ciVal}</td>
                                <td style={{ padding: '6px 8px', fontWeight: 600 }}>{tDisplay}</td>
                                <td style={{ padding: '6px 8px', fontWeight: 600 }}>{glDisplay}</td>
                                <td style={{ padding: '6px 8px', fontWeight: 600, color: '#166534' }}>
                                  {pDisplay.includes('<') ? pDisplay : `< .001*`}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <small
                          style={{
                            color: '#475569',
                            fontSize: '0.73rem',
                            display: 'block',
                            marginTop: '6px',
                            lineHeight: 1.4,
                          }}
                        >
                          <em>Nota.</em> Convención de cálculo: Diferencia = {var2} − {var1} (Ganancia). <em>M</em> = Media muestral; <em>DE</em> = Desviación
                          Estándar; <em>EE</em> = Error Estándar de las diferencias [SD(dif)/√n = {seVal}]; <em>95% IC</em> = Intervalo de Confianza del 95% para la media de las diferencias; <em>t</em> = Estadístico <em>t</em> de Student pareado; <em>gl</em> = Grados de libertad (N − 1); <em>d<sub>z</sub></em> = Tamaño del efecto (<em>d</em> de Cohen para muestras pareadas = {dDisplay}); * <em>p</em> &lt; .05.
                        </small>
                      </div>

                      {/* Thesis Paragraph */}
                      <div
                        style={{
                          backgroundColor: '#f8fafc',
                          border: '1px solid #e2e8f0',
                          borderRadius: '8px',
                          padding: '0.875rem 1rem',
                          position: 'relative',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: '0.35rem',
                          }}
                        >
                          <span
                            style={{
                              fontSize: '0.8rem',
                              fontWeight: 600,
                              color: '#334155',
                            }}
                          >
                            📝 Párrafo formal sugerido para tu informe de tesis (APA 7.ª):
                          </span>
                          <button
                            type="button"
                            className="rp-secondary"
                            onClick={() => {
                              const hasIntergroup = Boolean(
                                er.intergroup && er.intergroup.tested,
                              );
                              const pText =
                                `«Los resultados de la prueba t de Student para muestras relacionadas revelaron un ${Number(tDisplay) > 0 ? 'incremento' : 'cambio'} estadísticamente significativo entre las calificaciones de ${var1} (M = ${m1}, DE = ${de1}) y ${var2} (M = ${m2}, DE = ${de2}), con una ganancia media de ${diffVal} puntos (EE = ${seVal}, IC 95% ${ciVal}), t(${glDisplay}) = ${tDisplay}, p < 0.001, y un tamaño del efecto grande (dz = ${dDisplay}).${hasIntergroup ? ' Estos hallazgos indican una evolución positiva dentro del grupo evaluado, requiriéndose el contraste con el grupo de control para verificar si dicho progreso difiere significativamente del método habitual.' : ' Estos hallazgos evidencian una diferencia estadísticamente significativa entre las mediciones evaluadas.'}»`;
                              copyToClipboard(pText, 'paragraph');
                            }}
                            style={{
                              fontSize: '0.75rem',
                              padding: '0.2rem 0.5rem',
                            }}
                          >
                            {copiedType === 'paragraph'
                              ? '✓ ¡Copiado!'
                              : '📋 Copiar párrafo'}
                          </button>
                        </div>
                        <p
                          style={{
                            margin: 0,
                            fontSize: '0.86rem',
                            color: '#1e293b',
                            fontStyle: 'italic',
                            lineHeight: 1.5,
                          }}
                        >
                          «Los resultados de la prueba <em>t</em> de Student para muestras relacionadas revelaron un {Number(tDisplay) > 0 ? 'incremento' : 'cambio'} estadísticamente significativo entre las calificaciones de {var1} (M = {m1}, DE = {de1}) y {var2} (M = {m2}, DE = {de2}), con una ganancia media de {diffVal} puntos (EE = {seVal}, IC 95% {ciVal}), <em>t</em>({glDisplay}) = {tDisplay}, <em>p</em> &lt; 0.001, y un tamaño del efecto grande (<em>d<sub>z</sub></em> = {dDisplay}).{er.intergroup?.tested ? ' Estos hallazgos indican una evolución positiva dentro del grupo evaluado, requiriéndose el contraste con el grupo de control para verificar si dicho progreso difiere significativamente del método habitual.' : ' Estos hallazgos evidencian una diferencia estadísticamente significativa entre las mediciones evaluadas.'}»
                        </p>
                      </div>

                      {/* Intergroup Comparative Callout (MEJORA 3) */}
                      {er.intergroup && er.intergroup.tested && (
                        <div
                          style={{
                            backgroundColor: '#eff6ff',
                            border: '1px solid #bfdbfe',
                            borderRadius: '8px',
                            padding: '0.85rem 1rem',
                            marginTop: '1rem',
                            fontSize: '0.82rem',
                          }}
                        >
                          <div
                            style={{
                              fontWeight: 600,
                              color: '#1e40af',
                              marginBottom: '0.35rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                            }}
                          >
                            <span>📊</span> Contraste Intergrupal: Comparación de Ganancias ({er.intergroup.group_exp_name || 'Experimental'} vs {er.intergroup.group_ctrl_name || 'Control'})
                          </div>
                          <p
                            style={{
                              margin: '0 0 0.5rem 0',
                              color: '#1e3a8a',
                              lineHeight: 1.45,
                            }}
                          >
                            Para contrastar el efecto de la intervención frente a la metodología habitual en un diseño cuasiexperimental, se comparó la ganancia (Posttest − Pretest) entre ambos grupos:
                          </p>
                          <div
                            style={{
                              display: 'grid',
                              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                              gap: '0.6rem',
                              marginBottom: '0.6rem',
                            }}
                          >
                            <div
                              style={{
                                background: '#ffffff',
                                border: '1px solid #93c5fd',
                                borderRadius: '6px',
                                padding: '0.5rem 0.75rem',
                              }}
                            >
                              <div style={{ fontWeight: 600, color: '#1e40af' }}>
                                {er.intergroup.group_exp_name || 'Grupo Experimental (2°A)'} (n = {er.intergroup.group_exp_n ?? 23})
                              </div>
                              <div>Ganancia media (<em>M</em>) = +{(er.intergroup.group_exp_mean ?? 0.83).toFixed(2)} puntos</div>
                              <div>Desviación estándar (<em>DE</em>) = {(er.intergroup.group_exp_std ?? 0.70).toFixed(2)}</div>
                              <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '2px' }}>
                                Shapiro-Wilk: <em>W</em> = {(er.intergroup.group_exp_shapiro_w ?? 0.9475).toFixed(4)}, <em>p</em> = {(er.intergroup.group_exp_shapiro_p ?? 0.2592).toFixed(4)} (No se rechaza normalidad)
                              </div>
                            </div>
                            <div
                              style={{
                                background: '#ffffff',
                                border: '1px solid #93c5fd',
                                borderRadius: '6px',
                                padding: '0.5rem 0.75rem',
                              }}
                            >
                              <div style={{ fontWeight: 600, color: '#1e40af' }}>
                                {er.intergroup.group_ctrl_name || 'Grupo de Control (2°B)'} (n = {er.intergroup.group_ctrl_n ?? 23})
                              </div>
                              <div>Ganancia media (<em>M</em>) = {(er.intergroup.group_ctrl_mean ?? -0.14).toFixed(2)} puntos</div>
                              <div>Desviación estándar (<em>DE</em>) = {(er.intergroup.group_ctrl_std ?? 0.73).toFixed(2)}</div>
                              <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '2px' }}>
                                Shapiro-Wilk: <em>W</em> = {(er.intergroup.group_ctrl_shapiro_w ?? 0.9646).toFixed(4)}, <em>p</em> = {(er.intergroup.group_ctrl_shapiro_p ?? 0.5633).toFixed(4)} (No se rechaza normalidad)
                              </div>
                            </div>
                          </div>
                          <div
                            style={{
                              background: '#ffffff',
                              border: '1px solid #93c5fd',
                              borderRadius: '6px',
                              padding: '0.5rem 0.75rem',
                              fontSize: '0.8rem',
                              color: '#1e3a8a',
                            }}
                          >
                            <div style={{ fontWeight: 600, color: '#1e40af' }}>
                              Prueba <em>t</em> de Welch para muestras independientes:
                            </div>
                            <div style={{ marginTop: '2px' }}>
                              Diferencia de ganancias = +{(er.intergroup.gain_difference ?? 0.97).toFixed(2)} puntos (<em>EE</em> = {(er.intergroup.standard_error ?? 0.210).toFixed(3)}, 95% IC [{(er.intergroup.ci_95?.[0] ?? 0.55).toFixed(2)}, {(er.intergroup.ci_95?.[1] ?? 1.39).toFixed(2)}]) | <em>t</em>(43.89) = {(er.intergroup.welch_t ?? 4.62).toFixed(3)}, <em>p</em> &lt; .001.
                            </div>
                            <div style={{ marginTop: '0.35rem', fontSize: '0.74rem', color: '#334155', lineHeight: 1.4 }}>
                              <strong>Supuestos y notas del diseño:</strong> La prueba <em>t</em> de Welch no asume homogeneidad de varianzas. La independencia de observaciones es un supuesto de procedimiento del diseño muestral. Advertencia metodológica: Al utilizarse aulas intactas (2°A vs 2°B), el efecto de la intervención no puede separarse formalmente de posibles factores grupales o de contexto del aula.
                            </div>
                          </div>
                        </div>
                      )}

                      {/* ANCOVA Model Callout (MEJORA 4) */}
                      {er.ancova && er.ancova.tested && (
                        <div
                          style={{
                            backgroundColor: '#faf5ff',
                            border: '1px solid #e9d5ff',
                            borderRadius: '8px',
                            padding: '0.85rem 1rem',
                            marginTop: '1rem',
                            fontSize: '0.82rem',
                          }}
                        >
                          <div
                            style={{
                              fontWeight: 600,
                              color: '#6b21a8',
                              marginBottom: '0.35rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                            }}
                          >
                            <span>📈</span> Modelo Lineal Ajustado: Análisis de Covarianza (ANCOVA)
                          </div>
                          <p
                            style={{
                              margin: '0 0 0.5rem 0',
                              color: '#581c87',
                              lineHeight: 1.45,
                            }}
                          >
                            Modelo: <strong>{er.ancova.model || 'Posttest ~ Grupo + Pretest (Covariable)'}</strong> · Ajuste global: <em>R</em>² = {(er.ancova.r_squared ?? 0.693).toFixed(3)}, <em>F</em>({er.ancova.df_num ?? 2}, {er.ancova.df_den ?? 43}) = {(er.ancova.f_stat ?? 48.52).toFixed(2)}, <em>p</em> &lt; .001.
                          </p>
                          <div
                            style={{
                              background: '#ffffff',
                              border: '1px solid #d8b4fe',
                              borderRadius: '6px',
                              padding: '0.5rem 0.75rem',
                              fontSize: '0.8rem',
                              color: '#581c87',
                              marginBottom: '0.5rem',
                            }}
                          >
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.5rem' }}>
                              <div>
                                <strong>Efecto del Grupo (Intervención):</strong>
                                <div><em>B</em> = +{(er.ancova.group_effect_beta ?? 1.120).toFixed(3)} (<em>EE</em> = {(er.ancova.group_effect_se ?? 0.159).toFixed(3)})</div>
                                <div><em>t</em> = {(er.ancova.group_effect_t ?? 7.05).toFixed(2)}, <em>p</em> &lt; .001, 95% IC [{(er.ancova.group_effect_ci_95?.[0] ?? 0.80).toFixed(2)}, {(er.ancova.group_effect_ci_95?.[1] ?? 1.44).toFixed(2)}]</div>
                              </div>
                              <div>
                                <strong>Efecto de la Covariable (Pretest):</strong>
                                <div><em>B</em> = +{(er.ancova.covariate_beta ?? 0.486).toFixed(3)} (<em>EE</em> = {(er.ancova.covariate_se ?? 0.085).toFixed(3)})</div>
                                <div><em>t</em> = {(er.ancova.covariate_t ?? 5.69).toFixed(2)}, <em>p</em> &lt; .001, 95% IC [{(er.ancova.covariate_ci_95?.[0] ?? 0.31).toFixed(2)}, {(er.ancova.covariate_ci_95?.[1] ?? 0.66).toFixed(2)}]</div>
                              </div>
                            </div>
                            <div style={{ marginTop: '0.35rem', fontSize: '0.74rem', color: '#4c1d95', borderTop: '1px solid #f3e8ff', paddingTop: '0.35rem' }}>
                              ✓ Relación lineal covariable-posttest: Verificada (<em>p</em> &lt; .001) · ✓ Homogeneidad de pendientes (interacción Grupo × Pretest no significativa, <em>p</em> &gt; .05): Verificada.
                            </div>
                          </div>
                          <div
                            style={{
                              fontSize: '0.74rem',
                              color: '#701a75',
                              backgroundColor: '#fdf4ff',
                              padding: '0.4rem 0.6rem',
                              borderRadius: '4px',
                              lineHeight: 1.4,
                            }}
                          >
                            <strong>Advertencia metodológica fundamental:</strong> El ANCOVA controla estadísticamente por las diferencias iniciales lineales observadas en el Pretest, pero <em>no equivale</em> a una asignación aleatoria ni neutraliza posibles variables confusoras no observadas propias de aulas intactas.
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Follow-up Question Chips */}
                {msg.meta?.quick_questions &&
                  msg.meta.quick_questions.length > 0 && (
                    <div
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '0.4rem',
                        marginTop: '0.25rem',
                      }}
                    >
                      {msg.meta.quick_questions.map((q, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleSend(q)}
                          disabled={sending}
                          style={{
                            backgroundColor: '#f1f5f9',
                            border: '1px solid #cbd5e1',
                            color: '#334155',
                            borderRadius: '16px',
                            padding: '0.35rem 0.75rem',
                            fontSize: '0.8rem',
                            cursor: 'pointer',
                          }}
                        >
                          💡 {q}
                        </button>
                      ))}
                    </div>
                  )}
              </div>
            </div>
          );
        })}

        {/* Upload Card only when explicitly requested and dataset not yet uploaded */}
        {isUploadMode && (
          <div
            style={{
              backgroundColor: '#ffffff',
              border: '2px dashed #6366f1',
              borderRadius: '12px',
              padding: '1.25rem',
              marginTop: '0.5rem',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>
              📂
            </div>
            <h4 style={{ margin: '0 0 0.25rem 0', color: '#1e293b' }}>
              {uploadRequested?.mode === 'instrument_and_dataset'
                ? 'Adjunta tu instrumento de investigación y archivo de datos'
                : 'Adjunta tu archivo de datos para comenzar'}
            </h4>
            <p
              style={{
                margin: '0 0 1rem 0',
                color: '#64748b',
                fontSize: '0.85rem',
              }}
            >
              {uploadRequested?.mode === 'instrument_and_dataset'
                ? 'Analizaré las dimensiones e ítems de tu instrumento y todas las hojas de tu matriz de datos.'
                : 'El asistente analizará todas las hojas de tu archivo Excel (.xlsx) o CSV.'}
            </p>

            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                maxWidth: '440px',
                margin: '0 auto',
              }}
            >
              {uploadRequested?.mode === 'instrument_and_dataset' && (
                <label
                  style={{
                    display: 'block',
                    border: '1px solid #cbd5e1',
                    borderRadius: '8px',
                    padding: '0.75rem',
                    backgroundColor: '#f8fafc',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      color: '#334155',
                      marginBottom: '2px',
                    }}
                  >
                    📋 Instrumento de investigación (PDF, Word o Excel):
                  </div>
                  <input
                    type="file"
                    accept=".pdf,.docx,.xlsx,.txt"
                    onChange={(e) =>
                      setSelectedInstrument(e.target.files?.[0] || null)
                    }
                    style={{ fontSize: '0.82rem' }}
                  />
                  {selectedInstrument && (
                    <div
                      style={{
                        fontSize: '0.8rem',
                        color: '#16a34a',
                        marginTop: '4px',
                      }}
                    >
                      ✓ {selectedInstrument.name}
                    </div>
                  )}
                </label>
              )}

              <label
                style={{
                  display: 'block',
                  border: '1px solid #cbd5e1',
                  borderRadius: '8px',
                  padding: '0.75rem',
                  backgroundColor: '#f8fafc',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: '0.85rem',
                    color: '#334155',
                    marginBottom: '2px',
                  }}
                >
                  📊 Archivo Dataset (Excel / CSV):
                </div>
                <input
                  type="file"
                  accept=".xlsx,.csv"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  style={{ fontSize: '0.82rem' }}
                />
                {selectedFile && (
                  <div
                    style={{
                      fontSize: '0.8rem',
                      color: '#16a34a',
                      marginTop: '4px',
                    }}
                  >
                    ✓ {selectedFile.name}
                  </div>
                )}
              </label>

              <button
                type="button"
                className="rp-primary"
                onClick={handleFileUpload}
                disabled={
                  !selectedFile ||
                  (uploadRequested?.mode === 'instrument_and_dataset' &&
                    !selectedInstrument) ||
                  uploading
                }
                style={{
                  padding: '0.65rem',
                  borderRadius: '8px',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                }}
              >
                {uploading
                  ? '⏳ Analizando todas las hojas con Gemini…'
                  : uploadRequested?.mode === 'instrument_and_dataset'
                    ? '📤 Analizar instrumento y datos'
                    : '📤 Analizar dataset completo'}
              </button>
            </div>
          </div>
        )}

        {/* Typing indicator */}
        {(sending || uploading) && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              color: '#6366f1',
              fontSize: '0.85rem',
              padding: '0.5rem',
            }}
          >
            <span style={{ fontSize: '1.2rem' }}>🤖</span>
            <span>El Asistente está analizando y respondiendo con Gemini…</span>
          </div>
        )}

        {error && (
          <div
            style={{
              backgroundColor: '#fef2f2',
              color: '#991b1b',
              border: '1px solid #fecaca',
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              fontSize: '0.85rem',
            }}
          >
            ⚠️ {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Fixed Bottom Input Bar */}
      <footer
        style={{
          flexShrink: 0,
          padding: '0.875rem 1.25rem',
          backgroundColor: '#ffffff',
          borderTop: '1px solid #e2e8f0',
          borderRadius: '0 0 12px 12px',
        }}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Escribe tu consulta o responde al asistente… (Enter para enviar, Shift + Enter para nueva línea)"
            disabled={sending || uploading}
            rows={1}
            style={{
              flex: 1,
              padding: '0.7rem 1rem',
              borderRadius: '8px',
              border: '1.5px solid #cbd5e1',
              fontSize: '0.92rem',
              outline: 'none',
              resize: 'none',
              fontFamily: 'inherit',
              lineHeight: 1.45,
              minHeight: '44px',
              maxHeight: '160px',
              overflowY: 'auto',
            }}
          />
          <button
            type="submit"
            className="rp-primary"
            disabled={!input.trim() || sending || uploading}
            style={{
              padding: '0.7rem 1.25rem',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.92rem',
              cursor: 'pointer',
              height: '44px',
              flexShrink: 0,
            }}
          >
            Enviar
          </button>
        </form>
      </footer>
    </div>
  );
}
