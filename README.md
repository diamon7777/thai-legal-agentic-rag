# Thai Legal Agentic RAG

โปรเจกต์ตัวอย่าง Agentic RAG ขนาดเล็กสำหรับตอบคำถามจากข้อความกฎหมายไทยที่คัดมาเฉพาะส่วน ใช้เพื่อแสดงการทำงานของสอง agent ไม่ใช่คำแนะนำทางกฎหมาย

## Flow

```text
คำถาม
  → Data Retriever Agent สร้าง 1–3 sub-queries
  → custom keyword search บน knowledge_base.txt
  → Report Generator Agent สรุปจาก snippets ที่พบเท่านั้น
```

- **Data Retriever Agent** ใช้ BBL `gpt-5-mini` สร้าง keyword phrase สั้น ๆ แล้วเรียก `search_knowledge_base()` ต่อ phrase
- **Report Generator Agent** ได้รับเฉพาะ snippets ที่ค้นพบ และต้องอ้างอิงเป็น `[KB-xx]`
- หากไม่พบหลักฐาน ระบบตอบข้อความ deterministic และไม่เรียก Report Generator Agent

## Run locally

ต้องมี Python 3.11+ และ [uv](https://docs.astral.sh/uv/)

```powershell
uv sync --extra dev
Copy-Item .env.example .env
```

ใส่ BBL API key ใน `.env` เท่านั้น:

```dotenv
BBL_LLM_API_KEY=
```

จากนั้นรัน:

```powershell
uv run legal-brief --query "ใครสามารถประกอบธุรกิจธนาคารพาณิชย์ได้"
```

CLI จะแสดงคำถาม, sub-queries, evidence IDs และคำตอบสุดท้ายตามลำดับ

## Knowledge base

`knowledge_base.txt` มี 10 มาตราที่คัดมาจากพระราชบัญญัติธุรกิจสถาบันการเงิน พ.ศ. 2551:

- มาตรา 9, 11, 12: การประกอบธุรกิจธนาคารและการใช้ชื่อ
- มาตรา 15–21: หุ้น การรายงานการถือหุ้น ข้อจำกัดเกิน 10% และผลของการถือหุ้นส่วนเกิน

Custom retrieval เป็น keyword/phrase matching แบบพื้นฐาน: แยกคำจาก sub-query, นับคำที่ปรากฏในแต่ละ chunk และคืนสูงสุดสาม chunk ที่มีคะแนนมากกว่า 0 เพิ่ม phrase ไทย 14 อักขระเพื่อค้นคำติดกัน และไม่นับข้อความกฎหมาย boilerplate ที่ปรากฏในทุก chunk หรือ keyword เดี่ยวที่กำกวมและปรากฏหลาย chunk จึงไม่มี embeddings, vector database หรือการสร้าง index

## Live smoke test

```powershell
uv run pytest tests/test_live_smoke.py -m live -q
```

test เดียวนี้เรียก pipeline และ LLM จริงด้วย focused banking query แล้วตรวจว่าได้ `KB-01` และคำตอบที่อ้าง `[KB-01]` หากยังไม่ได้ตั้ง `BBL_LLM_API_KEY` test จะ skip พร้อมข้อความชัดเจน

## Demo captures

หลังใส่ API key ให้รันคำสั่งต่อไปนี้ และบันทึก terminal output เป็น screenshots ตามชื่อในตาราง

| File | Query | สิ่งที่ควรเห็น |
| --- | --- | --- |
| `screenshots/01-banking-licence.png` | `ใครสามารถประกอบธุรกิจธนาคารพาณิชย์ได้` | evidence `KB-01` |
| `screenshots/02-bank-name-and-licence.png` | `ผู้ไม่ได้รับอนุญาตใช้คำว่าธนาคารในชื่อได้หรือไม่ และใครประกอบธุรกิจธนาคารได้` | 1–3 sub-queries และ evidence ที่เกี่ยวข้อง เช่น `KB-01`, `KB-03` |
| `screenshots/03-no-evidence.png` | `NovaTech ให้พนักงานเบิกค่าเดินทางต่างประเทศภายในกี่วัน` | ไม่มี evidence และข้อความ no-evidence |

## Limits

- Knowledge base เป็นตัวอย่างขนาดเล็ก ไม่ใช่ฐานกฎหมายที่ครบถ้วนหรือเป็นปัจจุบัน
- คำตอบต้องตรวจสอบกับแหล่งกฎหมายทางการและผู้เชี่ยวชาญก่อนใช้งานจริง
- ระบบตรวจว่า citation อยู่ใน evidence ที่ดึงมาและมีในทุกบรรทัดของรายงาน แต่ไม่ได้พิสูจน์ความถูกต้องเชิงความหมายของทุกประโยคโดยอัตโนมัติ
- โมเดลอาจล้มเหลวหาก API key หรือ endpoint ใช้งานไม่ได้; เวอร์ชันนี้ตั้งใจไม่ใส่ retry/fallback เพื่อให้ flow อ่านง่าย
