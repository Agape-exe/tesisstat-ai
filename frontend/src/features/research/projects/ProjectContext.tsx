import { navigateProject } from './navigation';
export function ProjectContext({
  projectId,
  title,
}: {
  projectId: string;
  title: string;
}) {
  return (
    <section aria-label="Contexto de investigación" className="rp-state">
      <h2>{title}</h2>
      <p>
        El contexto ayuda a elegir un análisis: qué quieres comprender, qué
        representa cada fila y qué variables tienes.
      </p>
      <p>
        La captura y confirmación de contexto sin documentos estará disponible
        más adelante. Puedes cargar y explorar tus datos desde ahora.
      </p>
      <p>
        Si ya trabajas con una tesis, conserva el recorrido documental
        disponible. Sus revisiones pertenecen a ese recorrido y no confirman el
        nuevo contexto.
      </p>
      <div className="rp-actions">
        <button onClick={() => navigateProject(projectId, 'datasets')}>
          Ir a Datos
        </button>
        <button
          className="rp-secondary"
          onClick={() => navigateProject(projectId, 'documents')}
        >
          Documentos de apoyo
        </button>
        <button
          className="rp-secondary"
          onClick={() => navigateProject(projectId, 'methodology')}
        >
          Revisión metodológica existente
        </button>
        <button
          className="rp-secondary"
          onClick={() => navigateProject(projectId, 'instrument')}
        >
          Instrumento
        </button>
      </div>
    </section>
  );
}
