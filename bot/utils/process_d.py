import os
import re
from glob import glob

import cv2
import pytesseract
from PIL import Image, ImageDraw, ImageFont

pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

font_path = "hr.ttf"
font_size = 46.5

input_folder = "./images_d"
output_dir = "./result_images_d"

os.makedirs(output_dir, exist_ok=True)
os.makedirs(input_folder, exist_ok=True)

psm_modes = [6, 7, 8, 13]  # улучшенный набор
_f = 2.5  # масштаб предобработки

# Проверка шрифта
try:
    font = ImageFont.truetype(font_path, font_size)
except IOError:
    print(f"⚠️ Шрифт {font_path} не найден. Используем дефолтный.")
    font = ImageFont.load_default()


def process_image_d():
    for input_path in glob(os.path.join(input_folder, "*.[Pp][Nn][Gg]")):
        original_image = cv2.imread(input_path)
        if original_image is None:
            print(f"❌ Не удалось загрузить изображение: {input_path}")
            continue

        original_rgb = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(original_rgb)
        draw = ImageDraw.Draw(pil_img)

        # Предобработка для OCR
        gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
        orig_h, orig_w = gray.shape
        gray = cv2.resize(gray, None, fx=_f, fy=_f)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        ocr_rgb = cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB)
        pil_for_ocr = Image.fromarray(ocr_rgb)

        found_any = False

        for psm in psm_modes:
            custom_config = f"--oem 3 --psm {psm}"
            ocr_data = pytesseract.image_to_data(
                pil_for_ocr,
                config=custom_config,
                lang="rus",
                output_type=pytesseract.Output.DICT,
            )

            n_boxes = len(ocr_data["text"])
            for i in range(n_boxes):
                text = ocr_data["text"][i].strip()
                if not text:
                    continue

                if re.search(r"Возвращ[её]н", text):
                    # Масштабирование координат обратно к оригиналу
                    x = int(ocr_data["left"][i] / _f)
                    y = int(ocr_data["top"][i] / _f)
                    w = int(ocr_data["width"][i] / _f)
                    h = int(ocr_data["height"][i] / _f)

                    text = f"{text} {ocr_data['text'][i + 1].strip()}"
                    x1 = int(ocr_data["left"][i + 1] / _f)
                    y1 = int(ocr_data["top"][i + 1] / _f)
                    w1 = int(ocr_data["width"][i + 1] / _f)
                    h1 = int(ocr_data["height"][i + 1] / _f)

                    found_any = True
                    # Закрашиваем белым
                    draw.rectangle((x, y, x + w, y + h), fill="white")
                    draw.rectangle((x1, y1, x1 + w1, y1 + h1), fill="white")
                    # Вставляем "Доставлен"
                    new_text = re.sub(
                        r"Возвращ[её]н", "Доставлен", text, flags=re.IGNORECASE
                    )
                    draw.text(
                        (x - 5, y), new_text, fill=(0, 179, 89), font=font
                    )  # зелёный цвет

            if found_any:
                break  # выходим после первого успешного режима

        output_path = os.path.join(output_dir, os.path.basename(input_path).lower())
        pil_img.save(output_path, format="PNG")


def clear_dirs_d():
    for file in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, file))
    for file in os.listdir(input_folder):
        os.remove(os.path.join(input_folder, file))
