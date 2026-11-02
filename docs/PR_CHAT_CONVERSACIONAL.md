## Objetivo

Incorporar el primer chat conversacional de TesisStat AI en **4. Asistente IA** dentro de cada
investigación. El estudiante puede crear conversaciones, enviar preguntas, continuar varios
turnos, recuperar el historial tras recargar o reiniciar y eliminar conversaciones con confirmación.

## Funcionalidades y arquitectura

- Módulo independiente `conversation` con modelos, servicio, puertos, contexto, repositorio
  SQLite y rutas en la API local existente; sin otro servidor de producto.
- Historial ordenado, páginas acotadas, separación comprobada por proyecto y eliminación
  asociada de mensajes y solicitudes.
- Reserva transaccional de turnos, idempotencia persistida y protección ante envíos concurrentes.
  No se reintentan automáticamente las llamadas fallidas o de resultado incierto.
- Interfaz adaptable a escritorio/móvil, estados de carga y error, Enter/Shift+Enter,
  navegación entre conversaciones y recuperación del proyecto/sección desde la URL.
- Consentimiento explícito para procesar mensajes, título e historial reciente en Cloudflare;
  el servidor exige también la confirmación en el cuerpo de cada envío.
- Puerto `ResponseGenerator` y construcción de contexto separada para evolución posterior.

## Integración con Qwen3

Se añade `CloudflareLanguageModel.chat()` para `@cf/qwen/qwen3-30b-a3b-fp8`, con mensajes
de sistema/historial/usuario y salida textual. Se conserva el contrato JSON de extracción
metodológica. Se comparte el transporte existente sin reintentos ni redirecciones, con límites
de entrada/salida, timeout y traducción segura de errores de credenciales, cuota y respuesta inválida.

El contexto contiene solo el título obtenido de ProjectService y turnos recientes completados.
No se envían documentos ni datasets. El chat no puede ejecutar estadísticas ni aprobar análisis.
Sin configuración se deshabilita el envío y se mantiene la consulta del historial.

## Archivos compartidos

- `backend/app/modules/research/dev_app.py`: composición y manejo acotado de peticiones del chat.
- `backend/app/shared/adapters/cloudflare.py`: operación textual y transporte compartido.
- `backend/.env.example`: límites configurables sin credenciales.
- `frontend/src/features/research/projects/ResearchProjects.tsx` y su prueba: cuarta sección,
  restauración tras recarga y conservación de formularios de paneles visitados.
- `README.md`: enlace a `docs/CHAT_CONVERSACIONAL.md`.

No se modifican Statistics, fórmulas, informes, los archivos de orquestación protegidos,
los seis contratos v1.0.0, dependencias ni `app.main`. Se parte de `f507f4f` en `develop`;
los cambios ya integrados de otros integrantes se conservan.

## Pruebas ejecutadas y resultados

- Pytest completo: **298 aprobadas**, incluidas **48 nuevas** de conversación.
- Vitest completo: **87 aprobadas en 19 archivos**.
- Ruff check y Ruff format: aprobados; 125 archivos con formato correcto.
- ESLint y Prettier: aprobados, sin advertencias pendientes.
- TypeScript y build principal: aprobados; entradas de aplicación, Research y Statistics.
- Build Research independiente: aprobado.
- Validación de contratos backend y generación de tipos frontend: aprobadas, sin diferencias.
- Compilación Python: aprobada.
- Navegador: prueba local con datos ficticios y proveedor inyectado rotulado como simulado;
  creación, procesamiento, dos turnos, F5, conversaciones, eliminación y navegación.
  Revisión visual en escritorio y pantalla estrecha. Los procesos existentes no se sustituyeron.

Las nuevas pruebas bloquean el transporte real por defecto. No se utilizaron credenciales
reales ni se consumió cuota de Cloudflare. No se eliminaron pruebas existentes.
El estado de GitHub Actions debe consultarse en los checks del PR; estas cifras son locales.

## Limitaciones y pendientes

**Conectividad real con Qwen3 pendiente:** la configuración local resultó no configurada y
no se autorizó una prueba real. Los mocks no prueban conectividad ni calidad de Qwen3.

Demostración exclusivamente local y sin autenticación. No incluye streaming, renombrado ni
edición de mensajes. Un fallo externo puede dejar el mensaje del estudiante sin respuesta.
Ante entrega incierta se consulta el historial y no se repite el consumo automáticamente.
Los paneles de Paquete ya abiertos conservan estado; su control existente de actualizar
fuentes permite recuperar cambios posteriores, con vigencia siempre validada en backend.

La Sesión 16A incorporará contexto avanzado de investigación y resultados. La Sesión 17A
incorporará agentes y LangGraph. Ninguna se implementa ni se declara disponible en este PR.
Documentación completa: `docs/CHAT_CONVERSACIONAL.md`.

La fusión queda reservada a revisión humana. No activar fusión automática.
