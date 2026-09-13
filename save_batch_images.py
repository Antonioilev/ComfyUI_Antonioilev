import os
import torch
import numpy as np
from PIL import Image
import time

class Save_batch_images:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "path": ("STRING", {"default": "L:/AI_3d/output"}),
                "filename": ("STRING", {"default": "view"}),
            },
            "optional": {
                "bc": ("IMAGE",),                 
                "nm": ("IMAGE",),
                "pos": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("preview",)
    FUNCTION = "save_images"
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

    def save_images(self, path, filename, bc=None, nm=None, pos=None):
        # 1. Проверяем, есть ли хоть какие-то данные на входе
        if bc is None and nm is None and pos is None:
            return (torch.zeros((1, 16, 16, 3)),)

        # 2. ШЛЮЗ: Проверяем первый попавшийся активный вход на предмет заглушки 16x16
        # Если пришла маленькая картинка от ListBatchImages - просто выходим без записи
        check_input = bc if bc is not None else (nm if nm is not None else pos)
        if check_input.shape[1] <= 16 or check_input.shape[2] <= 16:
            return (torch.zeros((1, 16, 16, 3)),)

        clean_path = os.path.normpath(path)
        os.makedirs(clean_path, exist_ok=True)
        all_images = []

        def process_batch(batch, suffix):
            if batch is None:
                return

            for i in range(batch.shape[0]):
                img_tensor = batch[i]
                
                # Конвертируем в PIL
                pil = self.tensor_to_image(img_tensor)
                
                # Формируем имя и сохраняем
                name = f"{filename}_{suffix}_{i+1}.png"
                full_path = os.path.join(clean_path, name)
                
                pil.save(full_path, compress_level=1)
                print(f"[SaveBatch] Writing: {full_path}")

                # Собираем для выходного превью
                arr = np.array(pil).astype(np.float32) / 255.0
                all_images.append(arr)

        # Обрабатываем каждый канал
        process_batch(bc, "bc")
        process_batch(nm, "nm")
        process_batch(pos, "pos")

        # Если записи не произошло (все каналы пустые), возвращаем заглушку
        if not all_images:
            return (torch.zeros((1, 16, 16, 3)),)

        # Возвращаем батч для Preview ноды
        result_batch = torch.from_numpy(np.stack(all_images, axis=0))
        return (result_batch,)

NODE_CLASS_MAPPINGS = {
    "AntonioilevSaveBatchImages": Save_batch_images
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AntonioilevSaveBatchImages": "💾 Save Batch Images (BC/NM/POS)"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']