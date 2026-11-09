import { ProjectDatasets } from '../datasets/ProjectDatasets';
import { ProjectSources } from './ProjectSources';

export function ProjectDataWorkspace({
  projectId,
  view,
  item,
  active,
  onNavigate,
}: {
  projectId: string;
  view: string | null;
  item: string | null;
  active: boolean;
  onNavigate: (view: string, item?: string) => void;
}) {
  const legacy =
    ['legacy', 'quality', 'preparation'].includes(view ?? '') ||
    (view === 'preview' && !!item);
  return (
    <>
      <div className="rp-actions" style={{ marginBottom: 20 }}>
        <button
          className="rp-secondary"
          aria-pressed={!legacy}
          onClick={() => onNavigate('sources')}
        >
          Archivos y tablas
        </button>
        <button
          className="rp-secondary"
          aria-pressed={legacy}
          onClick={() => onNavigate('legacy')}
        >
          Herramientas anteriores de datasets
        </button>
      </div>
      {legacy ? (
        <ProjectDatasets
          projectId={projectId}
          view={view === 'legacy' ? 'preview' : view}
          item={item}
          active={active}
          onNavigate={onNavigate}
        />
      ) : (
        <ProjectSources
          projectId={projectId}
          item={item}
          active={active}
          onSelect={(id) => onNavigate('table', id)}
        />
      )}
    </>
  );
}
