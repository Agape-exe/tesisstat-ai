import { useSyncExternalStore } from 'react';

export const sections = [
  ['assistant', 'Asistente IA'],
  ['documents', 'Documentos'],
  ['methodology', 'Metodología'],
  ['instrument', 'Instrumento'],
  ['datasets', 'Datos'],
  ['analysis', 'Análisis'],
  ['results', 'Resultados'],
  ['reports', 'Informes'],
] as const;
export type Section = (typeof sections)[number][0];
export interface ProjectRoute {
  projectId: string | null;
  section: Section;
  form: 'create' | 'edit' | null;
  view: string | null;
  item: string | null;
}

function subscribe(callback: () => void) {
  window.addEventListener('popstate', callback);
  window.addEventListener('hashchange', callback);
  window.addEventListener('tesisstat:navigate', callback);
  return () => {
    window.removeEventListener('popstate', callback);
    window.removeEventListener('hashchange', callback);
    window.removeEventListener('tesisstat:navigate', callback);
  };
}

export function useProjectRoute(): ProjectRoute {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash);
  const params = new URLSearchParams(hash.slice(1));
  const requested = params.get('section');
  // Preserve links created by the previous four-step workspace.
  const section = requested === 'package' ? 'analysis' : requested;
  const form = params.get('form');
  return {
    projectId: params.get('project') || null,
    view: params.get('view'),
    item: params.get('item'),
    section: sections.some(([id]) => id === section)
      ? (section as Section)
      : 'assistant',
    form: form === 'create' || form === 'edit' ? form : null,
  };
}

export function navigateProject(
  projectId: string | null = null,
  section: Section = 'assistant',
  form: ProjectRoute['form'] = null,
  replace = false,
  workspace?: { view?: string; item?: string },
) {
  const params = new URLSearchParams();
  if (projectId) {
    params.set('project', projectId);
    params.set('section', section);
  }
  if (form) params.set('form', form);
  if (workspace?.view) params.set('view', workspace.view);
  if (workspace?.item) params.set('item', workspace.item);
  const url = `${window.location.pathname}${window.location.search}${params.size ? `#${params}` : ''}`;
  if (
    url !==
    window.location.pathname + window.location.search + window.location.hash
  ) {
    window.history[replace ? 'replaceState' : 'pushState'](null, '', url);
  }
  window.dispatchEvent(new Event('tesisstat:navigate'));
}

export function navigateWorkspace(
  projectId: string,
  section: Section,
  view: string,
  item?: string,
) {
  navigateProject(projectId, section, null, false, { view, item });
}
