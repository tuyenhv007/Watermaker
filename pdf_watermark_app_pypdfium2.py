import io
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from pathlib import Path

import pypdfium2 as pdfium
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw, ImageFont, ImageTk


APP_TITLE = "PDF Watermark Offline"
DEFAULTS = {
    "text": "CHỈ DÙNG THAM KHẢO",
    "opacity": 20,
    "font_size": 34,       # points
    "color": "#777777",
    "angle": -35,
    "position": "Giữa trang",
}


def find_font():
    candidates = [
        # Windows
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


FONT_PATH = find_font()


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def make_watermarked_image(page, settings, dpi=200):
    """Render one PDF page and burn a centered translucent watermark into it."""
    scale = dpi / 72.0
    # PDFium renders the page directly to a Pillow image.
    image = page.render(scale=scale, rotation=0, rev_byteorder=True).to_pil().convert("RGBA")

    text = settings["text"].strip()
    if not text:
        return image.convert("RGB")

    opacity = max(0, min(100, int(settings["opacity"])))
    if opacity == 0:
        return image.convert("RGB")

    # Font size is specified in PDF points; convert to rendered pixels.
    font_px = max(8, int(float(settings["font_size"]) * scale))
    try:
        font = ImageFont.truetype(FONT_PATH, font_px) if FONT_PATH else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # Draw text on a tight transparent layer, rotate it, then center it on the page.
    dummy = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(dummy)
    spacing = max(4, int(font_px * 0.25))
    bbox = d.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center",
                                stroke_width=0)
    pad = max(12, int(font_px * 0.35))
    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])
    text_layer = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    rgb = hex_to_rgb(settings["color"])
    fill = (*rgb, int(255 * opacity / 100))
    td.multiline_text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=fill,
                      spacing=spacing, align="center")
    rotated = text_layer.rotate(float(settings["angle"]), resample=Image.Resampling.BICUBIC,
                                expand=True)

    position = settings.get("position", "Giữa trang")
    if position == "Trên giữa":
        cx, cy = image.width // 2, int(image.height * 0.22)
    elif position == "Dưới giữa":
        cx, cy = image.width // 2, int(image.height * 0.78)
    else:
        cx, cy = image.width // 2, image.height // 2

    x = cx - rotated.width // 2
    y = cy - rotated.height // 2
    image.alpha_composite(rotated, (x, y))
    return image.convert("RGB")


class WatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1120x760")
        self.root.minsize(900, 620)

        self.pdf_path = None
        self.doc = None
        self.page_settings = {}
        self.current_page = 0
        self.preview_photo = None
        self.preview_after_id = None
        self.busy = False

        self.text_var = tk.StringVar(value=DEFAULTS["text"])
        self.opacity_var = tk.IntVar(value=DEFAULTS["opacity"])
        self.font_size_var = tk.IntVar(value=DEFAULTS["font_size"])
        self.angle_var = tk.IntVar(value=DEFAULTS["angle"])
        self.color_var = tk.StringVar(value=DEFAULTS["color"])
        self.position_var = tk.StringVar(value=DEFAULTS["position"])
        self.page_label_var = tk.StringVar(value="Chưa mở PDF")
        self.status_var = tk.StringVar(value="Mở một file PDF để bắt đầu.")

        self._build_ui()
        self._set_controls_enabled(False)

    def _build_ui(self):
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Mở PDF…", command=self.open_pdf).pack(side="left")
        ttk.Button(toolbar, text="Xuất PDF đã Flatten…", command=self.export_pdf).pack(side="left", padx=8)
        ttk.Label(toolbar, textvariable=self.page_label_var).pack(side="right")

        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=10)
        main.add(left, weight=3)
        main.add(right, weight=2)

        ttk.Label(left, text="Xem trước trang", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.preview_frame = ttk.Frame(left, relief="sunken", borderwidth=1)
        self.preview_frame.pack(fill="both", expand=True, pady=8)
        self.preview_label = ttk.Label(self.preview_frame, text="Chưa có tài liệu", anchor="center")
        self.preview_label.pack(fill="both", expand=True)

        nav = ttk.Frame(left)
        nav.pack(fill="x")
        self.prev_button = ttk.Button(nav, text="◀ Trang trước", command=self.prev_page)
        self.prev_button.pack(side="left")
        self.next_button = ttk.Button(nav, text="Trang sau ▶", command=self.next_page)
        self.next_button.pack(side="left", padx=8)
        ttk.Label(nav, text="Chọn trang:").pack(side="left", padx=(18, 4))
        self.page_spin = ttk.Spinbox(nav, from_=1, to=1, width=6, command=self.go_to_page)
        self.page_spin.pack(side="left")
        self.page_spin.bind("<Return>", lambda _e: self.go_to_page())

        ttk.Label(right, text="Watermark cho trang đang chọn", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(right, text="Mỗi trang có thể có thiết lập riêng. Xem trước sẽ cập nhật sau khi bạn thay đổi.",
                  wraplength=350).pack(anchor="w", pady=(4, 12))

        form = ttk.Frame(right)
        form.pack(fill="x")
        ttk.Label(form, text="Nội dung").grid(row=0, column=0, sticky="w", pady=5)
        self.text_entry = ttk.Entry(form, textvariable=self.text_var, width=34)
        self.text_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)

        ttk.Label(form, text="Độ trong suốt").grid(row=1, column=0, sticky="w", pady=5)
        self.opacity_scale = ttk.Scale(form, from_=0, to=100, orient="horizontal",
                                       command=self._opacity_changed)
        self.opacity_scale.set(DEFAULTS["opacity"])
        self.opacity_scale.grid(row=1, column=1, sticky="ew", pady=5)
        self.opacity_value = ttk.Label(form, text="20%")
        self.opacity_value.grid(row=1, column=2, padx=5)

        ttk.Label(form, text="Cỡ chữ (pt)").grid(row=2, column=0, sticky="w", pady=5)
        self.font_spin = ttk.Spinbox(form, from_=8, to=120, textvariable=self.font_size_var, width=8)
        self.font_spin.grid(row=2, column=1, sticky="w", pady=5)

        ttk.Label(form, text="Góc xoay").grid(row=3, column=0, sticky="w", pady=5)
        self.angle_scale = ttk.Scale(form, from_=-90, to=90, orient="horizontal",
                                     command=self._angle_changed)
        self.angle_scale.set(DEFAULTS["angle"])
        self.angle_scale.grid(row=3, column=1, sticky="ew", pady=5)
        self.angle_value = ttk.Label(form, text="-35°")
        self.angle_value.grid(row=3, column=2, padx=5)

        ttk.Label(form, text="Vị trí").grid(row=4, column=0, sticky="w", pady=5)
        self.position_combo = ttk.Combobox(form, textvariable=self.position_var,
                                           values=["Giữa trang", "Trên giữa", "Dưới giữa"],
                                           state="readonly", width=18)
        self.position_combo.grid(row=4, column=1, columnspan=2, sticky="w", pady=5)

        ttk.Label(form, text="Màu chữ").grid(row=5, column=0, sticky="w", pady=5)
        self.color_swatch = tk.Label(form, text="      ", bg=self.color_var.get(), relief="groove")
        self.color_swatch.grid(row=5, column=1, sticky="w", pady=5)
        ttk.Button(form, text="Chọn màu…", command=self.choose_color).grid(row=5, column=2, sticky="w")

        form.columnconfigure(1, weight=1)

        ttk.Separator(right).pack(fill="x", pady=14)
        ttk.Button(right, text="Áp dụng thiết lập cho trang này", command=self.apply_current).pack(fill="x", pady=3)
        ttk.Button(right, text="Áp dụng thiết lập này cho tất cả trang", command=self.apply_all).pack(fill="x", pady=3)
        ttk.Button(right, text="Khôi phục mặc định cho trang này", command=self.reset_current).pack(fill="x", pady=3)

        ttk.Label(right, text="Lưu ý", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(16, 3))
        note = ("Khi xuất, mỗi trang sẽ được chuyển thành ảnh và ghép lại thành PDF. "
                "Văn bản không còn chọn/tìm kiếm/sửa riêng được; chất lượng phụ thuộc DPI xuất. "
                "Đây không phải biện pháp chống chụp màn hình hoặc xóa watermark bằng công cụ chuyên dụng.")
        ttk.Label(right, text=note, wraplength=350, justify="left").pack(anchor="w")

        footer = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        footer.pack(fill="x")
        self.progress = ttk.Progressbar(footer, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 5))
        ttk.Label(footer, textvariable=self.status_var).pack(anchor="w")

        for widget in (self.text_entry, self.font_spin):
            widget.bind("<KeyRelease>", lambda _e: self.schedule_preview())
        self.position_combo.bind("<<ComboboxSelected>>", lambda _e: self.schedule_preview())
        self.opacity_scale.bind("<ButtonRelease-1>", lambda _e: self.schedule_preview())
        self.angle_scale.bind("<ButtonRelease-1>", lambda _e: self.schedule_preview())

    def _set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in [self.text_entry, self.opacity_scale, self.font_spin,
                       self.angle_scale, self.position_combo, self.color_swatch]:
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass
        for widget in [self.prev_button, self.next_button, self.page_spin]:
            widget.configure(state=state)

    def open_pdf(self):
        path = filedialog.askopenfilename(title="Chọn PDF", filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        try:
            new_doc = pdfium.PdfDocument(path)
            if len(new_doc) == 0:
                messagebox.showerror("PDF rỗng", "Tài liệu không có trang.")
                new_doc.close()
                return
        except Exception as exc:
            messagebox.showerror(
                "Không mở được PDF",
                f"Không thể mở tài liệu này. Nếu PDF có mật khẩu, hãy mở khóa trước.\\n\\n{exc}"
            )
            return

        if self.doc:
            self.doc.close()
        self.doc = new_doc
        self.pdf_path = path
        self.page_settings = {i: DEFAULTS.copy() for i in range(len(self.doc))}
        self.current_page = 0
        self.page_spin.configure(to=len(self.doc))
        self.page_spin.delete(0, "end")
        self.page_spin.insert(0, "1")
        self.page_label_var.set(f"{Path(path).name}  •  {len(self.doc)} trang")
        self._set_controls_enabled(True)
        self._load_settings_into_controls()
        self.refresh_preview()
        self.status_var.set("PDF đã mở. Chỉnh watermark theo từng trang hoặc áp dụng cho tất cả.")

    def _read_controls(self):
        try:
            font_size = int(self.font_size_var.get())
        except Exception:
            font_size = DEFAULTS["font_size"]
        return {
            "text": self.text_var.get(),
            "opacity": int(round(float(self.opacity_scale.get()))),
            "font_size": max(8, min(120, font_size)),
            "color": self.color_var.get(),
            "angle": int(round(float(self.angle_scale.get()))),
            "position": self.position_var.get(),
        }

    def _load_settings_into_controls(self):
        s = self.page_settings[self.current_page]
        self.text_var.set(s["text"])
        self.opacity_scale.set(s["opacity"])
        self.opacity_value.configure(text=f'{s["opacity"]}%')
        self.font_size_var.set(s["font_size"])
        self.angle_scale.set(s["angle"])
        self.angle_value.configure(text=f'{s["angle"]}°')
        self.color_var.set(s["color"])
        self.color_swatch.configure(bg=s["color"])
        self.position_var.set(s["position"])

    def _save_controls_to_current(self):
        if self.doc:
            self.page_settings[self.current_page] = self._read_controls()

    def _opacity_changed(self, value):
        self.opacity_value.configure(text=f"{int(float(value))}%")
        self.schedule_preview()

    def _angle_changed(self, value):
        self.angle_value.configure(text=f"{int(float(value))}°")
        self.schedule_preview()

    def choose_color(self):
        chosen = colorchooser.askcolor(color=self.color_var.get(), title="Chọn màu watermark")
        if chosen and chosen[1]:
            self.color_var.set(chosen[1])
            self.color_swatch.configure(bg=chosen[1])
            self.schedule_preview()

    def schedule_preview(self):
        if not self.doc:
            return
        if self.preview_after_id:
            self.root.after_cancel(self.preview_after_id)
        self.preview_after_id = self.root.after(350, self.refresh_preview)

    def refresh_preview(self):
        self.preview_after_id = None
        if not self.doc:
            return
        self._save_controls_to_current()
        try:
            img = make_watermarked_image(self.doc[self.current_page],
                                         self.page_settings[self.current_page], dpi=90)
            max_w = max(250, self.preview_frame.winfo_width() - 24)
            max_h = max(250, self.preview_frame.winfo_height() - 24)
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=self.preview_photo, text="")
            self.page_label_var.set(f"{Path(self.pdf_path).name}  •  Trang {self.current_page+1}/{len(self.doc)}")
        except Exception as exc:
            self.status_var.set(f"Lỗi xem trước: {exc}")

    def apply_current(self):
        if not self.doc:
            return
        self._save_controls_to_current()
        self.refresh_preview()
        self.status_var.set(f"Đã áp dụng thiết lập cho trang {self.current_page+1}.")

    def apply_all(self):
        if not self.doc:
            return
        settings = self._read_controls()
        for i in range(len(self.doc)):
            self.page_settings[i] = settings.copy()
        self.refresh_preview()
        self.status_var.set("Đã áp dụng thiết lập hiện tại cho tất cả các trang.")

    def reset_current(self):
        if not self.doc:
            return
        self.page_settings[self.current_page] = DEFAULTS.copy()
        self._load_settings_into_controls()
        self.refresh_preview()
        self.status_var.set(f"Đã khôi phục mặc định cho trang {self.current_page+1}.")

    def _change_page(self, new_page):
        if not self.doc:
            return
        self._save_controls_to_current()
        self.current_page = max(0, min(len(self.doc)-1, new_page))
        self.page_spin.delete(0, "end")
        self.page_spin.insert(0, str(self.current_page + 1))
        self._load_settings_into_controls()
        self.refresh_preview()

    def prev_page(self):
        self._change_page(self.current_page - 1)

    def next_page(self):
        self._change_page(self.current_page + 1)

    def go_to_page(self):
        if not self.doc:
            return
        try:
            page = int(self.page_spin.get()) - 1
        except ValueError:
            return
        self._change_page(page)

    def export_pdf(self):
        if not self.doc or self.busy:
            return
        self._save_controls_to_current()
        default_name = Path(self.pdf_path).stem + "_watermarked_flattened.pdf"
        out_path = filedialog.asksaveasfilename(
            title="Lưu PDF đã Flatten",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf")]
        )
        if not out_path:
            return
        if os.path.abspath(out_path) == os.path.abspath(self.pdf_path):
            messagebox.showwarning("Không ghi đè file gốc", "Hãy chọn tên file đầu ra khác.")
            return

        try:
            dpi = 200
            self.busy = True
            self.progress.configure(maximum=len(self.doc), value=0)
            self.status_var.set(f"Đang xuất PDF ở {dpi} DPI…")
            self.root.update_idletasks()

            pdf_canvas = None
            for i in range(len(self.doc)):
                page = self.doc[i]
                img = make_watermarked_image(page, self.page_settings[i], dpi=dpi)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=95, subsampling=0, optimize=True)
                buffer.seek(0)

                page_width, page_height = page.get_size()
                if pdf_canvas is None:
                    pdf_canvas = canvas.Canvas(
                        out_path, pagesize=(page_width, page_height),
                        pageCompression=1
                    )
                    pdf_canvas.setTitle(Path(out_path).stem)
                    pdf_canvas.setSubject("PDF đã flatten và đóng watermark")
                    pdf_canvas.setCreator(APP_TITLE)
                else:
                    pdf_canvas.setPageSize((page_width, page_height))

                pdf_canvas.drawImage(
                    ImageReader(buffer), 0, 0,
                    width=page_width, height=page_height,
                    preserveAspectRatio=False, mask="auto"
                )
                pdf_canvas.showPage()

                self.progress.configure(value=i+1)
                self.status_var.set(f"Đang xử lý trang {i+1}/{len(self.doc)}…")
                self.root.update_idletasks()

            if pdf_canvas is not None:
                pdf_canvas.save()
            self.status_var.set(f"Hoàn tất: {out_path}")
            messagebox.showinfo("Đã xuất PDF", f"Đã tạo PDF đã Flatten:\n{out_path}\n\n"
                                "Mỗi trang là ảnh; không thể chọn hoặc sửa riêng lớp chữ/hình gốc.")
        except Exception as exc:
            messagebox.showerror("Lỗi khi xuất PDF", str(exc))
            self.status_var.set(f"Lỗi: {exc}")
        finally:
            self.busy = False
            self.progress.configure(value=0)

    def close(self):
        if self.doc:
            self.doc.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    app = WatermarkApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
