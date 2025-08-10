import cv2
import re
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from glob import glob
import datetime

pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

font_path = "hr.ttf"
font_size = 46.5
input_folder = "./images_d"
output_dir = "./result_images_d"
os.makedirs(output_dir, exist_ok=True)

# Универсальные PSM режимы
psm_modes = [6, 7, 8, 13]

# Масштаб для детекции мелкого текста
_f = 3.0

# Проверка шрифта
try:
    font = ImageFont.truetype(font_path, font_size)
except:
    font = ImageFont.load_default()


def process_image_d():
    for input_path in glob(os.path.join(input_folder, "*.[Pp][Nn][Gg]")):
        img = cv2.imread(input_path)
        if img is None:
            continue

        # === 1. УЛУЧШАЕМ КОНТРАСТ ДЛЯ ЛЮБОГО ФОНА ===
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        merged = cv2.merge((cl, a, b))
        enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

        # === 2. ГЕНЕРИРУЕМ 4 ВЕРСИИ ДЛЯ OCR ===
        versions = []

        # Версия 1: Стандартная обработка (светлый фон)
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, None, fx=_f, fy=_f, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(resized, 180, 255, cv2.THRESH_BINARY)
        versions.append(("light", thresh))

        # Версия 2: Инверсия (тёмный фон)
        _, thresh_inv = cv2.threshold(resized, 70, 255, cv2.THRESH_BINARY_INV)
        versions.append(("dark", thresh_inv))

        # Версия 3: Адаптивная бинаризация
        adaptive = cv2.adaptiveThreshold(
            resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        versions.append(("adaptive", adaptive))

        # Версия 4: Удаление фона (для градиентов)
        _, mask = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        removed_bg = cv2.inpaint(resized, mask, 3, cv2.INPAINT_TELEA)
        versions.append(("no_bg", removed_bg))

        # === 3. ИЩЕМ ТЕКСТ ВО ВСЕХ ВЕРСИЯХ ===
        found_any = False
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        for version_name, processed in versions:
            # Сохраняем для отладки (раскомментировать при проблемах)
            # cv2.imwrite(f"debug_{version_name}.png", processed)

            for psm in psm_modes:
                custom_config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist=АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789 "
                ocr_data = pytesseract.image_to_data(
                    Image.fromarray(processed),
                    config=custom_config,
                    lang="rus",
                    output_type=pytesseract.Output.DICT,
                )

                n_boxes = len(ocr_data["text"])
                for i in range(n_boxes):
                    text = ocr_data["text"][i].strip()
                    if not text:
                        continue

                    # УЛУЧШЕННЫЙ ПОИСК С РАЗНЫМИ ВАРИАНТАМИ НАПИСАНИЯ
                    if re.search(r"В[оа]звр[ао]щ[её]н", text, re.IGNORECASE):
                        # ТОЧНОЕ МАСШТАБИРОВАНИЕ КООРДИНАТ
                        x = int(ocr_data["left"][i] / _f)
                        y = int(ocr_data["top"][i] / _f)
                        w = int(ocr_data["width"][i] / _f)
                        h = int(ocr_data["height"][i] / _f)

                        # === УМНАЯ ЗАМЕНА ТЕКСТА С РАСШИРЕННЫМ БОКСОМ ===
                        # Определяем цвет фона ПРЯМО В ЭТОЙ ОБЛАСТИ (с запасом)
                        roi = img[
                            max(0, y - 10) : min(img.shape[0], y + h + 15),
                            max(0, x - 10) : min(img.shape[1], x + w + 10),
                        ]
                        if roi.size == 0:
                            continue

                        avg_color = np.mean(roi, axis=(0, 1))
                        is_dark = np.mean(avg_color) < 128
                        fill_color = (0, 0, 0) if is_dark else (255, 255, 255)

                        # 🔥 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: РАСШИРЕННЫЙ БОКС
                        padding_horiz = 8
                        padding_vert_top = 3
                        padding_vert_bot = 10

                        x1 = max(0, x - padding_horiz)
                        y1 = max(0, y - padding_vert_top)
                        x2 = min(pil_img.width, x + w + padding_horiz)
                        y2 = min(pil_img.height, y + h + padding_vert_bot)

                        draw.rectangle((x1, y1, x2, y2), fill=fill_color)

                        # Цвет текста: БЕЛЫЙ на тёмном, ЧЁРНЫЙ на светлом
                        text_color = (0, 179, 89) if is_dark else (0, 179, 89)

                        time = datetime.datetime.strptime(text[9:], "%d%m%Y")
                        time_str = time.strftime("%d.%m.%Y")
                        text = text.replace(text[9:], time_str)

                        # Заменяем ТОЛЬКО целое слово
                        new_text = re.sub(
                            r"В[оа]звр[ао]щ[её]н",
                            "Доставлен ",
                            text,
                            flags=re.IGNORECASE,
                        )

                        # Коррекция позиции (на случай смещения)
                        draw.text(
                            (x, y - int(h * 0.1)), new_text, fill=text_color, font=font
                        )
                        found_any = True

                if found_any:
                    break
            if found_any:
                break

        # Сохраняем результат
        output_path = os.path.join(output_dir, os.path.basename(input_path).lower())
        pil_img.save(output_path, format="PNG")


def clear_dirs_d():
    for file in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, file))
    for file in os.listdir(input_folder):
        os.remove(os.path.join(input_folder, file))
