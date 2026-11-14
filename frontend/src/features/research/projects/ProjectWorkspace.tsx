import { ProjectHome } from './ProjectHome';
import { ProjectContext } from './ProjectContext';
import { useCallback, useState } from 'react';
import { WorkspaceFocus } from './workspaceFocus';
import { AgenticChat } from '../../conversation/AgenticChat';
import { TutorChat } from '../../conversation/TutorChat';
import type { Selection } from '../../conversation/tutorApi';
import { ProjectDocuments } from '../documents/ProjectDocuments';
import { ProjectMethodology } from '../methodology/ProjectMethodology';
import { ProjectDataWorkspace } from '../sources/ProjectDataWorkspace';
import { AnalysisWorkspace } from '../packages/AnalysisWorkspace';
import { ProjectResults } from '../analysis/ProjectResults';
import { ProjectReports } from '../analysis/ProjectReports';
import { navigateWorkspace, type Section } from './navigation';
import { ProjectInstrument } from '../instrument/ProjectInstrument';
type WorkspaceRoute = { view: string | null; item: string | null };
export function ProjectWorkspace({
  projectId,
  projectTitle,
  projectDescription,
  section,
  view = null,
  item = null,
}: {
  projectId: string;
  projectTitle?: string;
  projectDescription?: string;
  section: Section;
  view?: string | null;
  item?: string | null;
}) {
  const routeKey = JSON.stringify([section, view, item]);
  const [showDataPanel, setShowDataPanel] = useState(false);
  const helpStage =
    (
      {
        datasets: 'data',
        instrument: 'data',
        reports: 'results',
        documents: 'context',
        methodology: 'context',
      } as Record<string, Selection['stage']>
    )[section] ??
    ((section === 'assistant' ? 'home' : section) as Selection['stage']);
  const [focus, setFocus] = useState<{
    key: string;
    selection: Selection;
  } | null>(null);
  const publish = useCallback(
    (selection: Selection) => {
      setFocus({ key: routeKey, selection });
    },
    [routeKey],
  );
  const baseSelection: Selection = {
    stage: helpStage,
    ...(section === 'datasets' &&
    ['table', 'review'].includes(view ?? '') &&
    item
      ? { dataset_id: item }
      : {}),
    ...(section === 'analysis' && view === 'diagnostics' && item
      ? { intent_id: item }
      : {}),
    ...(['results', 'reports'].includes(section) && item
      ? { result_id: item }
      : {}),
  };
  const boundSelection =
    focus?.key === routeKey ? focus.selection : baseSelection;

  const [cache, setCache] = useState<{
    key: string;
    routes: Partial<Record<Section, WorkspaceRoute>>;
    tutorStage: Selection['stage'];
  }>({
    key: routeKey,
    routes: { [section]: { view, item } },
    tutorStage: helpStage,
  });
  if (cache.key !== routeKey)
    setCache({
      key: routeKey,
      routes: { ...cache.routes, [section]: { view, item } },
      tutorStage: section === 'assistant' ? cache.tutorStage : helpStage,
    });
  return (
    <WorkspaceFocus.Provider value={publish}>
      <div
        className={`rp-workspace ${section === 'assistant' ? 'rp-workspace-chat' : ''} ${showDataPanel && section === 'assistant' ? 'rp-workspace-split' : ''}`}
        aria-label="Sección del proyecto"
      >
        {(Object.entries(cache.routes) as [Section, WorkspaceRoute][]).map(
          ([id, route]) => (
            <div className="rp-guided-content" key={id} hidden={id !== section}>
              <SectionContent
                projectId={projectId}
                projectTitle={projectTitle}
                projectDescription={projectDescription}
                section={id}
                view={route.view}
                item={route.item}
                active={id === section}
                tutorStage={cache.tutorStage}
                boundSelection={boundSelection}
                showDataPanel={showDataPanel}
                setShowDataPanel={setShowDataPanel}
              />
            </div>
          ),
        )}
      </div>
    </WorkspaceFocus.Provider>
  );
}
function SectionContent({
  projectId,
  projectTitle,
  projectDescription,
  section,
  view,
  item,
  active,
  tutorStage,
  boundSelection,
  showDataPanel,
  setShowDataPanel,
}: {
  projectId: string;
  projectTitle?: string;
  projectDescription?: string;
  section: Section;
  view: string | null;
  item: string | null;
  active: boolean;
  tutorStage?: Selection['stage'];
  boundSelection?: Selection;
  showDataPanel?: boolean;
  setShowDataPanel?: (show: boolean) => void;
}) {
  switch (section) {
    case 'home':
      return (
        <ProjectHome
          projectId={projectId}
          title={projectTitle ?? ''}
          description={projectDescription ?? ''}
          active={active}
        />
      );
    case 'context':
      return (
        <ProjectContext projectId={projectId} title={projectTitle ?? ''} />
      );
    case 'assistant':
      return (
        <section
          className="rp-chat-first-workspace rp-assistant-section"
          aria-label="Asistente IA"
        >
          <div className="rp-chat-workspace-header">
            <div className="rp-chat-workspace-title">
              <span className="rp-tutor-panel-badge">IA</span>
              <h2>Asistente Estadístico TesisStat</h2>
            </div>
            <button
              type="button"
              className={`rp-secondary rp-toggle-data-btn ${showDataPanel ? 'active' : ''}`}
              onClick={() => setShowDataPanel?.(!showDataPanel)}
              aria-expanded={showDataPanel}
            >
              {showDataPanel ? '✕ Ocultar datos' : '📊 Ver datos cargados'}
            </button>
          </div>
          <div
            className={`rp-chat-split-container ${showDataPanel ? 'split-active' : ''}`}
          >
            <div className="rp-chat-main-column">
              <AgenticChat
                key={`${projectId}:${view}:${item}`}
                projectId={projectId}
                projectTitle={projectTitle}
                onOpenDataPanel={() => setShowDataPanel?.(true)}
              />
            </div>
            {showDataPanel && (
              <aside
                className="rp-side-data-panel"
                aria-label="Panel de datos cargados"
              >
                <div className="rp-side-data-header">
                  <h3>Datos cargados y visualizaciones</h3>
                  <button
                    type="button"
                    className="rp-side-data-close"
                    aria-label="Cerrar panel de datos"
                    onClick={() => setShowDataPanel?.(false)}
                  >
                    ✕
                  </button>
                </div>
                <div className="rp-side-data-content">
                  <ProjectDataWorkspace
                    projectId={projectId}
                    view={view}
                    item={item}
                    active={true}
                    onNavigate={(v, i) =>
                      navigateWorkspace(projectId, 'assistant', v, i)
                    }
                  />
                </div>
              </aside>
            )}
          </div>
        </section>
      );
    case 'documents':
      return <ProjectDocuments projectId={projectId} />;
    case 'methodology':
      return (
        <ProjectMethodology
          projectId={projectId}
          view={view}
          item={item}
          active={active}
        />
      );
    case 'datasets':
      return (
        <ProjectDataWorkspace
          projectId={projectId}
          view={view}
          item={item}
          active={active}
          onNavigate={(next, selected) =>
            navigateWorkspace(projectId, 'datasets', next, selected)
          }
        />
      );
    case 'analysis':
      return (
        <AnalysisWorkspace
          projectId={projectId}
          view={view}
          item={item}
          active={active}
        />
      );
    case 'results':
      return (
        <>
          <button
            className="rp-secondary"
            onClick={() =>
              navigateWorkspace(
                projectId,
                'reports',
                'detail',
                item ?? undefined,
              )
            }
          >
            Informes y exportaciones
          </button>
          <ProjectResults projectId={projectId} item={item} active={active} />
        </>
      );
    case 'reports':
      return (
        <ProjectReports projectId={projectId} item={item} active={active} />
      );
    case 'instrument':
      return <ProjectInstrument projectId={projectId} active={active} />;
  }
}
