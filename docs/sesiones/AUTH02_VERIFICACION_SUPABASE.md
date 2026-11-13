# AUTH02 — Verificación de Supabase

## Objetivo

Resolver `IdentityProvider.resolve_user(token)` únicamente después de validar el JWT con las
claves públicas rotatorias del issuer configurado.

## Controles implementados

- Algoritmos permitidos: ES256 y/o RS256 mediante allowlist explícita.
- Firma obtenida desde JWKS, con caché de 300 segundos y timeout de 5 segundos configurables.
- Verificación exacta de issuer, audience, expiración, subject UUID y rol `authenticated`.
- `kid` desconocido delega el refresco al cliente JWKS; un fallo de claves no acepta el token y
  se traduce a proveedor no disponible.
- La configuración incompleta impide construir la aplicación autenticada.

La caché JWKS no equivale a revocación instantánea de una sesión. Esta entrega valida firma y
vigencia del token; no afirma comprobación remota de revocación por solicitud.
