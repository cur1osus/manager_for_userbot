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


def process_image_v(scale=1.1, y_offset=-5):
    """
    :param scale: масштабирование плашки "ВЫКУПИЛИ"
    :param y_offset: смещение по вертикали (в пикселях).
                     Отрицательное — вверх, положительное — вниз.
    """
    h_orig, w_orig = vykupili.shape[:2]
    new_w = int(w_orig * scale)
    new_h = int(h_orig * scale)

    if scale == 1.0:
        resized_vykupili = vykupili.copy()
    else:
        interp = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
        resized_vykupili = cv2.resize(vykupili, (new_w, new_h), interpolation=interp)

    for img_path in glob.glob(os.path.join(input_folder, "*.[Pp][Nn][Gg]")):
        img = cv2.imread(img_path)
        if img is None:
            print(f"Не удалось загрузить: {img_path}")
            continue

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(img_gray, otkazalis_template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.8
        loc = np.where(res >= threshold)

        for pt in zip(*loc[::-1]):
            x, y = pt  # левый верхний угол "ОТКАЗАЛИСЬ"
            h_template = oh

            # --- 1. Закрашиваем "ОТКАЗАЛИСЬ" ---
            cv2.rectangle(img, (x, y), (x + ow, y + h_template), (255, 255, 255), -1)

            # --- 2. Вычисляем позицию для "ВЫКУПИЛИ" ---
            vx1 = x
            vx2 = x + new_w

            # Центрируем по высоте, затем применяем смещение
            vy_center = y + (h_template - new_h) // 2
            vy1 = vy_center + y_offset  # смещение: + вниз, - вверх
            vy2 = vy1 + new_h

            # --- 3. Проверка границ ---
            if vx2 > img.shape[1] or vy2 > img.shape[0] or vx1 < 0 or vy1 < 0:
                print(
                    f"Пропуск: выход за границы при scale={scale}, y_offset={y_offset}"
                )
                continue

            # --- 4. Вставляем ---
            img[vy1:vy2, vx1:vx2] = resized_vykupili

        # Сохраняем
        filename = os.path.basename(img_path)
        cv2.imwrite(os.path.join(output_dir, filename), img)


def clear_dirs_v():
    for file in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, file))
    for file in os.listdir(input_folder):
        os.remove(os.path.join(input_folder, file))
