import { useState } from 'react';

export interface KeyMetricItem {
  symbol: string;
  label: string;
  value: string | number;
  sublabel?: string;
  highlight?: boolean;
}

export interface APATableData {
  title: string;
  columns: string[];
  rows: (string | number)[][];
  note: string;
}

export interface BoxplotStats {
  label: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  mean: number;
}

export interface ChatResultData {
  resultId: string;
  title: string;
  technique: string;
  techniqueBadge: string;
  keyMetrics: KeyMetricItem[];
  apaTable: APATableData;
  boxplots?: BoxplotStats[];
  pedagogicalExplanation: {
    decision: string;
    decisionDetail: string;
    thesisParagraph: string;
  };
  followupPrompt: string;
  suggestedQuestions: {
    chip: string;
    question: string;
    answer: string;
  }[];
}

export interface ChatResultViewProps {
  data: ChatResultData;
  onFollowupQuery: (question: string, answer: string) => void;
  onDownload: (format: 'docx' | 'pdf') => void;
  onStartNewAnalysis: () => void;
  isDownloading?: boolean;
}

export function ChatResultView({
  data,
  onFollowupQuery,
  onDownload,
  onStartNewAnalysis,
  isDownloading = false,
}: ChatResultViewProps) {
  const [copiedParagraph, setCopiedParagraph] = useState(false);
  const [copiedTable, setCopiedTable] = useState(false);

  const copyParagraphToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(
        data.pedagogicalExplanation.thesisParagraph,
      );
      setCopiedParagraph(true);
      setTimeout(() => setCopiedParagraph(false), 2500);
    } catch {
      // Fallback
    }
  };

  const copyTableToClipboard = async () => {
    try {
      const headerRow = data.apaTable.columns.join('\t');
      const bodyRows = data.apaTable.rows
        .map((row) => row.join('\t'))
        .join('\n');
      const fullText = `${data.apaTable.title}\n${headerRow}\n${bodyRows}\n${data.apaTable.note}`;
      await navigator.clipboard.writeText(fullText);
      setCopiedTable(true);
      setTimeout(() => setCopiedTable(false), 2500);
    } catch {
      // Fallback
    }
  };

  return (
    <div
      className="tutor-chat-result-card"
      role="region"
      aria-label="Resultados del análisis estadístico"
    >
      {/* 1. Encabezado de Resultados */}
      <div className="tutor-result-header">
        <span className="tutor-result-badge">
          ✓ {data.techniqueBadge || 'Análisis determinista completado'}
        </span>
        <h3 className="tutor-result-title">{data.title}</h3>
      </div>

      {/* 2. Métricas Clave */}
      <div className="tutor-metrics-section">
        <h4 className="tutor-section-subtitle">Métricas Clave del Contraste</h4>
        <div
          className="tutor-metrics-grid"
          role="group"
          aria-label="Métricas clave"
        >
          {data.keyMetrics.map((metric) => (
            <div
              key={metric.label}
              className={`tutor-metric-box ${metric.highlight ? 'tutor-metric-highlight' : ''}`}
            >
              <span className="tutor-metric-sym">{metric.symbol}</span>
              <span className="tutor-metric-val">{metric.value}</span>
              <span className="tutor-metric-lbl">{metric.label}</span>
              {metric.sublabel && (
                <span className="tutor-metric-sub">{metric.sublabel}</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 3. Tabla en Formato APA */}
      <div className="tutor-apa-section">
        <div className="tutor-section-header-actions">
          <h4 className="tutor-section-subtitle">
            Tabla en Formato APA (7.ª ed.)
          </h4>
          <button
            type="button"
            className="rp-secondary tutor-copy-btn"
            onClick={() => void copyTableToClipboard()}
            aria-label="Copiar tabla en formato APA"
          >
            {copiedTable ? '✓ Copiada' : '📋 Copiar tabla'}
          </button>
        </div>
        <p className="tutor-apa-caption">
          <em>{data.apaTable.title}</em>
        </p>
        <div className="tutor-apa-table-wrapper">
          <table className="tutor-apa-table">
            <thead>
              <tr>
                {data.apaTable.columns.map((col, idx) => (
                  <th key={idx}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.apaTable.rows.map((row, rowIdx) => (
                <tr key={rowIdx}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="tutor-apa-note">
          <small>{data.apaTable.note}</small>
        </p>
      </div>

      {/* 4. Gráfico Interactivo Integrado */}
      {data.boxplots && data.boxplots.length > 0 && (
        <div className="tutor-figure-section">
          <h4 className="tutor-section-subtitle">
            Distribución Comparativa (Diagrama de Cajas y Bigotes)
          </h4>
          <figure
            className="tutor-boxplot-figure"
            aria-label="Diagrama de cajas y bigotes interactivo"
          >
            <InteractiveBoxplotPlot boxplots={data.boxplots} />
            <figcaption className="tutor-figure-caption">
              <em>Figura 1</em>. Comparación de distribuciones entre mediciones
              (mediana, rango intercuartílico $Q_1-Q_3$, extremos y media).
            </figcaption>
          </figure>
        </div>
      )}

      {/* 5. Explicación Pedagógica y Párrafo Formal */}
      <div className="tutor-explanation-section">
        <h4 className="tutor-section-subtitle">
          Interpretación Pedagógica y Redacción para Tesis
        </h4>
        <div className="tutor-decision-box">
          <div className="tutor-decision-badge">
            Decisión Estadística:{' '}
            <strong>{data.pedagogicalExplanation.decision}</strong>
          </div>
          <p className="tutor-decision-detail">
            {data.pedagogicalExplanation.decisionDetail}
          </p>
        </div>

        <div className="tutor-thesis-box">
          <div className="tutor-thesis-header">
            <span>📝 Párrafo formal sugerido para el informe de tesis:</span>
            <button
              type="button"
              className="rp-primary tutor-copy-paragraph-btn"
              onClick={() => void copyParagraphToClipboard()}
              aria-label="Copiar párrafo formal para tesis"
            >
              {copiedParagraph ? '✓ ¡Párrafo copiado!' : '📋 Copiar párrafo'}
            </button>
          </div>
          <blockquote className="tutor-thesis-quote">
            «{data.pedagogicalExplanation.thesisParagraph}»
          </blockquote>
          <small className="tutor-thesis-tip">
            Listo para pegar directamente en tu capítulo de Resultados bajo
            normas APA (7.ª edición).
          </small>
        </div>
      </div>

      {/* 6. Consultas de Seguimiento Interactivas */}
      <div className="tutor-followup-section">
        <h4 className="tutor-followup-title">
          {data.followupPrompt ||
            '¿Tienes alguna duda sobre estos resultados o cómo interpretarlos en tu tesis?'}
        </h4>
        <div
          className="tutor-followup-chips"
          role="group"
          aria-label="Preguntas de seguimiento sugeridas"
        >
          {data.suggestedQuestions.map((q) => (
            <button
              key={q.chip}
              type="button"
              className="tutor-chip-btn"
              onClick={() => onFollowupQuery(q.question, q.answer)}
            >
              {q.chip}
            </button>
          ))}
        </div>
      </div>

      {/* 7. Acciones de Cierre: Descarga y Nuevo Análisis */}
      <div className="tutor-closing-actions">
        <button
          type="button"
          className="rp-primary tutor-closing-btn"
          disabled={isDownloading}
          onClick={() => onDownload('docx')}
        >
          📄 Descargar Informe en Word (.docx)
        </button>
        <button
          type="button"
          className="rp-secondary tutor-closing-btn"
          disabled={isDownloading}
          onClick={() => onDownload('pdf')}
        >
          📥 Descargar Informe en PDF
        </button>
        <button
          type="button"
          className="rp-secondary tutor-closing-btn"
          onClick={onStartNewAnalysis}
        >
          🔄 Iniciar nuevo análisis
        </button>
      </div>
    </div>
  );
}

function InteractiveBoxplotPlot({ boxplots }: { boxplots: BoxplotStats[] }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const allValues = boxplots.flatMap((b) => [b.min, b.max, b.mean]);
  const minValue = Math.min(...allValues, 0);
  const maxValue = Math.max(...allValues, 20);
  const range = maxValue - minValue || 1;

  const width = 420;
  const height = 240;
  const paddingTop = 25;
  const paddingBottom = 45;
  const paddingLeft = 45;
  const plotHeight = height - paddingTop - paddingBottom;
  const plotWidth = width - paddingLeft - 20;

  const getY = (val: number) => {
    const fraction = (val - minValue) / range;
    return height - paddingBottom - fraction * plotHeight;
  };

  const ticks = [0, 5, 10, 15, 20].filter(
    (v) => v >= minValue && v <= maxValue,
  );
  if (!ticks.includes(minValue)) ticks.unshift(Math.floor(minValue));
  if (!ticks.includes(maxValue)) ticks.push(Math.ceil(maxValue));
  const uniqueTicks = Array.from(new Set(ticks)).sort((a, b) => a - b);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="tutor-boxplot-svg"
      role="img"
      aria-label={`Diagrama de cajas y bigotes para ${boxplots.map((b) => b.label).join(' y ')}`}
    >
      {/* Grid lines */}
      {uniqueTicks.map((tick) => {
        const y = getY(tick);
        return (
          <g key={tick} className="tutor-grid-line">
            <line
              x1={paddingLeft}
              y1={y}
              x2={width - 20}
              y2={y}
              stroke="#e2e8f0"
              strokeDasharray="3 3"
            />
            <text
              x={paddingLeft - 8}
              y={y + 4}
              fontSize="11"
              fill="#64748b"
              textAnchor="end"
            >
              {tick}
            </text>
          </g>
        );
      })}

      {/* Axis lines */}
      <line
        x1={paddingLeft}
        y1={paddingTop}
        x2={paddingLeft}
        y2={height - paddingBottom}
        stroke="#94a3b8"
        strokeWidth="1.5"
      />
      <line
        x1={paddingLeft}
        y1={height - paddingBottom}
        x2={width - 20}
        y2={height - paddingBottom}
        stroke="#94a3b8"
        strokeWidth="1.5"
      />

      {/* Boxplots */}
      {boxplots.map((b, idx) => {
        const count = boxplots.length;
        const boxWidth = Math.min(70, plotWidth / (count * 1.8));
        const centerX = paddingLeft + ((idx + 0.5) / count) * plotWidth;

        const yMin = getY(b.min);
        const yQ1 = getY(b.q1);
        const yMed = getY(b.median);
        const yQ3 = getY(b.q3);
        const yMax = getY(b.max);
        const yMean = getY(b.mean);

        const isHovered = hoveredIndex === idx;

        return (
          <g
            key={b.label}
            className="tutor-box-group"
            onMouseEnter={() => setHoveredIndex(idx)}
            onMouseLeave={() => setHoveredIndex(null)}
            tabIndex={0}
            role="graphics-symbol"
            aria-label={`${b.label}: Mdn=${b.median}, Media=${b.mean}, Q1=${b.q1}, Q3=${b.q3}, Mín=${b.min}, Máx=${b.max}`}
          >
            {/* Whiskers */}
            <line
              x1={centerX}
              y1={yMin}
              x2={centerX}
              y2={yQ1}
              stroke="#334155"
              strokeWidth="1.5"
            />
            <line
              x1={centerX}
              y1={yQ3}
              x2={centerX}
              y2={yMax}
              stroke="#334155"
              strokeWidth="1.5"
            />
            {/* Whisker caps */}
            <line
              x1={centerX - boxWidth / 4}
              y1={yMin}
              x2={centerX + boxWidth / 4}
              y2={yMin}
              stroke="#334155"
              strokeWidth="1.5"
            />
            <line
              x1={centerX - boxWidth / 4}
              y1={yMax}
              x2={centerX + boxWidth / 4}
              y2={yMax}
              stroke="#334155"
              strokeWidth="1.5"
            />

            {/* Box Q1-Q3 */}
            <rect
              x={centerX - boxWidth / 2}
              y={yQ3}
              width={boxWidth}
              height={Math.max(2, yQ1 - yQ3)}
              fill={
                idx === 0
                  ? isHovered
                    ? '#bfdbfe'
                    : '#dbeafe'
                  : isHovered
                    ? '#bbf7d0'
                    : '#dcfce7'
              }
              stroke={idx === 0 ? '#1d4ed8' : '#15803d'}
              strokeWidth="2"
              rx="3"
            />

            {/* Median line */}
            <line
              x1={centerX - boxWidth / 2}
              y1={yMed}
              x2={centerX + boxWidth / 2}
              y2={yMed}
              stroke="#0f172a"
              strokeWidth="3"
            />

            {/* Mean marker: Diamond */}
            <polygon
              points={`${centerX},${yMean - 5} ${centerX + 5},${yMean} ${centerX},${yMean + 5} ${centerX - 5},${yMean}`}
              fill="#dc2626"
              stroke="#7f1d1d"
              strokeWidth="1"
            />

            {/* X-axis label */}
            <text
              x={centerX}
              y={height - paddingBottom + 18}
              fontSize="12"
              fontWeight="600"
              fill="#1e293b"
              textAnchor="middle"
            >
              {b.label}
            </text>

            <text
              x={centerX}
              y={height - paddingBottom + 32}
              fontSize="10"
              fill="#64748b"
              textAnchor="middle"
            >
              M = {b.mean.toFixed(2)}
            </text>

            {/* Value annotations when hovered or focused */}
            {isHovered && (
              <g className="tutor-box-tooltip">
                <rect
                  x={centerX - 55}
                  y={Math.max(5, yMax - 40)}
                  width="110"
                  height="34"
                  rx="4"
                  fill="#1e293b"
                  opacity="0.92"
                />
                <text
                  x={centerX}
                  y={Math.max(5, yMax - 40) + 14}
                  fill="#ffffff"
                  fontSize="9.5"
                  textAnchor="middle"
                >
                  Mdn={b.median.toFixed(2)} · M={b.mean.toFixed(2)}
                </text>
                <text
                  x={centerX}
                  y={Math.max(5, yMax - 40) + 27}
                  fill="#94a3b8"
                  fontSize="9"
                  textAnchor="middle"
                >
                  [{b.min} - {b.max}] Q1={b.q1} Q3={b.q3}
                </text>
              </g>
            )}
          </g>
        );
      })}

      {/* Legend at top right */}
      <g
        className="tutor-boxplot-legend"
        transform={`translate(${width - 170}, 8)`}
      >
        <line x1="0" y1="6" x2="16" y2="6" stroke="#0f172a" strokeWidth="2.5" />
        <text x="20" y="9" fontSize="9" fill="#475569">
          Mediana
        </text>
        <polygon
          points="70,2 74,6 70,10 66,6"
          fill="#dc2626"
          stroke="#7f1d1d"
        />
        <text x="78" y="9" fontSize="9" fill="#475569">
          Media
        </text>
      </g>
    </svg>
  );
}
