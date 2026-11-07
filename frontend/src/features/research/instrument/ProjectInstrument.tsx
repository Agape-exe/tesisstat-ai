import { EmptyState } from '../projects/ProjectShell';
import {
  Guidance,
  SectionColumns,
  SupportPanel,
} from '../projects/SectionLayout';
import { navigateProject } from '../projects/navigation';

export function ProjectInstrument({ projectId }: { projectId: string }) {
  return (
    <section aria-label="Instrumento de investigación">
      <SectionColumns
        support={
          <SupportPanel
            title="¿Para qué sirve?"
            projectId={projectId}
            destination="methodology"
            action="Revisar variables"
          >
            <p>
              Permitirá relacionar el instrumento con la metodología y las
              respuestas de tu investigación.
            </p>
            <Guidance
              items={[
                'Variables y dimensiones',
                'Ítems y escalas de medición',
                'Correspondencia con el dataset',
              ]}
            />
          </SupportPanel>
        }
      >
        <EmptyState title="Instrumento: próximamente">
          La interpretación estructurada del cuestionario o escala aún no está
          disponible. Los instrumentos podrán vincularse posteriormente con
          variables, dimensiones, ítems y datasets.
        </EmptyState>
        <div className="rp-instrument-action">
          <button onClick={() => navigateProject(projectId, 'documents')}>
            Guardar documento en Documentos
          </button>
          <p className="rp-hint">
            Almacenamiento de PDF o DOCX. La carga no detecta ítems, escalas,
            dimensiones ni indicadores del instrumento.
          </p>
        </div>
      </SectionColumns>
      <p className="rp-section-notice">
        El instrumento define qué se pretende medir; el dataset contiene las
        respuestas. La validez necesita evidencia y la confiabilidad requiere
        datos adecuados. No se calculan coeficientes a partir del PDF.
      </p>
    </section>
  );
}
