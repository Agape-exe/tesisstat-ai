# Reproducir la evidencia local

Todo el contenido es sintético. Estos scripts están separados del frontend y del backend de producción. El servidor de QA usa SQLite en `.cache/uxui-final-qa`, credenciales vacías y un proveedor conversacional simulado local. No se necesita ni se utiliza Qwen3.

Desde la raíz del worktree, en una terminal independiente:

```powershell
.\backend\.venv\Scripts\python.exe docs/uxui-final/qa/serve_backend.py
```

Desde `frontend`, en otra terminal:

```powershell
$env:VITE_RESEARCH_API_BASE_URL='http://127.0.0.1:8022'
npm run dev -- --port 5179
```

La galería se sirve desde la raíz del worktree:

```powershell
python -m http.server 8021 --bind 127.0.0.1
```

El HTML aprobado se sirve desde Descargas, con el servidor limitado a localhost, en el puerto 8020. La comparación de preservación utiliza un worktree detached de `ea7cd85`, servido por Vite en 5180 contra la misma API. No se cambia de rama ni se integra código remoto.

```powershell
python -m http.server 8020 --bind 127.0.0.1 --directory C:/Users/Melissa/Downloads
```

Los scripts Node usan el Playwright ya instalado en el runtime de Codex y Chromium local. `QA_PLAYWRIGHT_PATH` y `QA_CHROMIUM_PATH` permiten indicar otras rutas en `capture.cjs`. No se añadieron estas herramientas a las dependencias de producción.

```powershell
node docs/uxui-final/qa/capture.cjs
node docs/uxui-final/qa/functional.cjs
node docs/uxui-final/qa/empty-and-errors.cjs
```

`functional.cjs` crea una investigación nueva y verifica el recorrido real, incluida una ejecución estadística explícitamente aprobada. Las fixtures metodológicas iniciales se completan a través de endpoints públicos; el guardado del objetivo vinculado, la confirmación, validación, propuesta, aprobación y ejecución se realizan desde sus acciones React. `empty-and-errors.cjs` necesita su registro `funcional.json`, crea y elimina exclusivamente archivos temporales de esa investigación y simula un fallo de lectura HTTP solo en el navegador de QA.

Las descargas `informe-sintetico.pdf` e `informe-sintetico.docx` son archivos auténticos obtenidos de los endpoints de exportación durante la prueba. No representan una previsualización ni un catálogo de informes persistidos ofrecidos por la aplicación.
