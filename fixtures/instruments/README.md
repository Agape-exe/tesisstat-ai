# Fixtures de InstrumentContext

Todos los fixtures de esta carpeta son sintéticos. No contienen tesis, personas ni respuestas
reales.

- `satisfaction_confirmed.context.json`: instrumento confirmado, dos ítems de una dimensión,
  un ítem invertido y mapeo confirmado hacia columnas sintéticas.
- `invalid_unconfirmed_mapping.context.json`: mapeo marcado como confirmado sin confirmación
  humana; debe rechazarse.

Los casos límite que se derivan desde el fixture válido en
`backend/tests/test_instrument_context.py` cubren inversión sin rango explícito y un mapeo
confirmado que omite un ítem. Así se evita mantener copias casi idénticas del mismo contrato.
