import { useEffect, useRef, useState } from 'react';
import { createDocumentApi } from './api';
import type { DocumentApi, ResearchDocument } from './api';

const defaultApi = createDocumentApi();
const MAX_BYTES = 10 * 1024 * 1024;

export function ProjectDocuments({
  projectId,
  api = defaultApi,
}: {
  projectId: string;
  api?: DocumentApi;
}) {
  const [documents, setDocuments] = useState<ResearchDocument[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [retry, setRetry] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .list(projectId, controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) {
          setDocuments(items);
          setError('');
          setLoading(false);
        }
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setError(
            caught instanceof Error
              ? caught.message
              : 'No se pudieron cargar los documentos.',
          );
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [api, projectId, retry]);

  function choose(chosen: File | null) {
    setFile(chosen);
    setError('');
    setNotice('');
    if (chosen && !/\.(pdf|docx)$/i.test(chosen.name))
      setError('Adjunta un archivo PDF o DOCX.');
    else if (chosen && chosen.size === 0) setError('El archivo está vacío.');
    else if (chosen && chosen.size > MAX_BYTES)
      setError('El archivo supera el límite de 10 MB.');
  }

  async function upload() {
    if (!file || busy) return;
    if (
      !/\.(pdf|docx)$/i.test(file.name) ||
      file.size === 0 ||
      file.size > MAX_BYTES
    ) {
      choose(file);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const document = await api.upload(projectId, file);
      setDocuments((items) => [document, ...items]);
      setFile(null);
      if (input.current) input.current.value = '';
      setNotice('Documento adjuntado.');
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo adjuntar el documento.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(document: ResearchDocument) {
    if (
      busy ||
      !window.confirm(
        `¿Eliminar «${document.name}»? Esta acción no se puede deshacer.`,
      )
    )
      return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.delete(projectId, document.id);
      setDocuments((items) => items.filter((item) => item.id !== document.id));
      setNotice('Documento eliminado.');
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo eliminar el documento.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="rp-documents"
      aria-label="Documentos de investigación"
      aria-busy={loading || busy}
    >
      <h3>Documentos</h3>
      <p className="rp-hint">
        Adjunta PDF o DOCX de hasta 10 MB. Usa solo archivos ficticios en esta
        demo.
      </p>
      <label htmlFor="research-document">Archivo</label>
      <div className="rp-documents-upload">
        <input
          ref={input}
          id="research-document"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          disabled={busy}
          onChange={(event) => choose(event.target.files?.[0] ?? null)}
        />
        <button
          disabled={!file || busy || !!error}
          onClick={() => void upload()}
        >
          {busy ? 'Procesando…' : 'Adjuntar documento'}
        </button>
      </div>
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rp-success">
          {notice}
        </p>
      )}
      {loading ? (
        <p role="status">Cargando documentos…</p>
      ) : error && documents.length === 0 ? (
        <button
          className="rp-secondary"
          onClick={() => {
            setLoading(true);
            setRetry((value) => value + 1);
          }}
        >
          Reintentar listado
        </button>
      ) : documents.length === 0 ? (
        <p>Aún no hay documentos en esta investigación.</p>
      ) : (
        <ul className="rp-documents-list">
          {documents.map((document) => (
            <li key={document.id}>
              <div>
                <strong>{document.name}</strong>
                <small>
                  {document.format.toUpperCase()} ·{' '}
                  {(document.size / 1024).toFixed(1)} KB ·{' '}
                  {new Date(document.uploaded_at).toLocaleString('es-PE')}
                </small>
              </div>
              <button
                className="rp-delete"
                disabled={busy}
                onClick={() => void remove(document)}
                aria-label={`Eliminar documento ${document.name}`}
              >
                Eliminar
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
