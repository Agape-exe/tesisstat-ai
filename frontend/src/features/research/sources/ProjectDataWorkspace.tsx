import { ProjectDatasets } from '../datasets/ProjectDatasets';
import { ProjectSources } from './ProjectSources';
import { TableWorkspace } from '../data/TableWorkspace';
import { navigateProject } from '../projects/navigation';

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
          aria-pressed={!legacy && view !== 'review'}
          onClick={() => onNavigate('sources')}
        >
          Archivos y tablas
        </button>
        <button
          className="rp-secondary"
          aria-pressed={view === 'review'}
          onClick={() => onNavigate('review', item ?? undefined)}
        >
          Revisar datos y variables
        </button>
        <details>
          <summary>Herramientas avanzadas</summary>
          <button
            className="rp-secondary"
            aria-pressed={legacy}
            onClick={() => onNavigate('legacy')}
          >
            Herramientas anteriores de datasets
          </button>
        </details>
        <button
          className="rp-secondary"
          onClick={() => navigateProject(projectId, 'instrument')}
        >
          Instrumento y puntuaciones (opcional)
        </button>
      </div>
      {view === 'review' ? (
        <TableWorkspace
          projectId={projectId}
          tableId={item}
          active={active}
          onSelect={(id) => onNavigate('review', id)}
          onContext={(id) => onNavigate('table', id)}
        />
      ) : legacy ? (
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
          onReview={(id) => onNavigate('review', id)}
        />
      )}
    </>
  );
}
