# Contratos y estrategia de evolución

Normativo S00 (9 de noviembre de 2026), **diseño pendiente de implementación**.
Alcance/aceptación: [acuerdo de sesiones](ALCANCE_Y_SESIONES.md).
Identidad/durabilidad: [integración](INTEGRACION_PARALELA.md).
Este documento fija interfaces; S00 no cambia modelos, rutas, esquemas, repositorios ni motor.

## Decisión de compatibilidad

Congelar los seis contratos `schema_version: "1.0.0"` de
`backend/app/shared/contracts.py` y sus esquemas/tipos/fixtures. ResearchPackage exige
hipótesis y metodología reviewed; AnalysisPlan exige hypothesis_id. No son adecuados para
descriptivos sin hipótesis. No hacer opcionales esos campos silenciosamente ni construir
hipótesis/documentos/revisiones ficticios para entrar al motor v1.

Crear una familia **Analysis v2, schema_version="2.0.0"**, con modelos canónicos futuros
en `backend/app/shared/analysis_v2.py`, esquemas futuros en `contracts/v2/` y tipos generados
en una carpeta v2 separada. Nuevas rutas `/api/v2/research/projects/{project_id}`; no
reinterpretar payloads v1 por heurística. La creación simplificada C1 evoluciona el DTO
local Research existente y su ruta, fuera de los seis contratos compartidos.
InstrumentContext v1 también se conserva; C6 tiene v2 explícito por cambio de procedencia.
Versiones de esquema, revisión de recurso y versión de algoritmo son conceptos distintos.

Lectura de históricos: unión discriminada en el adaptador de aplicación por familia/versión
de payload; cada snapshot mantiene su versión. Las tablas/repositorios legados sin campo
de familia se reconocen por su procedencia conocida, no por inventar schema_version.
Vistas pueden normalizar para presentar, conservando el payload original. Nuevas propuestas
por contexto manual usan v2. La ruta documental v1 sigue disponible y probada; se puede
crear una nueva copia v2 desde campos revisados, con referencias explícitas y nueva aprobación.
No reusar aprobaciones, tokens o IDs de planes v1.

Statistics incorpora `PlanningInputV2`/`ExecutionInputV2` y adapta a funciones puras existentes
(`comparisons`, `inferential`, `nonparametric`, `descriptive`, `scoring`); no necesita fabricar
un AnalysisPlan v1 para llamar `engine.execute`. El motor v1 queda como consumidor legado.
Orchestration ensambla snapshots, obtiene bytes por puerto autorizado, aprueba, controla
vigencia y persiste resultados. Research conserva contexto, archivos, diccionario/instrumento.
Statistics no consulta repositorios Research, JWT, HTTP ni rutas físicas.

S02 implementa C2 y estructura del snapshot/intención C4; S03 C3; S04 C4–C5 y sus
consumidores; S05 C6; S06 C7. Primero modelos canónicos y exportadores, después regenerar
esquemas/tipos con scripts; jamás editar generados a mano. CI debe incluir ambos formatos,
fixtures v1 intactos, ejemplos v2 válidos y rechazo de versiones no admitidas (422).

## Reglas comunes C2–C7

| Tipo / campo común | Regla exacta |
| --- | --- |
| ID | Cadena opaca no vacía; nuevos IDs persistidos UUID generados por servidor. Ejemplos sintéticos usan UUID. IDs legados conservan su cadena; nunca autorizan acceso |
| Revisión | `revision: int >=1` en recursos guardados; ausente equivale a revisión 0 solo al crear; `expected_revision: int >=0` en mutaciones; CAS atómico; conflicto 409 |
| Fecha / hash | Fecha UTC RFC3339 del servidor; hash SHA-256 hexadecimal minúscula de 64 caracteres; no rutas/URLs firmadas en snapshots |
| Valores | JSON estricto sin campos adicionales; números finitos; texto recortado; texto opcional desconocido=null, listas vacías=[]; enums usan unknown; nunca string vacío como evidencia |
| Provenance | `{kind: manual|document|ai_suggestion|derived|unknown, source_refs: SourceRef[]}`; documento exige referencia+hash; IA no se vuelve manual al confirmar; derived exige fuente/algoritmo; unknown no tiene referencias |
| SourceRef | `{kind: project|context|dataset|dictionary|intent|profile|diagnostic|document|instrument|mapping|score|plan|result, id: ID, revision: int>=1, hash: Hash}`; hash de contenido canónico/bytes, no secreto |
| Confirmation | `null` o `{actor_ref: ID, confirmed_at: DateTime, revision: int>=1}` emitido por servidor para esa revisión; actor del principal validado, o actor local etiquetado en modo local; nunca tomado del body |
| Fact<T> | `{value:T|null, provenance:Provenance, confirmation:Confirmation|null}`; unknown enum es valor explícito desconocido y no confirmado; valor IA pendiente no es evidencia confirmada |
| Snapshot | `schema_version, id, project_id, revision, created_at, source_refs`; inmutable; un cambio crea nueva revisión/ID según contrato, no reescribe evidencia histórica |

