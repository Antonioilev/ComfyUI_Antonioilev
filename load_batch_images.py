import os
import re
import torch
import numpy as np
from PIL import Image
import glob
import time


class Load_batch_images:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "path_mask": ("STRING", {
                    "default": "/mnt/l/Game_2/Art/Chars/Char1/MVs/Head/MV_head_"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE")
    RETURN_NAMES = ("bc", "nm", "pos")
    FUNCTION = "load_images"
    CATEGORY = "Antonioilev/IO"

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return time.time()

    # -------------------------
    # ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
    # -------------------------
    def load_set(self, folder, prefix):
        extensions = ["png", "jpg", "jpeg", "tga", "bmp", "webp"]

        files = []
        for ext in extensions:
            pattern = os.path.join(folder, f"{prefix}*.{ext}")
            files.extend(glob.glob(pattern))

        # Если файлов нет, возвращаем None вместо Exception
        if len(files) == 0:
            print(f"[AntonioilevLoader] Skipping: No images found for {prefix}")
            return None

        # --- сортировка ---
        def extract_number(f):
            name = os.path.basename(f)
            nums = re.findall(r'\d+', name)
            return int(nums[-1]) if nums else None

        if any(extract_number(f) is not None for f in files):
            files.sort(key=lambda x: (extract_number(x) is None, extract_number(x)))
        else:
            files.sort()

        print(f"[AntonioilevLoader] {prefix} → {len(files)} images")

        images = []
        for f in files:
            img = Image.open(f).convert("RGB")
            img_np = np.array(img).astype(np.float32) / 255.0
            images.append(img_np)

        # --- выравнивание ---
        max_h = max(img.shape[0] for img in images)
        max_w = max(img.shape[1] for img in images)

        padded = []
        for img in images:
            h, w, c = img.shape
            canvas = np.zeros((max_h, max_w, 3), dtype=np.float32)
            canvas[:h, :w, :] = img
            padded.append(canvas)

        batch = torch.from_numpy(np.stack(padded, axis=0))
        return batch

    # -------------------------
    # ОСНОВНАЯ ФУНКЦИЯ
    # -------------------------
    def load_images(self, path_mask):
        folder = os.path.dirname(path_mask)
        base = os.path.basename(path_mask)

        if not os.path.exists(folder):
            raise Exception(f"[AntonioilevLoader] Folder not found: {folder}")

        bc_prefix = base + "bc_"
        nm_prefix = base + "nm_"
        pos_prefix = base + "pos_"

        bc = self.load_set(folder, bc_prefix)
        nm = self.load_set(folder, nm_prefix)
        pos = self.load_set(folder, pos_prefix)

        # Проверка: если не найдено ВООБЩЕ ничего
        if bc is None and nm is None and pos is None:
            raise Exception(f"[AntonioilevLoader] Error: No BC, NM, or POS images found in {folder} with prefix {base}")

        # Создаем пустую заглушку для пустых каналов (черный пиксель), 
        # чтобы линки в ComfyUI оставались валидными
        empty_image = torch.zeros((1, 64, 64, 3), dtype=torch.float32)

        res_bc = bc if bc is not None else empty_image
        res_nm = nm if nm is not None else empty_image
        res_pos = pos if pos is not None else empty_image

        # --- контроль размеров (только если каналы существуют) ---
        found_batches = [b for b in [bc, nm, pos] if b is not None]
        if len(found_batches) > 1:
            first_len = len(found_batches[0])
            if not all(len(b) == first_len for b in found_batches):
                print("!!! [AntonioilevLoader WARNING] Different batch sizes detected!")

        return (res_bc, res_nm, res_pos)


NODE_CLASS_MAPPINGS = {
    "AntonioilevLoadBatchImages": Load_batch_images
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AntonioilevLoadBatchImages": "📂 Load Batch Images (BC/NM/POS)"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']