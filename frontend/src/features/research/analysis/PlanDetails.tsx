import type { AnalysisRecord } from './api';
import { techniqueName } from './analysisPresentation';
export function PlanDetails({ record }: { record: AnalysisRecord }) {
  return (
    <>
      <div className="rp-section-heading">
        <h3>{techniqueName(record)}</h3>
        <span className="rp-badge">
          {record.plan.status === 'approved'
            ? 'Aprobado'
            : record.plan.status === 'needs_clarification'
              ? 'Aclaraciones pendientes'
              : 'Por aprobar'}
        </span>
      </div>
      <p>{record.plan.rationale}</p>
      <h4>Supuestos por comprobar</h4>
      {record.plan.assumptions_to_check?.length ? (
        <ul>
          {record.plan.assumptions_to_check.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>Sin supuestos adicionales declarados por el planificador.</p>
      )}
      {record.plan.pending_questions?.map((item) => (
        <p className="rp-warning" key={item}>
          Aclaración: {item}
        </p>
      ))}
      {record.limitation && <p className="rp-warning">{record.limitation}</p>}
      {record.invalidated_at && (
        <p className="rp-error">
          Plan desactualizado: {record.stale_reason ?? 'Las fuentes cambiaron'}.
        </p>
      )}
      <details className="rp-technical">
        <summary>Detalles del plan</summary>
        <p>
          Plan: {record.plan.id} · Estado: {record.plan.status}
        </p>
        <p>Paquete: {record.plan.research_package_id}</p>
        <p>Versión de fuentes: {record.source_version}</p>
      </details>
    </>
  );
}
