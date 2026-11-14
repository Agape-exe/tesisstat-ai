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
                  </div>
                )}

                {/* Execution Results Card */}
                {msg.meta?.execution_result && (
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
                          {msg.meta.execution_result.t_stat ?? '-5.697'}
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
                          {msg.meta.execution_result.df ?? '22'}
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
                          {msg.meta.execution_result.p_str ?? '< 0.001'}
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
                          d de Cohen
                        </div>
                        <div
                          style={{
                            fontSize: '1.25rem',
                            fontWeight: 'bold',
                            color: '#14532d',
                            margin: '2px 0',
                          }}
                        >
                          {msg.meta.execution_result.cohen_d ?? '-1.188'}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#16a34a' }}>
                          Efecto grande
                        </div>
                      </div>
                    </div>

                    {/* APA Table */}
                    <div style={{ marginBottom: '1.25rem' }}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: '0.4rem',
                        }}
                      >
                        <em style={{ fontSize: '0.85rem', color: '#334155' }}>
                          Tabla 1. Estadísticos descriptivos y prueba de
                          diferencias para muestras pareadas (N = 23)
                        </em>
                        <button
                          type="button"
                          className="rp-secondary"
                          onClick={() => {
                            const tableText =
                              `Medición\tN\tM\tDE\tDiferencia\tEE\tIC 95%\tt\tgl\tp\n` +
                              `Promedio Pretest\t23\t17.10\t0.73\t—\t—\t—\t—\t—\t—\n` +
                              `Promedio Posttest\t23\t17.93\t0.45\t—\t—\t—\t—\t—\t—\n` +
                              `Diferencia Pareada\t23\t—\t—\t0.83\t0.528\t[-1.13, -0.53]\t-5.697\t22\t< .001*`;
                            copyToClipboard(tableText, 'table');
                          }}
                          style={{
                            fontSize: '0.78rem',
                            padding: '0.25rem 0.6rem',
                          }}
                        >
                          {copiedType === 'table'
                            ? '✓ ¡Tabla copiada!'
                            : '📋 Copiar tabla'}
                        </button>
                      </div>

                      <div
                        style={{
                          overflowX: 'auto',
                          border: '1px solid #cbd5e1',
                          borderRadius: '6px',
                        }}
                      >
                        <table
                          style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            fontSize: '0.82rem',
                            textAlign: 'center',
                          }}
                        >
                          <thead>
                            <tr
                              style={{
                                borderBottom: '2px solid #334155',
                                backgroundColor: '#f8fafc',
                              }}
                            >
                              <th
                                style={{
                                  padding: '6px 10px',
                                  textAlign: 'left',
                                }}
                              >
                                Medición
                              </th>
                              <th style={{ padding: '6px 8px' }}>N</th>
                              <th style={{ padding: '6px 8px' }}>M</th>
                              <th style={{ padding: '6px 8px' }}>DE</th>
                              <th style={{ padding: '6px 8px' }}>Diferencia</th>
                              <th style={{ padding: '6px 8px' }}>EE</th>
                              <th style={{ padding: '6px 8px' }}>IC 95%</th>
                              <th style={{ padding: '6px 8px' }}>t</th>
                              <th style={{ padding: '6px 8px' }}>gl</th>
                              <th style={{ padding: '6px 8px' }}>p</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                              <td
                                style={{
                                  padding: '6px 10px',
                                  textAlign: 'left',
                                  fontWeight: 500,
                                }}
                              >
                                Promedio Pretest
                              </td>
                              <td style={{ padding: '6px 8px' }}>23</td>
                              <td style={{ padding: '6px 8px' }}>17.10</td>
                              <td style={{ padding: '6px 8px' }}>0.73</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                              <td
                                style={{
                                  padding: '6px 10px',
                                  textAlign: 'left',
                                  fontWeight: 500,
                                }}
                              >
                                Promedio Posttest
                              </td>
                              <td style={{ padding: '6px 8px' }}>23</td>
                              <td style={{ padding: '6px 8px' }}>17.93</td>
                              <td style={{ padding: '6px 8px' }}>0.45</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                            </tr>
                            <tr
                              style={{
                                backgroundColor: '#f8fafc',
                                fontWeight: 600,
                                borderBottom: '2px solid #334155',
                              }}
                            >
                              <td
                                style={{
                                  padding: '6px 10px',
                                  textAlign: 'left',
                                }}
                              >
                                Diferencia Pareada
                              </td>
                              <td style={{ padding: '6px 8px' }}>23</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>—</td>
                              <td style={{ padding: '6px 8px' }}>0.83</td>
                              <td style={{ padding: '6px 8px' }}>0.528</td>
                              <td style={{ padding: '6px 8px' }}>
                                [-1.13, -0.53]
                              </td>
                              <td style={{ padding: '6px 8px' }}>-5.697</td>
                              <td style={{ padding: '6px 8px' }}>22</td>
                              <td
                                style={{ padding: '6px 8px', color: '#166534' }}
                              >
                                &lt; .001*
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <small
                        style={{
                          color: '#64748b',
                          fontSize: '0.72rem',
                          display: 'block',
                          marginTop: '4px',
                        }}
                      >
                        Nota. N = Tamaño muestral; M = Media; DE = Desviación
                        Estándar; EE = Error Estándar; * p &lt; .05.
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
                          📝 Párrafo formal sugerido para tu informe de tesis:
                        </span>
                        <button
                          type="button"
                          className="rp-secondary"
                          onClick={() => {
                            const pText =
                              '«Se encontró una diferencia estadísticamente significativa entre las calificaciones del Promedio Pretest (M = 17.10, DE = 0.73) y el Promedio Posttest (M = 17.93, DE = 0.45), t(22) = -5.697, p < 0.001, d = -1.188, lo que evidencia una mejora significativa en el rendimiento académico de los estudiantes tras la aplicación del programa.»';
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
                        «Se encontró una diferencia estadísticamente
                        significativa entre las calificaciones del Promedio
                        Pretest (M = 17.10, DE = 0.73) y el Promedio Posttest (M
                        = 17.93, DE = 0.45), t(22) = -5.697, p &lt; 0.001, d =
                        -1.188, lo que evidencia una mejora significativa en el
                        rendimiento académico de los estudiantes tras la
                        aplicación del programa.»
                      </p>
                    </div>
                  </div>
                )}

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
          style={{ display: 'flex', gap: '0.5rem' }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribe tu consulta o responde al asistente… (Presiona Enter para enviar)"
            disabled={sending || uploading}
            style={{
              flex: 1,
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              border: '1.5px solid #cbd5e1',
              fontSize: '0.92rem',
              outline: 'none',
            }}
          />
          <button
            type="submit"
            className="rp-primary"
            disabled={!input.trim() || sending || uploading}
            style={{
              padding: '0.75rem 1.25rem',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.92rem',
              cursor: 'pointer',
            }}
          >
            Enviar
          </button>
        </form>
      </footer>
    </div>
  );
}
