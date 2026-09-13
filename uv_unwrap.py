import numpy as np
import trimesh
import xatlas
import gc
import comfy.model_management

class AntonioilevUVUnwrap:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "padding": ("INT", {"default": 4, "min": 0, "max": 64}),
                "resolution": ("INT", {"default": 2048, "min": 512, "max": 8192}),
            }
        }

    RETURN_TYPES = ("STRING", "TRIMESH")
    RETURN_NAMES = ("info", "mesh")
    FUNCTION = "unwrap_standard"
    CATEGORY = "Antonioilev/UV"

    def unwrap_standard(self, mesh, padding, resolution):
        if mesh is None: 
            return ("No mesh", None)
        
        work_mesh = mesh.copy()
        v_pos = work_mesh.vertices.astype(np.float32)
        f_ind = work_mesh.faces.astype(np.uint32)
        
        # Инициализация и запуск стандартного xatlas
        atlas = xatlas.Atlas()
        atlas.add_mesh(v_pos, f_ind)
        
        # Настройки упаковки (разрешение и отступы)
        p_options = xatlas.PackOptions()
        p_options.resolution = resolution
        p_options.padding = padding
        
        # Генерация развертки и упаковка
        atlas.generate(pack_options=p_options)
        
        # Получение результатов (xatlas сам дублирует вершины на швах)
        vmap, ind, uv = atlas[0]
        
        final_verts = v_pos[vmap]
        final_faces = ind
        final_uvs = uv
        
        # Сборка финального меша
        out_mesh = trimesh.Trimesh(vertices=final_verts, faces=final_faces, process=False)
        out_mesh.visual = trimesh.visual.TextureVisuals(uv=final_uvs)
        
        # Очистка памяти
        gc.collect()
        comfy.model_management.soft_empty_cache()
        
        info = f"Antonioilev Standard Xatlas | Resolution: {resolution} | Padding: {padding}"
        return (info, out_mesh)

NODE_CLASS_MAPPINGS = {"AntonioilevUVUnwrap": AntonioilevUVUnwrap}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevUVUnwrap": "🌀 UV Unwrap (Standard Xatlas)"}