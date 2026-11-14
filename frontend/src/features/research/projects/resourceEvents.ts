export function resourcesChanged(projectId: string) {
  window.dispatchEvent(
    new CustomEvent('tesisstat:resources-changed', { detail: projectId }),
  );
}
