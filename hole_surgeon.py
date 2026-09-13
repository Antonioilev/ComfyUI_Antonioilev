import numpy as np
import trimesh

class AntonioilevHoleSurgeon:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "hole_size_threshold": ("FLOAT", {"default": 0.5, "min": 0.001, "max": 10.0, "step": 0.01}),
                "max_points_in_hole": ("INT", {"default": 60, "min": 3, "max": 1000}), # Защита волос
                "remove_small_islands": ("BOOLEAN", {"default": True}),
                "fix_normals": ("BOOLEAN", {"default": True}),
                "relax_iterations": ("INT", {"default": 15, "min": 0, "max": 50, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "TRIMESH")
    RETURN_NAMES = ("info", "mesh")
    FUNCTION = "process"
    CATEGORY = "Antonioilev/Mesh/Fix"

    def process(self, mesh, hole_size_threshold, max_points_in_hole, remove_small_islands, fix_normals, relax_iterations):
        if mesh is None: return ("No input", None)
        
        work_mesh = mesh.copy()
        work_mesh.merge_vertices()
        
        if remove_small_islands:
            components = work_mesh.split(only_watertight=False)
            if len(components) > 1:
                max_area = max(c.area for c in components)
                work_mesh = trimesh.util.concatenate([c for c in components if c.area > max_area * 0.05])
                work_mesh.merge_vertices()

        old_face_count = len(work_mesh.faces)
        old_vertex_count = len(work_mesh.vertices)
        
        # 1. Сначала ищем контуры вручную, чтобы контролировать ЧТО мы зашиваем
        outline = work_mesh.outline()
        added_v_count = 0
        
        if hasattr(outline, 'entities'):
            for entity in outline.entities:
                idx = entity.points
                
                # КРИТИЧЕСКИЙ ФИЛЬТР:
                # Если в дырке слишком много точек (например, 200+) - это волосы или шея. 
                # Пропускаем, чтобы не "схлопнуть" голову.
                if len(idx) > max_points_in_hole:
                    continue
                
                pts = work_mesh.vertices[idx]
                # Проверка физического размера дырки
                if np.max(np.ptp(pts, axis=0)) <= hole_size_threshold:
                    center = pts.mean(axis=0)
                    c_idx = len(work_mesh.vertices)
                    
                    # Добавляем центр
                    work_mesh.vertices = np.vstack([work_mesh.vertices, center])
                    
                    # Создаем веер
                    new_f = []
                    for i in range(len(idx)):
                        new_f.append([idx[i], idx[(i + 1) % len(idx)], c_idx])
                    
                    work_mesh.faces = np.vstack([work_mesh.faces, new_f])
                    added_v_count += 1

        # 2. ИЗОЛИРОВАННАЯ РЕЛАКСАЦИЯ (только для новых центров заплат)
        if relax_iterations > 0 and added_v_count > 0:
            new_v_indices = np.arange(old_vertex_count, len(work_mesh.vertices))
            neighbors = work_mesh.vertex_neighbors
            
            for _ in range(relax_iterations):
                current_verts = work_mesh.vertices.copy()
                for v_idx in new_v_indices:
                    v_neighbors = neighbors[v_idx]
                    if len(v_neighbors) > 0:
                        work_mesh.vertices[v_idx] = current_verts[v_neighbors].mean(axis=0)

        # 3. Финализация
        new_face_count = len(work_mesh.faces)
        total_added = new_face_count - old_face_count
        
        if total_added > 0:
            colors = np.full((new_face_count, 4), [200, 200, 200, 255], dtype=np.uint8)
            colors[old_face_count:] = [255, 255, 0, 255] # Желтые заплатки
            work_mesh.visual.face_colors = colors
            
            if fix_normals:
                work_mesh.fix_normals()
                trimesh.repair.fix_winding(work_mesh)
            
            info = f"Success! Closed {total_added // 3} small holes. Head preserved by vertex count limit."
        else:
            info = "Nothing closed. Try to adjust 'max_points_in_hole' or 'hole_size_threshold'."

        return (info, work_mesh)

NODE_CLASS_MAPPINGS = {"AntonioilevHoleSurgeon": AntonioilevHoleSurgeon}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevHoleSurgeon": "💉 Hole Surgeon (Hair Safe)"}