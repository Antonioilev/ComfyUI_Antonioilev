import gc
import time
import torch
import comfy.model_management as mm


class AntonioilevClearVRAM:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {}
        }

    RETURN_TYPES = ()
    FUNCTION = "clear"
    CATEGORY = "Antonioilev/Utils"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return time.time()

    def clear(self):

        print("\n[Antonioilev] Full VRAM cleanup started...")

        # -----------------------------
        # 1. Comfy model unload layer
        # -----------------------------
        try:
            mm.unload_all_models()
        except Exception as e:
            print(f"[Antonioilev] unload_all_models error: {e}")

        try:
            mm.soft_empty_cache()
        except Exception as e:
            print(f"[Antonioilev] soft_empty_cache error: {e}")

        # -----------------------------
        # 2. Python GC pressure
        # -----------------------------
        for _ in range(8):
            gc.collect()

        # -----------------------------
        # 3. CUDA reset layer
        # -----------------------------
        if torch.cuda.is_available():

            try:
                torch.cuda.synchronize()
            except:
                pass

            # aggressive cache flush
            for _ in range(5):
                torch.cuda.empty_cache()

            try:
                torch.cuda.ipc_collect()
            except:
                pass

            # final flush burst (important for fragmentation)
            for _ in range(3):
                torch.cuda.empty_cache()

            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3

            print(f"[Antonioilev] CUDA allocated: {allocated:.2f} GB")
            print(f"[Antonioilev] CUDA reserved : {reserved:.2f} GB")

        print("[Antonioilev] Full VRAM cleanup complete.\n")

        return ()


# ===================================
# REGISTRATION (НЕ ИЗМЕНЯЛ)
# ===================================

NODE_CLASS_MAPPINGS = {
    "AntonioilevClearVRAM": AntonioilevClearVRAM
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AntonioilevClearVRAM": "🧹 Clear VRAM"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']