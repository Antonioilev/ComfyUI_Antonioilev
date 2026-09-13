import numpy as np
import trimesh
import torch

class UVShellScale:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trimesh_mesh": ("TRIMESH",),
                "scale_factor": ("FLOAT", {"default": 0.9, "min": 0.01, "max": 2.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("TRIMESH",)
    RETURN_NAMES = ("trimesh_mesh",)
    FUNCTION = "scale_uv"
    CATEGORY = "Antonioilev/UV"

    def scale_uv(self, trimesh_mesh, scale_factor):
        # 1. Глубокая копия меша
        mesh = trimesh_mesh.copy()
        
        # Проверка наличия UV
        if not hasattr(mesh.visual, 'uv') or mesh.visual.uv is None:
            print("!!! [UVShellScale] Mesh has no UV coordinates.")
            return (trimesh_mesh,)

        uvs = mesh.visual.uv.copy()
        
        # 2. Поиск островов через связность граней
        # face_adjacency говорит нам, какие грани соприкасаются
        # connected_components группирует их в "острова"
        try:
            island_groups = trimesh.graph.connected_components(
                mesh.face_adjacency, 
                nodes=np.arange(len(mesh.faces))
            )
        except Exception as e:
            print(f"!!! [UVShellScale] Error finding islands: {e}")
            return (trimesh_mesh,)

        # 3. Масштабирование каждого острова
        for face_indices in island_groups:
            # Получаем индексы вершин, принадлежащих этому острову граней
            # Важно: используем flatten(), чтобы получить линейный массив индексов
            vert_idx = np.unique(mesh.faces[face_indices].reshape(-1))
            
            if len(vert_idx) == 0:
                continue
                
            island_uvs = uvs[vert_idx]
            
            # Находим геометрический центр острова в UV-пространстве (0-1)
            # Используем min/max для более точного центра "коробки" (bounding box) острова
            uv_min = np.min(island_uvs, axis=0)
            uv_max = np.max(island_uvs, axis=0)
            center = (uv_min + uv_max) / 2.0
            
            # Либо можно через среднее (выбери что больше нравится, mean обычно стабильнее):
            # center = np.mean(island_uvs, axis=0)
            
            # Применяем масштаб относительно центра
            uvs[vert_idx] = center + (island_uvs - center) * scale_factor

        # 4. Записываем обновленные UV обратно в копию меша
        mesh.visual.uv = uvs
        
        print(f">>> [UVShellScale] Successfully scaled {len(island_groups)} UV islands.")
        return (mesh,)

NODE_CLASS_MAPPINGS = { "AntonioilevUVShellScale": UVShellScale }
NODE_DISPLAY_NAME_MAPPINGS = { "AntonioilevUVShellScale": "📐 UV Shell Scaler" }