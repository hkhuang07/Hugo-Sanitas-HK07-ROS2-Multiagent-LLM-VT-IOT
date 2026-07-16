"""
LanceMemory — LanceDB Vector Memory for Long-term Owner Preferences

LanceDB is embedded (no server process) and stores data as files on disk.
Cache size limited to 256MB per hardware constraints.
All writes are batched — never continuous I/O to avoid Disk Thrashing.

[HẠNCHẾ-#15 FIX] Vector Compaction Background Task:
  - compact_old_vectors() deletes all records older than 72 hours.
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
MAX_VECTOR_AGE_MS       = 259_200_000  # 72 hours in milliseconds


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

            # --- Initialize medical_guidelines table ---
            schema_guidelines = pa.schema([
                pa.field("id", pa.string()),
                pa.field("source", pa.string()),
                pa.field("title", pa.string()),
                pa.field("content", pa.string()),
                pa.field("timestamp_ms", pa.int64()),
                pa.field("embedding", pa.list_(pa.float32(), 384)),
            ])
            if "medical_guidelines" not in table_names:
                self._guidelines_table = await asyncio.to_thread(
                    self._db.create_table, "medical_guidelines", schema=schema_guidelines
                )
                log.info("[LANCE_MEMORY] Created new medical_guidelines table")
            else:
                self._guidelines_table = await asyncio.to_thread(self._db.open_table, "medical_guidelines")
                count = await asyncio.to_thread(self._guidelines_table.count_rows)
                log.info("[LANCE_MEMORY] Loaded medical_guidelines: %d records", count)

            # --- Initialize agent_chat_memory table ---
            schema_chat = pa.schema([
                pa.field("id", pa.string()),
                pa.field("user_prompt", pa.string()),
                pa.field("agent_response", pa.string()),
                pa.field("timestamp_ms", pa.int64()),
                pa.field("embedding", pa.list_(pa.float32(), 384)),
            ])
            if "agent_chat_memory" not in table_names:
                self._chat_table = await asyncio.to_thread(
                    self._db.create_table, "agent_chat_memory", schema=schema_chat
                )
                log.info("[LANCE_MEMORY] Created new agent_chat_memory table")
            else:
                self._chat_table = await asyncio.to_thread(self._db.open_table, "agent_chat_memory")
                count = await asyncio.to_thread(self._chat_table.count_rows)
                log.info("[LANCE_MEMORY] Loaded agent_chat_memory: %d records", count)

            self._initialized = True
        except ImportError:
            log.warning("[LANCE_MEMORY] lancedb not installed — running in mock mode")
        except Exception as e:
            log.error("[LANCE_MEMORY_ERROR] %s", e)

    async def store_emotional_event(self, user_message: str, response: str, user_id: str = "default_user"):
        """Batch write emotional events — avoids continuous disk I/O"""
        self._write_buffer.append({
            "id": f"em_{user_id}_{int(time.time()*1000)}",
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
          1. Delete all records with timestamp_ms older than MAX_VECTOR_AGE_MS (72h)
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
            # Only prune emotional events to preserve the medical baseline indefinitely
            predicate = f"type = 'emotional_event' AND timestamp_ms < {cutoff_ms}"
            await asyncio.to_thread(self._table.delete, predicate)

            count_after = await asyncio.to_thread(self._table.count_rows)
            pruned = count_before - count_after

            # Compact files to reclaim disk space (merge delta files into base)
            try:
                await asyncio.to_thread(self._table.compact_files)
                log.info("[LANCE_COMPACT] Pruned %d vectors (>72h old). Remaining: %d. Disk compacted.",
                         pruned, count_after)
            except AttributeError:
                # compact_files requires lancedb >= 0.5 — degrade gracefully
                log.info("[LANCE_COMPACT] Pruned %d vectors. Remaining: %d. (compact_files not available)",
                         pruned, count_after)

        except Exception as e:
            log.error("[LANCE_COMPACT_DELETE_ERROR] %s", e)

    async def recall_owner_preferences(self, user_id: str = "default_user") -> str:
        """Retrieve a text summary of owner preferences for agent context injection"""
        if not self._initialized or not self._table:
            return ""
        try:
            # Bounded predicate query to filter type and ID prefix directly in LanceDB
            records = await asyncio.to_thread(
                lambda: self._table.search()
                .where(f"type = 'emotional_event' AND id >= 'em_{user_id}_' AND id < 'em_{user_id}_\uFFFF'")
                .to_arrow()
                .to_pylist()
            )
            count = len(records)
            if count == 0:
                return ""
            return f"Đã có {count} sự kiện được ghi nhớ về chủ nhân."
        except Exception as e:
            log.warning("[LANCE_MEMORY] Bounded preferences query failed: %s. Falling back to full table scan.", e)
            try:
                records = await asyncio.to_thread(lambda: self._table.to_arrow().to_pylist())
                count = sum(1 for r in records if r.get("id", "").startswith(f"em_{user_id}_"))
                if count == 0:
                    return ""
                return f"Đã có {count} sự kiện được ghi nhớ về chủ nhân."
            except Exception:
                return ""

    async def sync_medical_baseline(self, body: dict):
        """
        Sync medical profile baseline into LanceDB vector memory.
        This represents the long-term static clinical profile of the owner.
        """
        if not self._initialized or not self._table:
            log.warning("[LANCE_MEMORY] Skipped sync_medical_baseline — not initialized (mock mode)")
            return

        user_id = body.get("userId", "default_user")
        
        # Build a highly detailed, clean string format of the medical baseline
        content = (
            f"BỆNH NHÂN: {body.get('fullName', 'N/A')}\n"
            f"Tuổi: {body.get('age', 'N/A')} | Giới tính: {body.get('gender', 'N/A')}\n"
            f"Chiều cao: {body.get('height', 'N/A')} cm | Cân nặng: {body.get('weight', 'N/A')} kg\n"
            f"Nhóm máu: {body.get('bloodType', 'N/A')}\n"
            f"Tiền sử bệnh lý: {body.get('medicalHistory', 'Không có')}\n"
            f"Tiền sử dị ứng: {body.get('allergies', 'Không dị ứng')}\n"
            f"Người liên hệ khẩn cấp: {body.get('emergencyContactName', 'N/A')} ({body.get('emergencyContactPhone', 'N/A')})"
        )

        record_id = f"mb_{user_id}"
        
        # Perform an upsert (delete old one if exists, then add new one)
        try:
            # Delete any existing medical baseline for this user
            predicate = f"id = '{record_id}'"
            await asyncio.to_thread(self._table.delete, predicate)
            
            # Insert the new baseline
            new_record = {
                "id": record_id,
                "type": "medical_baseline",
                "content": content,
                "timestamp_ms": int(time.time() * 1000),
                "embedding": [0.0] * 384,
            }
            await asyncio.to_thread(self._table.add, [new_record])
            log.info("[LANCE_MEMORY] Successfully synced medical baseline for user %s", user_id)
        except Exception as e:
            log.error("[LANCE_MEMORY_SYNC_ERROR] Failed to sync medical baseline: %s", e)

    async def recall_medical_baseline(self, user_id: str = "default_user") -> str:
        """Retrieve the medical baseline string from LanceDB memory"""
        if not self._initialized or not self._table:
            return "Hồ sơ y tế: Chưa được thiết lập."
        try:
            # Query the table for records of type 'medical_baseline' and matching mb_{user_id} using LanceDB search
            records = await asyncio.to_thread(
                lambda: self._table.search()
                .where(f"type = 'medical_baseline' AND id = 'mb_{user_id}'")
                .to_arrow()
                .to_pylist()
            )
            if not records:
                return "Hồ sơ y tế: Chưa có thông tin cấu hình."
            
            # Return the content of the most recent medical baseline (latest timestamp)
            records.sort(key=lambda x: x.get("timestamp_ms", 0), reverse=True)
            content = records[0]["content"]
            return content
        except Exception as e:
            log.warning("[LANCE_MEMORY] Bounded medical baseline query failed: %s. Falling back to full scan.", e)
            try:
                records = await asyncio.to_thread(lambda: self._table.to_arrow().to_pylist())
                baselines = [r for r in records if r.get("type") == "medical_baseline" and r.get("id") == f"mb_{user_id}"]
                if not baselines:
                    return "Hồ sơ y tế: Chưa có thông tin cấu hình."
                baselines.sort(key=lambda x: x.get("timestamp_ms", 0), reverse=True)
                return baselines[0]["content"]
            except Exception as ex:
                log.error("[LANCE_MEMORY_RECALL_ERROR] %s", ex)
                return "Hồ sơ y tế: Lỗi truy xuất cơ sở dữ liệu."

    async def retrieve_recent_events(self, limit: int = 5, user_id: str = "default_user") -> list:
        """Retrieve the most recent emotional events or preferences for RAG context"""
        if not self._initialized or not self._table:
            return []
        try:
            # Bounded predicate query to filter type and ID prefix, with a quick limit
            records = await asyncio.to_thread(
                lambda: self._table.search()
                .where(f"type = 'emotional_event' AND id >= 'em_{user_id}_' AND id < 'em_{user_id}_\uFFFF'")
                .limit(limit * 2)
                .to_arrow()
                .to_pylist()
            )
            if not records:
                return []
            records.sort(key=lambda x: x.get("timestamp_ms", 0), reverse=True)
            return records[:limit]
        except Exception as e:
            log.warning("[LANCE_MEMORY] Bounded events query failed: %s. Falling back to full scan.", e)
            try:
                records = await asyncio.to_thread(lambda: self._table.to_arrow().to_pylist())
                if not records:
                    return []
                user_records = [r for r in records if r.get("id", "").startswith(f"em_{user_id}_")]
                user_records.sort(key=lambda x: x.get("timestamp_ms", 0), reverse=True)
                return user_records[:limit]
            except Exception as ex:
                log.error("[LANCE_MEMORY_RETRIEVE_ERROR] %s", ex)
                return []

    async def search_similar_patterns(self, query: str, limit: int = 3, user_id: str = "default_user") -> list[dict]:
        """
        Search for similar patterns in owner memory using text-based matching.
        Avoids heavy embedding models to preserve memory and CPU resource limits.
        """
        if not self._initialized or not self._table:
            return []
        try:
            keywords = [kw for kw in query.lower().split() if len(kw) > 1]
            if not keywords:
                return []
                
            # Filter type and user directly in database to avoid loading extraneous users or record types
            records = await asyncio.to_thread(
                lambda: self._table.search()
                .where(f"type = 'emotional_event' AND id >= 'em_{user_id}_' AND id < 'em_{user_id}_\uFFFF'")
                .to_arrow()
                .to_pylist()
            )
            if not records:
                return []
            
            # Score each row based on keyword frequency
            scored_records = []
            for r in records:
                content = r.get("content") or ""
                content_lower = content.lower()
                score = sum(1 for kw in keywords if kw in content_lower)
                if score > 0:
                    r_copy = r.copy()
                    r_copy["score"] = score
                    scored_records.append(r_copy)

            if not scored_records:
                return []

            scored_records.sort(key=lambda x: (x["score"], x.get("timestamp_ms", 0)), reverse=True)
            return scored_records[:limit]
        except Exception as e:
            log.warning("[LANCE_MEMORY] Bounded search failed: %s. Falling back to full scan.", e)
            try:
                records = await asyncio.to_thread(lambda: self._table.to_arrow().to_pylist())
                if not records:
                    return []
                
                keywords = [kw for kw in query.lower().split() if len(kw) > 1]
                if not keywords:
                    return []
                    
                scored_records = []
                for r in records:
                    if not r.get("id", "").startswith(f"em_{user_id}_"):
                        continue
                    content = r.get("content") or ""
                    content_lower = content.lower()
                    score = sum(1 for kw in keywords if kw in content_lower)
                    if score > 0:
                        r_copy = r.copy()
                        r_copy["score"] = score
                        scored_records.append(r_copy)

                if not scored_records:
                    return []

                scored_records.sort(key=lambda x: (x["score"], x.get("timestamp_ms", 0)), reverse=True)
                return scored_records[:limit]
            except Exception as ex:
                log.error("[LANCE_MEMORY_SEARCH_ERROR] %s", ex)
                return []

    async def _crawl_and_ingest_guidelines(self, query: str) -> None:
        import urllib.parse
        import httpx
        import re
        from services.knowledge_ingestion import KnowledgeIngestionService
        
        search_query = f"site:who.int OR site:cdc.gov OR site:moh.gov.vn {query}"
        encoded = urllib.parse.quote_plus(search_query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        
        log.info("[LANCE_MEMORY_CRAWLER] Triggering DuckDuckGo query: %s", search_query)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    log.warning("[LANCE_MEMORY_CRAWLER] DDG request failed with status: %d", resp.status_code)
                    return
                html = resp.text
                
                # Extract uddg target links
                matches = re.findall(r'uddg=([^&"\']+)', html)
                urls = []
                for m in matches:
                    decoded_url = urllib.parse.unquote(m)
                    if any(domain in decoded_url for domain in ["who.int", "cdc.gov", "moh.gov.vn"]):
                        if decoded_url not in urls:
                            urls.append(decoded_url)
                
                if not urls:
                    log.info("[LANCE_MEMORY_CRAWLER] No whitelisted URLs found in search results.")
                    return
                    
                log.info("[LANCE_MEMORY_CRAWLER] Found whitelisted URLs: %s", urls[:3])
                
                ingestion_service = KnowledgeIngestionService(self)
                for target_url in urls[:2]:
                    try:
                        res = await ingestion_service.ingest_url(target_url)
                        log.info("[LANCE_MEMORY_CRAWLER] Ingested URL: %s, result: %s", target_url, res)
                    except Exception as ingest_err:
                        log.warning("[LANCE_MEMORY_CRAWLER] Ingestion of %s failed: %s", target_url, ingest_err)
        except Exception as e:
            log.error("[LANCE_MEMORY_CRAWLER] Background crawl error: %s", e)

    async def search_medical_guidelines(self, query: str, limit: int = 3) -> list[dict]:
        """
        Search for similar patterns in medical guidelines using text-based matching.
        Weights matches in title twice as much as content.
        """
        if not self._initialized or not hasattr(self, "_guidelines_table") or self._guidelines_table is None:
            log.warning("[LANCE_MEMORY] Skipped search_medical_guidelines — guidelines table not initialized")
            return []
            
        async def _perform_search():
            keywords = [kw for kw in query.lower().split() if len(kw) > 1]
            if not keywords:
                return []
            records = await asyncio.to_thread(
                lambda: self._guidelines_table.search()
                .select(["id", "source", "title", "content", "timestamp_ms"])
                .to_arrow()
                .to_pylist()
            )
            if not records:
                return []
            scored_records = []
            for r in records:
                title = (r.get("title") or "").lower()
                content = (r.get("content") or "").lower()
                score = 0
                for kw in keywords:
                    if kw in title:
                        score += 2
                    if kw in content:
                        score += 1
                if score > 0:
                    r_copy = r.copy()
                    r_copy["score"] = score
                    scored_records.append(r_copy)
            if not scored_records:
                return []
            scored_records.sort(key=lambda x: (x["score"], x.get("timestamp_ms", 0)), reverse=True)
            return scored_records[:limit]

        try:
            results = await _perform_search()
            if not results:
                log.info("[LANCE_MEMORY] Guidelines query yielded empty results. Crawling WHO/CDC/MOH for: %s", query)
                await self._crawl_and_ingest_guidelines(query)
                results = await _perform_search()
            return results
        except Exception as e:
            log.warning("[LANCE_MEMORY] Optimized guidelines search failed: %s. Falling back to full scan.", e)
            try:
                await self._crawl_and_ingest_guidelines(query)
                results = await _perform_search()
                return results
            except Exception as ex:
                log.error("[LANCE_MEMORY_GUIDELINE_SEARCH_ERROR] %s", ex)
                return []

    async def ingest_chat_cycle(self, user_prompt: str, agent_response: str, user_id: str = "default_user"):
        """Ingest a single user prompt & agent response into agent_chat_memory table"""
        if not self._initialized:
            await self.initialize()
            
        if not self._initialized or getattr(self, "_chat_table", None) is None:
            log.warning("[LANCE_MEMORY] Skipped ingest_chat_cycle — table not initialized even after retry.")
            return
        try:
            record = {
                "id": f"chat_{user_id}_{int(time.time()*1000)}",
                "user_prompt": user_prompt,
                "agent_response": agent_response,
                "timestamp_ms": int(time.time() * 1000),
                "embedding": [0.0] * 384,
            }
            await asyncio.to_thread(self._chat_table.add, [record])
            log.info("[LANCE_MEMORY] Ingested chat cycle into agent_chat_memory")
        except Exception as e:
            log.error("[LANCE_MEMORY_CHAT_INGEST_ERROR] Failed to ingest chat cycle: %s", e)