`hash` de recursos JSON = SHA256 de UTF-8 JSON canónico (claves ordenadas recursivamente,
separadores compactos, Unicode sin escape, números finitos; versión de canonicalización
`json-sort-v1`). En recursos editables se excluyen hash propio, fechas y confirmation del
contenido a hashear; las confirmaciones apuntan a la revisión. En dataset reutilizar
`compute_dataset_hash` y registrar `hash_algorithm="research-dataset-v1"`; no intercambiarlo
con SHA256 de solo bytes. SourceRef no se acepta como prueba enviada por cliente: resolverlo
en servidor y verificar pertenencia, revisión y hash. Sin ciclos entre fuentes.

Prefijo `P=/api/v2/research/projects/{project_id}` en operaciones previstas.
Respuesta de error nueva: `{error:{code:string,message:string,fields:string[],current_revision:int|null}}`.
401 identity_required/invalid_token; 404 resource_not_found (incluye ajeno); 403
consent_required (solo recurso propio); 409 revision_conflict/source_stale/approval_mismatch/
not_approved; 413 limit_exceeded; 415 unsupported_format; 422 invalid_payload/
unsupported_schema/incompatible_variables. 503 provider_unavailable o storage_unavailable,
sin convertir fallo de almacenamiento en recurso inexistente. No cambiar errores legados.
Una aclaración científica es respuesta 201/200 con estado needs_clarification, no error 500.

Confirmar: crear nueva revisión con valores elegidos y auditoría en la misma transacción;
si el usuario solo confirma un valor existente, también avanza revisión. En ese paso el
servidor asigna confirmation a la revisión resultante. Omitir una clave en PATCH conserva;
enviar null la borra e invalida su confirmación. PUT reemplaza solo donde se indica.
No aceptar `owner_id`, `actor_ref`, `approved_at` ni confirmaciones en cuerpos de cliente.

## C1 — Proyecto mínimo (Research → UI, chat, contexto; S01)

Mantener `POST /api/research/projects` (201 + Location) y GET/list/PUT/DELETE existentes.
`title` sigue siendo el nombre: string 1–200 tras trim, obligatorio; provisional válido.
`description` string 0–2000, opcional, default "". `university`, `faculty`, `program`:
string|null, máx.160, opcionales default null; `degree`: bachelor|master|doctorate|other|null;
`academic_year`: int 1900–2100|null. Aceptar payloads legados válidos. Respuesta conserva
id/status=draft/created_at/updated_at y datos académicos. GET tolera payloads anteriores sin
normalizarlos destructivamente. owner_id solo servidor y contrato de integración.

PUT actual se mantiene como actualización compatible de campos suministrados: ausentes
conservan valores previos, null explícito borra campo opcional; title no puede ser null.
S01 debe documentar esta semántica en API y probarla contra formularios legados que envían
todos los campos. No reemplazar académicos previos por defaults del DTO al editar nombre.
Creación no crea metodología revisada ni implica contexto completo. Nombre de proyecto es
canónico; Contexto muestra/enlaza ese título. Cambiar solo nombre/descripcion de presentación
no invalida análisis estadísticos; hashes analíticos excluyen esos campos.

Solicitud sintética completa mínima:

```json
{"title":"Ensayo provisional","description":""}
```

Errores: title vacío/longitud/año fuera de rango 422; proyecto inexistente/ajeno 404.
Estado de proyecto permanece draft en esta entrega: avance de Inicio se deriva de recursos,
no de un porcentaje persistido ni de declarar proyecto completed.

## C2 — Contexto progresivo (Research → Orchestration, UI, chat; S02)

`ProjectContextV2`: schema_version, project_id, revision, updated_at; estado informativo
`empty|partial|usable` derivado para la intención solicitada, no sello metodológico global.
Campos de contenido:

| Campo | Tipo / obligatoriedad |
| --- | --- |
| research_question, main_objective | Fact<string máx.2000>, default value=null; cualquiera permite orientar; ninguno bloquea EDA/descriptivos seleccionados |
| specific_objectives | Lista máx.40 de `{id:ID, text:Fact<string máx.2000>}`; default [] |
| hypotheses | Lista máx.40 de `{id:ID, statement:Fact<string>, objective_id:ID|null, alternative:two-sided|greater|less|unspecified}`; default []; no obligatoria |
| study_description, data_description | Fact<string máx.2000>, default null |
| observational_unit, sampling_notes | Fact<string máx.2000>, default null; inferencia requiere límites de muestreo explícitos, permite declarar no probabilístico/desconocido y restringir generalización |
| design | Fact<experimental|quasi_experimental|observational|unknown>, default unknown |
| observations | Fact<independent|paired|repeated|unknown>, default unknown; no inferir de tamaño |
| complementary_notes | Lista máx.20 de texto máx.2000 con provenance; no parámetros estadísticos ni editor genérico |
| pending_questions | Lista derivada `{code,field,question,blocks:profile|proposal|execution}`; no pregunta repetida si ya respondida |

