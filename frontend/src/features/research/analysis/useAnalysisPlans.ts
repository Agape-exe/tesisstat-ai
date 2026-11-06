import { useCallback, useEffect, useRef, useState } from 'react';
import { createAnalysisApi } from './api';
import { useReadResource } from '../projects/useReadResource';
const api = createAnalysisApi();
export function useAnalysisPlans(projectId: string, packageId?: string) {
  const load = useCallback(
    async () => [...(await api.plans(projectId))].reverse(),
    [projectId],
  );
  const resource = useReadResource(load, true, packageId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const ready = !resource.loading && !resource.error;
  async function work(action: () => Promise<unknown>, onRejected?: () => void) {
    if (lock.current || !ready) return false;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      await action();
      if (!alive.current) return false;
      resource.reload();
      return true;
    } catch (cause) {
      if (!alive.current) return false;
      onRejected?.();
      resource.reload();
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo completar la operación.',
      );
      return false;
    } finally {
      lock.current = false;
      if (alive.current) setBusy(false);
    }
  }
  return {
    records: resource.data ?? [],
    ready,
    busy,
    error: error || resource.error,
    work,
    reload: () => {
      setError('');
      resource.reload();
    },
  };
}
