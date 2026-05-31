"""
LanceMemory — LanceDB Vector Memory for Long-term Owner Preferences

LanceDB is embedded (no server process) and stores data as files on disk.
Cache size limited to 256MB per hardware constraints.
All writes are batched — never continuous I/O to avoid Disk Thrashing.
"""

import asyncio
import logging
import os

log = logging.getLogger("hk07.lance_memory")


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
                pa.field("type", pa.string()),      # "emotional_event" | "preference"
                pa.field("content", pa.string()),
                pa.field("timestamp_ms", pa.int64()),
                pa.field("embedding", pa.list_(pa.float32(), 384)),  # Placeholder
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
        import time
        self._write_buffer.append({
            "id": f"em_{int(time.time()*1000)}",
            "type": "emotional_event",
            "content": f"User: {user_message[:200]} | Hugo: {response[:200]}",
            "timestamp_ms": int(time.time() * 1000),
            "embedding": [0.0] * 384,  # Placeholder; real embedding via Gemini API
        })

        # Flush buffer every 10 events (batching)
        if len(self._write_buffer) >= 10 and self._table:
            await self._flush_buffer()

    async def _flush_buffer(self):
        if not self._write_buffer or not self._table:
            return
        try:
            import pyarrow as pa
            batch = self._write_buffer.copy()
            self._write_buffer.clear()
            await asyncio.to_thread(self._table.add, batch)
            log.debug("[LANCE_MEMORY] Flushed %d records to disk", len(batch))
        except Exception as e:
            log.error("[LANCE_MEMORY_FLUSH_ERROR] %s", e)

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