Título se lee de Project C1, no existe otro título editable que pueda divergir. Hipótesis
no se generan para dar contenido a hypotheses[]. Pregunta/objetivo pueden ser desconocidos
en un análisis exploratorio explícitamente limitado.

GET `P/context` devuelve revisión actual (empty, revision=0 virtual si no guardado);
PATCH `P/context` recibe `{expected_revision, changes:{campo:valor_crudo}, confirm_fields:string[]}`.
Para listas se envía la lista completa con IDs; para facts enum/text se envía solo value.
Servidor fija provenance manual de cambios manuales y confirma únicamente confirm_fields
presentes/revisables, incluyendo el caso de confirmación sin cambio. Paths usan JSON Pointer.
No promover valor IA sin selección humana. GET `P/context/revisions` conserva históricos.

Sugerencias opcionales: POST `P/context/suggestions` crea borrador separado con base_revision,
provenance y changes; POST `P/context/suggestions/{id}/apply` con expected_revision,
selected_fields y confirm=true aplica solo elegidos como nueva revisión; rechazo deja contexto
intacto. `pending→applied|rejected|stale`; stale si cambió base; no autoaplicar extracción.
Extracción documental conserva revisión y citas del documento original; importar campos
seleccionados al contexto no simula revisión completa del documento.

Ejemplo PATCH sin hipótesis:

```json
{"expected_revision":0,"changes":{"main_objective":"Describir las ventas registradas","observational_unit":"Una venta"},"confirm_fields":["/main_objective","/observational_unit"]}
```

Guardar contexto parcial nunca exige todo el catálogo de campos. S04 calcula elegibilidad
por intención y genera aclaraciones específicas sobre campos no confirmados relevantes.

## C3 — Diccionario y fuentes (Research → Statistics por puertos, UI/chat; S03)

CSV/XLSX, límites y preparación existentes se reutilizan; no cambiar fuente in situ.
`DatasetRefV2`: id, project_id, revision, hash, hash_algorithm, format=csv|xlsx,
row_count:int>=0, columns:`{id:ID,name:string,position:int>=0}[]`, sheet:string|null,
synthetic:bool|null, source_dataset_id:ID|null, preparation_ref:SourceRef|null.
`synthetic=null` significa no declarado: permite carga/perfil local, bloquea cálculo que
requiere autorización hasta declararlo. No incluir bytes, filas ni location física en snapshot
público. IDs de columna estables dentro de una revisión; no asumir correspondencia por posición.

`VariableDictionaryV2`: schema_version, project_id, id, revision, dataset_ref, updated_at,
`variables: VariableV2[]` (puede ser [] mientras se explora).
VariableV2: id; name:Fact<string 1–200>; description:Fact<string máx.2000>;
measurement_scale:Fact<nominal|ordinal|interval|ratio|unknown>;
column_ids:ID[] (vacío=mapeo pendiente); storage_type=string|integer|number|boolean|date|mixed|unknown
(evidencia derivada del perfil, no escala humana); category_order:string[] (default [],
exigida para ordinal cuando los códigos no expresen orden confirmado);
missing_markers:string[] (default ["", "NA", "N/A", "null", "none"], comparación trim/casefold);
possible_identifier:bool derivado, identifier_confirmed:Fact<bool> default null.
Roles pertenecen a la intención, no son una propiedad universal de la variable.

GET/PUT `P/datasets/{id}/dictionary`; PUT `{expected_revision,variables:[...]}` sustituye
definiciones de esta revisión con facts de entrada value/provenance controlada por servidor
y `confirm_fields` al nivel del body como C2. Variables no seleccionadas pueden seguir unknown.
Columnas inexistentes, IDs duplicados o vínculos ajenos: 422/404; revisión/hash antiguo: 409.
Una variable escalar usa una columna; multicolumna se permite para pares/ítems únicamente con
semántica en C4/C6; no sumar columnas tácitamente. Identificadores no entran al cálculo/chat.

Después de preparación: nuevo dataset/ref/diccionario. Renombre con receta conserva la
relación explícita old_column_id→new_column_id; eliminación deja variable sin vínculo y
pending_question; no emparejar nombres parecidos. Confirmación de nueva escala/mapeo exige
revisión humana. Históricos conservan sus refs. GET/POST de perfil/preparación legados
siguen sus contratos actuales; la capa v2 normaliza a C4 sin alterar v1.

