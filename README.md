# Gym Progress Tracker AI

Ứng dụng web **local-first** theo dõi buổi tập gym cá nhân: ghi set/rep/tạ/RPE, lịch tập, tiến bộ, gợi ý tăng tả, phát hiện chững tạ, và AI Coach (tùy chọn). Giao diện **mobile-first** — dùng tốt trên điện thoại khi tập.

Dữ liệu lưu trong **SQLite** (`gym_tracker.db` cạnh `app.py`). Không cần server riêng.

## Tính năng chính

| Tab | Mô tả |
|-----|--------|
| **Tập hôm nay** | Chọn template, xem lịch sử lần trước, nhập set, nhập bù ngày quá khứ, hoàn thành buổi tập |
| **Lịch tập** | Lịch tháng, badge template, chi tiết/xem/sửa/xóa mềm buổi tập |
| **Tiến bộ** | Biểu đồ e1RM, volume, PR, cảnh báo plateau |
| **AI Coach** | Phân tích buổi tập & chat hỏi đáp (cần API key) |
| **Cài đặt** | CRUD template, bài tập, gán bài vào template |

- Progressive overload: gợi ý tăng tạ/rep theo RPE và rep range  
- Plateau: phát hiện chững tạ (4 buổi gần nhất)  
- Soft delete: xóa buổi/set khỏi lịch và analytics, không xóa cứng DB  

## Cài đặt

Yêu cầu: **Python 3.11+**

```bash
cd gym_tracker
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Chạy app

```bash
streamlit run app.py
```

Mở URL Streamlit in ra (thường `http://localhost:8501`).

Lần chạy đầu: tự tạo `gym_tracker.db` và **seed** 5 template mẫu (Chân, Ngực, Lưng, Vai, Tay) nếu database trống.

Windows: double-click `ChayApp.bat` thay cho lệnh trên.

## Đưa lên web (GitHub + Streamlit Cloud)

Xem hướng dẫn chi tiết: **[DEPLOY.md](DEPLOY.md)**.

Tóm tắt: push repo → https://share.streamlit.io → Main file path: `app.py` → thêm **Secrets** cho AI (tùy chọn).

### Database tùy chỉnh (tùy chọn)

```bash
set GYM_TRACKER_DB=D:\data\my_gym.db
streamlit run app.py
```

## Cấu hình AI API (Gemini / OpenAI)

1. Sao chép `.env.example` → `.env`  
2. **Gemini** — lấy key tại https://aistudio.google.com/apikey

```env
AI_API_KEY=AIza...your_key
AI_MODEL=gemini-2.0-flash
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

3. **OpenAI** — dùng `gpt-4o-mini` và `https://api.openai.com/v1`

- Hỗ trợ mọi API **OpenAI-compatible**.  
- Trên web: cấu hình trong Streamlit **Secrets** (xem [DEPLOY.md](DEPLOY.md)).  
- **Không có API key**: app vẫn chạy; tab AI Coach không gọi API.

## Dữ liệu lưu ở đâu?

| Môi trường | File / nơi lưu |
|------------|----------------|
| **Máy bạn (local)** | `gym_tracker/gym_tracker.db` (SQLite) |
| **Web (Streamlit Cloud)** | `gym_tracker.db` trên server Streamlit (riêng, không đồng bộ với máy) |

Trong DB: buổi tập (`workout_sessions`), set (`workout_sets`), template, bài tập, phân tích AI đã lưu (`ai_reviews`).  
**Hội thoại chat AI** chỉ trong phiên trình duyệt (không lưu DB).  
Nên **backup** file `gym_tracker.db` trên máy nếu dữ liệu quan trọng.

## Cấu trúc project

```
gym_tracker/
├── app.py                 # Entry Streamlit
├── requirements.txt
├── .env.example
├── gym_tracker.db         # SQLite (tạo khi chạy)
├── assets/
│   └── style.css          # Mobile-first CSS
├── scripts/
│   └── smoke_test.py      # Kiểm tra edge case (tùy chọn)
└── src/
    ├── bootstrap.py       # Khởi tạo DB + CSS
    ├── db.py              # Schema + migration an toàn
    ├── seed.py            # Dữ liệu mẫu
    ├── utils.py
    ├── template_service.py
    ├── workout_service.py
    ├── analytics.py
    ├── today_ui.py
    ├── calendar_ui.py
    ├── progress_ui.py
    ├── session_summary_ui.py
    ├── session_edit_ui.py
    ├── settings_ui.py
    ├── overload_ui.py
    ├── ai_coach.py
    └── ai_coach_ui.py
```

## Migration database

Khi mở app, `init_schema()` + `run_migrations()`:

- Tạo bảng nếu chưa có (`CREATE TABLE IF NOT EXISTS`)  
- Thêm cột thiếu trên DB cũ (ví dụ `workout_sessions.status`, `workout_sets.status`)  
- **Không** xóa hay ghi đè dữ liệu hiện có  

## Kiểm tra nhanh (smoke test)

```bash
python scripts/smoke_test.py
```

## Lưu ý

- **Local-first**: dữ liệu trên máy bạn; nên backup file `gym_tracker.db` định kỳ.  
- Không có đăng nhập đa người dùng.  
- AI chỉ đọc dữ liệu đã ghi trong app; không thay thế tư vấn y tế.  

---

## Acceptance test (checklist)

Dùng checklist sau để xác nhận app hoạt động end-to-end:

- [ ] **Tạo template mới** — Tab Cài đặt → Template → thêm tên template  
- [ ] **Thêm bài tập** — Cài đặt → Bài tập → thêm tên + nhóm cơ  
- [ ] **Gán bài vào template** — Cài đặt → Gán bài cho template → chọn bài, thứ tự, rep range  
- [ ] **Chọn buổi tập hôm nay** — Tab Tập hôm nay → chọn template (nút/card)  
- [ ] **Nhập set/rep/tạ/RPE** — Mở từng bài → nhập set, RPE, khởi động nếu cần  
- [ ] **Lưu session** — Hoàn thành buổi tập → xem tổng kết  
- [ ] **Nhập bù** — Chọn ngày quá khứ trong Thông tin buổi tập → lưu → kiểm tra Lịch  
- [ ] **Xem lịch** — Tab Lịch tập → chọn ngày → Xem chi tiết buổi  
- [ ] **Sửa / xóa mềm** — Chi tiết buổi → Chỉnh sửa hoặc xóa (có xác nhận)  
- [ ] **Xem tiến bộ** — Tab Tiến bộ → chọn bài → biểu đồ & PR (sau vài buổi có dữ liệu)  
- [ ] **Xem plateau** — Cùng tab → khối “Đánh giá chững tạ” (cần ≥4 buổi/bài để đánh giá đầy đủ)  
- [ ] **Dùng AI Coach** *(nếu có API key)* — `.env` hợp lệ → phân tích buổi / hỏi đáp chat  

### Edge case đã xử lý

- Database trống (chưa seed): thông báo hướng dẫn, không crash  
- Chưa có lịch sử bài: copy lần trước / analytics / plateau báo thiếu dữ liệu  
- Chưa có API key: AI tab cảnh báo nhẹ  
- Tháng không có session: lịch trống, metric 0  
- Bài chưa có dữ liệu tiến bộ: thông báo + vẫn xem plateau (insufficient data)  
