# SPDX-License-Identifier: GPL-3.0-or-later
# Antonioilev - 2026 (Ultimate Multi-Colorizer - Compact Edition)

import numpy as np
import trimesh

class AntonioilevMultiColorizer:
    @classmethod
    def INPUT_TYPES(s):
        # Используем "optional", чтобы нода не блокировала очередь, 
        # если подключены не все 10 мешей.
        inputs = {
            "required": {},
            "optional": {}
        }
        
        # Генерируем строго 10 строк: Вход -> Цвет
        for i in range(1, 11):
            inputs["optional"][f"mesh_{i}"] = ("TRIMESH,MESH",)
            # Тип "COLOR" часто активирует графическую палитру в UI
            inputs["optional"][f"color_{i}"] = ("COLOR", {"default": "#FFFFFF"})
            
        return inputs

    # 10 соответствующих выходов
    RETURN_TYPES = ("TRIMESH,MESH", "TRIMESH,MESH", "TRIMESH,MESH", "TRIMESH,MESH", "TRIMESH,MESH", "TRIMESH,MESH", "TRIMESH,MESH", "TRIMESH,MESH", "TRIMESH,MESH", "TRIMESH,MESH")
    RETURN_NAMES = ("m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10")
    
    FUNCTION = "colorize_multi"
    CATEGORY = "Antonioilev/Meshes"

    def colorize_multi(self, **kwargs):
        results = []
        ui_colors = []

        for i in range(1, 11):
            mesh = kwargs.get(f"mesh_{i}", None)
            # Если палитра вернула объект цвета, приводим к строке
            color_hex = str(kwargs.get(f"color_{i}", "#FFFFFF"))
            
            ui_colors.append(color_hex)

            if mesh is not None:
                # Копируем меш
                colored_mesh = mesh.copy()
                
                # HEX -> RGB
                try:
                    hex_val = color_hex.lstrip('#')
                    if len(hex_val) == 6:
                        rgb = [int(hex_val[i:i + 2], 16) for i in range(0, 6, 2)]
                    elif len(hex_val) == 3:
                        rgb = [int(hex_val[i:i + 1] * 2, 16) for i in range(0, 3)]
                    else:
                        rgb = [255, 255, 255]
                except:
                    rgb = [255, 255, 255]

                # Формируем RGBA (A всегда 255 - полная непрозрачность)
                rgba = [*rgb, 255]

                # Красим вершины
                colored_mesh.visual.vertex_colors = np.full((len(colored_mesh.vertices), 4), rgba, dtype=np.uint8)
                results.append(colored_mesh)
            else:
                results.append(None)

        return {
            "ui": {"colors": ui_colors}, 
            "result": tuple(results)
        }

# МАППИНГИ
NODE_CLASS_MAPPINGS = {
    "AntonioilevMultiColorizer": AntonioilevMultiColorizer,
    "AntonioilevMeshColorizer": AntonioilevMultiColorizer
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AntonioilevMultiColorizer": "🎨 Multi Mesh Colorizer (10 Slots)",
    "AntonioilevMeshColorizer": "🎨 Mesh Colorizer (Legacy)"
}