Ejemplo sintético de cambio de escala/mapeo, fragmento de `variables` (no request completo):

```json
{"id":"33333333-3333-4333-8333-333333333333","column_ids":["44444444-4444-4444-8444-444444444444"],"measurement_scale":{"value":"nominal"}}
```

`P/datasets/{id}/profile` GET lee último perfil y POST `{dataset_revision, confirm:true}`
solicita perfil determinista explícito; perfil no afirma revisión de escalas. Consentimiento
para cálculo con datos no sintéticos se rige por integración, además de propiedad.

## C4 — Intención, perfil, diagnóstico y snapshot (S02 estructura; S04 comportamiento)

Research posee intención/snapshot de fuentes; Statistics el perfil diagnóstico y reglas de
selección; Orchestration coordina/persiste la evaluación. UI/chat consumen DTOs públicos.

`AnalysisIntentV2`: schema_version, id, project_id, revision, created_at/updated_at,
kind=descriptive|association|comparison|reliability|unknown; question:Fact<string> default
null; objective_id:ID|null; hypothesis_id:ID|null (referencias C2 reales, sin obligación);
variable_ids:ID[]; roles:`{variable_id,role:outcome|predictor|group|item|descriptive}[]`;
observations=independent|paired|repeated|unknown (de C2 confirmado o decisión confirmada de
esta intención con provenance); paired_columns:`{before_column_id,after_column_id}`|null;
group_column_id:ID|null; alternative=two-sided|greater|less|unspecified;
alpha:number (0,1), default .05; missing_policy=complete_cases; confirmation:null|Confirmation.
`estimand=summary|linear_association|monotonic_association|mean_difference|distribution_difference|
internal_consistency|unknown`; default unknown, descriptivo permite summary por selección
humana de esa ruta. `conditions` agrupa facts confirmables:
linearity, monotonicity, comparable_group_shapes, difference_symmetry y pooled_variance_justified,
cada uno Fact<yes|no|unknown> default unknown. Son juicios revisados del usuario con ayuda
de diagnósticos, no inferencias certificadas por IA. No son obligatorios fuera de su técnica.
Descriptivos usan alternative=unspecified; inferencia bilateral por defecto explícito al
confirmar la intención; unilateral requiere pregunta direccional confirmada antes de mirar p.
prediction no se añade a este mínimo; v1 conserva sus regresiones.

POST `P/intents` y PATCH `P/intents/{id}` con expected_revision, changes y confirm=true;
GET `P/intents`. `draft→confirmed`; editar genera nueva revisión draft o confirmada mediante
acción explícita; dependencias viejas quedan stale, no se sobrescriben. Unknown guarda
borrador y solicita aclaración. Roles/grupo/pares deben apuntar al diccionario/dataset elegido.

Solicitud mínima de intención descriptiva (IDs de variables existentes):

```json
{"expected_revision":0,"changes":{"kind":"descriptive","estimand":"summary","variable_ids":["33333333-3333-4333-8333-333333333333"],"roles":[],"alternative":"unspecified","alpha":0.05,"missing_policy":"complete_cases"},"confirm":true}
```

`ProfileEvidenceV2`: schema_version, id, project_id, revision=1, dataset_ref, dictionary_ref,
algorithm_version, created_at; total_rows, duplicate_rows (int>=0); por columna:
column_id, storage_type, valid_count, missing_count, unique_count, constant:bool,
possible_identifier:bool, warnings:string[]. Numeric summaries/contingencias pertenecen al
alcance seleccionado, con denominador/missing_policy explícitos. No exportar valores de PII
ni filas a IA. `AnalysisProfile` derivado para una intención añade complete_case_count,
excluded_count, group_counts:`{label,count}[]`, complete_pair_count:int|null,
expected_frequencies:number[][]|null, warnings; referencia perfil/dataset/diccionario/intención.
Conteos por grupo/pares deben usar los mismos casos que cálculo final.

`DiagnosticV2`: schema_version, id, project_id, revision=1, source_refs, created_at,
intent_id, scope:`{column_ids:ID[],checks:string[],missing_policy:"complete_cases",alpha:number}`,
status=completed|not_calculable|failed, algorithm_version, engine_version,
checks:`{name,method,method_version,target:string,case_count:int,statistic:number|null,
p_value:number|null,status:compatible|incompatible|not_checked,details:string}[]`, warnings:string[].
target distingue grupos/diferencias; no emitir passed como demostración de normalidad o
independencia. Not_checked exige razón. Independencia/muestreo requieren confirmación del
estudio; ninguna prueba de distribución los certifica.

Reglas mínimas de selección real S04b (política versionada `priority-selection-v2`):

