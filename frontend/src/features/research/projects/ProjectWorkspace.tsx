import { useState } from 'react';
import { ConversationChat } from '../../conversation/ConversationChat';
import { ProjectDocuments } from '../documents/ProjectDocuments';
import { ProjectDatasets } from '../datasets/ProjectDatasets';
import { ProjectPackage } from '../packages/ProjectPackage';
import { navigateProject, sections, type Section } from './navigation';
import { EmptyState } from './ProjectShell';

function panelFor(section: Section) {
  if (section === 'methodology') return 'documents';
  if (['analysis', 'results', 'reports'].includes(section)) return 'package';
  return section;
}

export function ProjectWorkspace({
  projectId,
  section,
}: {
  projectId: string;
  section: Section;
}) {
  const panel = panelFor(section);
  const [cache, setCache] = useState({ current: panel, visited: [panel] });
  if (cache.current !== panel) {
    setCache({
      current: panel,
      visited: cache.visited.includes(panel)
        ? cache.visited
        : [...cache.visited, panel],
    });
  }
  return (
    <div className="rp-workspace" aria-label="Sección del proyecto">
      {['methodology', 'results', 'reports'].includes(section) && (
        <h2>{sections.find(([id]) => id === section)?.[1]}</h2>
      )}
      {section === 'methodology' && (
        <p className="rp-hint">
          Selecciona un documento y abre su revisión metodológica. Conservamos
          el flujo de documentos y metodología durante esta fase.
        </p>
      )}
      {['analysis', 'results', 'reports'].includes(section) && (
        <p className="rp-hint">
          Estas secciones conservan el flujo integrado: prepara el paquete,
          revisa y aprueba el análisis; luego consulta los resultados y descarga
          sus informes. No es necesario volver a ejecutar un análisis para
          consultar su historial.
        </p>
      )}
      {section === 'instrument' && (
        <EmptyState title="Instrumento: próximamente">
          La extracción de ítems, validación y confiabilidad aún no están
          disponibles. Puedes adjuntar documentos de tu investigación en
          Documentos; esto no valida un instrumento.
        </EmptyState>
      )}
      {cache.visited.includes('assistant') && (
        <div hidden={panel !== 'assistant'}>
          <ConversationChat
            projectId={projectId}
            onOpenResource={(resource) => navigateProject(projectId, resource)}
          />
        </div>
      )}
      {cache.visited.includes('documents') && (
        <div hidden={panel !== 'documents'}>
          <ProjectDocuments projectId={projectId} />
        </div>
      )}
      {cache.visited.includes('datasets') && (
        <div hidden={panel !== 'datasets'}>
          <ProjectDatasets projectId={projectId} />
        </div>
      )}
      {cache.visited.includes('package') && (
        <div hidden={panel !== 'package'}>
          <ProjectPackage projectId={projectId} />
        </div>
      )}
    </div>
  );
}
