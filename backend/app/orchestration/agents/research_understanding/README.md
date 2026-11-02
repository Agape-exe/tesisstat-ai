# Research Understanding Agent

La implementación de sesión 6 vive en `app.modules.research.methodology.service.MethodologyService`.
Es el caso de uso Research Understanding: reutiliza la extracción textual, un puerto de IA y
un repositorio. La composición de desarrollo está en `research.dev_app`; no se duplica la
lógica ni se incorpora todavía un grafo LangGraph. Produce `MethodologyDraft` local, incompleto
y no revisado; nunca un ResearchPackage automático. La revisión manual corresponde a sesión 7.
Los documentos son datos no confiables. Ver `docs/RESEARCH_METHODOLOGY_AI.md`.
