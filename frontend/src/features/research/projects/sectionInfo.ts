import type { Section } from './navigation';
export const sectionInfo: Record<
  Section,
  { title: string; description: string; icon: string }
> = {
  home: {
    title: 'Inicio',
    description: 'Tu proyecto, paso a paso.',
    icon: 'folder',
  },
  context: {
    title: 'Contexto',
    description: 'Define qué quieres comprender con tus datos.',
    icon: 'book',
  },
  assistant: {
    title: 'Asistente IA',
    description: 'Conversación dentro del proyecto seleccionado',
    icon: 'message',
  },
  documents: {
    title: 'Documentos',
    description:
      'Organiza los archivos de tu tesis y accede a su revisión metodológica.',
    icon: 'file',
  },
  methodology: {
    title: 'Metodología',
    description:
      'Revisa los elementos académicos antes de relacionarlos con los datos.',
    icon: 'book',
  },
  instrument: {
    title: 'Instrumento de investigación',
    description:
      'Organiza tu instrumento de medición y conoce los próximos pasos.',
    icon: 'clipboard',
  },
  datasets: {
    title: 'Datos',
    description:
      'Organiza tus archivos, revisa sus hojas y describe cada tabla.',
    icon: 'database',
  },
  analysis: {
    title: 'Análisis estadístico',
    description:
      'Revisa la técnica propuesta y sus condiciones antes de cualquier ejecución.',
    icon: 'chart',
  },
  results: {
    title: 'Resultados estadísticos',
    description:
      'Consulta cálculos obtenidos y sus interpretaciones cuando estén disponibles.',
    icon: 'scatter',
  },
  reports: {
    title: 'Informes',
    description: 'Revisa la presentación de los hallazgos y sus exportaciones.',
    icon: 'report',
  },
};