| Intención y evidencia confirmada | Propuesta o aclaración |
| --- | --- |
| Descriptive + ≥1 variable vinculada | descriptive_summary según escalas; unknown permite perfil, pero pide escala antes de resumir numéricamente códigos ambiguos |
| Association + exactamente 2 variables cuantitativas + estimand=linear_association + linearity=yes | pearson; requiere independencia y diagnóstico vigente, revisión de influencia y límites de inferencia; no seleccionar solo por tipos |
| Association + ordinales/cuanti con orden confirmado + estimand=monotonic_association + monotonicity=yes | spearman; nunca mezcla nominal por descarte; declarar método de p y empates |
| Comparison + 2 grupos independientes + resultado cuantitativo + estimand=mean_difference | t_welch si condiciones revisadas permiten inferencia de medias; t_independent solo alternativa solicitada explícitamente y pooled_variance_justified=yes; no decidir por test de igualdad de varianzas únicamente |
| Comparison independiente + ordinal/cuanti + estimand=distribution_difference | mann_whitney si condiciones/método apropiados; comparable_group_shapes solo habilita interpretar diferencia de localización, no condición obligatoria para contrastar distribuciones |
| Comparison pareada ancha + dos columnas cuantitativas + estimand=mean_difference | t_paired, condiciones evaluadas sobre diferencias; requiere pares completos y variación utilizable |
| Comparison pareada + diferencias con magnitudes ordenables y estimand=distribution_difference + difference_symmetry=yes | wilcoxon; ordinales con distancias no justificadas requieren aclaración, no Wilcoxon automático |
| Reliability + instrumento/mapeo/regla confirmados + estimand=internal_consistency | cronbach_alpha sobre ítems recodificados; no score total como única columna |

Para inferencia de medias/correlación, un diagnóstico incompatible/no concluyente no cambia
automáticamente la pregunta a rangos: needs_clarification pide revisar outliers, modelo de
distribución y objetivo; aceptar alternativa requiere nueva intención confirmada. Los
mínimos de tamaño/método de cálculo se determinan por método validado S04a, no por la regla
de 50. Sin unidad/dependencia, escala, estimand o condición pertinente confirmada se devuelve
needs_clarification. Diseño experimental no es requisito general de una asociación.
`requested_technique: string|null` opcional en intención permite elegir una alternativa de
la allowlist (p.ej. Student); no evita elegibilidad ni aprobación. Técnicas fuera del mínimo
o unilateral no validada: aclaración/limitación explícita, no declarar ejecución validada.
S04a registra umbrales/opciones numéricas del método y fixtures; cambiar la política crea
versión nueva y nuevas propuestas, sin rediseñar estos DTOs.

POST `P/diagnostics` `{intent_id,intent_revision,dataset_id,dataset_revision,checks:string[],confirm:true}`
resuelve diccionario/contexto y crea diagnóstico inmutable (201); GET `P/diagnostics/{id}`.
Checks allowlist inicial: complete_cases, group_sizes, paired_cases, distribution,
normality, homogeneity, influence; cada uno con requisitos y límites S04a. `distribution`
incluye Q–Q/histograma en diagnóstico cuantitativo; influence genera indicadores y solicita
revisión de dispersión, no concluye linealidad/monotonía. Confirmar alcance no aprueba plan
final. Descriptivo puede usar solo perfil; propuesta inferencial exige diagnóstico vigente
con los checks pertinentes, o needs_clarification si falta. No calcular todas las técnicas
ni p de hipótesis finales en esta ruta. No llamar proveedor IA para producir diagnósticos.

`AnalysisSnapshotV2`: schema_version, id, project_id, revision=1, created_at,
context_ref:SourceRef|null, dictionary_ref, dataset_ref, intent_ref, profile_ref,
diagnostic_refs:SourceRef[], instrument_ref:SourceRef|null, score_ref:SourceRef|null,
confirmed_facts (solo facts relevantes con provenance/confirmation), variables (solo elegidas),
intent (revisión congelada), source_fingerprint:Hash. Sin hipótesis obligatoria ni
methodology_status. Lectura de bytes: puerto Research `read_dataset(principal,project_id,
dataset_id,expected_hash)->bytes`, tras autorización y comprobación de hash; Statistics
recibe tabla/arrays autorizados y snapshot, no principal ni ubicación de objetos.

Orchestration construye snapshot al proponer (no endpoint público que acepte fuentes
confiables del navegador). Valida mismo proyecto, referencias completas y confirmaciones
relevantes. Design unknown no bloquea descriptivos; para inferencia pedir unidad/dependencia,
escalas y pregunta pertinente; muestreo desconocido limita generalización y exige aceptación
visible de esa limitación. No se debe exigir una metodología documental revisada.

## C5 — Propuesta, aprobación, resultado y vigencia (Orchestration + Statistics; S04)

