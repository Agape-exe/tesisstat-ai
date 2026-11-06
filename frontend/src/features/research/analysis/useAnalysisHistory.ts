import { useCallback } from 'react';
import { createAnalysisApi } from './api';
import { createPackageApi } from '../packages/api';
import { useReadResource } from '../projects/useReadResource';
const api = createAnalysisApi();
const packages = createPackageApi();
export function useAnalysisHistory(projectId: string, active = true) {
  const load = useCallback(async () => {
    const [history, sources] = await Promise.allSettled([
      api.results(projectId),
      packages.status(projectId),
    ]);
    return {
      records:
        history.status === 'fulfilled'
          ? [...history.value].filter((r) => r.result).reverse()
          : [],
      error:
        history.status === 'rejected'
          ? history.reason instanceof Error
            ? history.reason.message
            : 'No se pudo recuperar el historial.'
          : '',
      status: sources.status === 'fulfilled' ? sources.value : null,
      sourceError:
        sources.status === 'rejected'
          ? 'No se pudo verificar la vigencia de las fuentes. Puedes leer el historial; las exportaciones y los gráficos autorizados quedan bloqueados.'
          : '',
    };
  }, [projectId]);
  const resource = useReadResource(load, active);
  return {
    records: resource.data?.records ?? [],
    status: resource.data?.status ?? null,
    error: resource.error || resource.data?.error || '',
    sourceError: resource.data?.sourceError ?? '',
    loading: resource.loading,
    reload: resource.reload,
  };
}
