# Revisión metodológica humana — sesión 7

## Alcance

La vista de metodología permite crear un registro editable a partir del borrador de IA o
manualmente para un documento existente. Se pueden cambiar título, problema, objetivos,
hipótesis, variables, rol, escala, dimensiones, indicadores, ítems, diseño, observaciones,
metodología adicional y aclaraciones. Las listas y variables se pueden agregar o eliminar.
Guardar un borrador incompleto y confirmar la revisión son operaciones distintas. La
confirmación significa que una persona revisó el registro; **no** certifica suficiencia
estadística ni genera `ResearchPackage`, `AnalysisPlan` o resultados.

## Modelo y procedencia

`MethodologyDraft` de la sesión 6 permanece intacto en `research_methodology`, con sus
citas, offsets y hash de fuente. La nueva `MethodologyReview` reside separada en
`research_methodology_reviews`. Incluye origen `ai` o `manual`, contenido editable,
campos pendientes, estado `unreviewed` o `reviewed`, versión, fecha de guardado y fecha
de confirmación. Cada valor usa `kind`: `quotation`, `inference`, `manual` o `unknown`.
Los valores iniciales de IA conservan sus citas. Cambiar un valor lo marca `manual` y
vacía sus evidencias; el servidor rechaza alterar o fabricar citas de IA. Las variables
tienen UUID estable; las dimensiones, indicadores e ítems permanecen agrupados por
variable. No se inventan relaciones más precisas entre esos elementos.

`ReviewService.reviewed_content(project_id, document_id)` es la interfaz de lectura
para una futura conversión a contratos; devuelve contenido solo tras confirmación.
No exige dataset en esta sesión.

## API

Base: `/api/research/projects/{project_id}/documents/{document_id}/methodology`.
Todas las rutas verifican proyecto y pertenencia del documento.

| Método | Ruta | Función |
| --- | --- | --- |
| GET | `/review/status` | Revisión existente o `null` |
| GET | `/review` | Revisión editable; 404 si no existe |
| POST | `/review` | Crear desde IA si existe un borrador; de otro modo, manual |
| PUT | `/review` | Guardar `{ "version": 0, "content": { ... } }` |
| POST | `/review/confirm` | Confirmar `{ "version": 1 }` |

Los endpoints de IA (`/status`, GET `/methodology`, POST `/extract`) siguen disponibles.
Un `PUT` exitoso incrementa la versión, guarda la fecha y vuelve a `unreviewed` si
había confirmación previa. Una versión antigua devuelve 409 y obliga a recargar.

## Validación y persistencia

Los modelos Pydantic rechazan campos extras. Cada valor tiene máximo 2000 caracteres;
las listas, 40 entradas; las variables, 20. Roles manuales: `independent`, `dependent`,
`covariate`, `descriptive`, `unknown`. Escalas manuales: `nominal`, `ordinal`,
`interval`, `ratio`, `unknown`. Se rechazan identificadores de variables duplicados,
valores en blanco, evidencias manuales, citas alteradas y JSON inválido. La API devuelve
422 con rutas de campo; la interfaz muestra el error. Guardar contenido parcial está
permitido. Para confirmar se requieren título, objetivo general, diseño de investigación
y al menos una variable con nombre. Los demás campos continúan listados como pendientes
incluso tras la confirmación.

SQLite usa una escritura condicionada por versión dentro de una transacción `BEGIN
IMMEDIATE`. Un trigger elimina la revisión al borrar su documento; el borrado de proyecto
elimina primero sus documentos. El registro se recupera tras reiniciar el backend.
SQLite y archivos siguen siendo solo almacenamiento local de desarrollo, sin
autenticación de usuarios finales.

## Demo sin Cloudflare

Usar solo datos sintéticos. En `backend`:

```powershell
$env:UV_CACHE_DIR = '.cache/uv'
uv sync --locked
$env:CORS_ORIGINS = '["http://localhost:5174"]'
uv run uvicorn app.modules.research.dev_app:app --host 127.0.0.1 --port 8001
```

En `frontend`, en otra terminal:

```powershell
npm ci
npx --no-install vite --config src/features/research/vite.demo.config.ts --host 127.0.0.1
```

Abrir `http://localhost:5174/research-demo/`. Crear proyecto ficticio y adjuntar un
PDF/DOCX sintético. Abrir el documento y la sección metodología. Pulsar **Crear
metodología manualmente** sin extraer texto ni configurar Cloudflare. Pulsar **Editar
metodología**, llenar campos, agregar una variable y sus componentes, y **Guardar
borrador**. Recargar: los cambios persisten. Editar otro valor y pulsar **Cancelar**
para descartarlo. Completar título, objetivo general, diseño y nombre de variable;
pulsar **Confirmar revisión**. El estado pasa a **Revisado por una persona**. Editar y
guardar de nuevo devuelve el estado a **Pendiente de revisión**. El navegador avisa
antes de cerrar o recargar con cambios sin guardar; Cancelar pide confirmación.

Si existe borrador de IA, el botón indica **Revisar metodología de IA**. Las citas
originales siguen visibles en el borrador y no aparecen como evidencia de cambios
manuales. Ningún paso del flujo manual consume tokens ni llama a Cloudflare.

## Verificación

- `uv run --locked pytest -q`: **104 aprobadas**, con datos sintéticos y proveedor falso.
- `uv run --locked ruff check .` y `ruff format --check .`: aprobados.
- `uv run --locked python -m scripts.export_contracts --check`: aprobado; sin cambios
  en los seis contratos.
- `npm test`: **46 aprobadas**.
- `npm run lint`, `npm run format:check`, `npm run build` y build de demo Research:
  aprobados; el build ejecuta TypeScript.

No se realizó llamada real a Cloudflare ni prueba manual de navegador. La sesión no
incluye autenticación, dataset, suficiencia estadística ni despliegue público.
