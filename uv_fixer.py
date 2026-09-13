import numpy as np
import trimesh

class AntonioilevUVFixer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "margin": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 0.1, "step": 0.001}),
            }
        }

    RETURN_TYPES = ("STRING", "TRIMESH")
    RETURN_NAMES = ("info", "mesh")
    FUNCTION = "process"
    CATEGORY = "Antonioilev/UV"

    def process(self, mesh, margin):
        if mesh is None or not hasattr(mesh, 'visual') or not hasattr(mesh.visual, 'uv'):
            return ("No UV found", mesh)
        
        mesh = mesh.copy()
        uvs = mesh.visual.uv.copy()
        faces = mesh.faces
        
        # 1. Определение ориентации островов
        # Считаем знаковую площадь (Signed Area) каждого 2D треугольника в UV пространстве
        # Формула: 0.5 * ((x1*y2 - x2*y1) + (x2*y3 - x3*y2) + (x3*y1 - x1*y3))
        v0 = uvs[faces[:, 0]]
        v1 = uvs[faces[:, 1]]
        v2 = uvs[faces[:, 2]]
        
        # Векторное произведение в 2D даст нам понимание ориентации (CW или CCW)
        areas = 0.5 * ((v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1]) - 
                       (v2[:, 0] - v0[:, 0]) * (v1[:, 1] - v0[:, 1]))
        
        # Группируем грани по островам (используем встроенный метод trimesh)
        island_masks = trimesh.graph.connected_components(mesh.face_adjacency)
        
        flipped_count = 0
        for mask in island_masks:
            island_faces = faces[mask]
            island_uv_indices = np.unique(island_faces)
            
            # Считаем суммарную площадь острова. Если отрицательная — остров вывернут.
            total_island_area = np.sum(areas[mask])
            
            if total_island_area < 0:
                # ФЛИПАЕМ: инвертируем ось U для всех вершин этого острова
                uvs[island_uv_indices, 0] = -uvs[island_uv_indices, 0]
                flipped_count += 1

        # 2. Layout (Упаковка в 0..1)
        # Сдвигаем всё в положительную зону
        uvs[:, 0] -= uvs[:, 0].min()
        uvs[:, 1] -= uvs[:, 1].min()
        
        # Масштабируем, чтобы вписаться в 1.0 с учетом отступа
        max_dim = np.max(uvs)
        if max_dim > 0:
            scale = (1.0 - 2 * margin) / max_dim
            uvs *= scale
            uvs += margin

        mesh.visual.uv = uvs
        
        return (f"Fixed {flipped_count} flipped islands. UV Packed.", mesh)

NODE_CLASS_MAPPINGS = {"AntonioilevUVFixer": AntonioilevUVFixer}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevUVFixer": "🌀 UV Fixer & Packer"}