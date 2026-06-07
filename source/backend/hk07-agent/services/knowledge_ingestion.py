"""
KnowledgeIngestionService — Scrapes and indexes curated medical guidelines.
Enforces whitelist validation (WHO, CDC, MoH VN) and handles HTML-to-text extraction.
"""

import asyncio
import logging
import re
import time
from urllib.parse import urlparse
from html.parser import HTMLParser
import httpx

log = logging.getLogger("hk07.knowledge_ingestion")

# Curated Allowlist Domains
ALLOWED_DOMAINS = [
    "who.int",
    "cdc.gov",
    "moh.gov.vn"
]


class HTMLTextExtractor(HTMLParser):
    """
    Lightweight, fast HTML-to-Text parser based on standard library HTMLParser.
    Avoids heavy BeautifulSoup dependencies.
    """
    def __init__(self):
        super().__init__()
        self.text = []
        self.ignore_tags = {
            "script", "style", "head", "title", "meta", "link", 
            "noscript", "iframe", "header", "footer", "nav"
        }
        self.current_tag = None
        self.ignore_depth = 0

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag in self.ignore_tags:
            self.ignore_depth += 1

    def handle_endtag(self, tag):
        if tag in self.ignore_tags:
            self.ignore_depth = max(0, self.ignore_depth - 1)
        if self.current_tag == tag:
            self.current_tag = None

    def handle_data(self, data):
        if self.ignore_depth == 0:
            text = data.strip()
            if text:
                # Normalize spaces
                text = re.sub(r'\s+', ' ', text)
                self.text.append(text)

    def get_text(self) -> str:
        # Separate blocks with newlines
        return "\n".join(self.text)


class KnowledgeIngestionService:
    def __init__(self, memory):
        self.memory = memory

    @staticmethod
    def validate_url(url: str) -> bool:
        """Verify the URL is from one of the allowlisted medical domains."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove port if present
            domain = domain.split(":")[0]
            
            # Match domain or subdomains (e.g. cdc.gov or www.cdc.gov)
            for allowed in ALLOWED_DOMAINS:
                if domain == allowed or domain.endswith("." + allowed):
                    return True
            return False
        except Exception as e:
            log.error("[INGEST_VALIDATION_ERROR] Invalid URL: %s, Error: %s", url, e)
            return False

    async def ingest_url(self, url: str) -> dict:
        """
        Asynchronously fetches and indexes the content from an allowlisted URL.
        Returns a dict summarizing the status and chunks added.
        """
        if not self.validate_url(url):
            log.warning("[INGEST_BLOCKED] URL not in allowlist: %s", url)
            return {"status": "blocked", "message": "Domain is not in the allowlist (WHO, CDC, MoH VN)."}

        log.info("[INGEST_START] Ingesting URL: %s", url)
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return {"status": "error", "message": f"HTTP error {response.status_code}"}
                
                html_content = response.text

            # Extract title using simple regex
            title_match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Cẩm nang y học"
            # Clean up title
            title = re.sub(r'\s+', ' ', title)

            # Extract body text using HTMLTextExtractor
            extractor = HTMLTextExtractor()
            extractor.feed(html_content)
            body_text = extractor.get_text()

            # Clean and filter body text
            body_text = self._clean_extracted_text(body_text)

            if not body_text:
                return {"status": "error", "message": "No meaningful text could be extracted from page."}

            # Ingest content into LanceDB guidelines table
            chunks_added = await self.ingest_text(source=url, title=title, text=body_text)
            
            return {
                "status": "success",
                "url": url,
                "title": title,
                "chunks_added": chunks_added,
                "message": f"Successfully ingested {chunks_added} guideline chunks."
            }

        except Exception as e:
            log.error("[INGEST_FAILED] Ingesting URL: %s, Error: %s", url, e)
            return {"status": "error", "message": str(e)}

    async def ingest_text(self, source: str, title: str, text: str) -> int:
        """
        Splits clean text into chunks and registers them in the LanceDB guidelines table.
        """
        if not self.memory or not hasattr(self.memory, "_guidelines_table") or self.memory._guidelines_table is None:
            log.error("[INGEST_DB_ERROR] LanceMemory guidelines table is not initialized")
            return 0

        chunks = self.chunk_text(text, max_chunk_size=800)
        records = []
        base_time_ms = int(time.time() * 1000)

        for i, chunk in enumerate(chunks):
            # Clean the chunk content from extreme spacing
            chunk_content = chunk.strip()
            if not chunk_content:
                continue
                
            records.append({
                "id": f"g_{base_time_ms}_{i}",
                "source": source,
                "title": title,
                "content": chunk_content,
                "timestamp_ms": base_time_ms + i,  # slight offset to ensure stable sorting
                "embedding": [0.0] * 384
            })

        if records:
            try:
                await asyncio.to_thread(self.memory._guidelines_table.add, records)
                log.info("[INGEST_DB_SUCCESS] Added %d records from source: %s", len(records), source)
                return len(records)
            except Exception as e:
                log.error("[INGEST_DB_WRITE_ERROR] Failed to save chunks: %s", e)
                return 0
        return 0

    @staticmethod
    def chunk_text(text: str, max_chunk_size: int = 800) -> list[str]:
        """
        Intelligently splits text into chunks targeting ~max_chunk_size.
        Attempts to split on paragraph/newline boundaries first to preserve sentence semantics.
        """
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            # If a single paragraph is longer than max_chunk_size, split it into sentences
            if len(para) > max_chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split paragraph by sentence ending characters
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    if current_size + len(sentence) > max_chunk_size:
                        if current_chunk:
                            chunks.append("\n".join(current_chunk))
                        current_chunk = [sentence]
                        current_size = len(sentence)
                    else:
                        current_chunk.append(sentence)
                        current_size += len(sentence) + 1
            else:
                if current_size + len(para) > max_chunk_size:
                    if current_chunk:
                        chunks.append("\n".join(current_chunk))
                    current_chunk = [para]
                    current_size = len(para)
                else:
                    current_chunk.append(para)
                    current_size += len(para) + 1

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _clean_extracted_text(self, text: str) -> str:
        """Cleans up raw parsed HTML text to keep only medical content."""
        # Replace multiple newlines with single ones
        text = re.sub(r'\n+', '\n', text)
        
        # Filter out lines that are typical navigation links, cookies notice, copyright, etc.
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            l = line.lower().strip()
            # Ignore cookies, terms, privacy, copyright, phone headers, social links, footer lines
            if any(w in l for w in [
                "cookie policy", "privacy policy", "terms of use", "copyright", 
                "all rights reserved", "social media", "subscribe", "newsletter",
                "phone number", "contact us", "skip to main content"
            ]):
                continue
            # Keep lines that contain words
            if len(line.split()) > 2:
                cleaned_lines.append(line)
                
        return "\n".join(cleaned_lines)
