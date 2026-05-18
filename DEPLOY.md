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

### 3. Kiểm tra trên GitHub (bắt buộc trước Streamlit)

Mở: **https://github.com/yasuo19502-ux/gymtracker**

- [ ] Đăng nhập đúng tài khoản `yasuo19502-ux`
- [ ] Thấy file `app.py`, thư mục `src/`, `requirements.txt` (không trống)
- [ ] Nhánh mặc định là **`main`** (góc trái khi xem code)

**Nếu repo Private** — Streamlit phải được phép đọc repo:

1. GitHub → ảnh đại diện → **Settings**
2. **Applications** → **Authorized OAuth Apps** (hoặc **Installed GitHub Apps**)
3. Tìm **Streamlit** / **Streamlit Community Cloud** → **Configure**
4. **Repository access** → chọn **Only select repositories** → tick **`gymtracker`**
   - Hoặc chọn **All repositories** (đơn giản hơn)
5. **Save**

**Nếu không thấy Streamlit trong danh sách:** vào https://share.streamlit.io → đăng nhập GitHub lại → khi hỏi quyền repo, bấm **Authorize** / **Grant access**.

**Cách dễ nhất nếu vẫn không thấy repo:** đổi repo sang **Public** tạm:

- Repo → **Settings** → cuối trang **Danger zone** → **Change visibility** → Public  
- (Sau khi deploy xong có thể đổi lại Private nếu muốn)

### 4. Deploy Streamlit Community Cloud

1. Vào https://share.streamlit.io → đăng nhập **cùng GitHub** đã push code
2. **Create app** (góc phải)
3. **Repository:** `yasuo19502-ux/gymtracker` — nếu không có trong list → làm mục 3 ở trên
4. **Branch:** `main`
5. **Main file path:** `app.py` (không gõ `gym_tracker/app.py`)
6. **Deploy** → đợi 2–5 phút → mở URL app

**Lỗi hay gặp khi không deploy được:**

| Triệu chứng | Làm gì |
|-------------|--------|
| Không thấy repo trong dropdown | Cấp quyền Streamlit đọc repo (mục 3) hoặc đổi Public |
| Deploy đỏ / crash | Mở **Manage app** → **Logs**; thường sai `Main file path` |
| Đăng nhập Streamlit khác GitHub push | Đăng xuất Streamlit → login lại đúng account |
| Trang GitHub 404 | Sai URL hoặc repo chưa tạo / chưa push — chạy lại `PushLenGitHub.bat` |

URL app dạng: `https://ten-ban-chon.streamlit.app`

### 5. Cấu hình AI — Gemini hoặc OpenAI (tùy chọn)

App dùng API dạng **OpenAI-compatible** (`/chat/completions`).

#### Chạy trên máy (local)

1. Sao chép `.env.example` → `.env` (file `.env` không đưa lên GitHub)
2. Lấy key Gemini: https://aistudio.google.com/apikey
3. Sửa `.env`:

```env
AI_API_KEY=AIza...key_cua_ban
AI_MODEL=gemini-2.0-flash
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

4. Khởi động lại app (`ChayApp.bat`)

#### Chạy trên Streamlit Cloud (cách dễ — nhập trên web)

1. Mở app → tab **Cài đặt** → **Cấu hình AI (Gemini)**
2. Dán API key → **Lưu cấu hình AI** (lưu trong `gym_tracker.db` trên server, **không** lên GitHub)

Hoặc dùng **Secrets** (admin, không qua UI):

App → **Settings** → **Secrets**:

```toml
AI_API_KEY = "AIza...key_cua_ban"
AI_MODEL = "gemini-2.0-flash"
AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
```

**Save** → **Reboot app**.

| Nền tảng | Model ví dụ | AI_BASE_URL |
|----------|-------------|-------------|
| **Gemini** | `gemini-2.0-flash`, `gemini-1.5-flash` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| **OpenAI** | `gpt-4o-mini` | `https://api.openai.com/v1` |

Không cấu hình: app vẫn chạy, tab AI Coach chỉ báo chưa có key.

### 6. Cập nhật sau này

```powershell
git add .
git commit -m "Mo ta thay doi"
git push
```

Streamlit tự build lại khi push lên `main`.

---

## Quy trình sửa app (hàng ngày)

```
Sửa code trên máy → Chạy thử local → Commit → Push → Streamlit tự deploy
```

### 1. Sửa trên máy

- Mở project: `d:\Long\Tool trackergym\gym_tracker`
- Sửa file trong `src/` (UI, logic) hoặc `app.py`, `assets/style.css`
- **Không** commit `.env`, `gym_tracker.db`

### 2. Chạy thử local (nên làm trước khi push)

Double-click **`ChayApp.bat`** hoặc:

```powershell
cd "d:\Long\Tool trackergym\gym_tracker"
streamlit run app.py
```

Kiểm tra tab bạn vừa sửa (Tập hôm nay / Lịch / Tiến bộ / …).

### 3. Đẩy lên GitHub

**Cách nhanh:** double-click **`PushLenGitHub.bat`**  
(dán URL repo nếu hỏi — hoặc đã lưu `origin` rồi thì chỉ cần push)

**Hoặc PowerShell:**

```powershell
cd "d:\Long\Tool trackergym\gym_tracker"
git add .
git commit -m "Them tinh nang X / Sua loi Y"
git push
```

### 4. Chờ web cập nhật

- Vào https://share.streamlit.io → app của bạn → tab **Activity** / **Logs**
- Thường **1–3 phút** sau `git push` (nhánh `main`)
- Mở URL app → **Ctrl+F5** (hard refresh) nếu vẫn thấy giao diện cũ

### 5. Chỉ khi đổi thư viện Python

Nếu thêm package mới → sửa **`requirements.txt`** rồi push. Streamlit cài lại dependency khi build.

### 6. Secrets / AI

Đổi API key: Streamlit Cloud → app → **Settings → Secrets** → Save → **Reboot app**  
(không cần push Git)

---

## Gợi ý theo loại thay đổi

| Bạn muốn | Sửa chủ yếu |
|----------|-------------|
| Giao diện tab Tập hôm nay | `src/today_ui.py`, `assets/style.css` |
| Lịch / sửa buổi tập | `src/calendar_ui.py`, `src/session_edit_ui.py` |
| Biểu đồ / plateau | `src/progress_ui.py`, `src/analytics.py` |
| Lưu DB / validation | `src/workout_service.py`, `src/db.py` |
| AI Coach | `src/ai_coach.py`, `src/ai_coach_ui.py` |
| Template / bài tập (Cài đặt) | `src/settings_ui.py`, `src/template_service.py` |

Dữ liệu tập trên **web** (SQLite trên server) và trên **máy** (`gym_tracker.db`) là **khác nhau** — sửa code không mất data web; redeploy đôi khi reset DB trên cloud (xem lưu ý SQLite ở trên).

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

- **`empty ident name (for <>) not allowed`** → Chưa nhập tên/email Git. Chạy lại `PushLenGitHub.bat` và điền đủ 2 ô (không Enter trống). Hoặc:
  ```powershell
  git config user.name "Ten ban"
  git config user.email "ban@users.noreply.github.com"
  git commit -m "Initial commit: Gym Progress Tracker AI"
  ```
- **`src refspec main does not match any`** → Chưa có commit. Chạy `git commit` thành công trước khi `git push`.
- **`ModuleNotFoundError: src`** → Main file path sai; đặt `app.py`, repo root đúng thư mục có `src/`
- **Build fail** → Xem Logs trên Streamlit; chạy local `pip install -r requirements.txt`
- **AI không hoạt động** → Kiểm tra Secrets + Reboot app
