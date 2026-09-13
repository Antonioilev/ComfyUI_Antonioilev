import numpy as np
import trimesh

class AntonioilevMeshCleaner:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "merge_distance": ("FLOAT", {"default": 0.001, "min": 0, "max": 0.1, "step": 0.0001}),
                "min_island_size": ("FLOAT", {"default": 0.03, "min": 0, "max": 1.0, "step": 0.01}),
                "remove_islands_ratio": ("FLOAT", {"default": 0.01, "min": 0, "max": 1.0, "step": 0.01}),
                "fix_normals": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "clean"
    CATEGORY = "Antonioilev/Mesh/Fix"

    def clean(self, mesh, merge_distance, min_island_size, remove_islands_ratio, fix_normals):
        if mesh is None: return (None, "No input")
        
        new_mesh = mesh.copy()
        
        # 1. Склеиваем только ОЧЕНЬ близкие точки (микро-разрывы)
        new_mesh.merge_vertices(merge_distance)
        
        # 2. Умное удаление мусора
        if remove_islands_ratio > 0 or min_island_size > 0:
            components = new_mesh.split(only_watertight=False)
            if len(components) > 1:
                max_area = max(c.area for c in components)
                kept_components = []
                
                for c in components:
                    # Считаем габарит куска (диагональ его бокса)
                    c_size = np.linalg.norm(c.bounds[1] - c.bounds[0])
                    
                    # Условие сохранения: 
                    # Либо он большой по площади (ratio)
                    # ЛИБО он достаточно крупный физически (min_island_size)
                    if c.area > max_area * remove_islands_ratio or c_size >= min_island_size:
                        kept_components.append(c)
                
                if kept_components:
                    new_mesh = trimesh.util.concatenate(kept_components)
                    new_mesh.merge_vertices(merge_distance)
        
        if fix_normals:
            new_mesh.fix_normals()
            trimesh.repair.fix_winding(new_mesh)
            
        info = f"Cleaner: Kept {len(new_mesh.vertices)} verts. (Min Island: {min_island_size}m)"
        return (new_mesh, info)

NODE_CLASS_MAPPINGS = {"AntonioilevMeshCleaner": AntonioilevMeshCleaner}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevMeshCleaner": "🧹 Mesh Cleaner (Pre-op)"}