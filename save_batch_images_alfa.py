import sys
import os
import numpy as np
import time
import importlib
import gc
import subprocess
import io
import torch
import numpy as np
from PIL import Image
import comfy.model_management as mm

class SaveBatchImagesWithAlphaMask:
    _bg_model = None

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "bc": ("IMAGE",),
                "nm": ("IMAGE",),
                "pos": ("IMAGE",),                
                "path": ("STRING", {"default": "L:/AI_3d/output"}),
                "filename": ("STRING", {"default": "view"}),
                "low_vram": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("preview",)
    FUNCTION = "save_images_with_alpha"
    OUTPUT_NODE = True
    CATEGORY = "Antonioilev/IO"

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return time.time()

    def tensor_to_image(self, image):
        if isinstance(image, torch.Tensor):
            img = image.cpu()
            if img.ndim == 3 and img.shape[0] in [1, 3, 4]:
                img = img.permute(1, 2, 0)
            img = img.numpy()
            if img.max() <= 1.0:
                img = img * 255.0
            img = np.clip(img, 0, 255).astype(np.uint8)
        else:
            img = np.clip(image, 0, 255).astype(np.uint8)
        return Image.fromarray(img)

    def remove_background(self, pil_image, low_vram=True):
        """
        Возвращает маску объекта (фон черный, объект белый) для PIL-изображения.
        Использует CLI утилиту rembg, чтобы обойти локальный конфликт.
        """
        # Конвертируем PIL в байты PNG
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        # Запускаем rembg через subprocess
        process = subprocess.Popen(
            ["rembg", "i"],  # "i" = input из stdin, output в stdout
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out_bytes, err = process.communicate(input=img_bytes)

        if process.returncode != 0:
            raise RuntimeError(f"rembg failed: {err.decode()}")

        # Загружаем результат как PIL
        out_image = Image.open(io.BytesIO(out_bytes)).convert("RGBA")

        # Извлекаем альфа-канал
        mask_np = np.array(out_image)[:, :, 3]
        mask_img = Image.fromarray(mask_np).convert("L")

        return mask_img

    def save_images_with_alpha(self, bc, nm, pos, path, filename, low_vram):
        clean_path = os.path.normpath(path)
        os.makedirs(clean_path, exist_ok=True)

        all_images = []

        def process_batch(batch, suffix):
            for i, img in enumerate(batch):
                pil = self.tensor_to_image(img)

                # получаем маску
                mask = self.remove_background(pil, low_vram=low_vram)

                # объединяем RGB + маску в RGBA
                rgba = pil.convert("RGBA")
                rgba.putalpha(mask)

                name = f"{filename}_{suffix}_{i+1}.png"
                full_path = os.path.join(clean_path, name)
                rgba.save(full_path, compress_level=1)
                print(f"[SaveBatch] Saved RGBA: {full_path}")

                # collect for preview
                arr = np.array(rgba).astype(np.float32) / 255.0
                all_images.append(arr)

        process_batch(bc, "bc")
        process_batch(pos, "pos")
        process_batch(nm, "nm")        

        # возвращаем батч с альфа-каналом
        batch = torch.from_numpy(np.stack(all_images, axis=0))
        return (batch,)


NODE_CLASS_MAPPINGS = {
    "AntonioilevSaveBatchImagesWithAlpha": SaveBatchImagesWithAlphaMask
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AntonioilevSaveBatchImagesWithAlpha": "💾 Save Batch Images with Alpha Mask"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']