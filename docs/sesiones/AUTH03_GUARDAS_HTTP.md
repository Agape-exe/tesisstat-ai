# AUTH03 — Guardas HTTP

## Objetivo

Crear una frontera reutilizable para rutas protegidas sin acoplar los módulos científicos a
FastAPI ni a Supabase.

## Contrato verificable

| Caso | Resultado |
| --- | --- |
| Sin Bearer token | 401 y `WWW-Authenticate: Bearer` |
| Token inválido, expirado o de rol incorrecto | 401 sin filtrar detalles internos |
| JWKS/proveedor no disponible | 503 y fallo cerrado |
| Token válido | `Principal(subject, authenticated)` inmutable |

`GET /auth/me` permite comprobar la sesión desde un cliente futuro. No recibe contraseñas y no
crea cuentas: el inicio de sesión pertenece a Supabase Auth; esta API verifica el acceso tokenizado.