`AnalysisPlanV2`: schema_version, id, project_id, revision=1, snapshot_ref, intent_id,
dataset_id, status=needs_clarification|proposed|approved, technique:string|null (allowlist),
parameters:`{alpha:number,alternative:two-sided|greater|less|unspecified,
missing_policy:complete_cases,calculation_method:string}`;
rationale:string; evidence_refs:SourceRef[]; alternatives:`{technique,reason}[]`;
pending_questions:`{code,field,question}[]`; limitations:string[];
source_fingerprint, proposal_token:Hash; created_at; approval:null|Confirmation.
`calculation_method` es identificador allowlist del motor (p.ej. descriptive-v2,
welch-two-sided-v2), nunca código libre. Incluye opciones exactas/continuidad/ceros del
método elegido mediante un registro de métodos versionado en Statistics; cambiar ese
registro exige nueva versión de motor y nueva propuesta. No parámetros ocultos por IA.

Vigencia separada `validity=current|stale`, invalidated_at:null|DateTime,
stale_reasons:string[]; persistencia conserva payload de plan/aprobación original.
`needs_clarification` tiene technique=null si no hay elección defendible, no es aprobable;
`proposed` no tiene preguntas bloqueantes y es elegible; `approved` necesita acción humana
y token exacto. Resolver preguntas crea **nuevo plan ID** mediante nueva propuesta, nunca
reescribe el aprobado. Una nueva aprobación no resucita un plan stale.

`proposal_token` = SHA256 del plan inmutable sin status/approval/token + snapshot completo
canónico + source_fingerprint + versión de políticas/motor. Sirve para detectar propuesta
distinta, no para autorizar identidad. Recalcular fuentes/token antes de aprobar, leer bytes,
ejecutar y publicar resultado. Cambios concurrentes al finalizar cálculo: guardar salida
como histórica stale y no devolverla como vigente; no perder el intento auditado.

| Operación prevista | Request / respuesta y guardas |
| --- | --- |
| POST `P/analysis/plans` | `{intent_id,intent_revision,dataset_id,dataset_revision,diagnostic_ids:ID[]}` → 201 PlanV2; perfil/snapshot resueltos en servidor; aclaración también se persiste |
| GET `P/analysis/plans` / `/{id}` | Plan, validity y execution_status; no recalcula números |
| POST `P/analysis/plans/{id}/approve` | `{proposal_token,confirm:true}` → plan approved; verificar dueño, fuentes, evidencia, consentimiento; stale/token incorrecto 409 |
| POST `P/analysis/plans/{id}/execute` | `{proposal_token,request_id:UUID}` → 200 ResultV2; misma clave/plan retorna mismo resultado; distinta clave en plan ya completed no recalcula; no aprobado/stale 409 |
| GET `P/analysis/results` / `/{id}` | Histórico y estado actual, sin reejecutar; resultado ajeno 404 |
| GET `P/analysis/results/{id}/export?format=txt|docx|pdf` | Solo completed+approved+current y autorización de datos; usa payload persistido, no cálculo; 409 si stale |
| GET `P/analysis/results/{id}/figures` | Figuras especificadas por resultado vigente, límites y muestreo determinista; no endpoint genérico de filas |

`execution_status=not_started|running|completed|failed` en registro de aplicación; CAS/lock
evita doble ejecución. Inicio explícito, completed/failed terminal para ese intento; retry de
fallo requiere nuevo request_id y guardas vigentes; fallos conservan historial de intentos.
No usar tareas volátiles para prometer persistencia de running; S07 define recuperación
de intentos interrumpidos como failed/interrupted sin afirmar cálculo completado.

`AnalysisResultV2`: schema_version, id, project_id, revision=1, analysis_plan_id,
snapshot_ref, dataset_id, status=completed|failed|not_executed, created_at, engine_version,
method_version, source_fingerprint, case_counts:`{total,used,excluded,groups:[{label,count}],
pairs:int|null}`; metrics:`{key,label,value:number|null,unit:string|null,reason:string|null}[]`;
tables:`{id,title,columns:[{key,label,type:number|string}],rows:object[]}[]`;
figures:`{id,type,source_metric_keys:string[],caption}[]`;
assumptions (checks C4); warnings:string[]; limitations:string[];
interpretation:null|`{text,metric_keys:string[],source:template|ai,review_status:draft|reviewed}`.
Null métrica exige reason; no inventar cero. Failed/not_executed no contienen métricas de
inferencia ni interpretación concluyente. Métricas p=0 por redondeo se muestran como límite,
no probabilidad exactamente nula. IA solo referencia keys existentes y no escribe metrics.
Validez actual del resultado se deriva de su plan/fuentes y se devuelve en envelope de lectura.

Ejemplo completo de aprobación (token sintético ilustrativo, no credencial):

```json
{"proposal_token":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","confirm":true}
```

## Invalidez y dependencias (C2–C6)

