import { useCallback } from 'react';
import { createPackageApi } from './api';
import { useReadResource } from '../projects/useReadResource';
const api = createPackageApi();
export function useResearchPackage(projectId: string, active = true) {
  const load = useCallback(async () => {
    const status = await api.status(projectId);
    if (!status?.configuration || !Array.isArray(status.errors))
      throw new Error(
        'No se pudo verificar el estado de preparación recibido.',
      );
    const current =
      status.state === 'generated' && status.package_id
        ? await api.get(projectId)
        : null;
    return { status, current };
  }, [projectId]);
  const resource = useReadResource(load, active);
  return {
    status: resource.data?.status ?? null,
    current: resource.data?.current ?? null,
    loading: resource.loading,
    error: resource.error,
    reload: resource.reload,
  };
}
