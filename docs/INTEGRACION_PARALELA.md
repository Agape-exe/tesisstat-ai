# Acuerdo de integración, identidad y persistencia

Normativo S00, 9 de noviembre de 2026. Diseño para los siguientes chats; no autentica,
migra ni despliega nada en S00. Complementa [contratos](CONTRATOS_EVOLUCION.md) y
[alcance/sesiones](ALCANCE_Y_SESIONES.md). La división fina del compañero se decidirá después.

## Decisión viable de proveedores

Mantener el monolito modular FastAPI/Python 3.12; React/Vite como frontend estático.
Destino: **Supabase Auth + PostgreSQL + Storage privado**, Cloudflare Workers AI mediante
adaptador existente, Vercel para frontend y Render para cómputo backend de demostración remota.
El presupuesto sigue S/0. No aprovisionar, contratar, añadir tarjeta ni habilitar upgrades.
La arquitectura se prepara para usuarios autenticados; planes gratuitos no constituyen una
promesa de disponibilidad de un servicio de producción. Si no encajan las condiciones o
cuotas al desplegar, mantener la demostración local y registrar el bloqueo.

Revisión del estado real: `backend/app/shared/ports.py` anticipa IdentityProvider,
ObjectStorage.read y ResearchRepository.get(owner_id); `shared/adapters/supabase.py` es
un placeholder con NotImplementedError, no conexión implementada. Los repositorios actuales
son SQLite, con payload JSON y archivos locales. `research.dev_app` monta el recorrido
integrado sin autenticación con guardas loopback/development; `app.main` solo monta salud.
No basta cambiar la URL de frontend o desplegar app.main para obtener el producto integrado.

Evidencia oficial consultada el 9 de noviembre de 2026 (revalidar antes de desplegar):