`source_fingerprint` combina hashes/revisiones **relevantes** de dataset activo, diccionario
seleccionado, intención, facts confirmados usados, perfil, diagnóstico y, si aplica,
instrumento/mapeo/score, además de versiones de políticas. Declarar `dependency_fields`
JSON Pointer en snapshot (lista string[] obligatoria) para la proyección exacta de contexto
y diccionario usada; nunca comparar solo fechas. Mantener revisión íntegra para auditoría,
comparar hash de proyección para vigencia. Cambios en campos no consumidos no invalidan;
si el adaptador no puede demostrar independencia, invalidar conservadoramente.

| Cambio | Consecuencia |
| --- | --- |
| Dataset activo, bytes/hoja, receta de preparación o declaración/autorización de datos | Nuevo perfil/diagnóstico/snapshot; planes afectados stale; autorización ligada a fuente se revisa |
| Escala/missing markers/orden/mapeo seleccionado, intención o dependencia/unidad usada | Diagnósticos/propuestas afectados stale; confirmar nueva revisión y volver a proponer |
| Ítem/regla/inversión/mapeo del instrumento | Score y análisis dependientes stale; no tocar análisis ajenos al instrumento |
| Alfa/alternativa/método del plan | Crear propuesta nueva y aprobación; no editar parámetros de plan aprobado |
| Nombre/descripción del proyecto, notas complementarias no usadas, conversación nueva | No invalida cálculos; actualizar presentación/contexto del chat |
| Fuente eliminada/inaccesible | Stale con razón; histórico preservado; fallo de proveedor temporal se informa sin afirmar cambio de contenido |

Stale es terminal para ese snapshot/plan. Históricos no se borran; conservan evidencia y
aprobación de su momento. Lectura histórica permitida al dueño; exportación/re-ejecución
vigente bloqueadas como en la demo actual. El chat distingue histórico de actual.

## C6 — Instrumento y puntuaciones (Research / Statistics / Orchestration; S05)

Base verificada: `shared/instrument_contracts.py` y reexports Research definen ítems,
dimensiones, indicadores, opciones, reglas sum/mean y all_required; provenance v1 exige
methodology_review_* incluso en manual. No reutilizarlo con revisión inventada.
Crear `InstrumentContextV2`, versionado en familia v2, que conserva estructuras e invariantes
de variables/dimensiones/indicadores/ítems/reglas v1, con estas diferencias explícitas:

| Campo | Acuerdo |
| --- | --- |
| Cabecera | schema_version=2.0.0; instrument_id, project_id, revision>=1, created_at/updated_at; status=draft|reviewed|stale; confirmation:null|Confirmation |
| provenance | `{source_kind:manual|document,context_ref:SourceRef,source_document_ref:SourceRef|null,legacy_methodology_ref:SourceRef|null}`; contexto confirmado pertinente obligatorio al revisar; documento opcional solo para source_kind=document |
| variables/dimensions/indicators/items | ≥1 cada colección; IDs únicos y jerarquía consistente; methodology_variable_id v1 se reemplaza por context_variable_id:ID|null hacia diccionario C3; nunca inventar variable metodológica |
| item | Conserva text, response_type=single_choice|numeric, response_options(code,label,numeric_value), valid_min/max, reverse_scored y reverse_rule; números finitos, códigos únicos, inversión requiere límites explícitos; ordinalidad de ítem no autoriza tratar nominal como score |
| scoring_rules | Reglas con ID, scope=dimension|instrument, dimension_id|null, item_ids únicos no vacíos, aggregation=sum|mean, missing_policy=all_required y confirmación por revisión; suma/promedio sin imputación |
| mapping | Recurso separado `InstrumentMappingV2`: id, revision, instrument_ref, dataset_ref, item_columns:[{item_id,column_id}], status=draft|confirmed|stale, confirmation; 1:1, cobertura completa para confirmar, sin identificadores |

POST/GET/PATCH `P/instruments`; PATCH `/{id}` con expected_revision y contenido editable;
POST `/{id}/confirm` `{expected_revision,confirm:true}`; GET `/{id}/revisions`.
PUT `/{id}/mapping` con expected_revision/instrument_revision/dataset_id/dataset_revision/
item_columns/confirm; backend deriva refs y actor. Revisión del instrumento confirma reglas
y estructura; mapeo se confirma aparte. `draft→reviewed`; editar reviewed crea nueva revisión
draft, invalida mapeo/score antiguos; fuente cambiada→stale. Para volver a usar crear nueva
revisión y reconfirmar, no quitar stale de históricos.

