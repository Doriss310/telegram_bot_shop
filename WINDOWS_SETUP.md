# 🖥️ Hướng Dẫn Chạy Bot Trên Windows

File `.env` đã được cấu hình sẵn, chỉ cần làm theo các bước sau:

---

## Bước 1: Cài Docker Desktop

1. Tải Docker Desktop: https://www.docker.com/products/docker-desktop
2. Chạy file cài đặt, nhấn **Next** → **Install**
3. Khởi động lại máy khi được yêu cầu
4. Mở Docker Desktop và đợi đến khi icon 🐳 cá voi xanh ở taskbar hiện **"Docker is running"**

---

## Bước 2: Chạy Bot

1. Copy toàn bộ thư mục bot vào máy
2. Mở thư mục bot
3. Nhấn chuột phải vào vùng trống → **Open in Terminal**
   - Hoặc: Gõ `cmd` vào thanh địa chỉ rồi nhấn Enter
4. Chạy lệnh:
   ```
   docker-compose up -d --build
   ```
5. Đợi khoảng 1-2 phút để build xong
6. Done! Bot đang chạy 🎉

---

## Các lệnh thường dùng

| Lệnh | Mô tả |
|------|-------|
| `docker-compose logs -f` | Xem logs (Ctrl+C để thoát) |
| `docker-compose stop` | Dừng bot |
| `docker-compose start` | Chạy lại bot |
| `docker-compose restart` | Khởi động lại |
| `docker-compose down` | Xóa container |
| `docker-compose up -d --build` | Build lại và chạy |

---

## Tự động chạy khi bật máy

1. Mở **Docker Desktop** → **Settings** → **General**
2. Bật ✅ **"Start Docker Desktop when you log in"**
3. Bot sẽ tự chạy mỗi khi bật máy (nhờ `restart: always` trong config)

---

## Lưu ý quan trọng

- ✅ **Data không mất** khi tắt máy (lưu trong thư mục `data/`)
- ✅ **Không cần cài Python** - Docker đã bao gồm tất cả
- ⚠️ Mỗi lần bật máy, đợi Docker khởi động xong (1-2 phút)
- ⚠️ Nếu bot không tự chạy, mở Terminal và gõ `docker-compose up -d`

---

## Xử lý lỗi

### Docker không chạy được
- Kiểm tra đã bật **Virtualization** trong BIOS chưa
- Chạy **Windows Update** để cập nhật WSL2

### Bot không phản hồi
- Kiểm tra logs: `docker-compose logs -f`
- Restart bot: `docker-compose restart`

### Muốn cập nhật code mới
```
docker-compose down
docker-compose up -d --build
```
