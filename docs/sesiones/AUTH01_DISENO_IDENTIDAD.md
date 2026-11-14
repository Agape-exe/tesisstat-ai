# AUTH01 — Diseño de identidad y acceso

## Objetivo

Preparar autenticación real sin introducir un segundo sistema local de contraseñas ni modificar
el frontend. La fuente de identidad acordada es Supabase Auth y el backend solo confía en un
token cuya firma y claims hayan sido verificados.

## Entregables

- `Principal` inmutable con `subject: UUID` y modo explícito.
- `AuthorizedProject` y `ProjectAccess`, que crean alcance interno y no aceptan `owner_id` del
  navegador.
- Contrato uniforme: identidad ausente o inválida responde 401; proveedor no verificable, 503;
  proyecto ajeno e inexistente comparten `ProjectNotFound`.

## Decisiones

- No se usa email ni `user_metadata` para autorizar.
- El modo local sigue separado de una identidad autenticada.
- La autorización científica, el consentimiento y la propiedad continúan siendo controles
  distintos.
