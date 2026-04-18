"""
Realised-Value Replay Buffer Repository

This module implements the storage and retrieval system for replaying
successful ideas from previous brainstorming sessions.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from .models import (
    ReplayCandidate,
    ReplayRecord,
    ReplayStatus,
    ReplaySummary,
)

logger = logging.getLogger(__name__)


class ReplayBuffer:
    """
    Repository for storing and retrieving successful ideas for replay.

    The buffer maintains a database of high-performing ideas from previous
    sessions, with tracking of their realized value when replayed.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize the replay buffer repository."""
        if db_path is None:
            # Use absolute path to prevent creation at root
            db_path = str(Path(__file__).parent.parent.parent.parent / 'data' / 'brainstorm_replay.db')
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()

        # Replay records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS replay_records (
                id TEXT PRIMARY KEY,
                original_idea_id TEXT NOT NULL,
                content TEXT NOT NULL,
                persona TEXT,
                reasoning_path TEXT,
                original_score REAL DEFAULT 0.0,
                contexts_used TEXT,
                success_scores TEXT,
                replay_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                adaptation_history TEXT,
                tags TEXT,
                status TEXT DEFAULT 'fresh',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_replayed TEXT,
                effectiveness_trend TEXT
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_effectiveness
            ON replay_records(original_score DESC, replay_count DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_persona
            ON replay_records(persona)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON replay_records(status)
        """)

        # Replay sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS replay_sessions (
                session_id TEXT PRIMARY KEY,
                topic TEXT,
                records_retrieved INTEGER DEFAULT 0,
                records_used INTEGER DEFAULT 0,
                avg_success REAL DEFAULT 0.0,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._conn.commit()

    def _serialize_list(self, data: list) -> str:
        """Serialize list to JSON."""
        return json.dumps(data) if data else "[]"

    def _deserialize_list(self, data: str) -> list:
        """Deserialize JSON to list."""
        try:
            return json.loads(data) if data else []
        except json.JSONDecodeError:
            return []

    def add_record(self, record: ReplayRecord) -> None:
        """
        Add a record to the replay buffer.

        Args:
            record: The replay record to add
        """
        cursor = self._conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO replay_records
            (id, original_idea_id, content, persona, reasoning_path, original_score,
             contexts_used, success_scores, replay_count, success_count,
             adaptation_history, tags, status, created_at, last_replayed, effectiveness_trend)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.id,
            record.original_idea_id,
            record.content,
            record.persona,
            self._serialize_list(record.reasoning_path),
            record.original_score,
            self._serialize_list(record.contexts_used),
            self._serialize_list(record.success_scores),
            record.replay_count,
            record.success_count,
            json.dumps(record.adaptation_history),
            self._serialize_list(record.tags),
            record.status.value,
            record.created_at,
            record.last_replayed,
            self._serialize_list(record.effectiveness_trend),
        ))

        self._conn.commit()
        logger.debug(f"Added replay record: {record.id[:8]}...")

    def add_from_session(
        self,
        session_id: str,
        topic: str,
        ideas: list,  # List of Idea objects
        min_score: float = 70.0,
    ) -> dict[str, Any]:
        """
        Add high-scoring ideas from a session to the replay buffer.

        Args:
            session_id: Session identifier
            topic: The session topic
            ideas: List of ideas from the session
            min_score: Minimum score to qualify for replay buffer

        Returns:
            Summary of added records
        """
        added = 0
        skipped = 0

        for idea in ideas:
            if idea.score >= min_score:
                # Check if already exists
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT id FROM replay_records WHERE original_idea_id = ?",
                    (idea.id,),
                )

                if not cursor.fetchone():
                    # Extract tags from metadata
                    tags = []
                    if hasattr(idea, 'metadata'):
                        if "domains" in idea.metadata:
                            tags.extend(idea.metadata["domains"])
                        if "category" in idea.metadata:
                            tags.append(idea.metadata["category"])

                    record = ReplayRecord.from_idea(
                        idea_id=idea.id,
                        content=idea.content,
                        persona=idea.persona,
                        reasoning_path=idea.reasoning_path,
                        score=idea.score,
                        tags=tags,
                    )
                    # Tag with topic for retrieval
                    record.tags.append(topic.lower())

                    self.add_record(record)
                    added += 1
                else:
                    skipped += 1

        summary = {
            "session_id": session_id,
            "topic": topic,
            "added": added,
            "skipped": skipped,  # Already existed
            "total_ideas": len(ideas),
        }

        logger.info(f"Replay buffer update: +{added}, {skipped} already exist")
        return summary

    def get_record(self, record_id: str) -> ReplayRecord | None:
        """
        Get a specific record by ID.

        Args:
            record_id: The record ID

        Returns:
            The record or None if not found
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM replay_records WHERE id = ?",
            (record_id,),
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_record(row)
        return None

    def _row_to_record(self, row: sqlite3.Row) -> ReplayRecord:
        """Convert database row to ReplayRecord."""
        row_dict = dict(row)
        return ReplayRecord(
            id=row_dict["id"],
            original_idea_id=row_dict["original_idea_id"],
            content=row_dict["content"],
            persona=row_dict["persona"] or "",
            reasoning_path=self._deserialize_list(row_dict["reasoning_path"]),
            original_score=row_dict["original_score"],
            contexts_used=self._deserialize_list(row_dict["contexts_used"]),
            success_scores=self._deserialize_list(row_dict["success_scores"]),
            replay_count=row_dict["replay_count"],
            success_count=row_dict["success_count"],
            adaptation_history=json.loads(row_dict["adaptation_history"] or "[]"),
            tags=self._deserialize_list(row_dict["tags"]),
            status=ReplayStatus(row_dict["status"] or "fresh"),
            created_at=row_dict["created_at"],
            last_replayed=row_dict["last_replayed"] or "",
            effectiveness_trend=self._deserialize_list(row_dict["effectiveness_trend"]),
        )

    def find_candidates(
        self,
        topic: str,
        max_results: int = 5,
        min_effectiveness: float = 50.0,
        persona: str | None = None,
    ) -> list[ReplayCandidate]:
        """
        Find candidate ideas for replay based on topic similarity.

        Args:
            topic: The current topic
            max_results: Maximum number of candidates to return
            min_effectiveness: Minimum effectiveness score
            persona: Optional persona filter

        Returns:
            List of replay candidates
        """
        cursor = self._conn.cursor()

        # Build query with optional filters
        query = """
            SELECT * FROM replay_records
            WHERE original_score >= ?
        """
        params = [min_effectiveness]

        if persona:
            query += " AND persona = ?"
            params.append(persona)

        query += " ORDER BY original_score DESC, replay_count DESC LIMIT ?"
        params.append(max_results * 3)  # Get more, then filter by similarity

        cursor.execute(query, params)
        rows = cursor.fetchall()

        candidates = []
        topic_lower = topic.lower()

        for row in rows:
            record = self._row_to_record(row)

            # Calculate similarity based on tag and content overlap
            similarity = self._calculate_similarity(record, topic_lower)

            if similarity > 0.1:  # Minimum similarity threshold
                # Calculate relevance (similarity + effectiveness)
                relevance = (
                    similarity * 0.5 +
                    (record.effectiveness / 100.0) * 0.5
                )

                adapted = record.adapt_to_context(topic)

                candidates.append(ReplayCandidate(
                    record=record,
                    similarity_score=similarity,
                    relevance_score=relevance,
                    adapted_content=adapted,
                    replay_reason=self._generate_reason(record, similarity),
                ))

        # Sort by priority and limit
        candidates.sort(key=lambda c: c.priority, reverse=True)
        return candidates[:max_results]

    def _calculate_similarity(self, record: ReplayRecord, topic_lower: str) -> float:
        """Calculate similarity score (0-1) between record and topic."""
        # Check tag overlap
        tag_matches = 0
        for tag in record.tags:
            if tag.lower() in topic_lower:
                tag_matches += 1
            # Partial match
            elif any(word in tag.lower() for word in topic_lower.split()):
                tag_matches += 0.5

        tag_score = min(1.0, tag_matches / max(1, len(record.tags)))

        # Check content keyword overlap
        content_words = set(record.content.lower().split())
        topic_words = set(topic_lower.split())
        word_overlap = len(content_words & topic_words)
        content_score = min(1.0, word_overlap / max(1, len(topic_words)))

        # Combined similarity
        return tag_score * 0.7 + content_score * 0.3

    def _generate_reason(self, record: ReplayRecord, similarity: float) -> str:
        """Generate explanation for why this record was suggested."""
        reasons = []

        if record.is_proven:
            reasons.append(f"Proven success ({record.success_count}/{record.replay_count} replays)")

        if record.avg_success >= 70:
            reasons.append(f"High avg success ({record.avg_success:.0f})")

        if similarity > 0.5:
            reasons.append("Strong topic similarity")

        if record.persona:
            reasons.append(f"From {record.persona} persona")

        return "; ".join(reasons) if reasons else "Available for replay"

    def record_replay_session(
        self,
        session_id: str,
        topic: str,
        retrieved: int,
        used: int,
        avg_success: float,
    ) -> None:
        """
        Record a replay session.

        Args:
            session_id: Session identifier
            topic: The session topic
            retrieved: Number of records retrieved
            used: Number of records actually used
            avg_success: Average success of replayed ideas
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO replay_sessions
            (session_id, topic, records_retrieved, records_used, avg_success)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, topic, retrieved, used, avg_success))
        self._conn.commit()

    def get_stats(self) -> ReplaySummary:
        """Get summary statistics about the replay buffer."""
        cursor = self._conn.cursor()

        # Total records
        cursor.execute("SELECT COUNT(*) as count FROM replay_records")
        total = cursor.fetchone()["count"]

        # Proven records (multi-success, good rate)
        cursor.execute("""
            SELECT COUNT(*) as count FROM replay_records
            WHERE replay_count >= 2 AND
                  CAST(success_count AS REAL) / CAST(replay_count AS REAL) >= 0.5 AND
                  original_score >= 60
        """)
        proven = cursor.fetchone()["count"]

        # Average stats
        cursor.execute("""
            SELECT AVG(replay_count) as avg_replay,
                   AVG(CAST(success_count AS REAL) / replay_count) as avg_rate
            FROM replay_records
            WHERE replay_count > 0
        """)
        stats_row = cursor.fetchone()
        avg_replay = stats_row["avg_replay"] or 0.0
        avg_rate = stats_row["avg_rate"] or 0.0

        # Top personas by effectiveness
        cursor.execute("""
            SELECT persona,
                   AVG(original_score) * AVG(CAST(success_count + 1 AS REAL) / (replay_count + 1)) as effectiveness
            FROM replay_records
            WHERE persona IS NOT NULL AND persona != ''
            GROUP BY persona
            ORDER BY effectiveness DESC
            LIMIT 5
        """)
        top_personas = [(r["persona"], r["effectiveness"]) for r in cursor.fetchall()]

        # Freshness ratio (never replayed / total)
        cursor.execute("""
            SELECT CAST(COUNT(*) as REAL) / (SELECT COUNT(*) FROM replay_records) as ratio
            FROM replay_records
            WHERE replay_count = 0
        """)
        freshness = cursor.fetchone()["ratio"] or 0.0

        return ReplaySummary(
            total_records=total,
            proven_records=proven,
            avg_replay_count=avg_replay,
            avg_success_rate=avg_rate,
            top_personas=top_personas,
            freshness_ratio=freshness,
        )

    def evict_low_value(self, max_records: int = 1000) -> int:
        """
        Evict lowest-value records to maintain buffer size.

        Args:
            max_records: Maximum number of records to keep

        Returns:
            Number of records evicted
        """
        cursor = self._conn.cursor()

        # Count current records
        cursor.execute("SELECT COUNT(*) as count FROM replay_records")
        current_count = cursor.fetchone()["count"]

        if current_count <= max_records:
            return 0

        # Evict lowest effectiveness records
        to_remove = current_count - max_records

        cursor.execute("""
            DELETE FROM replay_records
            WHERE id IN (
                SELECT id FROM replay_records
                ORDER BY
                    CASE WHEN replay_count = 0 THEN original_score ELSE effectiveness_trend END ASC,
                    replay_count ASC,
                    created_at ASC
                LIMIT ?
            )
        """, (to_remove,))

        self._conn.commit()
        logger.info(f"Evicted {to_remove} low-value replay records")
        return to_remove

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global buffer instance
_global_buffer: ReplayBuffer | None = None


def get_global_buffer(db_path: str | None = None) -> ReplayBuffer:
    if db_path is None:
        db_path = str(Path(__file__).parent.parent.parent.parent / 'data' / 'brainstorm_replay.db')
    """Get or create the global replay buffer instance."""
    global _global_buffer
    if _global_buffer is None or _global_buffer.db_path != db_path:
        _global_buffer = ReplayBuffer(db_path)
    return _global_buffer
