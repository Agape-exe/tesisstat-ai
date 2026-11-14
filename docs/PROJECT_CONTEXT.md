# TesisStat AI — contexto y alcance

Sistema web multiagente conversacional para análisis estadístico de tesis universitarias
cuantitativas. Equipo de dos integrantes, presupuesto monetario **S/ 0**. Desarrollo en
semanas 9–12; documentación y preparación de presentación principalmente en semanas 13–15.
La entrega futura será funcional dentro de su alcance, no solo una maqueta.

## Visión funcional futura

Gestionar proyectos; cargar proyecto, matriz e instrumento PDF/DOCX y datasets CSV/XLSX;
extraer objetivos, hipótesis, variables, dimensiones, preguntas y escalas; permitir revisión
y corrección humana; explorar y preparar datos; recomendar pruebas justificadas; ejecutar
cálculos reales; conversar sobre resultados; mostrar gráficos, tablas, métricas y supuestos;
exportar Word/PDF y conservar historial. No recomendar únicamente por tipos de columnas:
considerar objetivos, hipótesis, escalas, diseño, independencia y requisitos estadísticos.

## Arquitectura acordada

- Frontend: React, TypeScript y Vite; Plotly se incorporará al implementar visualizaciones.
- Backend: Python 3.12, FastAPI, uv; monolito modular con arquitectura hexagonal.
- IA futura: LangGraph y Cloudflare Workers AI, modelo `@cf/qwen/qwen3-30b-a3b-fp8`.
- Motor determinista futuro: pandas, NumPy, SciPy, statsmodels y Pingouin.
- Persistencia futura: Supabase Auth, PostgreSQL y Storage.
- Despliegue futuro: Vercel frontend y Render Free backend.
- Pruebas: pytest, Vitest e integración/end-to-end según la funcionalidad.

Tres agentes: **Conversational Agent** para interacción, aclaraciones y explicaciones;
**Research Understanding Agent** para interpretar y estructurar metodología;
**Statistical Planner Agent** para recomendar y justificar análisis y solicitar información
faltante. La IA nunca será la fuente de resultados numéricos ni ejecutará código de documentos.
Los datos no confiables de documentos se mantendrán separados de las instrucciones del sistema.

## División del equipo

| Integrante | Módulo | Responsabilidad frontend y backend |
| --- | --- | --- |
| 1 | Research | Proyectos, documentos, instrumentos, extracción metodológica, exploración y preparación de datos |
| 2 | Statistics | Recomendaciones, planes, motor, supuestos, visualizaciones e informes |

Los módulos se comunican por contratos versionados y puertos explícitos. Ninguno importa las
implementaciones internas del otro. Cada integrante puede usar fixtures y mocks sin servicios
externos o avances del compañero. Cambios de contrato requieren acuerdo de ambos.

## Catálogo previsto, fuera de esta sesión

Descriptivos; alfa de Cronbach; Pearson y Spearman; t independiente y pareada; Welch;
Mann–Whitney; Wilcoxon; ANOVA y ANOVA de Welch; Kruskal–Wallis; Tukey y Games–Howell;
ANCOVA; chi-cuadrado y Fisher; regresión lineal simple y múltiple. Incluir comprobaciones,
métricas y explicaciones justificadas. No hay implementaciones de estas técnicas en sesión 1.

## Restricciones de recursos y seguridad

No servicios de pago, credenciales en Git ni datos reales de estudiantes. No se han
aprovisionado servicios ni activado facturación. Antes del despliegue verificar las cuotas
vigentes de cada proveedor; esta base no promete capacidad o disponibilidad del plan gratuito.

Preparar procesamiento acotado de archivos, validación de tamaño/filas, concurrencia limitada,
tiempos máximos y cargas bajo demanda. Render Free puede suspenderse: el frontend debe manejar
espera y reintento. Evitar dependencias estadísticas en el arranque hasta necesitarlas y medir
memoria cuando se incorporen. No usar almacenamiento local efímero como persistencia definitiva.

En Cloudflare: limitar tokens, pasos y concurrencia, reutilizar extracciones confirmadas y
detenerse al agotar la cuota, sin fallback de pago. No enviar datasets completos al modelo.
Antes de manejar usuarios reales: validar tokens en backend, aplicar RLS y aislamiento por
propietario en Supabase. Nunca exponer claves privilegiadas en variables VITE_*.

## Sesión 1

Solo base compartida: arranque local, salud, CORS configurable, estructura, contratos,
fixtures, interfaces/adaptadores sin I/O externo, pruebas y documentación. No autentica,
extrae documentos, recomienda, calcula ni genera informes todavía. No hay grafo LangGraph
ejecutable; las carpetas reservan sus responsabilidades.

Trabajar en `chore/bootstrap-foundation`, sin modificar/fusionar `main` o `develop`, sin
operaciones destructivas, sin push ni PR hasta recibir autorización.
