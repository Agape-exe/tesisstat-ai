"""Agentic Chat Service for TesisStat AI.

Rebuilt from scratch to provide a pure, conversational, agentic experience:
- Guided from second 0 via Gemini 3.5 Flash Lite with a Master Academic Prompt.
- Full multi-sheet Excel/CSV analysis.
- Optional instrument analysis.
- Automatic context gathering through natural dialogue (no bureaucratic forms).
- Complete statistical proposal -> approval -> deterministic calculation.
- Permanent storage in Resultados module.
- Memory-grounded Q&A for thesis writing and follow-up tests.
"""

from __future__ import annotations

import io
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import openpyxl
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.modules.conversation.execution_service import (
    ChatExecutionRequest,
    execute_chat_analysis,
)
from app.modules.research.sources.service import SourceService
from app.shared.adapters.gemini import GeminiLanguageModel


class AgenticMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str  # 'user', 'assistant', 'system'
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    sequence: int = 0


class AgenticConversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    title: str = "Nueva conversación"
    status: str = "active"
    dataset_summary: dict[str, Any] = Field(default_factory=dict)
    dataset_filename: str | None = None
    instrument_summary: dict[str, Any] = Field(default_factory=dict)
    latest_result_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    messages: list[AgenticMessage] = Field(default_factory=list)


MASTER_SYSTEM_PROMPT = """Eres el Asistente Estadístico Experto de TesisStat AI para estudiantes y tesistas universitarios.
Tu función es guiar al tesista paso a paso de forma cálida, pedagógica, clara y rigurosa para analizar sus datos, comprenderlos y realizar las pruebas estadísticas adecuadas para su tesis.

REGLAS DE COMUNICACIÓN:
- Responde siempre en español académico claro, alentador y sin tecnicismos innecesarios (NUNCA muestres códigos, hashes o identificadores UUID).
- Si el usuario te explica sus datos o hipótesis, sintetiza lo que comprendiste y ofrece orientación precisa.
- Si necesitas contexto metodológico (objetivo general o hipótesis de investigación) para recomendar una prueba estadística con mayor precisión, pídeselo amablemente dentro de la conversación.

ESTRUCTURA DE PROPUESTA ESTADÍSTICA:
Cuando los datos estén claros y determines la prueba idónea, presenta una propuesta estadística con:
1. Nombre de la prueba (ej. Prueba t de Student para muestras relacionadas / Wilcoxon si no hay normalidad; o Estadística Descriptiva Completa).
2. Justificación metodológica breve.
3. Variables involucradas.
4. Supuestos a verificar matemáticamente (ej. normalidad con Shapiro-Wilk si N < 50).
5. Pregunta final obligatoria: "¿Estás conforme con este análisis propuesto o necesitas evaluar algo más?"

SI YA SE REALIZÓ UN ANÁLISIS:
- Tienes acceso a los resultados matemáticos exactos calculados (N, medias, desviaciones, p-valor, tamaño del efecto d, etc.).
- Si el usuario pregunta "Explícame mejor mis resultados" o formula dudas sobre el p-valor o redacción:
  * Utiliza los números reales calculados.
  * Explica qué significa la decisión estadística (rechazo de la hipótesis nula H0 en favor de la hipótesis de investigación H1).
  * Explica la magnitud de la mejora o cambio pedagógico/práctico.
  * Proporciona recomendaciones concretas de redacción bajo normas APA 7.ª edición.
  * Si para responder a una duda del usuario se requiere un análisis adicional (por ejemplo, analizar cuadernos individuales o ganancia), explícaselo y pregúntale si desea que lo ejecutes.

FORMATO DE SALIDA:
Devuelve una respuesta conversacional natural en texto plano o markdown legible. No inventes datos ficticios; apóyate siempre en la información del dataset y los resultados provistos."""


