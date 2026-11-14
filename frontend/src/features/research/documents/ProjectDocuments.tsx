import { useEffect, useRef, useState } from 'react';
import { createDocumentApi } from './api';
import type { DocumentApi, ExtractionResult, ResearchDocument } from './api';
import {
  Guidance,
  SectionColumns,
  SupportPanel,
} from '../projects/SectionLayout';
import { UiIcon } from '../projects/UiIcon';
import { navigateWorkspace } from '../projects/navigation';

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
  const [selected, setSelected] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [extractionLoading, setExtractionLoading] = useState(false);
  const [extractionBusy, setExtractionBusy] = useState(false);
  const [extractionError, setExtractionError] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const extractionRequest = useRef(0);
  const [knownExtractions, setKnownExtractions] = useState<
    Record<string, ExtractionResult | null>
  >({});

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
      if (selected === document.id) {
        extractionRequest.current += 1;
        setSelected(null);
        setExtraction(null);
      }
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

  async function select(documentId: string) {
    const request = ++extractionRequest.current;
    setExtractionBusy(false);
    if (selected === documentId) {
      setSelected(null);
      return;
    }
    setSelected(documentId);
    setExtraction(null);
    setExtractionError('');
    setExtractionLoading(true);
    try {
      const next = await api.extraction(projectId, documentId);
      if (request !== extractionRequest.current) return;
      setExtraction(next);
      setKnownExtractions((items) => ({ ...items, [documentId]: next }));
    } catch (caught) {
      if (request !== extractionRequest.current) return;
      setExtractionError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo consultar la extracción.',
      );
    } finally {
      if (request === extractionRequest.current) setExtractionLoading(false);
    }
  }

  async function extract(documentId: string) {
    const request = ++extractionRequest.current;
    setExtractionBusy(true);
    setExtractionError('');
    try {
      const next = await api.extract(projectId, documentId);
      if (request !== extractionRequest.current) return;
      setExtraction(next);
      setKnownExtractions((items) => ({ ...items, [documentId]: next }));
    } catch (caught) {
      if (request !== extractionRequest.current) return;
      setExtractionError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo extraer el texto.',
      );
    } finally {
      if (request === extractionRequest.current) setExtractionBusy(false);
    }
  }

  return (
    <section
      className="rp-documents"
      aria-label="Documentos de investigación"
      aria-busy={loading || busy}
    >
      <div className="rp-section-heading">
        <h2>Documentos de la investigación</h2>
        <button onClick={() => input.current?.click()}>
          <UiIcon name="plus" /> Añadir documento
        </button>
      </div>
      <SectionColumns
        support={
          <SupportPanel
            title="Del documento a la metodología"
            projectId={projectId}
            destination="methodology"
            action="Ir a Metodología"
          >
            <Guidance
              items={[
                'Seleccionar archivo PDF/DOCX',
                'Extraer contenido con el backend',
                'Revisar objetivos e hipótesis',
                'Confirmar información',
              ]}
            />
          </SupportPanel>
        }
      >
        <div className="rp-surface rp-document-surface">
          <div className="rp-section-heading">
            <h3>Archivos del proyecto</h3>
            <span className="rp-badge">
              {documents.length}{' '}
              {documents.length === 1 ? 'archivo' : 'archivos'}
            </span>
          </div>
          <p className="rp-hint">
            Adjunta PDF o DOCX de hasta 10 MB. Usa solo archivos ficticios en
            esta demo.
          </p>
          <div className="rp-upload-zone">
            <UiIcon name="upload" />
            <label className="rp-file-picker" htmlFor="research-document">
              {file?.name || 'Selecciona un PDF o DOCX'}
            </label>
            <div className="rp-documents-upload">
              <input
                ref={input}
                id="research-document"
                aria-label="Archivo"
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
                  <span className="rp-file-symbol">
                    <UiIcon name="file" />
                  </span>
                  <div className="rp-file-copy">
                    <strong>{document.name}</strong>
                    <small>
                      {document.format.toUpperCase()} ·{' '}
                      {(document.size / 1024).toFixed(1)} KB ·{' '}
                      {new Date(document.uploaded_at).toLocaleString('es-PE')}
                    </small>
                    <small>
                      Extracción:{' '}
                      {document.id in knownExtractions
                        ? knownExtractions[document.id]?.status === 'completed'
                          ? 'Completada'
                          : knownExtractions[document.id]?.status === 'failed'
                            ? 'Fallida'
                            : knownExtractions[document.id]?.status ===
                                'no_text'
                              ? 'Sin texto legible'
                              : 'Sin extracción guardada'
                        : 'Por consultar'}
                    </small>
                  </div>
                  <button
                    className="rp-secondary"
                    disabled={busy}
                    onClick={() => void select(document.id)}
                  >
                    {selected === document.id
                      ? 'Ocultar texto'
                      : 'Ver extracción'}
                  </button>
                  <button
                    className="rp-delete"
                    disabled={busy}
                    onClick={() => void remove(document)}
                    aria-label={`Eliminar documento ${document.name}`}
                  >
                    Eliminar
                  </button>
                  {selected === document.id && (
                    <div
                      className="rp-extraction"
                      aria-busy={extractionLoading || extractionBusy}
                    >
                      {extractionLoading ? (
                        <p role="status">Consultando extracción…</p>
                      ) : (
                        <>
                          <button
                            disabled={extractionBusy}
                            onClick={() => void extract(document.id)}
                          >
                            {extractionBusy
                              ? 'Extrayendo texto…'
                              : extraction?.status === 'failed'
                                ? 'Reintentar extracción'
                                : 'Extraer texto'}
                          </button>
                          {extractionError && (
                            <p role="alert" className="rp-error">
                              {extractionError}
                            </p>
                          )}
                          {extraction && (
                            <div>
                              <p role="status">
                                Estado:{' '}
                                {extraction.status === 'completed'
                                  ? 'Completado'
                                  : extraction.status === 'no_text'
                                    ? 'Sin texto extraíble'
                                    : 'Fallido'}
                              </p>
                              <small>
                                {extraction.character_count} caracteres ·{' '}
                                {extraction.units_processed}{' '}
                                {document.format === 'pdf'
                                  ? 'páginas'
                                  : 'unidades'}{' '}
                                ·{' '}
                                {new Date(
                                  extraction.processed_at,
                                ).toLocaleString('es-PE')}
                                {extraction.truncated ? ' · Truncado' : ''}
                              </small>
                              {extraction.warnings.map((warning) => (
                                <p role="alert" key={warning}>
                                  {warning}
                                </p>
                              ))}
                              {extraction.text && (
                                <pre className="rp-text-preview">
                                  {extraction.text}
                                </pre>
                              )}
                            </div>
                          )}
                        </>
                      )}
                      <button
                        className="rp-secondary"
                        onClick={() =>
                          navigateWorkspace(
                            projectId,
                            'methodology',
                            'summary',
                            document.id,
                          )
                        }
                      >
                        Revisar metodología
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </SectionColumns>
      <p className="rp-section-notice">
        La presencia de un archivo no implica que su metodología se haya
        extraído o validado. Consulta la extracción y confirma la información
        antes de utilizarla.
      </p>
    </section>
  );
}
