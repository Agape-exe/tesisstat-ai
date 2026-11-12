import { createContext, useContext, useEffect } from 'react';
import type { Selection } from '../../conversation/tutorApi';

export const WorkspaceFocus = createContext<
  ((selection: Selection) => void) | null
>(null);

export function useWorkspaceFocus(selection: Selection, active: boolean) {
  const publish = useContext(WorkspaceFocus);
  const key = JSON.stringify(selection);
  useEffect(() => {
    if (active) publish?.(JSON.parse(key) as Selection);
  }, [publish, key, active]);
}
