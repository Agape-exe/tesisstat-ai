# Contratos compartidos v1

Versión de payload: `schema_version: "1.0.0"`. Fuente canónica:
`backend/app/shared/contracts.py`. Esquemas JSON Schema 2020-12 en `v1/`, ejemplos en
`v1/examples/`, tipos TypeScript generados en `frontend/src/shared/contracts/generated/`.
No editar artefactos generados a mano. Los tipos TS no validan JSON en ejecución: validar
payloads de las futuras rutas con Pydantic y, si entran en el navegador sin pasar por backend,
añadir un validador JSON Schema al implementar esas rutas.

| Contrato | Contenido |
| --- | --- |
| ResearchPackage | Metodología revisable, diseño, observaciones, variables, hipótesis y dataset |
| ResearchHypothesis | Enunciado, objetivo, tipo, variables y alternativa |
| ResearchVariable | Rol, escala, columnas, dimensiones y preguntas |
| DatasetReference | Clave opaca o ruta fixture, formato, filas, columnas, indicador sintético |
| AnalysisPlan | Referencias, estado, técnica opcional, justificación, alfa, supuestos y preguntas |
| AnalysisResult | Referencias, estado, métricas deterministas, supuestos, advertencias y versión del motor |

IDs son cadenas opacas. `location` no contiene URLs firmadas ni secretos y no autoriza leer
una ruta: el adaptador futuro resolverá claves con aislamiento por propietario. No incluir
filas del dataset en el paquete. Escalas, roles o diseño desconocidos se marcan `unknown`.
`reviewed` indica revisión humana, no aprobación automática de una prueba. `needs_clarification`
permite representar planes sin técnica seleccionada. El catálogo ejecutable se añadirá después;
el string `technique` nunca autorizará ejecutar código o una función arbitraria.

Pydantic valida IDs únicos y referencias internas de ResearchPackage. JSON Schema valida
estructura pero no esas relaciones. Referencias entre paquetes, planes y resultados serán
verificadas por los servicios de aplicación; los mocks ya rechazan solicitudes no coincidentes.
Las métricas no admiten NaN/Infinity; ausencia de un valor se representa sin esa métrica y con
advertencia. Los resultados fixture son `not_executed` y no contienen métricas.

Regenerar desde `backend/`:

```powershell
uv run python -m scripts.export_contracts
```

Desde `frontend/`:

```powershell
npm run contracts:generate
```

Ejecutar pruebas de ambos lados. CI comprueba que esquemas/tipos coinciden con las fuentes.
Cualquier cambio incompatible requiere una nueva versión mayor y carpeta; acordar cambios
aditivos entre ambos integrantes y actualizar ejemplos, fixtures y consumidores juntos.
