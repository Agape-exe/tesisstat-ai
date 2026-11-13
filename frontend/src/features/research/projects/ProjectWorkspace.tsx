import { ProjectHome } from './ProjectHome';
import { ProjectContext } from './ProjectContext';
import { useCallback, useEffect, useState } from 'react';
import { WorkspaceFocus } from './workspaceFocus';
import { TutorChat } from '../../conversation/TutorChat';
import {
  createTutorApi,
  type Selection,
  type TutorStatus,
} from '../../conversation/tutorApi';
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
  const [helpOpen, setHelpOpen] = useState(false);
  const [bubbleStatus, setBubbleStatus] = useState<TutorStatus | null>(null);
  const [pillDismissed, setPillDismissed] = useState(false);
  const tutorOpen = helpOpen;
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

  useEffect(() => {
    let ignore = false;
    const fetchStatus = () => {
      createTutorApi()
        .status(projectId, boundSelection)
        .then((s) => {
          if (!ignore) setBubbleStatus(s);
        })
        .catch(() => {});
    };
    if (section !== 'home' || tutorOpen) {
      fetchStatus();
    }
    const onResourcesChanged = (event: Event) => {
      if ((event as CustomEvent<string>).detail === projectId) {
        setPillDismissed(false);
        fetchStatus();
      }
    };
    window.addEventListener('tesisstat:resources-changed', onResourcesChanged);
    return () => {
      ignore = true;
      window.removeEventListener(
        'tesisstat:resources-changed',
        onResourcesChanged,
      );
    };
  }, [projectId, section, tutorOpen, JSON.stringify(boundSelection)]);

  const selectedTable = bubbleStatus?.guidance?.selected_table;
  const selectedTableName = selectedTable?.name ?? '';
  const hasNotaVar = bubbleStatus?.guidance?.variables?.some((v) =>
    v.name.toLowerCase().includes('nota'),
  );
  const isNotaTable =
    selectedTableName.toLowerCase().includes('nota') || Boolean(hasNotaVar);

  const pillNotification = isNotaTable
    ? 'He detectado tu tabla con variables de notas. ¿Quieres que te ayude a analizarlas?'
    : selectedTableName
      ? `He detectado tu tabla «${selectedTableName}». ¿Quieres que te ayude a analizarla?`
      : (bubbleStatus?.choices?.datasets?.length ?? 0) > 0 ||
          (bubbleStatus?.guidance?.table_count ?? 0) > 0
        ? 'He detectado datos cargados en tu proyecto. ¿Quieres que te ayude a analizarlos?'
        : null;

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
        className={`rp-workspace ${section === 'assistant' ? 'rp-workspace-chat' : ''}`}
        aria-label="Sección del proyecto"
      >
        {section !== 'assistant' && (
          <div
            className="rp-tutor-floating-container"
            aria-label="Asistente de tutoría IA"
          >
            {!tutorOpen && !pillDismissed && pillNotification && (
              <div
                className="rp-tutor-pill"
                role="status"
                onClick={() => {
                  setHelpOpen(true);
                  setPillDismissed(true);
                }}
              >
                <span className="rp-tutor-pill-icon" aria-hidden="true">
                  ✨
                </span>
                <span className="rp-tutor-pill-text">{pillNotification}</span>
                <button
                  type="button"
                  className="rp-tutor-pill-close"
                  aria-label="Cerrar notificación"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPillDismissed(true);
                  }}
                >
                  ×
                </button>
              </div>
            )}
            <button
              type="button"
              className={`rp-tutor-bubble ${tutorOpen ? 'rp-tutor-bubble-active' : ''}`}
              aria-label={
                tutorOpen ? 'Cerrar asistente IA' : 'Abrir asistente IA'
              }
              aria-expanded={tutorOpen}
              onClick={() => {
                setHelpOpen(!tutorOpen);
                if (!tutorOpen) setPillDismissed(true);
              }}
            >
              {tutorOpen ? (
                <span className="rp-tutor-bubble-close" aria-hidden="true">
                  ✕
                </span>
              ) : (
                <span className="rp-tutor-bubble-icon" aria-hidden="true">
                  <svg
                    width="26"
                    height="26"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    <circle cx="9" cy="10" r="1.25" fill="currentColor" />
                    <circle cx="15" cy="10" r="1.25" fill="currentColor" />
                  </svg>
                </span>
              )}
            </button>
            {tutorOpen && (
              <div
                className="rp-tutor-panel"
                role="dialog"
                aria-label="Asistente TesisStat"
              >
                <div className="rp-tutor-panel-header">
                  <div className="rp-tutor-panel-title">
                    <span className="rp-tutor-panel-badge">IA</span>
                    <strong>Asistente TesisStat</strong>
                  </div>
                  <button
                    type="button"
                    className="rp-tutor-panel-close-btn"
                    aria-label="Cerrar asistente"
                    onClick={() => setHelpOpen(false)}
                  >
                    ✕
                  </button>
                </div>
                <div className="rp-tutor-panel-content">
                  <TutorChat
                    key={`${projectId}:${JSON.stringify(boundSelection)}`}
                    projectId={projectId}
                    projectTitle={projectTitle}
                    stage={helpStage}
                    boundSelection={boundSelection}
                  />
                </div>
              </div>
            )}
          </div>
        )}
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
}: {
  projectId: string;
  projectTitle?: string;
  projectDescription?: string;
  section: Section;
  view: string | null;
  item: string | null;
  active: boolean;
  tutorStage?: Selection['stage'];
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
        <TutorChat
          key={`${projectId}:${view}:${item}:${tutorStage}`}
          projectId={projectId}
          projectTitle={projectTitle}
          stage={view === 'results' ? 'results' : (tutorStage ?? 'home')}
          active={active}
          resultId={view === 'results' ? (item ?? undefined) : undefined}
        />
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
