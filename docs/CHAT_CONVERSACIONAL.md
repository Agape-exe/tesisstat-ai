# Chat conversacional — Sesión 15A

Implementación del 2 de noviembre de 2026, basada en `origin/develop` (`f507f4f`, PR #25).
Rama: `feat/chat-conversacional`. Demostración local sin autenticación; usar solo datos ficticios.

## Objetivo y comportamiento

La cuarta sección de una investigación, **Asistente IA**, permite crear varias conversaciones,
enviar preguntas, continuar turnos, consultar mensajes anteriores y eliminar conversaciones con
confirmación. SQLite conserva el historial después de reiniciar el backend. La URL conserva el
proyecto y la sección al recargar; `sessionStorage` recuerda únicamente el identificador de la
conversación seleccionada por proyecto. Los mensajes no se guardan en el almacenamiento del navegador.

El chat solicita consentimiento explícito antes de habilitar el envío al proveedor externo.
El consentimiento se vuelve a solicitar al recargar o volver a montar el chat. El backend también
exige `external_ai_consent: true` en cada envío. Es una declaración del cliente, no autenticación
ni un registro legal de consentimiento. Sin configuración de Cloudflare se pueden organizar
conversaciones y consultar mensajes, pero el envío queda deshabilitado en la interfaz.

El sistema no utiliza respuestas de demostración en ejecución normal. Solo las pruebas inyectan
proveedores simulados. Si falla el proveedor, no se crea un mensaje del asistente.

## Arquitectura y archivos

`backend/app/modules/conversation/` contiene:

| Archivo | Responsabilidad |
| --- | --- |
| `__init__.py` | Límite del módulo conversacional |
| `models.py` | Conversation, Message, entradas estrictas y errores controlados |
| `ports.py` | Protocolos ConversationRepository y ResponseGenerator |
| `sqlite_repository.py` | Persistencia, orden, paginación y reserva idempotente de turnos |
| `context.py` | Mensaje de sistema y selección acotada de pares recientes |
| `service.py` | Casos de uso independientes de FastAPI y errores de IA en español |
| `routes.py` | Adaptador HTTP del servicio |

`frontend/src/features/conversation/` contiene:

| Archivo | Responsabilidad |
| --- | --- |
| `api.ts` | Tipos y cliente de la misma API local utilizada por Research |
| `ConversationChat.tsx` | Encabezado, conversaciones, mensajes, consentimiento, editor y diálogo |
| `conversation.css` | Estilos propios, distribución de dos columnas y adaptación móvil |
| `api.test.ts` | Contrato HTTP, errores y paginación |
| `ConversationChat.test.tsx` | Interacciones y estados con proveedor simulado |

Pruebas backend nuevas: `backend/tests/research/test_conversation.py`.
Documentación nueva: este archivo y `docs/PR_CHAT_CONVERSACIONAL.md`.

### Archivos compartidos modificados

| Archivo | Cambio mínimo e impacto de integración |
| --- | --- |
| `backend/app/modules/research/dev_app.py` | Componer el chat, inyectar proveedor de pruebas, limitar cuerpo y traducir errores |
| `backend/app/shared/adapters/cloudflare.py` | Añadir `chat()` textual y compartir transporte acotado con `generate()`; extracción conserva JSON Schema |
| `backend/.env.example` | Documentar límites configurables sin secretos |
| `frontend/src/features/research/projects/ResearchProjects.tsx` | Cuarta sección, restauración por URL y conservación de paneles visitados |
| `frontend/src/features/research/projects/ResearchProjects.test.tsx` | Probar navegación y recarga; aislar el hash entre pruebas |
| `README.md` | Enlace de acceso a la nueva guía |

No se modificaron dependencias, `app.main`, Statistics, informes, los archivos de orquestación
protegidos ni los seis contratos v1.0.0. No se añadió otro servidor a la aplicación normal.
Los paneles ya visitados permanecen montados al cambiar de sección para conservar formularios.
Si se modifican fuentes después de abrir Paquete, su botón existente de actualizar fuentes
permite recargar el estado; el backend mantiene sus comprobaciones de vigencia y aprobación.

## API

Prefijo: `/api/research/projects/{project_id}/conversations`.

| Método y ruta relativa | Operación |
| --- | --- |
| `POST /` (sin barra final) | Crear; cuerpo `{"title":"Consulta de metodología"}`; 201 |
| `GET /` (sin barra final) | Listar por actualización descendente; `?offset=0` |
| `GET /status` | Estado local de configuración, modelo y límites; no llama al proveedor |
| `GET /{conversation_id}` | Conversación y página reciente de mensajes en orden ascendente |
| `GET /{conversation_id}?before=51` | Recuperar mensajes anteriores a la secuencia 51 |
| `POST /{conversation_id}/messages` | Reservar turno, generar y persistir respuesta |
| `DELETE /{conversation_id}` | Eliminar conversación y mensajes; 204 |

Ejemplo de envío con datos ficticios:

```json
{
  "content": "¿Qué diferencia hay entre variable e hipótesis?",
  "request_id": "37ae1f8e-93b8-4f20-8dbf-d559edc2d847",
  "external_ai_consent": true
}
```

La respuesta de envío contiene `messages`, el par `user`/`assistant` persistido. La consulta
contiene `conversation`, `messages` y `has_more`. Los límites de página se aplican en backend.
Los identificadores deben ser UUID. Se comprueban proyecto, conversación y pertenencia en cada
operación. No se admiten campos adicionales, roles elegidos por el cliente, mensajes de sistema,
texto vacío ni entradas superiores al límite configurado. Los mensajes se muestran como texto
escapado por React; no se interpreta HTML ni Markdown con HTML.

Errores: 404 para recursos ausentes o conversaciones de otro proyecto; 422 para entradas
inválidas; 409 para reserva activa, clave reutilizada o intento vencido; 413 para cuerpo excesivo;
503 para configuración, cuota, autenticación, respuesta inválida o almacenamiento; 504 para timeout.
Los errores de IA incluyen `code` y `detail` sanitizados.

## Persistencia y concurrencia

Se utiliza `RESEARCH_DB_PATH`, el mismo archivo SQLite local de Research:

- `conversations`: id, project_id, title, created_at y updated_at.
- `conversation_messages`: id, conversation_id, request_id, role, content, created_at y sequence.
- `conversation_requests`: clave compuesta conversation_id/request_id, contenido, estado y fecha.

`BEGIN IMMEDIATE` reserva un turno antes de contactar al proveedor. Solo se permite un turno
pendiente por conversación, incluso con varias instancias del servicio sobre la misma base.
Las restricciones únicas protegen secuencias, roles del turno y solicitudes repetidas.
La respuesta y el estado completado se guardan en una sola transacción.

Repetir una solicitud completada devuelve el mismo par, incluso después del reinicio, sin
otra llamada a IA. Reutilizar la clave con otro contenido devuelve 409. Una solicitud fallida
o en curso no se reenvía automáticamente. El estudiante debe consultar el historial y decidir
si quiere un nuevo envío, que utiliza otro UUID. No se garantiza entrega exactamente una vez
ante un cierre entre la respuesta externa y su persistencia; se evita repetir el consumo
automáticamente. Las reservas interrumpidas se invalidan al reservar otro turno después del
timeout configurado más diez segundos. Una respuesta vencida no puede sobrescribir el turno nuevo.

El mensaje del estudiante se guarda antes de generar. Si falla la IA, puede quedar sin respuesta
en el historial; no se utiliza ese turno fallido en el contexto de llamadas posteriores. Si falla
el almacenamiento al completar, la respuesta no se presenta como persistida. La interfaz vuelve
a consultar el historial ante una entrega incierta y bloquea el envío si esa recuperación falla.

Claves foráneas y triggers eliminan mensajes y solicitudes al borrar una conversación. Un trigger
adicional limpia conversaciones al eliminar un proyecto, también desde las conexiones existentes
que no habilitan claves foráneas. No se alteran tablas previas ni se migran datos de otros módulos.
Los puertos permiten sustituir este repositorio por otro, por ejemplo Supabase en una sesión futura.

## Qwen3 y configuración

Modelo previsto: `@cf/qwen/qwen3-30b-a3b-fp8`, mediante `CloudflareLanguageModel.chat()`.
Se revisó la [documentación oficial del modelo](https://developers.cloudflare.com/workers-ai/models/qwen3-30b-a3b-fp8/)
el 2 de noviembre de 2026: mensajes de chat, endpoint REST `ai/run`, límite de salida y respuesta
de completado. Se aceptan envolturas `result.response` y `choices[].message.content`.
`generate()` conserva su formato estructurado para extracción metodológica; `chat()` no envía
`response_format` ni herramientas. Se descarta el razonamiento separado y se retira un bloque
inline `<think>…</think>`; respuestas vacías, truncadas o con razonamiento sin terminar se rechazan.

Variables solo en el backend, nunca en `VITE_*`:

| Variable | Valor predeterminado / uso |
| --- | --- |
| `APP_ENV` | `development`; otros entornos rechazan la app de demostración |
| `CLOUDFLARE_ACCOUNT_ID` | Identificador de cuenta, 32 caracteres hexadecimales |
| `CLOUDFLARE_API_TOKEN` | Token privado con permisos para Workers AI |
| `CLOUDFLARE_MODEL` | `@cf/qwen/qwen3-30b-a3b-fp8` |
| `CLOUDFLARE_TIMEOUT_SECONDS` | 45; entre 1 y 120; timeout de transporte y comprobaciones de deadline |
| `CLOUDFLARE_MAX_INPUT_TOKENS` | 12000; presupuesto conservador basado en bytes UTF-8 |
| `CLOUDFLARE_MAX_OUTPUT_TOKENS` | 4096; límite compartido del adaptador |
| `CONVERSATION_MAX_MESSAGE_CHARACTERS` | 2000; máximo configurable 16000 |
| `CONVERSATION_PAGE_SIZE` | 50; entre 2 y 200 |
| `CONVERSATION_HISTORY_TURNS` | 8 pares completados recientes; entre 0 y 50 |
| `CONVERSATION_MAX_REQUEST_BYTES` | 32768; límite del cuerpo HTTP, también sin Content-Length |
| `CONVERSATION_MAX_CONTEXT_BYTES` | 10000; ajustado también al presupuesto del adaptador |
| `CONVERSATION_MAX_OUTPUT_TOKENS` | 1024; acotado al límite compartido |
| `RESEARCH_DB_PATH` | `.cache/research/projects.sqlite3` |
| `CORS_ORIGINS` | Orígenes locales permitidos; ver `.env.example` |

No hay reintentos, redirecciones ni proveedores alternativos. El adaptador limita la respuesta
de transporte a 128 KiB y el servicio limita el texto aceptado a 64 KiB. El presupuesto de entrada
usa bytes de forma conservadora; no es una medición exacta del tokenizador de Qwen3.
No se registran conversaciones ni credenciales. Las pruebas de transporte usan tokens ficticios.

**Estado comprobado:** la configuración local fue evaluada como no configurada, sin mostrar
valores privados. No hubo solicitudes reales a Cloudflare ni consumo de cuota. La conectividad
y la calidad de respuesta del modelo real quedan pendientes de credenciales válidas y autorización
expresa. Las pruebas simuladas no acreditan conectividad real.

## Inicio y acceso

Desde la raíz del repositorio, en dos terminales:

```powershell
cd backend
uv sync --locked
uv run uvicorn app.modules.research.dev_app:app --reload --host 127.0.0.1 --port 8001
```

```powershell
cd frontend
npm ci
npm run dev
```

Abrir [http://localhost:5173/](http://localhost:5173/), crear o abrir una investigación ficticia,
seleccionar **4. Asistente IA** y crear una conversación. `VITE_RESEARCH_API_BASE_URL` utiliza
la API local integrada, por defecto `http://127.0.0.1:8001`.
Una vez configurado el proveedor y autorizado su uso, aceptar el aviso explícito del chat.
Enter envía; Shift+Enter inserta una línea; Enter durante composición IME no envía.

Secuencia ficticia sugerida para una prueba real posteriormente autorizada:

1. Preguntar «¿Qué es una variable cuantitativa?».
2. Continuar «¿En qué se diferencia de una variable cualitativa?».
3. Revisar la respuesta, recargar, consultar ambos turnos, crear otra conversación y volver.
4. Abrir otra investigación, comprobar separación y eliminar la conversación de prueba.

No se incluye una respuesta atribuida a Qwen3 porque no fue verificada.

## Pruebas y resultados

Backend, desde `backend/`:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m scripts.export_contracts --check
uv run python -m compileall -q app scripts tests
```

Frontend, desde `frontend/`:

```powershell
npm test
npm run lint
npm run format:check
npm run contracts:generate
npm run build
npm run build:research
```

Resultados locales del 2 de noviembre de 2026:

| Comprobación | Resultado |
| --- | --- |
| Pytest completo | 298 aprobadas, incluidas 48 nuevas de conversación |
| Vitest completo | 87 aprobadas en 19 archivos |
| Ruff check | Aprobado |
| Ruff format --check | Aprobado, 125 archivos |
| ESLint | Aprobado, sin advertencias |
| Prettier | Aprobado |
| TypeScript | Aprobado con `tsc -b` en build |
| Build principal | Aprobado; incluye aplicación, Research y demo Statistics |
| Build Research independiente | Aprobado |
| Contratos backend y generación frontend | Aprobados; diff vacío de contratos y tipos generados |
| Compilación Python | Aprobada |

Las pruebas cubren CRUD, reinicio, dos turnos, aislamiento, consentimiento, roles, tamaños,
idempotencia persistida, concurrencia, timeout, cuota, credenciales, respuesta inválida,
fallos de almacenamiento, HTML escapado y ausencia de ejecución estadística desde el chat.
Las nuevas pruebas backend bloquean el transporte de red por defecto. No se eliminaron pruebas previas.

Se verificó el recorrido en navegador contra una base ficticia aislada y un proveedor inyectado
que rotulaba cada respuesta como **PROVEEDOR SIMULADO; NO ES QWEN3**. Los puertos normales
8001/5173 estaban ocupados y se respetaron sus procesos: se usaron 8011/5181 con orígenes locales
y credenciales vacías. Este servidor temporal no forma parte del producto ni se publica.
Se comprobaron creación del proyecto, acceso, procesamiento, dos turnos, F5, otra conversación,
cambio de historial, eliminación y acceso a las secciones previas. Las capturas son QA local,
no evidencias finales para Notion. La persistencia tras reinicio del servicio se probó con Pytest.

El estado de publicación y CI se registra en la descripción del PR y en el informe final;
los resultados locales por sí solos no acreditan una ejecución de GitHub Actions.

## Límites, errores conocidos y sesiones siguientes

Solo se incorpora el título obtenido con ProjectService y pares recientes completados. El sistema
declara que no conoce documentos, hipótesis, objetivos ni resultados. El mensaje de sistema es una
orientación de comportamiento; no garantiza que el modelo nunca se equivoque. No hay herramientas
de cálculo, aprobación, ejecución estadística, modificación de documentos ni acceso a archivos.

No existen autenticación multiusuario, Supabase, streaming, edición de mensajes, renombrado de
conversaciones ni paginación por cursor para la lista de conversaciones. Los títulos nuevos
utilizan el nombre genérico y la fecha para distinguirse. La lista usa offset; cambios simultáneos
de orden pueden requerir actualizarla. La separación por proyecto no equivale a control de acceso
entre usuarios. La API solo admite loopback y APP_ENV=development, como la demo previa.

Si se elimina una conversación desde otra ventana, el identificador recordado puede devolver 404;
se muestra el error y se puede seleccionar otra o crear una nueva. Un fallo externo puede dejar
un mensaje del estudiante sin respuesta. Los mensajes y las solicitudes idempotentes se conservan
sin vencimiento hasta eliminar la conversación. No hay bloqueo funcional conocido en las pruebas
con proveedores simulados; la integración con Cloudflare real permanece sin verificar.

Sesión 16A: incorporar contexto verificado de objetivos, variables, hipótesis, ResearchPackage
y resultados mediante `context.py`, sin confiar en identificadores contenidos en el texto del usuario.
Sesión 17A: implementar agentes especializados y LangGraph usando `ResponseGenerator` y
ConversationService. En esta sesión no se implementó LangGraph ni se crearon agentes ficticios.

La rama y el PR quedan para revisión humana. No se fusionan automáticamente ni se continúa con
las sesiones 16A o 17A.
