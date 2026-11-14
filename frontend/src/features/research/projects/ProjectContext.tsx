import { useCallback } from 'react';
import { createContextApi } from '../context/api';
import { ContextEditor } from '../context/ContextEditor';
import { useReadResource } from './useReadResource';
const api = createContextApi();
export function ProjectContext({
  projectId,
  title,
}: {
  projectId: string;
  title: string;
}) {
  const load = useCallback(() => api.get(projectId), [projectId]);
  const resource = useReadResource(load);
  if (resource.loading) return <p role="status">Cargando contexto…</p>;
  if (resource.error || !resource.data)
    return (
      <div role="alert">
        <p>{resource.error || 'No se pudo cargar el contexto.'}</p>
        <button onClick={resource.reload}>Reintentar</button>
      </div>
    );
  return (
    <ContextEditor
      key={projectId}
      projectId={projectId}
      title={title}
      initial={resource.data}
    />
  );
}
