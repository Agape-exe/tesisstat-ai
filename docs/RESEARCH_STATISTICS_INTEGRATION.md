# Puente seguro de Research hacia Statistics

## Estado y responsabilidades

En `develop` después del PR #11, Statistics todavía no incluye `BytesDatasetReader`, el planificador ni el motor de la rama `feat/statistics-research-bridge`. Esta sesión prepara y prueba el proveedor interno de Research. **La integración completa y la ejecución estadística real siguen pendientes.** No se copiaron archivos ni se cambiaron algoritmos de Statistics o los seis contratos v1.0.0.

Research conserva proyectos, revisión metodológica, paquetes, datasets y control de acceso a sus recursos. Statistics conserva planificación, selección y ejecución de técnicas y resultados. `app.orchestration.research_statistics.ResearchStatisticsBridge` es la capa de composición. En la app de desarrollo se instancia como `app.state.research_statistics_bridge`; no se publica una ruta HTTP que entregue bytes.

## Puertos, adaptadores y flujo

El puente recibe `ProjectService`, `PackageService` y `DatasetService` por inyección. Usa `PackageReaderAdapter` para leer el contrato compartido `ResearchPackage`, después de validar el proyecto y el paquete vigente con `PackageService.get_package(project_id)`. El ID solicitado debe ser el ID del paquete vigente de ese proyecto. La vigencia reutiliza la versión de configuración, la revisión confirmada, las huellas de metodología y dataset, y la selección del dataset activo. Un ID de paquete de otro proyecto no autoriza lectura.

`get_package(project_id, package_id)` devuelve el paquete vigente o lanza `ResearchInputError` con un código seguro. Las hipótesis, variables y `DatasetReference` llegan juntos en ese contrato. El consumidor selecciona una hipótesis por ID existente; tener el paquete no garantiza que una técnica sea válida.

`read_dataset(project_id, package, reference)` vuelve a validar el paquete antes y después de la lectura. Exige que el paquete y la referencia recibidos coincidan con los contratos vigentes. Acepta solamente `research-dataset:<UUID canónico>` y comprueba que el UUID de `location`, `DatasetReference.id`, el dataset del paquete y el registro del proyecto coincidan. Usa `DatasetService.get` y `DatasetService.read`, nunca interpreta `location` como ruta. Comprueba actividad, proyecto, formato, columnas, filas, procedencia sintética y tamaño. Analiza los bytes con los lectores acotados de CSV/XLSX de Research para verificar los metadatos. Funciona con originales y derivados de la preparación de datos. Los códigos de fallo distinguen proyecto o paquete ausente, paquete desactualizado, referencia inválida, dataset inactivo, inaccesible o incompatible; los mensajes no contienen rutas ni bytes.

## Conexión cuando se fusione Statistics

La rama del Integrante 2 expone `BytesDatasetReader(read_bytes: Callable[[DatasetReference], bytes])`. Una vez integrada y coordinada, la capa de composición puede inyectar Research así:

```python
package = bridge.get_package(project_id, package_id)
reader = BytesDatasetReader(
    lambda reference: bridge.read_dataset(project_id, package, reference)
)
table = reader.read(package.dataset)
```

El código de composición debe obtener `project_id` de un contexto autorizado, no de un identificador arbitrario del cliente. Debe pasar el paquete y la misma referencia recibida del puente. `BytesDatasetReader` validará su propia tabla, sin conocer el almacenamiento de Research. No se requiere modificar Research ni los contratos. Cuando se fusione el planificador, pasarle el paquete y el ID de una hipótesis real, verificar los IDs del `AnalysisPlan` y mantener el estado `proposed` o `needs_clarification`. La conversión de columnas a `AnalysisInput`, la aprobación explícita y la ejecución del motor pertenecen a Statistics; no están implementadas aquí.

## Pruebas y demostración

`backend/tests/research/test_statistics_bridge.py` usa exclusivamente documentos y datasets ficticios. Prueba el puerto con un consumidor sintético del contrato, CSV original, XLSX original, CSV derivado, proyecto ajeno, paquete ausente o desactualizado, referencia opaca alterada, metadatos incompatibles, inactividad, eliminación y cambio de metodología o archivo. Es una prueba real de lectura de bytes desde Research; **no es una prueba del planificador ni del motor real de Statistics**. El frontend comprueba estados de paquete generado y desactualizado. Las pruebas de integración con `BytesDatasetReader`, planificador y motor quedan pendientes de la fusión del Integrante 2.

Para demostrar localmente, ejecutar el backend con `uv run uvicorn app.modules.research.dev_app:app --host 127.0.0.1 --port 8001` y el frontend con `npx vite --config src/features/research/vite.demo.config.ts --host 127.0.0.1`. Crear un proyecto ficticio, confirmar una revisión metodológica, subir y activar un dataset ficticio, declarar su procedencia, vincular variables e hipótesis, validar y generar el paquete. La sección **Preparar investigación para análisis** muestra el estado, ID vigente, dataset, hipótesis y aclaraciones. Si el paquete es vigente, avisa que Statistics sigue pendiente; no muestra resultados estadísticos.

## Límites de seguridad y despliegue

La demo de Research no autentica usuarios ni implementa aislamiento definitivo entre propietarios. El contexto de proyecto del puente es explícito, pero no sustituye Supabase Auth y las políticas de acceso futuras. Usar solo datos sintéticos y `localhost`; no desplegar esta app para datos reales. No hay descarga pública de bytes, envío de datasets a servicios externos ni registro de su contenido. La revalidación reduce referencias obsoletas durante una lectura; una garantía transaccional entre archivo y metadatos requerirá almacenamiento y control de concurrencia de producción.
