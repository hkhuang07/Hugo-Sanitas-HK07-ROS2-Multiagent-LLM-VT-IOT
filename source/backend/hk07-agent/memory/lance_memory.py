"""
LanceMemory — LanceDB Vector Memory for Long-term Owner Preferences

LanceDB is embedded (no server process) and stores data as files on disk.
Cache size limited to 256MB per hardware constraints.
All writes are batched — never continuous I/O to avoid Disk Thrashing.

[HẠNCHẾ-#15 FIX] Vector Compaction Background Task:
  - compact_old_vectors() deletes all records older than 24 hours.
  - Triggered hourly via asyncio.create_task() from main.py lifespan.
  - Uses asyncio.to_thread() so the LanceDB delete call never blocks the event loop.
  - After deletion, calls self._db.compact_files() to reclaim disk space.
"""

import asyncio
import logging
import os
import time

log = logging.getLogger("hk07.lance_memory")

# ── Compaction Config ────────────────────────────────────────────────────────
COMPACTION_INTERVAL_SEC = 3600   # 1 hour between compaction runs
MAX_VECTOR_AGE_MS       = 86_400_000  # 24 hours in milliseconds


class LanceMemory:
    DB_PATH = os.getenv("LANCE_DB_PATH", "./data/lance_memory")
    MAX_CACHE_MB = 256

    def __init__(self):
        self._db = None
        self._table = None
        self._write_buffer = []
        self._initialized = False

    async def initialize(self):
        """Load LanceDB index from disk (one-time startup, ~50-100ms)"""
        try:
            import lancedb
            import pyarrow as pa

            os.makedirs(self.DB_PATH, exist_ok=True)
            self._db = await asyncio.to_thread(lancedb.connect, self.DB_PATH)

            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("type", pa.string()),       # "emotional_event" | "preference"
                pa.field("content", pa.string()),
                pa.field("timestamp_ms", pa.int64()),
                pa.field("embedding", pa.list_(pa.float32(), 384)),
            ])

            table_names = await asyncio.to_thread(self._db.table_names)
            if "owner_memory" not in table_names:
                self._table = await asyncio.to_thread(
                    self._db.create_table, "owner_memory", schema=schema
                )
                log.info("[LANCE_MEMORY] Created new owner_memory table")
            else:
                self._table = await asyncio.to_thread(self._db.open_table, "owner_memory")
                count = await asyncio.to_thread(self._table.count_rows)
                log.info("[LANCE_MEMORY] Loaded owner_memory: %d records", count)

            self._initialized = True
        except ImportError:
            log.warning("[LANCE_MEMORY] lancedb not installed — running in mock mode")
        except Exception as e:
            log.error("[LANCE_MEMORY_ERROR] %s", e)

    async def store_emotional_event(self, user_message: str, response: str):
        """Batch write emotional events — avoids continuous disk I/O"""
        self._write_buffer.append({
            "id": f"em_{int(time.time()*1000)}",
            "type": "emotional_event",
            "content": f"User: {user_message[:200]} | Hugo: {response[:200]}",
            "timestamp_ms": int(time.time() * 1000),
            "embedding": [0.0] * 384,
        })

        if len(self._write_buffer) >= 10 and self._table:
            await self._flush_buffer()

    async def _flush_buffer(self):
        if not self._write_buffer or not self._table:
            return
        try:
            batch = self._write_buffer.copy()
            self._write_buffer.clear()
            await asyncio.to_thread(self._table.add, batch)
            log.debug("[LANCE_MEMORY] Flushed %d records to disk", len(batch))
        except Exception as e:
            log.error("[LANCE_MEMORY_FLUSH_ERROR] %s", e)

    # ── [HẠNCHẾ-#15] Vector Compaction Background Loop ──────────────────────

    async def run_compaction_loop(self):
        """
        Background asyncio task — runs forever, waking every COMPACTION_INTERVAL_SEC.

        Each cycle:
          1. Delete all records with timestamp_ms older than MAX_VECTOR_AGE_MS (24h)
          2. Compact LanceDB files on disk to reclaim freed space
          3. Log how many vectors were pruned and current table size

        Uses asyncio.to_thread() for all LanceDB I/O to keep event loop free.
        """
        log.info("[LANCE_COMPACT] Compaction loop started — interval=%ds, max_age=%dh",
                 COMPACTION_INTERVAL_SEC, MAX_VECTOR_AGE_MS // 3_600_000)

        while True:
            try:
                await asyncio.sleep(COMPACTION_INTERVAL_SEC)
                await self._compact_old_vectors()
            except asyncio.CancelledError:
                log.info("[LANCE_COMPACT] Compaction loop cancelled — shutdown")
                break
            except Exception as e:
                log.error("[LANCE_COMPACT_ERROR] %s", e)
                # Don't crash the loop — retry next cycle
                await asyncio.sleep(60)

    async def _compact_old_vectors(self):
        """
        Delete vectors older than MAX_VECTOR_AGE_MS, then compact disk files.
        """
        if not self._initialized or not self._table:
            log.debug("[LANCE_COMPACT] Skipped — not initialized (mock mode)")
            return

        cutoff_ms = int(time.time() * 1000) - MAX_VECTOR_AGE_MS

        try:
            # Count before deletion
            count_before = await asyncio.to_thread(self._table.count_rows)

            # LanceDB delete by predicate (runs on thread to avoid event loop block)
            predicate = f"timestamp_ms < {cutoff_ms}"
            await asyncio.to_thread(self._table.delete, predicate)

            count_after = await asyncio.to_thread(self._table.count_rows)
            pruned = count_before - count_after

            # Compact files to reclaim disk space (merge delta files into base)
            try:
                await asyncio.to_thread(self._table.compact_files)
                log.info("[LANCE_COMPACT] Pruned %d vectors (>24h old). Remaining: %d. Disk compacted.",
                         pruned, count_after)
            except AttributeError:
                # compact_files requires lancedb >= 0.5 — degrade gracefully
                log.info("[LANCE_COMPACT] Pruned %d vectors. Remaining: %d. (compact_files not available)",
                         pruned, count_after)

        except Exception as e:
            log.error("[LANCE_COMPACT_DELETE_ERROR] %s", e)

    async def recall_owner_preferences(self) -> str:
        """Retrieve a text summary of owner preferences for agent context injection"""
        if not self._initialized or not self._table:
            return ""
        try:
            count = await asyncio.to_thread(self._table.count_rows)
            if count == 0:
                return ""
            return f"Đã có {count} sự kiện được ghi nhớ về chủ nhân."
        except Exception:
            return ""

    async def retrieve_recent_events(self, limit: int = 5) -> list:
        """Retrieve the most recent emotional events or preferences for RAG context"""
        if not self._initialized or not self._table:
            return []
        try:
            df = await asyncio.to_thread(self._table.to_pandas)
            if df.empty:
                return []
            # Sort by timestamp_ms descending
            df_sorted = df.sort_values(by="timestamp_ms", ascending=False).head(limit)
            return df_sorted.to_dict(orient="records")
        except Exception as e:
            log.error("[LANCE_MEMORY_RETRIEVE_ERROR] %s", e)
            return []

