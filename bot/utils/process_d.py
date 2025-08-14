import cv2
import re
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from glob import glob
import datetime
import time as t
import logging

pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

font_path = "hr.ttf"
font_size = 46.5
input_folder = "./images_d"
output_dir = "./result_images_d"
os.makedirs(output_dir, exist_ok=True)

logger = logging.getLogger(__name__)

# Универсальные PSM режимы
psm_modes = [6, 7, 8, 13]

# Масштаб для детекции мелкого текста
_f_v2 = 3.0
_f = 3.0

# Проверка шрифта
try:
    font = ImageFont.truetype(font_path, font_size)
except:
    font = ImageFont.load_default()


def get_paths():
    return glob(os.path.join(input_folder, "*.[Pp][Nn][Gg]"))


def process_image_d_v2(input_path: str):
    img = cv2.imread(input_path)
    if img is None:
        return

    # === 1. УЛУЧШАЕМ КОНТРАСТ ДЛЯ ЛЮБОГО ФОНА ===
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    merged = cv2.merge((cl, a, b))
    enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    # === 2. ГЕНЕРИРУЕМ 4 ВЕРСИИ ДЛЯ OCR ===
    versions = []

    gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=_f_v2, fy=_f_v2, interpolation=cv2.INTER_CUBIC)
    # Версия 2: Инверсия (тёмный фон)
    _, thresh_inv = cv2.threshold(resized, 70, 255, cv2.THRESH_BINARY_INV)
    versions.append(("dark", thresh_inv))
    # Версия 1: Стандартная обработка (светлый фон)
    _, thresh = cv2.threshold(resized, 180, 255, cv2.THRESH_BINARY)
    versions.append(("light", thresh))

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
                    x = int(ocr_data["left"][i] / _f_v2)
                    y = int(ocr_data["top"][i] / _f_v2)
                    w = int(ocr_data["width"][i] / _f_v2)
                    h = int(ocr_data["height"][i] / _f_v2)

                    fill_color = (0, 0, 0)

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
                    text_color = (0, 179, 89)
                    try:
                        time = datetime.datetime.strptime(text[9:], "%d%m%Y")
                        time_str = time.strftime("%d.%m.%Y")
                        text = text.replace(text[9:], time_str)
                    except:
                        pass

                    # Заменяем ТОЛЬКО целое слово
                    new_text = re.sub(
                        r"В[оа]звр[ао]щ[её]н",
                        "Доставлен ",
                        text,
                        flags=re.IGNORECASE,
                    )

                    # Коррекция позиции (на случай смещения)
                    draw.text(
                        (x - 5, y - int(h * 0.1)),
                        new_text,
                        fill=text_color,
                        font=font,
                    )
                    found_any = True
            if found_any:
                break
        if found_any:
            break

    # Сохраняем результат
    output_path = os.path.join(output_dir, os.path.basename(input_path).lower())
    pil_img.save(output_path, format="PNG")
    return found_any


def process_image_d_v1(input_path: str):
    original_image = cv2.imread(input_path)
    if original_image is None:
        logger.error(f"❌ Не удалось загрузить изображение: {input_path}")
        return

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
            break

    output_path = os.path.join(output_dir, os.path.basename(input_path).lower())
    pil_img.save(output_path, format="PNG")
    return found_any


def process_image_d_vertical(input_path: str):
    original_image = cv2.imread(input_path)
    if original_image is None:
        logger.error(f"❌ Не удалось загрузить изображение: {input_path}")
        return

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

            if re.search(r"Возвращ[её]н", text) or re.search(
                r"(\d{2}).(\d{2}).(\d{4})", text
            ):
                # Масштабирование координат обратно к оригиналу
                x = int(ocr_data["left"][i] / _f)
                y = int(ocr_data["top"][i] / _f)
                w = int(ocr_data["width"][i] / _f)
                h = int(ocr_data["height"][i] / _f)

                found_any = True
                # Закрашиваем белым
                draw.rectangle((x, y, x + w, y + h), fill="white")
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
    return found_any


def clear_dirs_d():
    for file in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, file))
    for file in os.listdir(input_folder):
        os.remove(os.path.join(input_folder, file))
