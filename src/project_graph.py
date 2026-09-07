"""
Cross-Thread Project Entity & Memory Graph Engine (Procurement Dossier Engine)
Enterprise Trading Corporation

Implements:
  - ACID-compliant Pure Python SQLite backend (data/project_graph.db)
  - Entity Alias Resolution (Tender No, PO No, NOA Ref, Clean Normalized Title)
  - Cross-Thread Timeline Reconstruction (Stitches disjoint Gmail threads into a single Project Dossier)
  - Zero-configuration auto-learning (Learns new identifiers as deals progress)
"""

import sqlite3
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "project_graph.db"

class ProjectGraph:
    """Enterprise Cross-Thread Project Entity & Memory Graph."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    plant_name TEXT,
                    current_stage TEXT,
                    tender_no TEXT,
                    po_no TEXT,
                    noa_no TEXT,
                    contract_value TEXT,
                    pg_amount TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS project_aliases (
                    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    alias_type TEXT NOT NULL,
                    alias_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(alias_type, alias_value),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS project_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    timestamp TEXT,
                    sender TEXT,
                    is_outgoing INTEGER DEFAULT 0,
                    stage TEXT,
                    summary_text TEXT,
                    raw_data_json TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(message_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_alias_lookup ON project_aliases(alias_value);
                CREATE INDEX IF NOT EXISTS idx_project_events ON project_events(project_id, timestamp);
            """)

    def _migrate_db(self):
        """Apply non-breaking schema migrations for multi-tier support."""
        with self._get_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(projects)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            
            if 'tier' not in existing_cols:
                conn.execute("ALTER TABLE projects ADD COLUMN tier TEXT DEFAULT 'BUYER'")
            if 'source_domain' not in existing_cols:
                conn.execute("ALTER TABLE projects ADD COLUMN source_domain TEXT")

    @staticmethod
    def normalize_key(s: str) -> str:
        """Normalizes an identifier string for robust matching."""
        if not s:
            return ""
        clean = re.sub(r'[^a-zA-Z0-9]', '', str(s).lower())
        return clean

    def extract_candidate_aliases(self, text_corpus: str) -> List[Tuple[str, str]]:
        """
        Extracts candidate aliases from email subject, body, and filenames.
        Returns list of (alias_type, raw_value).
        """
        candidates = []
        if not text_corpus:
            return candidates

        # 1. Tender Reference Patterns (e.g., powergen_a/Site C&M/2023-24/32 or powergen_a /MM/2025-26/TE/140)
        # Pre-normalize: collapse spaces around '/' so "powergen_a /MM/" → "powergen_a/MM/"
        norm_corpus = re.sub(r'\s*/\s*', '/', text_corpus)
        tender_matches = re.findall(r'(?:powergen_a|powergen_b|BPDB)[A-Za-z0-9\/\-_&]+(?:\d{2,4}[-\/]\d{2,4}[-\/]\d{1,4}|\b\d{2,4}\b)', norm_corpus, re.IGNORECASE)
        for tm in tender_matches:
            candidates.append(("tender_no", tm.strip()))

        short_tenders = re.findall(r'\b20\d{2}-\d{2}\/\d{1,4}\b', text_corpus)
        for st in short_tenders:
            candidates.append(("tender_no", st.strip()))

        # 2. Standard Power Plant PO Numbers (e.g., 322300161, 322400072, 322500059)
        po_matches = re.findall(r'\b322\d{6}\b', text_corpus)
        for po in set(po_matches):
            candidates.append(("po_no", po.strip()))

        # 3. NOA References
        noa_matches = re.findall(r'NOA[A-Za-z0-9\/\-_]+(?:\d{2,4}[-\/]\d{2,4}[-\/]\d{1,4}|\b\d{2,4}\b)', text_corpus, re.IGNORECASE)
        for nm in noa_matches:
            candidates.append(("noa_no", nm.strip()))

        # 4. Canonical Equipment Keywords
        known_equipments = [
            ("edwards rotary vane vacuum pump", "edwards_vacuum_pump"),
            ("soft iron pressure seal ring", "soft_iron_seal_rings"),
            ("spiral wound gasket", "spiral_wound_gasket"),
            ("positive displacement pump", "positive_metering_pump"),
            ("rockwool insulation", "rockwool_insulation"),
            ("gland packing", "gland_packing")
        ]
        text_lower = text_corpus.lower()
        for phrase, key in known_equipments:
            if phrase in text_lower:
                candidates.append(("equipment_key", key))

        return list(set(candidates))

    def resolve_or_create_project(self, email_obj: Dict[str, Any], extracted_data: Optional[Dict[str, Any]] = None, tier: str = 'BUYER', source_domain: str = '') -> Tuple[str, bool]:
        """
        Resolves the email to an existing project_id using aliases.
        If no project exists, creates a new one and registers discovered aliases.
        Returns: (project_id, is_new_project)
        """
        headers = email_obj.get("headers", {})
        subj = headers.get("subject", "")
        body = email_obj.get("body", "")
        att_names = " ".join([a.get("filename", "") for a in email_obj.get("attachments", [])])
        full_corpus = f"{subj} {body[:4000]} {att_names}"

        # 1. Collect candidate aliases
        aliases = self.extract_candidate_aliases(full_corpus)

        # 1b. Thread-based matching — same Gmail thread = same project
        thread_id = email_obj.get("thread_id") or headers.get("thread_id", "")
        if thread_id:
            aliases.append(("thread_id", thread_id))

        if extracted_data:
            if extracted_data.get("tender_no") and extracted_data.get("tender_no") != "N/A":
                aliases.append(("tender_no", extracted_data.get("tender_no")))
            if extracted_data.get("po_number") and extracted_data.get("po_number") != "N/A":
                aliases.append(("po_no", extracted_data.get("po_number")))

        # 2. Check if any alias exists in project_aliases table
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            for alias_type, raw_val in aliases:
                norm_val = self.normalize_key(raw_val)
                row = conn.execute(
                    "SELECT project_id FROM project_aliases WHERE alias_type = ? AND alias_value = ?",
                    (alias_type, norm_val)
                ).fetchone()
                if row:
                    project_id = row["project_id"]
                    # Register any other new aliases for this project
                    self._register_aliases_tx(conn, project_id, aliases, now_iso)
                    return (project_id, False)

            # 3. If no match found, create a new Project Dossier
            from src.tender_parser import clean_dossier_title
            clean_title = clean_dossier_title(subj)
            if not clean_title or clean_title == "Industrial Procurement Package":
                clean_title = re.sub(r'^(?:Re:|Fwd:|FW:)\s*', '', subj, flags=re.IGNORECASE).strip()
            if not clean_title:
                clean_title = f"Procurement Project ({datetime.now().strftime('%Y-%m-%d')})"

            # Generate semantic slug project_id
            slug_base = re.sub(r'[^a-zA-Z0-9]+', '-', clean_title[:40].lower()).strip('-')
            project_id = f"proj-{slug_base}-{datetime.now().strftime('%H%M%S')}"

            plant_name = "প্ল্যান্ট-এ পাওয়ার প্ল্যান্ট (powergen_a)" if "powergen_a" in full_corpus.lower() else "প্ল্যান্ট-বি পাওয়ার প্ল্যান্ট (powergen_b)"
            tender_no = next((v for t, v in aliases if t == "tender_no"), "N/A")
            po_no = next((v for t, v in aliases if t == "po_no"), "N/A")
            noa_no = next((v for t, v in aliases if t == "noa_no"), "N/A")

            conn.execute("""
                INSERT INTO projects (
                    project_id, title, plant_name, current_stage,
                    tender_no, po_no, noa_no, contract_value, pg_amount,
                    created_at, updated_at, tier, source_domain
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, clean_title, plant_name, "1_NEW_RFQ",
                tender_no, po_no, noa_no, "N/A", "N/A",
                now_iso, now_iso, tier, source_domain
            ))

            self._register_aliases_tx(conn, project_id, aliases, now_iso)
            return (project_id, True)

    def _register_aliases_tx(self, conn: sqlite3.Connection, project_id: str, aliases: List[Tuple[str, str]], now_iso: str):
        for alias_type, raw_val in aliases:
            norm_val = self.normalize_key(raw_val)
            if norm_val:
                conn.execute("""
                    INSERT OR IGNORE INTO project_aliases (project_id, alias_type, alias_value, created_at)
                    VALUES (?, ?, ?, ?)
                """, (project_id, alias_type, norm_val, now_iso))

    def record_event(
        self,
        project_id: str,
        thread_id: str,
        message_id: str,
        timestamp: str,
        sender: str,
        is_outgoing: bool,
        stage: str,
        summary_text: str,
        extracted_data: Dict[str, Any]
    ):
        """Records a timeline event in the project dossier and updates project state."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            # 1. Insert Event (Idempotent ON CONFLICT IGNORE)
            conn.execute("""
                INSERT OR IGNORE INTO project_events (
                    project_id, thread_id, message_id, timestamp,
                    sender, is_outgoing, stage, summary_text,
                    raw_data_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, thread_id, message_id, timestamp,
                sender, 1 if is_outgoing else 0, stage, summary_text,
                json.dumps(extracted_data, ensure_ascii=False), now_iso
            ))

            # 2. Update Project Metadata
            updates = ["updated_at = ?", "current_stage = ?"]
            params = [now_iso, stage]

            if extracted_data.get("tender_no") and extracted_data.get("tender_no") != "N/A":
                updates.append("tender_no = ?")
                params.append(extracted_data.get("tender_no"))
            if extracted_data.get("po_number") and extracted_data.get("po_number") != "N/A":
                updates.append("po_no = ?")
                params.append(extracted_data.get("po_number"))
            if extracted_data.get("total_contract_value") and extracted_data.get("total_contract_value") != "N/A":
                updates.append("contract_value = ?")
                params.append(extracted_data.get("total_contract_value"))
            if extracted_data.get("po_number") and extracted_data.get("po_number") != "N/A":
                updates.append("po_no = ?")
                params.append(extracted_data.get("po_number"))
            if extracted_data.get("bg_amount") and extracted_data.get("bg_amount") != "N/A":
                updates.append("pg_amount = ?")
                params.append(extracted_data.get("bg_amount"))

            params.append(project_id)
            sql = f"UPDATE projects SET {', '.join(updates)} WHERE project_id = ?"
            conn.execute(sql, params)

            # 3. Register any new aliases discovered in extracted_data
            new_aliases = []
            if extracted_data.get("tender_no") and extracted_data.get("tender_no") != "N/A":
                new_aliases.append(("tender_no", extracted_data.get("tender_no")))
            if extracted_data.get("po_number") and extracted_data.get("po_number") != "N/A":
                new_aliases.append(("po_no", extracted_data.get("po_number")))
            self._register_aliases_tx(conn, project_id, new_aliases, now_iso)

    def get_cross_thread_history(self, project_id: str, exclude_message_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves complete chronological dialogue history across ALL linked threads for this project.
        """
        with self._get_connection() as conn:
            query = """
                SELECT thread_id, message_id, timestamp, sender, is_outgoing, stage, summary_text, raw_data_json
                FROM project_events
                WHERE project_id = ?
            """
            params = [project_id]
            if exclude_message_id:
                query += " AND message_id != ?"
                params.append(exclude_message_id)
            query += " ORDER BY timestamp ASC, event_id ASC"

            rows = conn.execute(query, params).fetchall()
            history = []
            for idx, r in enumerate(rows, 1):
                raw = {}
                if r["raw_data_json"]:
                    try:
                        raw = json.loads(r["raw_data_json"])
                    except Exception:
                        pass

                is_out = bool(r["is_outgoing"])
                party = "Enterprise Solutions (Vendor)" if is_out else "Buyer / Plant"
                history.append({
                    "turn": idx,
                    "thread_id": r["thread_id"],
                    "message_id": r["message_id"],
                    "date": r["timestamp"] or "N/A",
                    "party": party,
                    "sender": r["sender"],
                    "stage": r["stage"],
                    "snippet": r["summary_text"] or "",
                    "key_details": raw
                })
            return history

    def get_project_summary(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Returns the high-level dossier for a project."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if not row:
                return None
            res = dict(row)

            # Count total threads and events
            threads = conn.execute("SELECT DISTINCT thread_id FROM project_events WHERE project_id = ?", (project_id,)).fetchall()
            events = conn.execute("SELECT COUNT(*) as cnt FROM project_events WHERE project_id = ?", (project_id,)).fetchone()

            res["total_linked_threads"] = len(threads)
            res["total_events"] = events["cnt"] if events else 0
            return res
