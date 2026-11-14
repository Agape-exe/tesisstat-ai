# Extracción metodológica con IA — sesión 6

Implementación local de Research desde `develop` `09662be`, que incluye la sesión 5
(`c811012`, PR #5). Rama: `feat/research-methodology-ai`. No modifica Statistics ni
los seis contratos compartidos. No genera resultados, pruebas recomendadas, informes
ni ResearchPackage. No se desplegó públicamente.

## Arquitectura y archivos

- `backend/app/modules/research/methodology/models.py`: borrador local y esquema Pydantic.
- `service.py`: caso de uso Research Understanding, puerto MethodologyProvider,
  selección de fragmentos, validación y trazabilidad. Reutiliza `ExtractionService.get`
  de sesión 5; nunca reprocesa PDF/DOCX ni extrae texto automáticamente.
- `repository.py`: puerto de persistencia. `sqlite_repository.py`: adaptador SQLite,
  reserva atómica de intentos, estado, caché, pausa y limpieza al eliminar documentos.
- `routes.py`: endpoints y consentimiento explícito. `research/dev_app.py`: composición
  independiente con inyección de proveedor para pruebas.
- `backend/app/shared/adapters/cloudflare.py`: transporte real Workers AI reutilizable;
  `shared/ai_errors.py`: códigos públicos independientes del proveedor.
- `backend/app/core/config.py`: oculta el token en la representación de Settings.
- `backend/app/orchestration/agents/research_understanding/README.md`: enlaza al caso
  de uso implementado. No se duplica un agente ni se introduce LangGraph todavía.
- `frontend/src/features/research/methodology/`: DTOs locales, cliente HTTP, interfaz y
  pruebas. `documents/ProjectDocuments.tsx` monta la vista dentro del documento abierto;
  los estilos están en `projects/projects.css`.
- `backend/tests/research/test_methodology.py`: pruebas sintéticas de servicio, API,
  persistencia, concurrencia y transporte. Se actualizó la prueba del antiguo adaptador
  esqueleto en `backend/tests/test_module_boundaries.py`.

No se añadieron dependencias. El adaptador usa la biblioteca estándar de Python.

## Modelo metodológico intermedio

`MethodologyDraft` conserva `project_id`, `document_id`, fecha UTC, modelo, versión de
esquema `1`, hash SHA-256 del texto fuente y `review_status: unreviewed`. No contiene
referencia ficticia de dataset ni se convierte a ResearchPackage.

`content` representa título, problema general, objetivo general y objetivos específicos,
hipótesis general y específicas, variables, diseño de investigación, observaciones o
comparación, metodología adicional, advertencias y preguntas. Cada variable agrupa nombre,
rol, escala, dimensiones, indicadores e ítems de instrumento. Estas asociaciones son por
variable; todavía no hay un editor ni relaciones detalladas entre dimensión e indicador.

Cada `Finding` tiene:

```json
{"value": null, "kind": "unknown", "evidence": []}
```

Los otros tipos son `quotation` e `inference`. Un hallazgo conocido necesita valor y
citas textuales. Las citas deben existir exactamente dentro de los fragmentos enviados;
en una cita, el valor también debe aparecer literalmente en la evidencia. El servidor
calcula documento, campo e índices `start`/`end` en el texto guardado (índices Python,
base cero, final exclusivo), sin confiar en offsets creados por el modelo.

Una respuesta JSON incompleta se conserva como información desconocida, con campos
pendientes calculados por el servidor. Campos adicionales, tipos incorrectos, citas
inventadas, JSON inválido y escalas o roles marcados como inferencia invalidan toda la
respuesta. Las inferencias de otros campos se muestran explícitamente y quedan pendientes
de revisión. Las listas vacías también producen pendientes, incluidas las de cada variable.

La existencia de una cita no demuestra que el modelo la interpretó correctamente.
La revisión humana de sesión 7 sigue siendo necesaria, incluso para citas literales.

## Endpoints

Prefijo: `/api/research/projects/{project_id}/documents/{document_id}`.

| Método | Sufijo | Resultado |
| --- | --- | --- |
| GET | `/methodology/status` | Estado, disponibilidad del proveedor, intentos, error público, pausa y borrador si existe |
| GET | `/methodology` | Borrador persistido; 404 si todavía no existe |
| POST | `/methodology/extract` | Analiza o devuelve caché; exige el cuerpo de consentimiento |

```json
{"send_to_external_ai": true}
```

Los tres endpoints comprueban que el proyecto existe y que el documento le pertenece.
No aceptan texto documental ni credenciales en el cuerpo. El POST es síncrono; el estado
`processing` queda visible para otra consulta durante la llamada. Los estados son
`not_started`, `processing`, `completed` y `failed`. Un fallo del proveedor se guarda y
devuelve como estado `failed` con HTTP 200, sin fabricar un borrador.

Errores previos al análisis: 404 proyecto/documento ajeno o inexistente; 422 consentimiento
inválido o texto no disponible; 503 proveedor no configurado; 409 análisis en curso,
pausa activa o máximo de intentos. Los fallos de almacenamiento usan los manejadores
existentes. Nunca se devuelve el cuerpo de error ni un stack trace del proveedor.

## Configuración Cloudflare

Solo variables de entorno del backend, también leídas desde `backend/.env` por Settings.
No usar variables `VITE_*` para secretos. No guardar tokens en Git ni imprimir Settings
serializado. La cuenta debe tener acceso a Workers AI y el token permiso de ejecución.

| Variable | Predeterminado / validación |
| --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | Vacío; ID hexadecimal de 32 caracteres |
| `CLOUDFLARE_API_TOKEN` | Vacío; token exclusivamente en backend |
| `CLOUDFLARE_MODEL` | `@cf/qwen/qwen3-30b-a3b-fp8` |
| `CLOUDFLARE_TIMEOUT_SECONDS` | 45; entre 1 y 120 |
| `CLOUDFLARE_MAX_INPUT_TOKENS` | 12000; entre 4000 y 24000 |
| `CLOUDFLARE_MAX_OUTPUT_TOKENS` | 4096; entre 256 y 8192 |
| `CLOUDFLARE_MAX_CALLS_PER_REQUEST` | 1; límite fijo, rechaza otros valores |
| `RESEARCH_METHODOLOGY_MAX_CHARACTERS` | 6000; entre 200 y 20000 |
| `RESEARCH_METHODOLOGY_MAX_ATTEMPTS` | 3; entre 1 y 5, por documento |
| `RESEARCH_METHODOLOGY_RETRY_SECONDS` | 30; entre 1 y 3600 |

Se conservan `RESEARCH_DB_PATH`, `RESEARCH_DOCUMENTS_PATH`, `CORS_ORIGINS` y los límites
de extracción textual de sesión 5. La configuración inválida de límites impide iniciar
la aplicación para evitar operar sin límites efectivos. Sin cuenta o token, la demo
arranca normalmente y comunica «IA no configurada». Esto no prueba validez de credenciales:
la autorización efectiva solo puede comprobarse haciendo una llamada real explícita.

El adaptador realiza POST HTTPS a
`https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}` con Bearer,
mensajes separados de sistema/usuario, `response_format` con JSON Schema, temperatura 0,
`max_tokens` y streaming desactivado. Admite el envoltorio `result.response` y la salida
actual de Qwen `choices[].message.content`. Rechaza respuestas truncadas por longitud.

Se consultaron la [ficha oficial del modelo](https://developers.cloudflare.com/workers-ai/models/qwen3-30b-a3b-fp8/),
la [API run](https://developers.cloudflare.com/api/resources/ai/methods/run/),
[JSON Mode](https://developers.cloudflare.com/workers-ai/features/json-mode/) y
los [errores de Workers AI](https://developers.cloudflare.com/workers-ai/platform/errors/).
La validación Pydantic local se aplica aunque el proveedor acepte el esquema.

## Consumo, persistencia y seguridad

- Una sola llamada por POST, cero reintentos automáticos, sin fallback ni redirects HTTP.
- Se envía primero contexto inicial y luego ventanas alrededor de palabras metodológicas.
  Se respetan caracteres y un presupuesto conservador de bytes UTF-8 como cota de tokens,
  incluyendo esquema, instrucciones, JSON y reserva de framing. Se evita la aproximación
  caracteres/4, que podría subestimar textos Unicode. La salida usa `max_tokens`.
- Como máximo 128 KiB de respuesta. Timeout de operaciones de red y comprobación de plazo
  entre lecturas `read1`; una operación bloqueada puede extender el plazo hasta otro timeout.
  La reserva de procesamiento dura `2 * timeout + 60` segundos. Se evita una lectura
  ilimitada si llegan bytes lentamente. Tras un cierre abrupto se puede reintentar al vencer
  la reserva, sujeto al máximo de intentos.
- Reserva SQLite `BEGIN IMMEDIATE` por documento evita llamadas simultáneas duplicadas.
  Una respuesta tardía no puede sobrescribir un intento más reciente.
- Un resultado completo se devuelve de caché incluso sin credenciales al reiniciar.
  El documento y su extracción completada son inmutables en este flujo. Cambiar el modelo
  no dispara gasto adicional ni invalida el borrador existente automáticamente.
- Fallos tienen pausa y máximo de intentos persistidos. No hay un endpoint de reinicio
  de ese contador. Al agotar el máximo se comunica el límite; no se insiste automáticamente.
- Trigger SQLite elimina el borrador/estado cuando se elimina el documento, también en
  la eliminación del proyecto. No permite recrearlo si el documento se eliminó en vuelo.
- Texto documental es información no confiable, enviado como JSON en un mensaje de usuario
  separado. Las instrucciones del sistema indican ignorar órdenes dentro del documento.
  No hay herramientas ejecutables, navegación, envío de datasets ni interpretación HTML.
- La interfaz requiere marcar consentimiento y pulsar el botón. Abrir la vista solo hace
  GET local. Cancelar una petición de navegador no garantiza cancelar la llamada ya iniciada
  en el servidor; se debe consultar estado antes de reintentar.
- No se registran documentos, prompts, respuestas de IA, tokens ni errores crudos del proveedor.

## Prueba local

Desde `backend`, configurar las variables privadas en el entorno o `.env` ignorado,
y arrancar (no hace falta configurar Cloudflare para probar el estado deshabilitado):

```powershell
uv sync --locked
$env:CORS_ORIGINS = '["http://localhost:5174"]'
uv run uvicorn app.modules.research.dev_app:app --host 127.0.0.1 --port 8001
```

Desde `frontend`, en otra terminal:

```powershell
npm ci
npx --no-install vite --config src/features/research/vite.demo.config.ts --host 127.0.0.1
```

Abrir `http://localhost:5174/research-demo/`. Crear un proyecto ficticio, adjuntar un
PDF/DOCX sintético y usar «Ver extracción» → «Extraer texto». En «Metodología con IA»,
leer el aviso, marcar consentimiento y pulsar «Analizar metodología con IA». Revisar
objetivos, hipótesis, variables, campos desconocidos, citas, advertencias y preguntas.
Recargar conserva el borrador sin nuevas llamadas. Si el cliente pierde conexión,
usar «Consultar estado de IA» antes de iniciar otro intento.

Sin credenciales se ve el aviso y el botón deshabilitado; proyectos, documentos y texto
siguen funcionando. La validación real con Cloudflare está pendiente de credenciales
válidas y una llamada explícita con documento sintético. No se ha probado conectividad
real ni se afirma haber consumido IA durante las pruebas automatizadas.

## Verificación automatizada

Backend: `uv run --locked pytest`, `uv run --locked ruff check .`,
`uv run --locked ruff format --check .`,
`uv run --locked python -m scripts.export_contracts --check`.

Frontend: `npm test`, `npm run lint`, `npm run format:check`, `npm run build`,
`npx --no-install vite build --config src/features/research/vite.demo.config.ts`.

Se usan exclusivamente documentos y respuestas sintéticas. Las pruebas cubren estructura,
datos incompletos, JSON/campos/citas inválidos, roles y escalas desconocidos, separación de
instrucciones maliciosas, límites, proveedor ausente, timeout/cuota/HTTP, protección de tokens,
propiedad, persistencia, caché, concurrencia, borrado, consentimiento, carga, error y resultados
en interfaz. Incluyen regresión de proyectos, documentos, extracción textual y contratos.

En el sandbox de Windows, asyncio puede bloquearse creando su socket local de TestClient;
la suite se ejecuta fuera del sandbox. Se usa un directorio de caché local para uv y
`--basetemp=.cache/pytest-session6` para mantener archivos temporales dentro del proyecto.
Eso no habilita llamadas reales al proveedor en las pruebas.

Resultado local de cierre: **100 pruebas pytest y 44 pruebas Vitest aprobadas**.
Ruff check/format, exportación de contratos sin cambios, ESLint, Prettier, TypeScript,
compilación Python y builds principal y Research demo aprobados. La comprobación de
interfaz fue automatizada con Testing Library; no se realizó una sesión manual de
navegador ni una llamada real a Cloudflare.

## Pendientes

Sesión 7: editor, revisión y confirmación humana, relaciones finas de instrumentos y
conversión a contratos solo con información suficiente y dataset real vinculado.
No hay grafo multiagente, cola de trabajos ni autenticación. SQLite y archivos son solo
persistencia local; ejecutar en loopback, sin datos personales. No hay Supabase ni cambios
en Statistical Planner. La calidad de interpretación del modelo y su compatibilidad
efectiva deben verificarse con una prueba real autorizada; los dobles no la acreditan.