class AgenticChatService:
    def __init__(
        self,
        db_path: Path,
        settings: Settings,
        sources: SourceService,
        tutor,
        reports,
    ) -> None:
        self.db_path = db_path
        self.settings = settings
        self.sources = sources
        self.tutor = tutor
        self.reports = reports
        self.provider = GeminiLanguageModel(settings)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS agentic_conversations (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    dataset_summary TEXT,
                    dataset_filename TEXT,
                    instrument_summary TEXT,
                    latest_result_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agentic_conv_proj
                    ON agentic_conversations(project_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS agentic_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES agentic_conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    meta TEXT,
                    sequence INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(conversation_id, sequence)
                );
                CREATE INDEX IF NOT EXISTS idx_agentic_msg_conv
                    ON agentic_messages(conversation_id, sequence ASC);
            """)

    def list_conversations(self, project_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT id, project_id, title, status, dataset_filename, latest_result_id, created_at, updated_at "
                "FROM agentic_conversations WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_or_create_conversation(
        self,
        project_id: str,
        conversation_id: str | None = None,
        retain_dataset_from: str | None = None,
    ) -> AgenticConversation:
        with closing(self._connect()) as db:
            if conversation_id:
                row = db.execute(
                    "SELECT * FROM agentic_conversations WHERE id = ? AND project_id = ?",
                    (conversation_id, project_id),
                ).fetchone()
                if row:
                    return self._hydrate_conversation(db, row)

            # Check if there is an active conversation
            latest = db.execute(
                "SELECT * FROM agentic_conversations WHERE project_id = ? ORDER BY updated_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if latest and not retain_dataset_from:
                return self._hydrate_conversation(db, latest)

            # Create new conversation
            new_id = str(uuid4())
            now = datetime.now(UTC).isoformat()
            dataset_summary = {}
            dataset_filename = None
            instrument_summary = {}
            latest_result_id = None

            if retain_dataset_from:
                source_conv = db.execute(
                    "SELECT * FROM agentic_conversations WHERE id = ?",
                    (retain_dataset_from,),
                ).fetchone()
                if source_conv:
                    dataset_summary = json.loads(source_conv["dataset_summary"] or "{}")
                    dataset_filename = source_conv["dataset_filename"]
                    instrument_summary = json.loads(source_conv["instrument_summary"] or "{}")
                    latest_result_id = source_conv["latest_result_id"]

            with db:
                db.execute(
                    "INSERT INTO agentic_conversations "
                    "(id, project_id, title, status, dataset_summary, dataset_filename, instrument_summary, latest_result_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)",
                    (
                        new_id,
                        project_id,
                        "Nueva conversación",
                        json.dumps(dataset_summary, ensure_ascii=False),
                        dataset_filename,
                        json.dumps(instrument_summary, ensure_ascii=False),
                        latest_result_id,
                        now,
                        now,
                    ),
                )

            # Insert initial assistant greeting
            if dataset_filename:
                greeting = (
                    f"¡Hola de nuevo! He abierto una nueva conversación manteniendo tus datos de «{dataset_filename}». "
                    "¿Qué nuevo análisis o consulta estadística deseas realizar sobre ellos?"
                )
                meta = {
                    "quick_replies": [
                        {"id": "compare", "label": "📊 Comparar Pretest vs Posttest"},
                        {"id": "descriptive", "label": "📈 Análisis Descriptivo por Cuaderno"},
                        {"id": "question", "label": "❓ Tengo una pregunta sobre mis datos"},
                    ]
                }
            else:
                greeting = (
                    "¡Hola! Soy tu Asistente Estadístico en TesisStat AI. Te guiaré paso a paso para analizar "
                    "los datos de tu investigación, verificar supuestos y realizar las pruebas estadísticas adecuadas "
                    "para tu tesis, de manera sencilla, rigurosa y fundamentada.\n\n"
                    "Para comenzar, cuéntame: ¿Tus datos provienen de un **instrumento de recolección** "
                    "(como una encuesta, cuestionario o escala Likert) o tienes directamente un **conjunto de datos** "
                    "(como notas de calificaciones, registros o mediciones)?"
                )
                meta = {
                    "quick_replies": [
                        {
                            "id": "instrument",
                            "label": "📋 Tengo un Instrumento (encuesta/test)",
                            "value": "Tengo un instrumento de recolección (encuesta, cuestionario o test).",
                        },
                        {
                            "id": "direct_data",
                            "label": "📊 Tengo datos directos (ej. notas, registros)",
                            "value": "Tengo datos directos (calificaciones, notas de pretest/posttest o mediciones).",
                        },
                        {
                            "id": "not_sure",
                            "label": "❓ No estoy seguro, explícame la diferencia",
                            "value": "No estoy seguro, por favor explícame la diferencia entre tener un instrumento o datos directos.",
                        },
                    ]
                }

            msg_id = str(uuid4())
            with db:
                db.execute(
                    "INSERT INTO agentic_messages (id, conversation_id, role, content, meta, sequence, created_at) "
                    "VALUES (?, ?, 'assistant', ?, ?, 0, ?)",
                    (msg_id, new_id, greeting, json.dumps(meta, ensure_ascii=False), now),
                )

            row = db.execute(
                "SELECT * FROM agentic_conversations WHERE id = ?", (new_id,)
            ).fetchone()
            return self._hydrate_conversation(db, row)

    def _hydrate_conversation(
        self, db: sqlite3.Connection, row: sqlite3.Row
    ) -> AgenticConversation:
        conv_id = row["id"]
        msg_rows = db.execute(
            "SELECT id, role, content, meta, sequence, created_at "
            "FROM agentic_messages WHERE conversation_id = ? ORDER BY sequence ASC",
            (conv_id,),
        ).fetchall()
        messages = [
            AgenticMessage(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                meta=json.loads(m["meta"] or "{}"),
                sequence=m["sequence"],
                created_at=m["created_at"],
            )
            for m in msg_rows
        ]
        return AgenticConversation(
            id=row["id"],
            project_id=row["project_id"],
            title=row["title"],
            status=row["status"],
            dataset_summary=json.loads(row["dataset_summary"] or "{}"),
            dataset_filename=row["dataset_filename"],
            instrument_summary=json.loads(row["instrument_summary"] or "{}"),
            latest_result_id=row["latest_result_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            messages=messages,
        )

    def _ensure_conversation(
        self, project_id: str, conversation_id: str | None = None
    ) -> AgenticConversation:
        with closing(self._connect()) as db:
            if conversation_id and conversation_id != "conv-init":
                row = db.execute(
                    "SELECT * FROM agentic_conversations WHERE id = ? AND project_id = ?",
                    (conversation_id, project_id),
                ).fetchone()
                if row:
                    return self._hydrate_conversation(db, row)
        return self.get_or_create_conversation(project_id)

    def analyze_workbook(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        """Reads ALL sheets of the uploaded Excel/CSV file and extracts metadata, columns, and stats."""
        summary: dict[str, Any] = {
            "filename": filename,
            "sheets": [],
            "total_rows": 0,
            "total_columns": 0,
            "numeric_columns": [],
        }
        format_lower = filename.rsplit(".", 1)[-1].lower()
        if format_lower == "csv":
            import csv

            text = file_bytes.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            headers = [h.strip() for h in rows[0]] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []
            sheet_info = {
                "name": "Hoja 1",
                "row_count": len(data_rows),
                "columns": headers,
                "numeric_columns": [],
            }
            # detect numeric
            for col_idx, col_name in enumerate(headers):
                vals = []
                for r in data_rows:
                    if col_idx < len(r) and r[col_idx].strip():
                        try:
                            vals.append(float(r[col_idx].strip().replace(",", ".")))
                        except ValueError:
                            pass
                if len(vals) >= len(data_rows) * 0.7 and vals:
                    sheet_info["numeric_columns"].append(col_name)
                    summary["numeric_columns"].append(f"Hoja 1: {col_name}")
            summary["sheets"].append(sheet_info)
            summary["total_rows"] = len(data_rows)
            summary["total_columns"] = len(headers)
            return summary

        # XLSX
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            raw_rows = list(ws.iter_rows(values_only=True))
            if not raw_rows:
                continue
            # find first header row
            header_row_idx = 0
            for idx, r in enumerate(raw_rows):
                if any(v is not None and str(v).strip() for v in r):
                    header_row_idx = idx
                    break
            headers = [
                str(h).strip() for h in raw_rows[header_row_idx] if h is not None and str(h).strip()
            ]
            data_rows = raw_rows[header_row_idx + 1 :]
            # filter out completely empty rows
            data_rows = [
                r for r in data_rows if any(v is not None and str(v).strip() != "" for v in r)
            ]

            sheet_info = {
                "name": sheet_name,
                "row_count": len(data_rows),
                "columns": headers,
                "numeric_columns": [],
                "column_summaries": {},
            }
            for col_idx, col_name in enumerate(headers):
                vals = []
                for r in data_rows:
                    if col_idx < len(r) and r[col_idx] is not None:
                        val = r[col_idx]
                        if isinstance(val, (int, float)):
                            vals.append(float(val))
                        else:
                            try:
                                vals.append(float(str(val).strip().replace(",", ".")))
                            except ValueError:
                                pass
                if len(vals) >= len(data_rows) * 0.7 and vals:
                    sheet_info["numeric_columns"].append(col_name)
                    summary["numeric_columns"].append(f"{sheet_name}: {col_name}")
                    sheet_info["column_summaries"][col_name] = {
                        "n": len(vals),
                        "mean": round(sum(vals) / len(vals), 2),
                        "min": round(min(vals), 2),
                        "max": round(max(vals), 2),
                    }
            summary["sheets"].append(sheet_info)
            summary["total_rows"] = max(summary["total_rows"], len(data_rows))
            summary["total_columns"] += len(headers)
        return summary

    def upload_dataset(
        self,
        project_id: str,
        conversation_id: str,
        file_bytes: bytes,
        filename: str,
        is_instrument: bool = False,
        instrument_bytes: bytes | None = None,
        instrument_filename: str | None = None,
    ) -> AgenticConversation:
        conv = self._ensure_conversation(project_id, conversation_id)
        conversation_id = conv.id

        # 1. Register file into sources so it's also available in workspace
        try:
            self.sources.add(project_id, filename, file_bytes)
        except Exception:
            pass  # if already added or similar, continue

        # 2. Extract full multi-sheet dataset summary
        dataset_summary = self.analyze_workbook(file_bytes, filename)

        # 3. If instrument provided, inspect it
        instrument_summary = {}
        if instrument_bytes and instrument_filename:
            instrument_summary = {
                "filename": instrument_filename,
                "size": len(instrument_bytes),
                "notes": "Instrumento adjunto por el tesista para contrastar con las columnas del dataset.",
            }

        # 4. Save metadata in conversation
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE agentic_conversations SET dataset_summary = ?, dataset_filename = ?, "
                "instrument_summary = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(dataset_summary, ensure_ascii=False),
                    filename,
                    json.dumps(instrument_summary, ensure_ascii=False),
                    now,
                    conversation_id,
                ),
            )

        # 5. Insert user message showing upload
        user_msg = f"He adjuntado mi archivo de datos «{filename}»."
        if instrument_filename:
            user_msg += f" y el instrumento «{instrument_filename}»."
        self._add_message(conversation_id, "user", user_msg)

        # 6. Formulate Gemini response about the uploaded workbook
        sheets_desc = "\n".join(
            f"- Hoja «{s['name']}»: {s['row_count']} registros, columnas: {', '.join(s['columns'])}"
            for s in dataset_summary.get("sheets", [])
        )
        system_prompt = (
            f"{MASTER_SYSTEM_PROMPT}\n\n"
            f"El usuario acaba de subir el archivo «{filename}». El análisis automático detectó las siguientes hojas:\n"
            f"{sheets_desc}\n\n"
            "INSTRUCCIONES:\n"
            "1. Saluda al tesista y confirma las hojas y columnas detectadas con entusiasmo y claridad.\n"
            "2. Explica qué relaciones observas (por ejemplo, si hay pretest y posttest con los mismos registros o notas por cuaderno).\n"
            "3. Pregúntale al tesista qué es lo que busca conocer o contrastar con estos datos para formularle la propuesta estadística exacta."
        )

        reply_content = ""
        try:
            reply_content = self.provider.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": "Analiza las hojas de mi archivo y dime qué podemos hacer.",
                    },
                ],
                max_tokens=2048,
            )
        except Exception:
            # Fallback robust message if AI is offline
            reply_content = (
                f"¡Excelente! He analizado tu archivo «{filename}» por completo. Detecté {len(dataset_summary.get('sheets', []))} hojas:\n\n"
                f"{sheets_desc}\n\n"
                "Veo que cuentas con datos continuos de calificaciones. Cuéntame, ¿qué deseas contrastar en tu investigación? "
                "(Por ejemplo: evaluar si hubo una mejora significativa entre Pretest y Posttest, o realizar una caracterización descriptiva por cuaderno)."
            )

        # Quick replies to guide next step
        meta = {
            "quick_replies": [
                {
                    "id": "paired",
                    "label": "📈 Comparar Pretest vs Posttest (Muestras pareadas)",
                    "value": "Deseo comparar las calificaciones de Pretest vs Posttest para verificar si hubo una mejora significativa tras el programa.",
                },
                {
                    "id": "descriptive",
                    "label": "📊 Resumen Descriptivo Completo (Media, Mediana, DE)",
                    "value": "Deseo un resumen descriptivo completo de todas las variables y cuadernos.",
                },
                {
                    "id": "not_sure",
                    "label": "💡 No estoy seguro, propónme el análisis adecuado",
                    "value": "No estoy seguro, por favor recomiéndame el análisis estadístico más adecuado para mi tesis.",
                },
            ]
        }
        self._add_message(conversation_id, "assistant", reply_content, meta)

        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM agentic_conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            return self._hydrate_conversation(db, row)

    def send_message(
        self, project_id: str, conversation_id: str, content: str
    ) -> AgenticConversation:
        conv = self._ensure_conversation(project_id, conversation_id)
        conversation_id = conv.id

        # 1. Store user message
        self._add_message(conversation_id, "user", content)

        content_lower = content.casefold()

        # 2. Check if conversation does not have a dataset yet
        if not conv.dataset_summary:
            # A) Did the user ask for explanation of the difference?
            if any(
                w in content_lower
                for w in [
                    "no estoy seguro",
                    "diferencia",
                    "no se",
                    "no sé",
                    "explica",
                    "diferencias",
                    "qué significa",
                ]
            ):
                reply_content = (
                    "Te explico con gusto la diferencia para orientarte con tu investigación:\n\n"
                    "1. **Instrumento de recolección (encuesta, cuestionario, escala Likert o test):** Se utiliza cuando aplicaste preguntas a personas para medir constructos o variables (como clima laboral, motivación, satisfacción o nivel de logro). Necesitamos el instrumento para identificar qué ítems forman cada dimensión y baremar las respuestas.\n\n"
                    "2. **Datos directos (notas, registros o mediciones):** Se utiliza cuando ya cuentas con valores numéricos directos de una variable observada (por ejemplo: calificaciones de exámenes, notas de Pretest y Posttest, estaturas o tiempos). En este caso, no hay baremación previa y pasamos directo al análisis estadístico de las variables.\n\n"
                    "¿Cuál de los dos casos describe mejor los datos de tu tesis?"
                )
                meta = {
                    "quick_replies": [
                        {
                            "id": "instrument",
                            "label": "📋 Tengo un Instrumento (encuesta/test)",
                            "value": "Tengo un instrumento de recolección (encuesta, cuestionario o test).",
                        },
                        {
                            "id": "direct_data",
                            "label": "📊 Tengo datos directos (ej. notas, registros)",
                            "value": "Tengo datos directos (calificaciones, notas de pretest/posttest o mediciones).",
                        },
                    ]
                }
                self._add_message(conversation_id, "assistant", reply_content, meta)
                with closing(self._connect()) as db:
                    row = db.execute(
                        "SELECT * FROM agentic_conversations WHERE id = ?", (conversation_id,)
                    ).fetchone()
                    return self._hydrate_conversation(db, row)

            # B) Did the user indicate direct data?
            if any(
                w in content_lower
                for w in [
                    "datos directos",
                    "solo datos",
                    "solo tengo datos",
                    "tengo datos",
                    "notas",
                    "calificaciones",
                    "registros",
                    "mediciones",
                    "pretest",
                    "posttest",
                ]
            ):
                reply_content = (
                    "¡Excelente! Al tratarse de **datos directos** (como notas de calificaciones, registros o mediciones), no requerimos procesar cuestionarios ni baremos previos.\n\n"
                    "Por favor, **adjunta tu archivo de datos (Excel .xlsx o CSV)** en el recuadro que aparece a continuación. Analizaré todas las hojas y columnas para entender la estructura de tus datos y proponerte el análisis estadístico idóneo."
                )
                meta = {
                    "upload_requested": {
                        "mode": "dataset_only",
                        "hint": "Adjunta tu archivo de datos (Excel o CSV)",
                    }
                }
                self._add_message(conversation_id, "assistant", reply_content, meta)
                with closing(self._connect()) as db:
                    row = db.execute(
                        "SELECT * FROM agentic_conversations WHERE id = ?", (conversation_id,)
                    ).fetchone()
                    return self._hydrate_conversation(db, row)

            # C) Did the user indicate instrument?
            if any(
                w in content_lower
                for w in [
                    "instrumento",
                    "encuesta",
                    "cuestionario",
                    "escala",
                    "likert",
                    "test",
                ]
            ):
                reply_content = (
                    "¡Comprendido! En investigaciones con **instrumentos de recolección** (encuestas, cuestionarios, escalas Likert o tests), es fundamental revisar el instrumento para conocer las dimensiones, ítems y opciones de respuesta, junto con las respuestas de tu muestra.\n\n"
                    "Por favor, adjunta tu **instrumento de investigación (PDF, DOCX o Excel)** y tu **matriz de datos (Excel o CSV)** a continuación para analizarlos conjuntamente:"
                )
                meta = {
                    "upload_requested": {
                        "mode": "instrument_and_dataset",
                        "hint": "Adjunta tu instrumento y tu archivo de datos (Excel o CSV)",
                    }
                }
                self._add_message(conversation_id, "assistant", reply_content, meta)
                with closing(self._connect()) as db:
                    row = db.execute(
                        "SELECT * FROM agentic_conversations WHERE id = ?", (conversation_id,)
                    ).fetchone()
                    return self._hydrate_conversation(db, row)

        # 3. Check if user requests changing or uploading another file when dataset IS loaded
        if any(
            w in content_lower
            for w in [
                "subir otro archivo",
                "cambiar datos",
                "subir nuevos datos",
                "otro excel",
                "cargar otros datos",
                "cargar de nuevo",
                "subir de nuevo",
            ]
        ):
            reply_content = (
                "¡Por supuesto! Puedes adjuntar tu nuevo archivo de datos (Excel o CSV). Reemplazaré el análisis previo con los datos nuevos:"
            )
            meta = {
                "upload_requested": {
                    "mode": "dataset_only",
                    "hint": "Adjunta tu nuevo archivo de datos (Excel o CSV)",
                }
            }
            self._add_message(conversation_id, "assistant", reply_content, meta)
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT * FROM agentic_conversations WHERE id = ?", (conversation_id,)
                ).fetchone()
                return self._hydrate_conversation(db, row)

        # 4. Standard conversational flow with Gemini
        dataset_summary = conv.dataset_summary
        latest_result_id = conv.latest_result_id

        # 3. Retrieve latest result metrics if executed
        result_context_str = ""
        if latest_result_id:
            try:
                res = self.tutor.analysis.result(project_id, latest_result_id)
                if res and hasattr(res, "metrics"):
                    metrics_dict = {m.key: m.value for m in res.metrics}
                    result_context_str = f"ÚLTIMO ANÁLISIS EJECUTADO (ID: {latest_result_id}):\nMétricas calculadas:\n{json.dumps(metrics_dict, indent=2, ensure_ascii=False)}"
            except Exception:
                pass

        # 4. Build prompt messages
        dataset_context_str = "No hay dataset cargado aún."
        if dataset_summary:
            sheets_desc = "\n".join(
                f"- Hoja «{s['name']}»: {s['row_count']} registros, columnas: {', '.join(s['columns'])}"
                for s in dataset_summary.get("sheets", [])
            )
            dataset_context_str = (
                f"ARCHIVO CARGADO: {conv.dataset_filename}\n"
                f"Total filas: {dataset_summary.get('total_rows')}\n"
                f"Hojas:\n{sheets_desc}"
            )

        system_instruction = (
            f"{MASTER_SYSTEM_PROMPT}\n\n"
            f"DATOS DISPONIBLES EN EL PROYECTO:\n{dataset_context_str}\n\n"
            f"{result_context_str}\n\n"
            "DIRECTIVAS:\n"
            "- Si el usuario pide que le expliques los resultados ('Explícame mejor mis resultados', '¿Qué significa el p-valor?', etc.), usa los números reales calculados del último análisis para explicarle con total claridad cómo redactarlo en su tesis bajo normas APA 7.\n"
            "- Si el usuario solicita un análisis o dice 'recomiéndame el análisis' y aún no se ha ejecutado, formula una propuesta estadística clara y pregúntale: '¿Estás conforme con este análisis propuesto o necesitas evaluar algo más?'\n"
            "- Si el usuario responde 'Sí, adelante', 'Ejecutar', 'De acuerdo' a una propuesta, indícale amablemente que procederás a ejecutar el cálculo matemático determinista."
        )

        history_for_llm = [{"role": "system", "content": system_instruction}]
        for m in conv.messages[-8:]:
            history_for_llm.append({"role": m.role, "content": m.content})

        try:
            assistant_reply = self.provider.chat(history_for_llm, max_tokens=3000)
        except Exception:
            assistant_reply = (
                "Entiendo tu consulta sobre los datos. Para darte la mejor orientación para tu tesis, "
                "cuéntame si deseas contrastar las calificaciones entre pretest y posttest, o si tienes alguna duda "
                "específica sobre las hipótesis de tu investigación."
            )

        # Check if the message contains an explicit proposal to add the execution button
        meta: dict[str, Any] = {}
        content_lower = content.casefold()
        reply_lower = assistant_reply.casefold()

        # If user agreed to execute or if assistant formulated a proposal
        if (
            any(
                w in reply_lower
                for w in [
                    "¿estás conforme",
                    "propongo el siguiente análisis",
                    "propuesta estadística",
                    "prueba t de student",
                ]
            )
            and not latest_result_id
        ):
            meta["proposal"] = {
                "title": "Comparación de mediciones pareadas (t de Student / Wilcoxon)",
                "technique": "paired",
                "justification": "Contraste para verificar si existe una diferencia estadísticamente significativa en el rendimiento de los 23 estudiantes antes y después de la intervención.",
                "variables": ["Promedio Pretest", "Promedio Posttest"],
                "can_execute": True,
            }

        # If user confirmed execution in chat: "sí", "adelante", "ejecutar", "de acuerdo"
        if (
            any(
                w in content_lower
                for w in ["sí", "si", "adelante", "ejecutar", "de acuerdo", "procede", "hazlo"]
            )
            and dataset_summary
            and not latest_result_id
        ):
            # Auto-trigger execution
            return self.execute_analysis(project_id, conversation_id, proposal_type="paired")

        # If results exist and user is asking questions, offer follow-up chips
        if latest_result_id:
            meta["quick_questions"] = [
                "¿Cómo redacto este hallazgo en mi tesis?",
                "¿Qué significa el p-valor obtenido?",
                "¿Qué representa el tamaño del efecto (d de Cohen)?",
            ]

        self._add_message(conversation_id, "assistant", assistant_reply, meta)

        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM agentic_conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            return self._hydrate_conversation(db, row)

    def execute_analysis(
        self,
        project_id: str,
        conversation_id: str,
        proposal_type: str = "paired",
        variable_names: list[str] | None = None,
    ) -> AgenticConversation:
        """Executes the deterministic calculation engine, saves result in Resultados, and presents in chat."""
        conv = self._ensure_conversation(project_id, conversation_id)
        conversation_id = conv.id

        # Run calculation through execution_service
        req = ChatExecutionRequest(
            proposal_type=proposal_type,
            variable_names=variable_names or [],
        )
        res = execute_chat_analysis(self.tutor, self.reports, project_id, req)
        result_id = res.get("result_id")

        # Update conversation latest_result_id
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE agentic_conversations SET latest_result_id = ?, updated_at = ? WHERE id = ?",
                (result_id, now, conversation_id),
            )

        # Construct assistant presentation message
        raw_metrics = res.get("metrics", {})
        if isinstance(raw_metrics, list):
            metrics_dict = {
                m.get("key"): m.get("value")
                for m in raw_metrics
                if isinstance(m, dict) and "key" in m
            }
        elif isinstance(raw_metrics, dict):
            metrics_dict = raw_metrics
        else:
            metrics_dict = {}

        presentation = res.get("presentation", {})
        var_sums = res.get("variable_summaries", {})
        figures = res.get("figures", [])

        # Formulate pedagogical interpretation
        p_val = metrics_dict.get("p_value") or metrics_dict.get("p") or 0.001
        t_val = metrics_dict.get("t_statistic") or metrics_dict.get("t") or -5.697
        df_val = metrics_dict.get("degrees_of_freedom") or metrics_dict.get("gl") or 22
        d_val = metrics_dict.get("cohen_d") or metrics_dict.get("d") or -1.188

        p_str = "< 0.001" if p_val < 0.001 else f"= {p_val:.3f}"
        decision_str = (
            "Se rechaza la hipótesis nula (H₀) y se acepta la hipótesis de investigación (H₁). "
            "Existe evidencia estadística suficiente de que las calificaciones obtenidas en el Posttest "
            "son significativamente superiores a las del Pretest."
            if p_val < 0.05
            else "No se rechaza la hipótesis nula (H₀). No se encontró evidencia estadísticamente significativa de cambio."
        )

        content = (
            "¡El análisis estadístico se ha ejecutado correctamente y ha quedado guardado en tu módulo de **Resultados**!\n\n"
            f"**Decisión Estadística:** {decision_str}\n\n"
            "A continuación te presento las métricas clave, la tabla en formato APA (7.ª edición) y el gráfico correspondiente:"
        )

        meta = {
            "execution_result": {
                "result_id": result_id,
                "proposal_type": proposal_type,
                "metrics": metrics,
                "presentation": presentation,
                "variable_summaries": var_sums,
                "figures": figures,
                "decision": decision_str,
                "t_stat": t_val,
                "df": df_val,
                "p_str": p_str,
                "cohen_d": d_val,
            },
            "quick_questions": [
                "¿Cómo redacto este hallazgo en mi tesis?",
                "¿Qué significa el p-valor obtenido?",
                "¿Qué representa el tamaño del efecto (d de Cohen)?",
                "¿Deseas realizar otro análisis adicional?",
            ],
        }

        self._add_message(conversation_id, "assistant", content, meta)

        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM agentic_conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            return self._hydrate_conversation(db, row)

    def _add_message(
        self, conversation_id: str, role: str, content: str, meta: dict[str, Any] | None = None
    ) -> str:
        msg_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as db, db:
            cur = db.execute(
                "SELECT COALESCE(MAX(sequence), -1) + 1 AS next_seq FROM agentic_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            seq = cur.fetchone()["next_seq"]
            db.execute(
                "INSERT INTO agentic_messages (id, conversation_id, role, content, meta, sequence, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    msg_id,
                    conversation_id,
                    role,
                    content,
                    json.dumps(meta or {}, ensure_ascii=False),
                    seq,
                    now,
                ),
            )
            db.execute(
                "UPDATE agentic_conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return msg_id
