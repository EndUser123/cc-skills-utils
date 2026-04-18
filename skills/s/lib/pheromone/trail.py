"""
Pheromone Trail Repository - Managing Exploration Path Memory

This module implements the main pheromone trail system.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    ExplorationGuidance,
    PathSegmentType,
    PathSignature,
    PheromoneNode,
)

logger = logging.getLogger(__name__)


class PheromoneTrail:
    """
    Repository for pheromone trail management.

    The trail maintains a graph of exploration paths with pheromone strengths.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize the pheromone trail repository."""
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent.parent / "data" / "brainstorm_pheromones.db")
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()

        # Nodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pheromone_nodes (
                id TEXT PRIMARY KEY,
                signature_hash TEXT NOT NULL,
                pheromone_strength REAL DEFAULT 0.0,
                deposit_count INTEGER DEFAULT 0,
                last_deposit TEXT,
                last_evaporation TEXT,
                success_scores TEXT,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signature_hash
            ON pheromone_nodes(signature_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pheromone_strength
            ON pheromone_nodes(pheromone_strength DESC)
        """)

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pheromone_sessions (
                session_id TEXT PRIMARY KEY,
                topic TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                nodes_deposited INTEGER DEFAULT 0,
                total_strength REAL DEFAULT 0.0
            )
        """)

        self._conn.commit()

    def _save_node(self, node: PheromoneNode) -> None:
        """Save node to database."""
        cursor = self._conn.cursor()

        # Serialize complex fields
        success_scores_json = json.dumps(node.success_scores)
        metadata_json = json.dumps(node.metadata)

        # Check if exists
        cursor.execute(
            "SELECT id FROM pheromone_nodes WHERE id = ?",
            (node.id,),
        )

        if cursor.fetchone():
            # Update
            cursor.execute("""
                UPDATE pheromone_nodes
                SET signature_hash = ?,
                    pheromone_strength = ?,
                    deposit_count = ?,
                    last_deposit = ?,
                    last_evaporation = ?,
                    success_scores = ?,
                    metadata = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                node.signature_hash,
                node.pheromone_strength,
                node.deposit_count,
                node.last_deposit,
                node.last_evaporation,
                success_scores_json,
                metadata_json,
                node.id,
            ))
        else:
            # Insert
            cursor.execute("""
                INSERT INTO pheromone_nodes
                (id, signature_hash, pheromone_strength, deposit_count,
                 last_deposit, last_evaporation, success_scores, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.id,
                node.signature_hash,
                node.pheromone_strength,
                node.deposit_count,
                node.last_deposit,
                node.last_evaporation,
                success_scores_json,
                metadata_json,
            ))

        self._conn.commit()

    def get_or_create_node(self, signature: PathSignature) -> PheromoneNode:
        """Get existing node or create new one for a signature."""
        cursor = self._conn.cursor()

        # Try to find existing node
        cursor.execute(
            "SELECT * FROM pheromone_nodes WHERE signature_hash = ?",
            (signature.hash,),
        )
        row = cursor.fetchone()

        if row:
            # Convert Row to dict for safe access
            row_dict = dict(row)
            return PheromoneNode.from_dict({
                "id": row_dict["id"],
                "signature_hash": row_dict["signature_hash"],
                "pheromone_strength": row_dict["pheromone_strength"],
                "deposit_count": row_dict["deposit_count"],
                "last_deposit": row_dict["last_deposit"],
                "last_evaporation": row_dict["last_evaporation"],
                "success_scores": json.loads(row_dict["success_scores"]) if row_dict["success_scores"] else [],
                "metadata": json.loads(row_dict["metadata"]) if row_dict.get("metadata") else {},
            })

        # Create new node
        node = PheromoneNode(signature_hash=signature.hash)
        self._save_node(node)
        return node

    def deposit(
        self,
        signature: PathSignature,
        score: float,
        weight: float = 1.0,
    ) -> PheromoneNode:
        """Deposit pheromones for a successful exploration path."""
        node = self.get_or_create_node(signature)
        node.deposit(score, weight)
        self._save_node(node)

        logger.debug(
            f"Deposited pheromones: {signature.hash[:8]}... "
            f"strength={node.pheromone_strength:.1f} score={score:.1f}"
        )

        return node

    def deposit_from_idea(
        self,
        topic: str,
        persona: str,
        reasoning_path: list[str],
        score: float,
        domains: list[str] | None = None,
    ) -> PheromoneNode:
        """Deposit pheromones from a single successful idea."""
        signature = PathSignature.from_idea(
            topic=topic,
            persona=persona,
            reasoning_path=reasoning_path,
            domains=domains,
        )

        # Weight deposit by score (high scores get more pheromone)
        weight = min(2.0, score / 50.0) if score > 0 else 0.5

        return self.deposit(signature, score, weight)

    def deposit_from_session(
        self,
        session_id: str,
        topic: str,
        ideas: list[Any],  # List of Idea objects
        min_score: float = 60.0,
    ) -> dict[str, Any]:
        """Deposit pheromones from a complete brainstorm session."""
        deposited = 0
        total_strength = 0.0
        nodes_updated = []

        for idea in ideas:
            if idea.score >= min_score:
                node = self.deposit_from_idea(
                    topic=topic,
                    persona=idea.persona,
                    reasoning_path=idea.reasoning_path,
                    score=idea.score,
                    domains=idea.metadata.get("domains"),
                )
                deposited += 1
                total_strength += node.pheromone_strength
                nodes_updated.append(node.id)

        # Record session
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO pheromone_sessions
            (session_id, topic, nodes_deposited, total_strength)
            VALUES (?, ?, ?, ?)
        """, (session_id, topic, deposited, total_strength))
        self._conn.commit()

        summary = {
            "session_id": session_id,
            "deposited": deposited,
            "total_ideas": len(ideas),
            "total_strength": total_strength,
            "nodes_updated": nodes_updated,
        }

        logger.info(f"Session deposit: {deposited}/{len(ideas)} ideas, strength={total_strength:.1f}")

        return summary

    def evaporate_all(self, max_age_hours: float = 168) -> dict[str, Any]:
        """Apply evaporation to all nodes."""
        cursor = self._conn.cursor()

        # Get all nodes with recent deposits
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        cursor.execute("""
            SELECT id, signature_hash, pheromone_strength, last_deposit, last_evaporation
            FROM pheromone_nodes
            WHERE CAST(strftime('%s', last_deposit) AS REAL) > ?
        """, (cutoff,))

        rows = cursor.fetchall()

        total_evaporated = 0.0
        nodes_updated = []

        for row in rows:
            row_dict = dict(row)
            node = PheromoneNode.from_dict({
                "id": row_dict["id"],
                "signature_hash": row_dict["signature_hash"],
                "pheromone_strength": row_dict["pheromone_strength"],
                "last_deposit": row_dict["last_deposit"],
                "last_evaporation": row_dict["last_evaporation"],
            })

            old_strength = node.pheromone_strength
            node.evaporate()
            self._save_node(node)

            evaporated = old_strength - node.pheromone_strength
            if evaporated > 0.1:
                total_evaporated += evaporated
                nodes_updated.append(node.id)

        summary = {
            "nodes_processed": len(rows),
            "nodes_updated": len(nodes_updated),
            "total_evaporated": total_evaporated,
        }

        logger.info(f"Evaporation: {len(nodes_updated)}/{len(rows)} nodes, {total_evaporated:.1f} strength")

        return summary

    def get_guidance(
        self,
        topic: str,
        threshold: float = 100.0,
        max_results: int = 5,
    ) -> ExplorationGuidance:
        """Get exploration guidance for a topic based on pheromone trails."""
        cursor = self._conn.cursor()

        # Find nodes with strong pheromone
        cursor.execute("""
            SELECT signature_hash, pheromone_strength, success_scores, metadata
            FROM pheromone_nodes
            WHERE pheromone_strength >= ?
            ORDER BY pheromone_strength DESC
            LIMIT ?
        """, (threshold, max_results * 3))

        rows = cursor.fetchall()

        guidance = ExplorationGuidance()

        # Extract suggestions from strong nodes
        persona_scores: dict[str, float] = {}
        domain_scores: dict[str, float] = {}
        direction_scores: dict[str, float] = {}

        for row in rows:
            row_dict = dict(row)
            strength = row_dict["pheromone_strength"]
            success_scores = json.loads(row_dict["success_scores"]) if row_dict["success_scores"] else []
            avg_score = sum(success_scores) / len(success_scores) if success_scores else 50.0

            # Combined strength metric (pheromone + success rate)
            combined = strength * (avg_score / 100.0)

            # Try to find segments from metadata
            metadata_str = row_dict["metadata"]
            metadata = json.loads(metadata_str) if metadata_str else {}
            segments = metadata.get("segments", [])

            for segment in segments:
                seg_type = segment.get("segment_type")
                value = segment.get("value")

                if seg_type == PathSegmentType.PERSONA:
                    persona_scores[value] = persona_scores.get(value, 0) + combined
                elif seg_type == PathSegmentType.DOMAIN_SHIFT:
                    domain_scores[value] = domain_scores.get(value, 0) + combined
                elif seg_type == PathSegmentType.DIRECTION:
                    direction_scores[value] = direction_scores.get(value, 0) + combined

        # Sort and limit results
        guidance.suggested_personas = sorted(
            persona_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:max_results]

        guidance.suggested_domains = sorted(
            domain_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:max_results]

        guidance.suggested_directions = sorted(
            direction_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:max_results]

        # Calculate confidence based on total strength
        total_strength = sum(strength for _, strength in [
            *guidance.suggested_personas,
            *guidance.suggested_domains,
            *guidance.suggested_directions,
        ])

        guidance.confidence = min(1.0, total_strength / 1000.0)

        return guidance

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the pheromone trail."""
        cursor = self._conn.cursor()

        # Total nodes
        cursor.execute("SELECT COUNT(*) as count FROM pheromone_nodes")
        total_nodes = cursor.fetchone()["count"]

        # Strong nodes
        cursor.execute("SELECT COUNT(*) as count FROM pheromone_nodes WHERE pheromone_strength > 200")
        strong_nodes = cursor.fetchone()["count"]

        # Fresh nodes (deposited in last 7 days)
        cursor.execute("""
            SELECT COUNT(*) as count FROM pheromone_nodes
            WHERE CAST(strftime('%s', last_deposit) AS REAL) > ?
        """, (datetime.now().timestamp() - (7 * 24 * 3600),))
        fresh_nodes = cursor.fetchone()["count"]

        # Total sessions
        cursor.execute("SELECT COUNT(*) as count FROM pheromone_sessions")
        total_sessions = cursor.fetchone()["count"]

        # Average strength
        cursor.execute("SELECT AVG(pheromone_strength) as avg FROM pheromone_nodes WHERE pheromone_strength > 0")
        avg_strength = cursor.fetchone()["avg"] or 0

        return {
            "total_nodes": total_nodes,
            "strong_nodes": strong_nodes,
            "fresh_nodes": fresh_nodes,
            "total_sessions": total_sessions,
            "avg_pheromone_strength": round(avg_strength, 2),
        }

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


# Global trail instance
_global_trail: PheromoneTrail | None = None


def get_global_trail(db_path: str | None = None) -> PheromoneTrail:
    if db_path is None:
        db_path = str(Path(__file__).parent.parent.parent.parent / "data" / "brainstorm_pheromones.db")
    """Get or create the global pheromone trail instance."""
    global _global_trail
    if _global_trail is None or _global_trail.db_path != db_path:
        _global_trail = PheromoneTrail(db_path)
    return _global_trail
