"""
State Store for Gmail CRM Agent

This module manages the state of processed email messages to avoid
reprocessing the same messages multiple times. Uses JSONL format for
append-only logging with timestamps and reasons.
"""

import json
from pathlib import Path
from typing import Set, Dict, Any, Optional
from datetime import datetime


class StateStore:
    """State store for tracking processed email messages in JSONL format."""

    def __init__(self, store_path: Optional[Path] = None):
        """
        Initialize state store.

        Args:
            store_path: Path to JSONL store file (defaults to data/processed.jsonl)
        """
        self.project_root = Path(__file__).resolve().parents[1]

        if store_path is None:
            self.store_path = self.project_root / "data" / "processed.jsonl"
        else:
            self.store_path = store_path

        # Ensure parent directory exists
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state (in-memory cache for fast lookups)
        self._processed_cache: Set[str] = set()
        self._load_cache()

    def _load_cache(self) -> None:
        """Load processed message IDs into in-memory cache."""
        if not self.store_path.exists():
            return

        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            record = json.loads(line)
                            message_id = record.get("message_id")
                            if message_id:
                                self._processed_cache.add(message_id)
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            continue
        except Exception as e:
            print(f"Warning: Could not load processed cache: {e}")

    def is_processed(self, message_id: str) -> bool:
        """
        Check if a message has been processed.

        Args:
            message_id: Gmail message/thread ID

        Returns:
            True if message has been processed
        """
        return message_id in self._processed_cache

    def mark_processed(
        self,
        message_id: str,
        reason: str = "processed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark a message as processed and append to JSONL store.

        Args:
            message_id: Gmail message/thread ID
            reason: Reason for processing result (e.g., "lead", "spam", "skip", "error")
            metadata: Additional metadata to store
        """
        if message_id in self._processed_cache:
            return  # Already processed

        # Create record
        record = {
            "message_id": message_id,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
        }

        # Add metadata if provided
        if metadata:
            record["metadata"] = metadata

        # Append to JSONL file
        try:
            with open(self.store_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            # Update cache
            self._processed_cache.add(message_id)
        except Exception as e:
            print(f"Warning: Could not save processed state: {e}")

    def get_stats(self) -> Dict[str, int]:
        """
        Get processing statistics from JSONL store.

        Returns:
            Dictionary with counts by reason
        """
        stats: Dict[str, int] = {"total": 0}

        if not self.store_path.exists():
            return stats

        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            record = json.loads(line)
                            stats["total"] += 1

                            reason = record.get("reason", "unknown")
                            stats[reason] = stats.get(reason, 0) + 1
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"Warning: Could not calculate stats: {e}")

        return stats

    def get_processed_count(self) -> int:
        """
        Get count of processed messages.

        Returns:
            Number of processed messages
        """
        return len(self._processed_cache)

    def clear_processed(self) -> None:
        """Clear all processed state (use with caution)."""
        if self.store_path.exists():
            self.store_path.unlink()
        self._processed_cache.clear()

    def get_processing_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive processing summary.

        Returns:
            Dictionary with processing summary
        """
        stats = self.get_stats()
        total = stats.get("total", 0)

        # Calculate success rate
        successful = stats.get("lead", 0) + stats.get("skip", 0)
        success_rate = round((successful / total) * 100, 2) if total > 0 else 0.0

        # Get last run timestamp
        last_run = None
        if self.store_path.exists() and total > 0:
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        last_record = json.loads(lines[-1])
                        last_run = last_record.get("timestamp")
            except Exception:
                pass

        return {
            "total_processed": total,
            "leads_found": stats.get("lead", 0),
            "skipped": stats.get("skip", 0) + stats.get("spam", 0),
            "errors": stats.get("error", 0),
            "last_run": last_run,
            "processed_threads_count": total,
            "success_rate": success_rate,
        }

    def add_processing_result(self, message_id: str, result: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add processing result and mark as processed.

        Args:
            message_id: Gmail message/thread ID
            result: Processing result ('lead', 'skip', 'spam', 'error')
            metadata: Additional metadata to store
        """
        self.mark_processed(message_id, reason=result, metadata=metadata)


# Backward compatibility functions
def load_state() -> Dict[str, Any]:
    """Legacy function - use StateStore class instead."""
    store = StateStore()
    return {
        "processed_thread_ids": list(store._processed_cache),
        "stats": store.get_stats(),
    }


def save_state(state: Dict[str, Any]) -> None:
    """Legacy function - use StateStore class instead."""
    # No-op for backward compatibility
    pass


def processed_ids_set(state: Dict[str, Any]) -> Set[str]:
    """Legacy function - use StateStore class instead."""
    return set(state.get("processed_message_ids", []))


def mark_processed(state: Dict[str, Any], *message_ids: str) -> None:
    """Legacy function - use StateStore class instead."""
    store = StateStore()
    for msg_id in message_ids:
        store.mark_processed(msg_id)
