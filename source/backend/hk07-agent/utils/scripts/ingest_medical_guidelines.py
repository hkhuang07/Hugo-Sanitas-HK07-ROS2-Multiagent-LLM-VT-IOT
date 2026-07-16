"""
ingest_medical_guidelines.py — Seeds baseline medical guidelines from allowed domains.
Ensures the system has a localized, high-quality RAG knowledge base out-of-the-box.
"""

import os
import sys
import asyncio
import logging

# Set up path so we can import packages
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.memory.lance_memory import LanceMemory
from services.knowledge_ingestion import KnowledgeIngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("hk07.ingest_seed")

# Curated high-quality static guidelines to seed
SEED_GUIDELINES = [
    {
        "source": "https://moh.gov.vn/stroke-guidelines",
        "title": "Hướng dẫn nhận biết đột quỵ và xử trí khẩn cấp (Bộ Y Tế Việt Nam)",
        "content": (
            "ĐỘT QUỴ (TAI BIẾN MẠCH MÁU NÃO) - QUY TẮC F.A.S.T:\n"
            "1. Face (Khuôn mặt): Yêu cầu người bệnh cười. Một bên mặt có bị xệ xuống không?\n"
            "2. Arm (Cánh tay): Yêu cầu giơ cả hai tay lên. Một bên tay có bị rơi xuống hoặc yếu hơn không?\n"
            "3. Speech (Giọng nói): Yêu cầu nói một câu đơn giản. Giọng nói có bị ngọng, lí nhí hoặc không rõ từ không?\n"
            "4. Time (Thời gian gọi cấp cứu 115): Nếu có bất kỳ dấu hiệu nào trên, gọi ngay cấp cứu 115 hoặc đưa người bệnh đến bệnh viện gần nhất có đơn vị đột quỵ trong 'Giờ Vàng' (dưới 4.5 giờ).\n"
            "Xử trí sơ cứu đột quỵ:\n"
            "- Để bệnh nhân nằm nghiêng, đầu cao nhẹ 30 độ, nới lỏng quần áo.\n"
            "- Tuyệt đối KHÔNG tự ý cho bệnh nhân uống thuốc, KHÔNG cạo gió, KHÔNG bấm huyệt, KHÔNG cho ăn uống gì đề phòng sặc vào đường thở."
        )
    },
    {
        "source": "https://www.cdc.gov/heart-attack-signs",
        "title": "CDC Warning Signs of a Heart Attack (Trung tâm Kiểm soát Dịch bệnh CDC Hoa Kỳ)",
        "content": (
            "DẤU HIỆU CẢNH BÁO NHỒI MÁU CƠ TIM (HEART ATTACK):\n"
            "1. Đau ngực hoặc khó chịu ở ngực: Đa số các cơn đau thắt ngực tập trung ở giữa ngực, kéo dài vài phút hoặc biến đi rồi quay lại. Cảm giác như bị đè ép, bóp nghẹt hoặc đau tức.\n"
            "2. Khó chịu ở các vùng phía trên cơ thể: Cơn đau có thể lan ra sau lưng, lên cổ, hàm, dạ dày hoặc đau dọc cánh tay trái.\n"
            "3. Khó thở: Xuất hiện đi kèm đau ngực hoặc trước khi đau ngực.\n"
            "4. Các triệu chứng khác: Vã mồ hôi lạnh, buồn nôn hoặc chóng mặt nhẹ đột ngột.\n"
            "Xử trí sơ cứu:\n"
            "- Hãy gọi ngay số điện thoại cấp cứu 115 lập tức.\n"
            "- Để người bệnh ngồi nghỉ ngơi hoàn toàn ở vị trí thoải mái, tránh xúc động mạnh hay di chuyển."
        )
    },
    {
        "source": "https://www.who.int/cardiovascular-diseases",
        "title": "WHO Prevention and First Aid for Cardiovascular Diseases (Tổ chức Y tế Thế giới)",
        "content": (
            "PHÒNG CHỐNG BỆNH TIM MẠCH VÀ SƠ CỨU SUY TIM:\n"
            "Bệnh tim mạch là nguyên nhân gây tử vong hàng đầu thế giới. Các biện pháp phòng ngừa khẩn cấp:\n"
            "- Kiểm soát huyết áp: Huyết áp tâm thu luôn giữ dưới 130 mmHg và tâm trương dưới 80 mmHg.\n"
            "- Nhận biết suy tim cấp: Người bệnh mệt mỏi cực độ, khó thở khi nằm phẳng, ho có bọt hồng, mắt cá chân bị sưng phù do tích nước.\n"
            "- Hành động khẩn cấp: Đưa người bệnh về tư thế ngồi thõng chân, cung cấp oxy thở nếu có và gọi cứu trợ y tế ngay lập tức. Tránh đặt bệnh nhân nằm ngửa vì có thể gây ứ dịch phổi nặng thêm."
        )
    },
    {
        "source": "https://moh.gov.vn/hypertension-prevention",
        "title": "Bộ Y Tế VN - Hướng dẫn chẩn đoán và điều trị tăng huyết áp",
        "content": (
            "TĂNG HUYẾT ÁP VÀ CƠN TĂNG HUYẾT ÁP KHẨN CẤP:\n"
            "Huyết áp được phân loại theo Bộ Y Tế:\n"
            "- Huyết áp bình thường: Dưới 120/80 mmHg.\n"
            "- Tăng huyết áp độ 1: 140-159/90-99 mmHg.\n"
            "- Tăng huyết áp độ 2: Trên 160/100 mmHg.\n"
            "Cơn tăng huyết áp khẩn cấp (Hypertensive Crisis):\n"
            "Huyết áp vọt cao trên 180 mmHg (tâm thu) hoặc trên 120 mmHg (tâm trương) kèm theo đau đầu dữ dội, tức ngực, mờ mắt, khó thở.\n"
            "Xử trí sơ cứu: Nằm nghỉ nơi yên tĩnh, đo lại huyết áp sau 15 phút. Nếu huyết áp vẫn cao kèm theo đau ngực hoặc yếu liệt chi, gọi ngay 115 cấp cứu."
        )
    }
]


async def main():
    log.info("Starting medical guidelines ingestion script...")
    
    memory = LanceMemory()
    await memory.initialize()
    
    if not memory._initialized or not hasattr(memory, "_guidelines_table") or memory._guidelines_table is None:
        log.error("Failed to initialize LanceDB guidelines table. Exit.")
        return
        
    # Check if table already contains guidelines
    try:
        count = await asyncio.to_thread(memory._guidelines_table.count_rows)
        log.info("Current guidelines table row count: %d", count)
    except Exception as e:
        log.error("Error reading table rows: %s", e)
        return
        
    # Seed guidelines
    ingest_service = KnowledgeIngestionService(memory)
    
    seeded_count = 0
    for seed in SEED_GUIDELINES:
        # Check if already seeded (by source)
        records = await asyncio.to_thread(lambda: memory._guidelines_table.to_arrow().to_pylist())
        sources = [r.get("source") for r in records]
        if seed["source"] in sources:
            log.info("Guideline source '%s' already exists. Skipping.", seed["source"])
            continue
            
        chunks = await ingest_service.ingest_text(
            source=seed["source"],
            title=seed["title"],
            text=seed["content"]
        )
        seeded_count += chunks
        
    log.info("Guidelines ingestion completed. Seeded %d new chunks.", seeded_count)


if __name__ == "__main__":
    asyncio.run(main())
