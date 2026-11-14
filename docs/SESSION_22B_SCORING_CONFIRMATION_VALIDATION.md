# Sesión 22B — revalidación de confirmación sin persistencia

## Alcance

`InstrumentScoringConfirmationValidator` recompone una previsualización mediante el servicio ya
autorizado y compara su fingerprint con el aceptado por la persona usuaria. Esta entrega no
confirma identidades, no persiste resultados y no define repositorios de Research.

## Flujo

1. La solicitud identifica proyecto, instrumento y regla, incluye el fingerprint previo y exige
   `confirm=true`.
2. Orchestration vuelve a ejecutar la autorización y el cálculo completos.
3. Si la huella cambió, se genera `StaleScoringPreviewError` y no se entrega un resultado parcial.
4. Si coincide, se devuelve el estado interno `validated` junto con la previsualización recompuesta.

`validated` no equivale a `confirmed` ni a `persisted`. Es únicamente la precondición que utilizará
la futura composición cuando Research publique su repositorio histórico.

## Seguridad

- La solicitud rechaza campos adicionales, incluido un `confirmer_ref` suministrado por el cliente.
- La identidad del confirmante será incorporada posteriormente por una capa autenticada.
- Un cambio de fuentes, puntuaciones, confiabilidad o versión del motor modifica el fingerprint y
  obliga a generar una nueva previsualización.
- No se exponen filas originales, rutas, archivos ni repositorios.
