import numpy as np
import trimesh

class AntonioilevHardBottomCap:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "cap_offset": ("FLOAT", {"default": 0.001, "min": -0.05, "max": 0.05, "step": 0.001}),
                "z_ratio": ("FLOAT", {"default": 0.05, "min": 0.01, "max": 0.2, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("STRING", "TRIMESH")
    RETURN_NAMES = ("info", "mesh")
    FUNCTION = "process"
    CATEGORY = "Antonioilev/Mesh"

    def process(self, mesh, cap_offset, z_ratio):
        if mesh is None: return ("No input", None)
        
        mesh = mesh.copy()
        mesh.merge_vertices()
        
        # 1. Поиск граничных ребер (стабильный метод)
        edges = mesh.edges_sorted
        order = np.lexsort(edges.T)
        edges_sorted = edges[order]
        diff = np.any(edges_sorted[1:] != edges_sorted[:-1], axis=1)
        unique_indices = np.where(np.concatenate(([True], diff)) & np.concatenate((diff, [True])))[0]
        
        if len(unique_indices) == 0:
            return ("Mesh already watertight", mesh)
            
        boundary_edges = edges_sorted[unique_indices]
        
        # 2. ОПРЕДЕЛЕНИЕ ГРАНИЦЫ СРЕЗА (Strict Filter)
        z_min = mesh.vertices[:, 2].min()
        # Лимит высоты: ищем дырку только в самом низу (по умолчанию 5% высоты)
        z_limit = z_min + (mesh.extents[2] * z_ratio)
        
        valid_edge_indices = []
        for i, edge in enumerate(boundary_edges):
            v1, v2 = mesh.vertices[edge[0]], mesh.vertices[edge[1]]
            
            # Ребро должно быть:
            # А) Оба конца ниже z_limit
            # Б) Почти горизонтальным (чтобы не зашивать вертикальные разрезы)
            if v1[2] < z_limit and v2[2] < z_limit:
                if abs(v1[2] - v2[2]) < 0.01: # Порог горизонтальности
                    valid_edge_indices.append(i)
        
        if not valid_edge_indices:
            return (f"No horizontal boundary found below {z_limit:.4f}", mesh)
            
        target_edges = boundary_edges[valid_edge_indices]
        target_nodes = np.unique(target_edges)

        # 3. СОЗДАНИЕ ПЛОСКОЙ "ПРОБКИ"
        # Точка зашивки — строго под центром среза
        bottom_points = mesh.vertices[target_nodes]
        center_pt = bottom_points.mean(axis=0)
        center_pt[2] = z_min - cap_offset 
        
        new_v_idx = len(mesh.vertices)
        new_vertices = np.vstack([mesh.vertices, center_pt])
        
        # Строим грани
        new_faces = []
        for edge in target_edges:
            new_faces.append([edge[0], edge[1], new_v_idx])
            
        # 4. СБОРКА
        new_mesh = trimesh.Trimesh(vertices=new_vertices, 
                                  faces=np.vstack([mesh.faces, new_faces]))
        
        # Лечим нормали, чтобы крышка смотрела наружу
        trimesh.repair.fix_winding(new_mesh)
        trimesh.repair.fix_normals(new_mesh)
        
        return (f"Sealed {len(new_faces)} faces at Z={z_min:.4f}", new_mesh)

NODE_CLASS_MAPPINGS = {"AntonioilevHardBottomCap": AntonioilevHardBottomCap}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevHardBottomCap": "⚓ Hard Bottom Cap (Strict)"}