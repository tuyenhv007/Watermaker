# PDF Watermark Offline

Ứng dụng desktop chạy offline trên Windows/macOS/Linux để:
- Mở PDF và xem trước từng trang.
- Chỉnh watermark chữ chìm ở giữa trang: nội dung, độ trong suốt, cỡ chữ, màu, góc xoay, vị trí.
- Lưu thiết lập riêng cho từng trang hoặc áp dụng cho toàn bộ tài liệu.
- Xuất PDF đã flatten: mỗi trang được render thành ảnh và ghép lại thành PDF mới.

## Cài đặt (Windows)

1. Cài Python 3.10 trở lên từ https://www.python.org/downloads/
   - Khi cài, chọn **Add Python to PATH**.
2. Giải nén thư mục này.
3. Mở Command Prompt tại thư mục chứa file `pdf_watermark_app.py`.
4. Chạy:

```bat
py -m pip install -r requirements.txt
py pdf_watermark_app.py
```

Nếu lệnh `py` không hoạt động, thử `python` thay cho `py`.

## Cách dùng

1. Nhấn **Mở PDF…**.
2. Dùng nút Trang trước/Trang sau hoặc nhập số trang để chọn trang.
3. Chỉnh watermark ở bảng bên phải. Xem trước tự cập nhật.
4. Nhấn **Áp dụng thiết lập cho trang này** để lưu thiết lập trang hiện tại.
5. Muốn dùng cùng thiết lập cho mọi trang, nhấn **Áp dụng thiết lập này cho tất cả trang**.
6. Nhấn **Xuất PDF đã Flatten…** và chọn nơi lưu.

## Lưu ý quan trọng

- Ứng dụng không tải tài liệu lên Internet; xử lý trực tiếp trên máy.
- PDF đầu ra là PDF ảnh (image-only). Nội dung chữ gốc không còn chọn, tìm kiếm hoặc sửa riêng được.
- DPI xuất mặc định là 200. Có thể đổi `dpi = 200` trong hàm `export_pdf` thành 300 nếu cần in rõ hơn; file sẽ lớn hơn và tốn RAM/thời gian hơn.
- Nếu PDF gốc có chữ ký số, biểu mẫu điền được, liên kết hoặc lớp văn bản OCR, các thành phần này sẽ không được giữ trong PDF đầu ra.
- Flatten không phải DRM: người nhận vẫn có thể chụp màn hình, OCR, hoặc dùng công cụ xử lý ảnh để xóa/che watermark.
- Hãy giữ lại bản gốc riêng. Không dùng PDF đã flatten làm bản lưu trữ duy nhất.
