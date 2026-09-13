import os
import torch
import numpy as np
from PIL import Image
import time


class ImageLoader:
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
                    "default": "M_Face_1"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load"
    OUTPUT_NODE = True
    CATEGORY = "Antonioilev/IO"

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return time.time()

    def load(self, path, filename):

        clean_path = os.path.normpath(path)

        img_path = os.path.join(clean_path, f"{filename}.png")
        mask_path = os.path.join(clean_path, f"{filename}_mask.png")

        image_tensor = None
        mask_tensor = None

        # -------------------------
        # LOAD IMAGE
        # -------------------------
        if os.path.exists(img_path):

            img = Image.open(img_path).convert("RGB")

            img_array = np.array(img, dtype=np.float32) / 255.0

            image_tensor = torch.from_numpy(img_array)
            image_tensor = image_tensor.unsqueeze(0).float().contiguous()

            print(f"!!! [ImageLoader] Loaded IMAGE: {img_path}")

        # -------------------------
        # LOAD MASK
        # -------------------------
        if os.path.exists(mask_path):

            img_mask = Image.open(mask_path).convert("RGB")

            mask_rgb = np.array(img_mask, dtype=np.float32) / 255.0

            # robust extraction
            r = mask_rgb[:, :, 0]
            g = mask_rgb[:, :, 1]
            b = mask_rgb[:, :, 2]

            mask = np.maximum(np.maximum(r, g), b)

            mask = np.clip(mask, 0.0, 1.0)

            mask_tensor = torch.from_numpy(mask)
            mask_tensor = mask_tensor.unsqueeze(0).float().contiguous()

            print(f"!!! [ImageLoader] Loaded MASK: {mask_path}")

        # -------------------------
        # FALLBACKS
        # -------------------------

        # если image нет, но mask есть
        if image_tensor is None and mask_tensor is not None:

            H = mask_tensor.shape[1]
            W = mask_tensor.shape[2]

            image_tensor = torch.zeros((1, H, W, 3), dtype=torch.float32)

            print("!!! [ImageLoader] IMAGE missing -> created empty image")

        # если mask нет, но image есть
        if mask_tensor is None and image_tensor is not None:

            H = image_tensor.shape[1]
            W = image_tensor.shape[2]

            mask_tensor = torch.zeros((1, H, W), dtype=torch.float32)

            print("!!! [ImageLoader] MASK missing -> created empty mask")

        # если вообще ничего нет
        if image_tensor is None and mask_tensor is None:

            raise FileNotFoundError(
                f"[ImageLoader] Neither image nor mask found for filename: {filename}"
            )

        return (image_tensor, mask_tensor)


NODE_CLASS_MAPPINGS = {
    "ImageLoader": ImageLoader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageLoader": "📥 Image + Mask Loader"
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS"
]