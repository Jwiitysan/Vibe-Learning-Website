# Vibe Learning Website

## ตั้งค่า API Key สำหรับ Generate Questions

ฟีเจอร์ **Generate Questions** จะอ่านคีย์จาก environment variable ชื่อ `OPENAI_API_KEY`

### วิธีที่ง่ายที่สุด

1. คัดลอกไฟล์ตัวอย่าง
   ```bash
   cp .env.example .env
   ```
2. เปิดไฟล์ `.env` แล้วใส่คีย์จริง
   ```env
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini
   ```
3. รันแอปตามปกติ

> ระบบจะโหลด `.env` อัตโนมัติจาก `app.py` ตอนเริ่มรันเซิร์ฟเวอร์
