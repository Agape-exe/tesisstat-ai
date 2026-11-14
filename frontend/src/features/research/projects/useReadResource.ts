import { useCallback, useEffect, useMemo, useState } from 'react';

// A read is keyed by its inputs and activation. Late responses cannot replace
// another section/project's data; loading is derived during render.
export function useReadResource<T>(
  load: () => Promise<T>,
  active = true,
  scope = '',
) {
  const [attempt, setAttempt] = useState(0);
  const key = useMemo(
    () => ({ load, active, attempt, scope }),
    [load, active, attempt, scope],
  );
  const [state, setState] = useState<{
    key: typeof key;
    data: T | null;
    error: string;
  } | null>(null);
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    load()
      .then((data) => {
        if (!cancelled) setState({ key, data, error: '' });
      })
      .catch((cause) => {
        if (!cancelled)
          setState({
            key,
            data: null,
            error:
              cause instanceof Error
                ? cause.message
                : 'No se pudo cargar la información.',
          });
      });
    return () => {
      cancelled = true;
    };
  }, [load, active, key]);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return {
    data:
      state?.key.load === load && state.key.scope === scope ? state.data : null,
    error: state?.key === key ? state.error : '',
    loading: active && state?.key !== key,
    reload,
    setData: (data: T) => setState({ key, data, error: '' }),
  };
}
