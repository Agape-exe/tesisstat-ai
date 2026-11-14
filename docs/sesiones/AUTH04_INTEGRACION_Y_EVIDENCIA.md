# AUTH04 — Integración y evidencia

## Composición

`app.authenticated_app:create_authenticated_app` es una raíz separada de las demos locales.
Configura CORS para Bearer, monta salud pública mínima y la ruta protegida `/auth/me`. No monta
automáticamente los endpoints de producto todavía: cada familia debe recibir alcance de proyecto
antes de exponerse en modo remoto.

## Evidencia automatizada

`backend/tests/test_auth.py` cubre:

- JWT válido con firma RS256 y subject UUID;
- rol, audience, issuer, expiración y subject inválidos;
- proveedor JWKS no disponible;
- respuestas 401/503 y sesión válida;
- arranque remoto sin configuración;
- aislamiento entre dos dueños mediante `ProjectAccess`.

Las pruebas con claves sintéticas verifican la capa de aplicación. No demuestran todavía RLS ni
Auth reales de un proyecto Supabase; esa evidencia requiere un entorno autorizado y permanece
como condición de integración remota.
