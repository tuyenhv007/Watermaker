import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("test.pdf")

print("Số trang PDF:", len(pdf))

page = pdf[0]
image = page.render(scale=1.5).to_pil()

image.save("preview.png")

print("Đã xuất ảnh preview.png")