import os
import torch
import numpy as np
from PIL import Image
import time


class ImageSaver:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "path": ("STRING", {
                    "default": "L:/AI_3d/Art3d_generations/output/my_character"
                }),
                "filename": ("STRING", {
                    "default": "view"
                }),
            },
            "optional": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Antonioilev/IO"

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return time.time()

    def save(self, path, filename, image=None, mask=None):

        clean_path = os.path.normpath(path)
        os.makedirs(clean_path, exist_ok=True)

        # -------------------------
        # IMAGE SAVE
        # -------------------------
        if image is not None:

            for i, img in enumerate(image):

                tensor = img.cpu()

                # normalize shape
                if tensor.ndim == 3 and tensor.shape[0] in [1, 3, 4]:
                    tensor = tensor.permute(1, 2, 0)

                arr = tensor.numpy()

                arr = np.clip(arr, 0.0, 1.0)
                arr = (arr * 255.0).astype(np.uint8)

                # grayscale protection
                if arr.ndim == 3 and arr.shape[-1] == 1:
                    arr = arr.squeeze(-1)

                pil = Image.fromarray(arr)

                idx_str = f"_{i}" if len(image) > 1 else ""

                file_path = os.path.join(
                    clean_path,
                    f"{filename}{idx_str}.png"
                )

                pil.save(file_path, compress_level=1)

                print(f"!!! [ImageSaver] Saved IMAGE: {file_path}")

        # -------------------------
        # MASK SAVE
        # -------------------------
        if mask is not None:

            for i, m in enumerate(mask):

                tensor = m.cpu()

                # normalize mask shape
                if tensor.ndim == 3:
                    tensor = tensor.squeeze(0)

                arr = tensor.numpy()

                arr = np.clip(arr, 0.0, 1.0)
                arr = (arr * 255.0).astype(np.uint8)

                # IMPORTANT:
                # save mask as RGB for robust loader compatibility
                rgb_mask = np.stack([arr, arr, arr], axis=-1)

                pil = Image.fromarray(rgb_mask)

                idx_str = f"_{i}" if len(mask) > 1 else ""

                file_path = os.path.join(
                    clean_path,
                    f"{filename}{idx_str}_mask.png"
                )

                pil.save(file_path, compress_level=1)

                print(f"!!! [ImageSaver] Saved MASK: {file_path}")

        # -------------------------
        # NOTHING CONNECTED
        # -------------------------
        if image is None and mask is None:

            print("!!! [ImageSaver] Nothing connected.")

        return ()


NODE_CLASS_MAPPINGS = {
    "ImageSaver": ImageSaver
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageSaver": "💾 Image + Mask Saver"
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS"
]