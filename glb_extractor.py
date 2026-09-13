import os
import torch
import numpy as np
from PIL import Image
import trimesh

class GLBTextureExtractor:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "glb_path": ("STRING", {"default": "path/to/your/model.glb"}),
                "save_dir": ("STRING", {"default": "/mnt/l/Game_2/Art/Chars/Char1/Texturing"}),
                "filename": ("STRING", {"default": "extracted_basecolor"}),
                "save_texture": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "TRIMESH", "STRING")
    RETURN_NAMES = ("texture", "alpha_mask", "trimesh_mesh", "saved_path")
    FUNCTION = "extract"
    CATEGORY = "Antonioilev/Texturing"

    def extract(self, glb_path, save_dir, filename, save_texture):
        if not os.path.exists(glb_path):
            raise FileNotFoundError(f"GLB file not found: {glb_path}")

        # 1. Загружаем меш
        mesh = trimesh.load(glb_path, force='mesh')
        
        texture_pil = None
        
        # 2. Пытаемся достать текстуру из материала
        if hasattr(mesh.visual, 'material'):
            material = mesh.visual.material
            # Проверяем стандартные атрибуты trimesh для текстур
            if hasattr(material, 'image') and material.image is not None:
                texture_pil = material.image
            elif hasattr(material, 'baseColorTexture') and material.baseColorTexture is not None:
                texture_pil = material.baseColorTexture

        # Если текстуры нет в материале, ищем в simple_visual (иногда trimesh грузит туда)
        if texture_pil is None and hasattr(mesh.visual, 'kind') and mesh.visual.kind == 'texture':
             if hasattr(mesh.visual, 'uv'):
                 # Бывает, что картинка лежит просто в визуале
                 texture_pil = mesh.visual.material.image

        if texture_pil is None:
            print(f"[Antonioilev] Warning: No texture found in {glb_path}. Generating dummy white texture.")
            texture_pil = Image.new("RGB", (1024, 1024), (255, 255, 255))

        # 3. Сохранение на диск (если включено)
        saved_path = ""
        if save_texture:
            try:
                os.makedirs(save_dir, exist_ok=True)
                # Очищаем имя файла от расширения, если пользователь его ввел
                clean_name = os.path.splitext(filename)[0]
                full_path = os.path.join(save_dir, f"{clean_name}.png")
                
                # Сохраняем в PNG
                texture_pil.save(full_path, "PNG")
                saved_path = full_path
                print(f"[Antonioilev] Texture successfully saved to: {saved_path}")
            except Exception as e:
                print(f"[Antonioilev] Error saving texture: {e}")

        # 4. Подготовка данных для ComfyUI
        # Конвертируем в RGB для основного выхода
        texture_rgb = texture_pil.convert("RGB")
        
        # Создаем маску из альфа-канала (если он был)
        if texture_pil.mode == 'RGBA':
            alpha = texture_pil.getchannel('A')
            mask = torch.from_numpy(np.array(alpha).astype(np.float32) / 255.0)
        else:
            # Если альфы нет, маска полностью белая (1.0)
            mask = torch.ones((texture_rgb.height, texture_rgb.width), dtype=torch.float32)

        # Подготовка тензора изображения (BHWC)
        img_array = np.array(texture_rgb).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_array).unsqueeze(0)
        
        # Подготовка тензора маски (BHW)
        mask_tensor = mask.unsqueeze(0)

        return (img_tensor, mask_tensor, mesh, saved_path)

# Регистрация новой ноды
NODE_CLASS_MAPPINGS = { "AntonioilevGLBTextureExtractor": GLBTextureExtractor }
NODE_DISPLAY_NAME_MAPPINGS = { "AntonioilevGLBTextureExtractor": "📦 GLB Texture Extractor" }