| Fuente | Hecho relevante y consecuencia de diseño |
| --- | --- |
| [Supabase JWT](https://supabase.com/docs/guides/auth/jwts) y [signing keys](https://supabase.com/docs/guides/auth/signing-keys) | JWT verificable por servidor, claves públicas JWKS con rotación; usar algoritmo asimétrico configurado, no confiar en decode sin verificar |
| [Supabase Storage](https://supabase.com/docs/guides/storage/security/access-control) | Políticas RLS regulan objetos; claves privilegiadas pueden eludirlas. Bucket privado y acceso acotado por dueño/proyecto |
| [Supabase Free](https://supabase.com/pricing) | Referencia consultada: 500 MB de base, 1 GB archivos, 5 GB egress y pausa tras una semana inactivo; validar cuotas del proyecto y prever copia/recuperación |
| [Render Free](https://render.com/docs/free) | Suspende web tras 15 min sin tráfico; filesystem efímero en reinicio/redeploy/suspensión; no discos persistentes Free; Postgres Free expira a 30 días. No usar SQLite/archivos ni ese Postgres como fuente durable |
| [Vercel Hobby](https://vercel.com/docs/plans/hobby) | Uso personal no comercial; revisar elegibilidad real del proyecto/equipo antes de usarlo, sin asumir permiso de plan por ser tesis |
| [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/) | Asignación gratuita diaria limitada; bloquear al agotar presupuesto, sin fallback de pago; conservar recorrido por formularios |

Elección de persistencia: adaptadores Supabase por **Data API con JWT del usuario** para
operaciones ordinarias, RLS y funciones SQL transaccionales con permisos del invocador para
CAS/aprobación/ejecución. Evita mezclar una conexión Postgres privilegiada con un JWT que no
se propaga a RLS. No usar service_role en solicitudes normales. Credenciales de migración
solo proceso administrativo fuera del servidor público; ningún secreto en VITE_* o Git.
En SQLite local se conserva la interfaz de repositorios con implementación equivalente.
No introducir un ORM ni sustituir todas las funciones estadísticas para esta migración.

## Identidad y propiedad

Un proyecto tiene **un dueño**, no colaboración multiusuario en esta entrega.
`project.owner_id: UUID` referencia `auth.users.id` en destino remoto; obligatorio e
inmutable por API. Se asigna desde `Principal.subject` validado, jamás desde body, header
inventado X-User ni nombre/email del usuario. No confiar en user_metadata para permisos.
Proyectos locales anteriores pueden tener owner_id=null exclusivamente en modo local.

Autenticación HTTP: Bearer token de Supabase; validar firma con JWKS del issuer configurado,
algoritmos allowlist (p.ej. ES256/RS256 según configuración real), issuer exacto,
audience configurada, exp y nbf si existe, subject UUID y rol autenticado esperado. Rechazar
anon/service-role como identidad de usuario. Cache JWKS acotada, refresco ante kid desconocido,
timeouts y sin fallback a token sin validar; si verificador no disponible, 503/fallo cerrado.
Rotación/revocación y TTL de caché deben documentarse y probarse: JWKS offline no demuestra
cierre inmediato de sesión. Para revocación estricta añadir comprobación de sesión; no
prometerla si no se implementó. CORS no reemplaza autorización.

Responsabilidades y puertos **previstos**, no cambios ejecutados en S00:

| Límite | Firma/resultado acordado | Responsable |
| --- | --- | --- |
| Identidad HTTP | `IdentityProvider.resolve_user(access_token)->subject` existente se conserva; adaptador verifica token; dependencia crea `Principal(subject:UUID, mode:local|authenticated)` | shared/auth y composition root; entrega paralela |
| Acceso a proyecto | `ProjectAccess.require(principal,project_id)->AuthorizedProject(id,owner_id,mode)`; `list_owned(principal)` | Research aplicación; puerto compartido consumido por Orchestration/Conversation |
| Repositorio | `get/list/add/replace/delete` siempre recibe scope autorizado; CAS `replace(...,expected_revision)->bool`; get ajeno no retorna payload | Adaptadores locales/remotos por módulo |
| Archivos | `ProjectFiles.read(scope,resource_id,expected_hash)->bytes`; write/delete con scope, tipo y límites; generar clave en servidor | Research; Storage detrás del puerto, nunca clave arbitraria desde Statistics |
| Planes/resultados | `AnalysisStore` get/list/add/edit recibe scope; CAS y transacción para aprobar/claim ejecución/publicar | Orchestration; motor Statistics puro |
| Tutor/instrumento | Lectores reciben scope o se construyen con scope; usan acceso al proyecto antes de construir fuentes/preview/extracción | Conversation/Research + puentes Orchestration |

El alcance autorizado es interno e inmutable, creado por ProjectAccess; no DTO que pueda
enviar el navegador. El IdentityProvider legado devuelve string, no necesita cambiar los
seis contratos. Nuevos puertos pueden vivir en `shared/access.py` y `shared/persistence.py`;
acordar sus cambios una sola vez. Statistics recibe tablas/snapshots ya autorizados sin
importar autenticación, repositorios Research ni SDK Supabase.

Todos los recursos heredan autorización por project_id: documentos y sus extracciones,
metodologías/contextos y revisiones, datasets/perfiles/preparación/derivados/diccionarios,
conversaciones/mensajes/consentimientos, instrumentos/mapeos/puntuaciones, paquetes/snapshots,
diagnósticos/planes/aprobaciones/resultados, figuras y exportaciones. Comprobar también que
cada hijo pertenece al padre de la URL. Cambiar un project_id manteniendo un child_id no
permite acceder al hijo. IDs opacos/hash/tokens de propuesta no son permisos.

Errores: sin token/expirado/inválido 401 (WWW-Authenticate: Bearer); usuario válido y recurso
ajeno o inexistente 404 con mismo mensaje; 403 para falta de consentimiento de recurso
propio; 409 revisiones/fuentes/aprobación; 503 proveedor indisponible. No exponer dueño de
otro proyecto en errores/logs. Los errores de dominio los traduce el adaptador HTTP;
Statistics informa problemas científicos sin HTTPException ni identidad.

RLS: `projects.owner_id=auth.uid()` para SELECT/INSERT/UPDATE/DELETE, UPDATE no permite
cambiar owner_id; tablas hijas `EXISTS(projects WHERE id=project_id AND owner_id=auth.uid())`
en USING y WITH CHECK. FKs evitan hijos de proyecto diferente; índices por project_id.
Aplicar también a tablas legadas importadas y tablas nuevas v2. Funciones SQL ordinarias
SECURITY INVOKER, search_path explícito y permisos mínimos; no funciones que eludan RLS.
El servicio verifica acceso aun si RLS existe: defensa en ambas capas.

Storage: bucket privado; claves generadas
`{owner_id}/{project_id}/{resource_type}/{resource_id}/{version}`; sin nombre real en clave.
Políticas verifican prefijo + pertenencia del proyecto, no solo object owner. Preferir
descarga por backend autorizado; URL firmada solo si necesaria tras guardas, TTL breve
(máx.60 s) y sin persistirla en contratos/historial/logs. El path por sí solo no autoriza.

## Modo local y aplicación destino

Mantener comandos/servidores de demo actuales durante el trabajo funcional. No quitar
loopback/local_only de dev_app para conseguir remoto. LocalProvider usa principal
etiquetado `local` y scope exclusivo de sus recursos; ese actor no es un usuario Supabase.
Producción exige APP_ENV/APP_MODE explícitos, configuración de Auth/DB/Storage válidas y
falla al arrancar si falta alguna; nunca selecciona SQLite o actor local por defecto.

Crear factory de aplicación autenticada en entrega paralela, reutilizando servicios/rutas
mediante composición segura. No importar dev_app con sus efectos al arrancar. El comando
remoto se documenta solo al integrar y verificar ese factory; app.main podrá delegar después
de acuerdo en S07, sin afirmar que su estado actual integra el producto. Health público
mínimo no divulga configuración. Demos independientes Statistics/Research no se montan en
el factory remoto; todos los endpoints de producto, incluidos v1, llevan las guardas.
Dependencias del proveedor no deben impedir usar la demo local sin credenciales externas.

Autorización de datos ≠ propiedad ≠ consentimiento IA ≠ aprobación de análisis. Conservar
declaración synthetic explícita y autorización para cálculo no sintético ligada a
proyecto/dataset/hash/snapshot. En destino persistir recibo con usuario, alcance, fuentes,
fecha y revocación; no reutilizar el grant volátil local como autorización remota. Una
aprobación no implica permiso para enviar filas al proveedor. Consentimientos de chat y
extracción independientes, con sus versiones y revocación.

## Durabilidad, migración y anteriores sin dueño

Datos durables en Postgres: proyectos, contexto/revisiones/provenance/confirmaciones,
documentos/metadatos/extracciones, datasets/perfiles/diccionario/recetas, instrumentos y
mapeos, score records, snapshots/diagnósticos, planes/tokens/aprobaciones, intentos/resultados,
conversaciones/mensajes y recibos de consentimiento. Bytes fuente, derivados y exportaciones
persistidas en Storage privado; temporal local solo durante procesamiento y descartable.
No olvidar repositorios de chat/instrumento al migrar únicamente projects.

Estrategia incremental: tablas con columnas indexadas id/project_id/revision/schema_version/
updated_at y payload JSONB validado por modelo para minimizar reescritura; ownership fuera
de payload, con restricciones relacionales. Plan/result refs, unique request_id por plan y
CAS deben ser restricciones/transacciones, no un lock Python entre instancias. Migraciones
SQL versionadas, idempotencia de importador y manifiesto de conteos/hashes, sin alterar
bases locales en sitio. Conservar formatos históricos originales.

Storage y DB no comparten transacción: subir objeto inmutable a staging, verificar hash,
confirmar metadatos en transacción y marcar ready; fallo deja pendiente recuperable y no
recurso visible como listo. Limpieza de huérfanos con manifiesto y reintento explícito;
no incorporar un sistema complejo de colas. Preparaciones/score/resultados no se anuncian
completed hasta persistencia durable. Reintentos no crean dos derivados para la misma clave.

Proyectos locales sin propietario: permanecerán locales. **No asignarlos al primer usuario
que inicia sesión**, ni a una cuenta tomada del email Git. Migración futura requiere comando
administrativo explícito con mapping proyecto→subject validado, inventario/backup, dry-run,
confirmación de la usuaria y copia a destino. Rechazar omisiones/ambigüedad de mapping;
importar árbol completo con manifiesto, fuente/hash y trazas históricas. Si hay conflicto de
IDs, tabla explícita de correspondencias; no reutilizar aprobaciones para nuevas fuentes.
El comando no será endpoint público de «reclamar» IDs. Datos reales/credenciales nunca a Git.

Gate de durabilidad: reiniciar backend y desplegar nueva revisión sin perder registros ni
bytes; recuperar un upload pendiente, intento running interrumpido y duplicado request_id;
exportar copia de DB+objetos y restaurarla en entorno aislado con conteos/hashes iguales.
Respaldos automáticos del plan no se presuponen; copia manual verificada y política de
retención deberán registrarse antes de remoto. No prometer restauración si solo se probó restart.

## Trabajo paralelo sin bloquear el recorrido local

No se asignan aún sesiones C01/C02 ni responsabilidades personales detalladas. Se fijan
paquetes que pueden prepararse desde S00 en copia/worktree propios:

| Paquete | Entrega revisable | Puede avanzar sin S01–S06 | Integración necesaria |
| --- | --- | --- | --- |
| Identidad/acceso | Verificador Supabase, Principal/ProjectAccess, guardas y contrato de errores, factory autenticado | Con puertos/fakes y fixtures sintéticos; sin credenciales no simular validación remota | Research/Orchestration/Conversation pasan scope; acordar una adaptación por servicio |
| Persistencia | Migraciones SQL/RLS, adaptadores Data API/Storage, importador dry-run y pruebas de contratos | Implementar v1 actual y puertos; v2 se agrega conforme S02–S05 integra modelos | Dueño de cada módulo valida modelos; repositorio equivalente local/remoto y CAS |
| Verificación aislada | Matriz dos usuarios, configuración fail-closed, restart/backup | Fakes para pruebas locales; pruebas reales RLS/Auth cuando exista entorno autorizado | S07 exige integración real, no solo mocks |

La entrega paralela no rediseña pantallas, selección estadística o contratos C1–C7 por su
cuenta; la rama funcional no implementa un segundo auth. Mantener la demo local operativa
con adaptadores SQLite y credenciales ausentes. Cambios de interfaz se acuerdan en el documento
normativo con ejemplo y migración; mocks no justifican otra forma de payload.

Archivos de coordinación exclusiva (no modificar a la vez sin acuerdo):

- `backend/app/shared/contracts.py`, `instrument_contracts.py`, nuevos analysis_v2/puertos,
  exportadores, `contracts/`, tipos generados y fixtures.
- `backend/app/modules/research/dev_app.py`, `backend/app/main.py`, `backend/app/core/config.py`,
  nuevas factories: un integrador monta routers/seguridad tras revisar ambas ramas.
- `backend/app/orchestration/analysis_service.py`, `analysis_models.py`, `research_statistics.py`,
  puentes instrumento y `conversation/research_context.py`: funcionalidades y scope se solapan.
- Models/repository/use_cases de projects, datasets, packages, instrument y conversación:
  dueño funcional define modelos; entrega paralela añade adaptadores/puertos coordinados.
- `backend/pyproject.toml`, `uv.lock`, `frontend/package.json`, lockfile, `.github/workflows/ci.yml`:
  agrupar dependencias (SciPy/Auth/SDK) en integraciones pequeñas, no regenerar locks en paralelo.
- Navegación, ProjectWorkspace/ProjectShell, clientes API y auth frontend, README y estos
  acuerdos: una rama por interfaz compartida, informe de cambio al integrar.

Worktree propio desde develop verificado; rama tradicional `<tipo>/<descripcion>`
(`docs/`, `feat/`, `fix/`, `refactor/`, `test/` o `chore/`, según el trabajo); no cambiar ramas de
otra copia. PRs pequeños hacia develop y sin fusionar sin autorización. Registrar commit
base y dependencias; rebase/merge solo de la propia rama de forma acordada sin force push
ni reescribir historial ajeno. Fijar el commit integrado de contratos antes de cambiar consumidores.

## Pruebas obligatorias de aislamiento (entrega paralela y S07)

Dos sujetos A/B con proyectos propios y recursos de cada familia. Ejecutar por API y RLS
directa con sus JWT, además de tests unitarios del verificador:

1. A solo lista su proyecto; B no lee/edita/borra/activa el de A. IDs inexistentes y ajenos
   responden igual; ninguna respuesta contiene payload/metadatos ajenos.
2. Probar todos los hijos: documento/download/extracción, dataset/preview/EDA/preparación,
   contexto/revisiones, conversaciones/mensajes, instrumento/mapeo/score, paquete/snapshot,
   diagnóstico/plan/aprobación/resultado/figura/exportación. Mezclar padre propio/hijo ajeno.
3. Body owner_id falsificado, JWT manipulado/expirado/issuer/audience incorrectos o sin token
   no crean ni mutan recursos; tokens de propuesta de A no sirven para B.
4. Storage deniega acceso directo, listado, subida/sobrescritura y borrado cruzados; claves
   o URLs fabricadas no evaden RLS; autorización de exportación revalida plan/fuente.
5. Dos solicitudes concurrentes no eluden CAS ni ejecutan dos veces; mismo request_id retorna
   lo guardado. Revocación de consentimiento bloquea nueva llamada externa de recurso propio.
6. Modo remoto sin configuración falla cerrado, no monta demos ni cae a SQLite. Local sin
   dueño no aparece al autenticarse. Reinicio/redeploy/recuperación conservan solo datos propios.

Registrar entorno, commits, usuarios sintéticos, pruebas ejecutadas y pendientes. Pruebas
con fakes validan aplicación; no demuestran RLS real ni persistencia del proveedor. S07
solo cierra el gate remoto después de contar con esa evidencia, sin publicar durante S00.

## Recursos C3 integrados en S03A

S03 se divide en S03A y S03B según el alcance aprobado. S03A añade `research/sources/`,
`shared/data_sources_v2.py`, rutas v2 files/sheets/tables y contexto de tabla. Conserva
SQLite/archivos locales; no aprovisiona servicios ni migra datos. La entrega de persistencia
debe incluir `source_files_v2`, `source_file_revisions_v2`, `imported_tables_v2`,
`table_context_revisions_v2`, originales y tablas JSON, además de los recursos anteriores.
Original y extracción son inmutables; selección/contexto tienen CAS e historial.

`SourceService.read_table` es el puerto local de lectura completa para S03B/S04; comprueba
proyecto, padres, inclusión y hash del contenido. `source_refs` resuelve referencias servidor
`source_file|source_sheet|table|table_context`; sus tipos amplían únicamente v2. El contexto
de tabla no altera hashes de datasets legados ni los seis contratos v1. S03B añadirá diccionario,
perfil y derivados, con combinación confirmada por IDs; S04 resolverá varias fuentes por
análisis. El tutor actual no consume estos facts. Autenticación/Storage remoto siguen siendo
entrega paralela pendiente; no se afirma aislamiento de usuarios remotos desde pruebas locales.

Garantías reales de publicación y comando de recuperación de manifiestos:
[API de fuentes](../backend/app/modules/research/sources/README.md). Adaptadores remotos
deberán conservar pertenencia y referencias padre/hijo y extender RLS al árbol completo.

## Recursos C3 incorporados en S03B

`research/data_workspace/` adapta importadas y derivadas a DatasetRefV2 table_json, sin
alterar datasets v1. `TableReadPort` comprueba proyecto, inclusión de antecesores, revisión y
hash esperados antes de devolver todas las filas. S04 consume ese puerto, diccionario y perfil
vigentes; S06 aún no incorpora filas ni facts automáticamente al tutor.

Persistencia remota deberá añadir `data_workspace_revisions_v2` (diccionario/perfil/preview/
recibo histórico) y `derived_content_v2` (contenido completo), con CAS y UNIQUE proyecto/preview,
además de originales/objetos S03A. En SQLite se publican derivado, recibo y diccionario en una
transacción. No trasladar esa garantía a Storage+Postgres sin protocolo de publicación.
El derivado referencia todos sus padres y diccionarios, linaje completo y receta confirmada;
el acceso remoto debe aplicar scope al árbol entero. Hash table-json-v1 y formatos JSON son
explícitos; no reutilizar el hash research-dataset-v1 para estos bytes. No hay nueva aprobación
ni ejecución v2 en esta entrega. Detalle: [API S03B](../backend/app/modules/research/data_workspace/README.md).

## Recurso C2 incorporado en S02B

La migración de persistencia debe incluir `context_suggestions_v2` por proyecto y su recibo
de aplicación. Adaptadores implementan `create_suggestion`, `list_suggestions` y
`suggestion_operation` del puerto de Contexto, además del append existente. Aplicación,
historial y estado/recibo tienen que compartir transacción y exclusión mutua/CAS en DB;
el ID de sugerencia evita duplicados en reintentos. No trasladar esto a locks por proceso.
Autorizar proyecto y pertenencia del hijo en todos los GET/POST y RLS; el ID no autoriza.
No almacenar texto original ni tesis, solo propuesta normalizada y trazabilidad acotada.
Origen de IA permanece al confirmar/corregir; el recibo y el historial permiten auditarlo.
Sin nuevo proveedor, autenticación, despliegue ni cambios de los seis contratos v1.

La corrección de alcance S02B no migra hechos ni históricos: observational_unit general
es opcional; row_meaning sigue en cada tabla C3. observations global es antecedente legado,
no confirmación heredable por intenciones. El adaptador de sugerencias proyecta propuestas
pending/stale antiguas a nota/unknown solo en la vista, conservando su original y recibos.
Aplicación rechaza seleccionar observations en servidor, incluidas solicitudes alteradas.
Persistencia remota debe preservar esta distinción sin reescribir valores/confirmaciones
al migrar ni vincular tablas por nombres. S04 comprobará cada comparación concreta.
