# Research Understanding Agent

El nodo `research` de la Sesión 17A vive en `agent.py`. Consulta `ResearchContextBuilder`
para recuperar objetivos, hipótesis, variables, dimensiones, escalas, metodología revisada,
metadatos del dataset/EDA/preparación, paquete, planes y resultados con estado de vigencia.
Informa advertencias y referencias verificadas. No llama al modelo ni repite extracción.

La extracción de documentos de la sesión 6 conserva su caso de uso independiente en
`app.modules.research.methodology.service.MethodologyService`; produce borradores que
requieren revisión humana. El chat no invoca ese proceso ni confirma borradores.

Ver [arquitectura y demo](../../../../../docs/ORQUESTACION_MULTIAGENTE.md).
