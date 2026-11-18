
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from pathlib import Path

images = [
    "anh_1.jpg",
    "anh_2.jpg"
]

output = "merged_2_pages.pdf"

# Kích thước A4 (đơn vị point)
page_width, page_height = A4

# Tạo PDF
pdf = canvas.Canvas(output, pagesize=A4)

for image_path in images:

    img = Image.open(image_path).convert("RGB")
    img_width, img_height = img.size

    # Tính tỷ lệ để ảnh vừa trong khổ A4
    scale = min(
        page_width / img_width,
        page_height / img_height
    )

    # Kích thước ảnh sau khi điều chỉnh
    new_width = img_width * scale
    new_height = img_height * scale

    # Căn giữa ảnh trên trang A4
    x = (page_width - new_width) / 2
    y = (page_height - new_height) / 2

    # Vẽ ảnh
    pdf.drawImage(
        ImageReader(img),
        x,
        y,
        width=new_width,
        height=new_height
    )

    pdf.showPage()

    img.close()

pdf.save()

print("Đã tạo:", output)
print("Kích thước mỗi trang: A4 (210 x 297 mm)")
