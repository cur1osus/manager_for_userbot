import glob
import os

import cv2
import numpy as np

input_folder = "./images_v"
output_dir = "./result_images_v"

vykupili = cv2.imread("./vu.png")
otkazalis_template = cv2.imread("./ot.png", cv2.IMREAD_GRAYSCALE)
oh, ow = otkazalis_template.shape

os.makedirs(output_dir, exist_ok=True)
os.makedirs(input_folder, exist_ok=True)


def _process_image_v():
    for img_path in glob.glob(os.path.join(input_folder, "*.[Pp][Nn][Gg]")):
        img = cv2.imread(img_path)

        # 2. Ищем плашку "ОТКАЗАЛИСЬ"
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(img_gray, otkazalis_template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.8
        loc = np.where(res >= threshold)

        for pt in zip(*loc[::-1]):
            # Масштабируем плашку "ВЫКУПИЛИ" под размер найденной области
            resized_vykupili = cv2.resize(vykupili, (ow, oh))

            # Полностью заменяем область
            img[pt[1] : pt[1] + oh, pt[0] : pt[0] + ow] = resized_vykupili

        # 3. Сохраняем результат
        path = os.path.join(output_dir, f"{img_path.split('/')[-1]}")
        cv2.imwrite(path, img)


def process_image_v():
    vykupili_h, vykupili_w = vykupili.shape[:2]  # размеры оригинального изображения

    for img_path in glob.glob(os.path.join(input_folder, "*.[Pp][Nn][Gg]")):
        img = cv2.imread(img_path)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Поиск "ОТКАЗАЛИСЬ"
        res = cv2.matchTemplate(img_gray, otkazalis_template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.8
        loc = np.where(res >= threshold)

        for pt in zip(*loc[::-1]):  # pt = (x, y) — левый верхний угол совпадения
            x, y = pt  # левый верхний угол "ОТКАЗАЛИСЬ"
            h = oh  # высота шаблона "ОТКАЗАЛИСЬ"

            # --- Шаг 1: Закрашиваем область "ОТКАЗАЛИСЬ" белым ---
            cv2.rectangle(img, (x, y), (x + ow, y + h), (255, 255, 255), -1)

            # --- Шаг 2: Вставляем "ВЫКУПИЛИ" по левому краю ---
            # Горизонтально: начинаем с x (левый край)
            vx1 = x
            vx2 = x + vykupili_w

            # Вертикально: центрируем по высоте "ОТКАЗАЛИСЬ"
            vy1 = y + (h - vykupili_h) // 2  # центр по вертикали
            vy2 = vy1 + vykupili_h

            # Проверка на выход за границы изображения
            if vx2 > img.shape[1] or vy2 > img.shape[0] or vy1 < 0:
                print(f"Пропуск: 'ВЫКУПИЛИ' не помещается в {img_path}")
                continue

            # Вставляем оригинальное изображение "ВЫКУПИЛИ"
            img[vy1:vy2, vx1:vx2] = vykupili

        # Сохраняем
        filename = os.path.basename(img_path)
        cv2.imwrite(os.path.join(output_dir, filename), img)


def clear_dirs_v():
    for file in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, file))
    for file in os.listdir(input_folder):
        os.remove(os.path.join(input_folder, file))
