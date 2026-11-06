import { useState } from 'react';
import { EmptyState } from '../projects/ProjectShell';
import { navigateProject, navigateWorkspace } from '../projects/navigation';
import { createAnalysisApi } from './api';
import { useAnalysisHistory } from './useAnalysisHistory';
import {
  dateLabel,
  recordIsCurrent,
  recordState,
  techniqueName,
} from './analysisPresentation';
const api = createAnalysisApi();

export function ProjectReports({
  projectId,
  item,
  active = true,
}: {
  projectId: string;
  item?: string | null;
  active?: boolean;
}) {
  const history = useAnalysisHistory(projectId, active);
  const [format, setFormat] = useState<'pdf' | 'docx'>('pdf');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [noticeFor, setNoticeFor] = useState('');
  const sources = history.records.filter(
    (record) => record.result?.status === 'completed',
  );
  const selected =
    sources.find((record) => record.plan.id === item) ?? sources[0];
  const allowed =
    !!selected &&
    !history.error &&
    !history.loading &&
    recordIsCurrent(selected, history.status) &&
    selected.result?.status === 'completed' &&
    selected.plan.status === 'approved' &&
    !!selected.approved_at &&
    selected.executable;
  async function download() {
    if (!selected || !allowed || busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.download(projectId, selected, format);
      setNotice('Descarga preparada a partir del resultado guardado.');
      setNoticeFor(`${selected.plan.id}:${selected.invalidated_at}`);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo descargar el informe.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Informes de investigación">
      <div className="rp-section-heading">
        <div>
          <p className="rp-eyebrow">COMPARTE TUS HALLAZGOS</p>
          <h2>Informes</h2>
          <p>Exporta un resultado aprobado en PDF o DOCX.</p>
        </div>
        <button
          className="rp-secondary"
          disabled={history.loading || busy}
          onClick={() => void history.reload()}
        >
          Actualizar informes
        </button>
      </div>
      {history.loading && <p role="status">Consultando exportaciones…</p>}
      {(history.error || error) && (
        <p role="alert" className="rp-error">
          {history.error || error}
        </p>
      )}
      {history.sourceError && (
        <p role="status" className="rp-warning">
          {history.sourceError}
        </p>
      )}
      {notice &&
        noticeFor === `${selected?.plan.id}:${selected?.invalidated_at}` && (
          <p role="status" className="rp-success">
            {notice}
          </p>
        )}
      {!history.loading && !sources.length && !history.error && (
        <EmptyState title="Aún no hay informes disponibles">
          Cuando un análisis aprobado termine, podrás exportarlo aquí. No se
          recalculan estadísticas para descargar.
        </EmptyState>
      )}
      {!!sources.length && (
        <div className="rp-master-detail">
          <nav className="rp-record-list" aria-label="Análisis de origen">
            {sources.map((record) => (
              <button
                key={record.plan.id}
                className="rp-secondary"
                aria-current={
                  selected?.plan.id === record.plan.id ? 'true' : undefined
                }
                disabled={busy}
                onClick={() => {
                  setError('');
                  setNotice('');
                  navigateWorkspace(
                    projectId,
                    'reports',
                    'export',
                    record.plan.id,
                  );
                }}
              >
                <strong>{techniqueName(record)}</strong>
                <small>{dateLabel(record.created_at)}</small>
                <span className="rp-badge">
                  {recordState(record, history.status)}
                </span>
              </button>
            ))}
          </nav>
          {selected && (
            <div className="rp-surface">
              <h3>{techniqueName(selected)}</h3>
              <p>{dateLabel(selected.created_at)}</p>
              <p className="rp-hint">
                El informe se prepara al descargarlo, a partir de este resultado
                guardado.
              </p>
              {!allowed && !history.loading && (
                <p className="rp-warning">
                  {selected.stale_reason ??
                    'La exportación requiere un resultado completado, aprobado y vigente.'}{' '}
                  Las fuentes históricas o sin verificar no permiten exportar.
                </p>
              )}
              {selected.result?.warnings?.map((w) => (
                <p className="rp-warning" key={w}>
                  {w}
                </p>
              ))}
              <label className="rp-field">
                Formato de descarga
                <select
                  value={format}
                  disabled={busy}
                  onChange={(e) => setFormat(e.target.value as 'pdf' | 'docx')}
                >
                  <option value="pdf">PDF</option>
                  <option value="docx">DOCX</option>
                </select>
              </label>
              <button
                disabled={!allowed || busy}
                onClick={() => void download()}
              >
                {busy ? 'Preparando descarga…' : 'Descargar informe'}
              </button>
              <p className="rp-hint">
                Los datos no sintéticos necesitan además autorización local
                vigente. El servidor la verifica al descargar.
              </p>
              <button
                className="rp-link"
                onClick={() =>
                  navigateWorkspace(projectId, 'analysis', 'execution')
                }
              >
                Revisar autorización en Análisis
              </button>
              <details className="rp-technical">
                <summary>Referencias de la exportación</summary>
                <p>Plan: {selected.plan.id}</p>
                <p>Resultado: {selected.result?.id}</p>
              </details>
            </div>
          )}
        </div>
      )}
      {!sources.length && (
        <button
          className="rp-secondary"
          onClick={() => navigateProject(projectId, 'analysis')}
        >
          Ir a Análisis
        </button>
      )}
    </section>
  );
}
