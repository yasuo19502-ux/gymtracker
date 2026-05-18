# Đưa app lên web (GitHub + Streamlit Cloud)

Phần **đã chuẩn bị sẵn** trong project: `.gitignore`, `requirements.txt`, `app.py`, hướng dẫn dưới đây.

## Việc bạn cần làm (khoảng 10–15 phút)

### 1. Tạo repo trên GitHub

1. Đăng nhập https://github.com → **New repository**
2. Tên ví dụ: `gym-progress-tracker`
3. Chọn **Private** (khuyến nghị)
4. Không thêm README / .gitignore (project đã có)
5. **Create repository** → copy URL, ví dụ:
   `https://github.com/TEN_CUA_BAN/gym-progress-tracker.git`

### 2. Commit & push code từ máy Windows

Repo Git **đã được khởi tạo** trong `gym_tracker`, file đã `git add` (không gồm `.env` / `.db`).

Mở PowerShell:

```powershell
cd "d:\Long\Tool trackergym\gym_tracker"

# Lần đầu dùng Git trên máy — chỉ cần chạy 1 lần (thay email/tên của bạn):
git config user.email "email-cua-ban@example.com"
git config user.name "Ten GitHub"

# Tạo commit (nếu chưa có commit)
git commit -m "Initial commit: Gym Progress Tracker AI"

git remote add origin https://github.com/TEN_CUA_BAN/gym-progress-tracker.git
git push -u origin main
```

Nếu `remote origin` đã tồn tại:

```powershell
git remote set-url origin https://github.com/TEN_CUA_BAN/gym-progress-tracker.git
git push -u origin main
```

Lần đầu GitHub có thể hỏi đăng nhập (trình duyệt hoặc [Personal Access Token](https://github.com/settings/tokens)).

Nếu `git push` báo lỗi nhánh, thử:

```powershell
git branch -M main
git push -u origin main
```

### 3. Deploy Streamlit Community Cloud

1. Vào https://share.streamlit.io → đăng nhập bằng **GitHub**
2. **Create app**
3. Chọn repo vừa push
4. **Branch:** `main`
5. **Main file path:** `app.py`
6. **Deploy**

URL app dạng: `https://ten-ban-chon.streamlit.app`

### 4. Cấu hình AI (tùy chọn)

Trên Streamlit Cloud: app → **Settings** → **Secrets**, dán:

```toml
AI_API_KEY = "sk-..."
AI_MODEL = "gpt-4o-mini"
AI_BASE_URL = "https://api.openai.com/v1"
```

**Save** → **Reboot app**.

Không cấu hình: app vẫn chạy, chỉ tab AI Coach không gọi API.

### 5. Cập nhật sau này

```powershell
git add .
git commit -m "Mo ta thay doi"
git push
```

Streamlit tự build lại khi push lên `main`.

---

## Lưu ý quan trọng

| Chủ đề | Giải thích |
|--------|------------|
| **SQLite trên cloud** | File `gym_tracker.db` tạo trên server; có thể **mất khi redeploy**. Dùng web để demo/thử; dữ liệu lâu dài nên backup file `.db` trên máy local. |
| **Bảo mật** | Không commit `.env` / `.db`. Repo **Private** + không chia URL công khai nếu chỉ dùng cá nhân. |
| **Main file path** | Phải là `app.py` (repo root = thư mục `gym_tracker`). |

## Kiểm tra nhanh sau deploy

- [ ] Mở URL, không có lỗi đỏ
- [ ] Tab Tập hôm nay → chọn template
- [ ] Lưu 1 buổi → xem Lịch / Tiến bộ
- [ ] (Tùy chọn) AI Coach sau khi thêm Secrets

## Lỗi thường gặp

- **`ModuleNotFoundError: src`** → Main file path sai; đặt `app.py`, repo root đúng thư mục có `src/`
- **Build fail** → Xem Logs trên Streamlit; chạy local `pip install -r requirements.txt`
- **AI không hoạt động** → Kiểm tra Secrets + Reboot app