Puntuaciones: Orchestration coordina Research (fuentes/derivado), Statistics (recodificar y
calcular puro). POST `P/instruments/{id}/score-previews` con `{expected_revision,mapping_revision,
scoring_rule_id,confirm:true}` → `ScorePreviewV2`: id, source_refs, fingerprint, expires_at,
scoring_engine_version, rule_id, counts:{total,valid,missing}, column_name, bounded_preview,
warnings. No calcular alfa en preview público: el preview interno actual incluye reliability,
por lo que debe separarse/suprimirse ese cálculo en el adaptador público, no solo ocultarlo.
Un score es preparación explícita y revisable, no aprobación de la inferencia final.

POST `P/instruments/{id}/scores` `{preview_id,fingerprint,confirm:true,request_id:UUID}` crea
ScoreRecordV2 (schema_version=2.0.0,id,project_id,revision=1,source_refs,rule_id,engine_version,
fingerprint,derived_dataset_ref,derived_column_id,counts,confirmed_by:ID,confirmed_at:DateTime).
IDs/refs/conteos tienen los tipos comunes/C3; engine_version es string no vacío.
Repetición idempotente;
preview expirado/cambio de fuente=409. Derivado conserva fuente y posición de filas (null en
fila incompleta), no sobrescribe columnas ni activa el nuevo dataset sin selección humana.
Nombre de score no colisiona; error 422 requiere escoger otro nombre. Todo es durable.
Después confirmar diccionario de score para usarlo como cuantitativo en análisis posterior.

Alfa se propone/aprueba/ejecuta por C4–C5 con kind=reliability y fuente de ítems recodificados
conservada por puerto autorizado. Nunca calcular alfa usando solo total; ni asumir que todos
los ítems miden un constructo. Not_calculable (casos/variación insuficientes) se registra como
not_executed con razones; alfa negativo es valor posible con advertencia, no se recorta.
Ejemplo conceptual de recodificación: límites 1/5, reverse_scored=true,
reverse_rule=min_plus_max_minus_value: respuesta 2 produce 4 antes de sumar/promediar.

## C7 — Contexto del tutor (Conversation/Orchestration → proveedor/UI; S06)

`TutorContextV2`: schema_version, project_id, stage=home|context|data|analysis|results,
context_fingerprint, source_refs, confirmed_summary (facts permitidos), pending_questions,
data_summary (metadatos/conteos agregados sin filas/PII), intent_summary,
current_plan_ref:SourceRef|null, current_result_ref:SourceRef|null,
historical_refs:SourceRef[], allowed_actions:`{kind:open|propose_update|request_diagnostic|
request_proposal,resource_id:ID|null,label:string}[]`, warnings.
Research aporta fuentes por puertos; mismo servicio C4/C5 para recomendar desde chat y UI.
Un cambio de etapa/fuentes reconstruye contexto; fingerprint se guarda con cada mensaje.
No exigir una metodología/hypothesis_id al no existir. Las fuentes declaradas por usuario
en texto no reemplazan las verificadas del servidor.

MessageDraftV2 en `POST P/conversations/{id}/messages`: content string 1–16000,
request_id:UUID, stage (enum anterior), external_ai_consent=true,
consent_scope="tutor_context_v3". El v2 de familia de contratos no es el antiguo alcance
`research_context_v2`: no asumir consentimiento previo para nuevas fuentes/instrumento.
Requiere consentimiento revocable del dueño; respuesta contiene mensaje y contexto usado,
refs de métricas/fuentes y acciones propuestas. Sin consentimiento se informa 403 al enviar
al proveedor; ayuda estática y formularios continúan. Proveedor ausente 503/cuota 429 con
mensaje claro, sin simulación de respuesta exitosa.

Una actualización IA produce SuggestionV2 separado, nunca PATCH directo al contexto.
Aceptar valores usa C2/C3 y confirmación humana; diagnósticos/propuesta usan botones que
explican alcance; aprobación/ejecución solo C5. «Sí» escrito al chat no firma aprobación.
Explicaciones basadas en ResultV2 citan metric keys existentes; sin resultado no presentar
números inventados. Mantener consentimiento de extracción documental separado. Redactar
identificadores/nombres/categorías sensibles antes de enviar, limitar tokens y no enviar
dataset completo. Auditoría registra refs/versiones, no secretos ni prompts con PII.

## Entrega y comprobaciones de contratos por implementar

S01: compatibilidad C1 y preservación académica. S02: C2/contexto vacío, CAS/confirmación y
estructura de intención/snapshot. S03: diccionario sin escala inferida y linaje. S04:
recomendación real, inputs v2 a funciones puras, token/fuentes/estados/race/idempotencia y
regresión v1. S05: procedencia manual real, score e históricos. S06: consentimiento/fuentes
y propuestas separadas. Trabajo paralelo: todos pasan por principal y acceso a proyecto,
incluidos exports y lectores internos. S07 verifica juntos: una pantalla funcional no
acredita contrato seguro, ni contrato diseñado acredita funcionalidad implementada.
