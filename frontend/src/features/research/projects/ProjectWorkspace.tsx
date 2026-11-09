import { ProjectHome } from './ProjectHome';
import { ProjectContext } from './ProjectContext';
import { useState } from 'react';
import { ConversationChat } from '../../conversation/ConversationChat';
import { ProjectDocuments } from '../documents/ProjectDocuments';
import { ProjectMethodology } from '../methodology/ProjectMethodology';
import { ProjectDataWorkspace } from '../sources/ProjectDataWorkspace';
import { AnalysisWorkspace } from '../packages/AnalysisWorkspace';
import { ProjectResults } from '../analysis/ProjectResults';
import { ProjectReports } from '../analysis/ProjectReports';
import { navigateProject, navigateWorkspace, type Section } from './navigation';
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
  const [cache, setCache] = useState<{
    key: string;
    routes: Partial<Record<Section, WorkspaceRoute>>;
  }>({ key: routeKey, routes: { [section]: { view, item } } });
  if (cache.key !== routeKey)
    setCache({
      key: routeKey,
      routes: { ...cache.routes, [section]: { view, item } },
    });
  return (
    <div
      className={`rp-workspace ${section === 'assistant' ? 'rp-workspace-chat' : ''}`}
      aria-label="Sección del proyecto"
    >
      {(Object.entries(cache.routes) as [Section, WorkspaceRoute][]).map(
        ([id, route]) => (
          <div key={id} hidden={id !== section}>
            <SectionContent
              projectId={projectId}
              projectTitle={projectTitle}
              projectDescription={projectDescription}
              section={id}
              view={route.view}
              item={route.item}
              active={id === section}
            />
          </div>
        ),
      )}
    </div>
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
}: {
  projectId: string;
  projectTitle?: string;
  projectDescription?: string;
  section: Section;
  view: string | null;
  item: string | null;
  active: boolean;
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
        <ConversationChat
          projectId={projectId}
          projectTitle={projectTitle}
          onOpenResource={(resource) => navigateProject(projectId, resource)}
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
      return <ProjectInstrument projectId={projectId} />;
  }
}
