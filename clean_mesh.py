import numpy as np
import trimesh
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

class AntonioilevCleanMesh:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "fold_threshold": ("FLOAT", {"default": -0.85, "min": -1.0, "max": -0.5, "step": 0.05}),
                "scale_threshold": ("FLOAT", {"default": 0.3, "min": 0.01, "max": 0.9}),
                "protect_outer": ("BOOLEAN", {"default": True}),
                "flat_bottom": ("BOOLEAN", {"default": True}),
                "close_holes": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "TRIMESH")
    RETURN_NAMES = ("info", "mesh")
    FUNCTION = "process"
    CATEGORY = "Antonioilev/Mesh/Fix"

    def process(self, mesh, fold_threshold, scale_threshold, protect_outer, flat_bottom, close_holes):
        if mesh is None: return ("No input", None)
        
        mesh = mesh.copy()
        mesh.merge_vertices()
        
        center_mass = mesh.centroid
        total_extent = np.max(mesh.extents)
        z_min_global = mesh.bounds[0][2]
        info_log = []

        # --- 1. ПРЕДВАРИТЕЛЬНЫЙ РАЗРЫВ ПЕТЛИ ---
        if flat_bottom:
            z_cut = z_min_global + (mesh.extents[2] * 0.015)
            mask = mesh.vertices[:, 2] > z_cut
            if np.any(mask):
                mesh.update_faces(mask[mesh.faces].any(axis=1))
                mesh.remove_unreferenced_vertices()

        # --- 2. РАЗДЕЛЕНИЕ НА КУСКИ ---
        parts = mesh.split(only_watertight=False)
        if len(parts) <= 1:
            # Если разделение не произошло, работаем с тем что есть
            valid_parts = [mesh]
        else:
            # --- 3. УМНЫЙ ВЫБОР ПОВЕРХНОСТИ (Плечи + Голова) ---
            valid_parts = []
            for i, p in enumerate(parts):
                # Проверка высоты части
                part_z_max = p.bounds[1][2]
                relative_top = (part_z_max - z_min_global) / (mesh.extents[2] + 1e-6)
                
                # Направленность
                to_part = p.centroid - center_mass
                avg_normal = np.mean(p.face_normals, axis=0)
                is_outer = np.dot(to_part, avg_normal) > -0.2 # Смягченный порог для плеч
                
                area = p.area
                # ЗАЩИТА: Оставляем если смотрит наружу ИЛИ если это массивный кусок сверху/посредине
                if is_outer or (area > (mesh.area * 0.05) and relative_top > 0.3):
                    valid_parts.append(p)
            
            if not valid_parts:
                mesh = max(parts, key=lambda m: m.area)
            else:
                mesh = trimesh.util.concatenate(valid_parts)

        # --- 4. УДАЛЕНИЕ ШВОВ (Динамический Рейкаст) ---
        mesh.merge_vertices()
        if len(mesh.faces) > 0:
            face_adjacency = mesh.face_adjacency
            # Угол между нормалями
            dot_products = np.sum(mesh.face_normals[face_adjacency[:, 0]] * mesh.face_normals[face_adjacency[:, 1]], axis=1)
            bad_adj_mask = dot_products < fold_threshold
            
            if np.any(bad_adj_mask):
                bad_edges = mesh.face_adjacency_edges[bad_adj_mask]
                n_v = len(mesh.vertices)
                adj_matrix = csr_matrix((np.ones(len(bad_edges)), (bad_edges[:, 0], bad_edges[:, 1])), shape=(n_v, n_v))
                n_comp, labels = connected_components(adj_matrix, directed=False)
                
                faces_to_del = []
                for i in range(n_comp):
                    nodes = np.where(labels == i)[0]
                    if len(nodes) < 3: continue
                    
                    comp_extent = np.max(np.ptp(mesh.vertices[nodes], axis=0))
                    if comp_extent > (total_extent * scale_threshold):
                        # Находим грани этого "шва"
                        cand_idx = np.where(np.isin(mesh.faces, nodes).any(axis=1))[0]
                        if len(cand_idx) == 0: continue

                        f_centers = mesh.triangles_center[cand_idx]
                        f_normals = mesh.face_normals[cand_idx]

                        # ДИНАМИЧЕСКИЙ ЦЕНТР: Проверка "от оси" на уровне самой грани
                        dyn_centers = np.tile(center_mass, (len(f_centers), 1))
                        dyn_centers[:, 2] = f_centers[:, 2] - (total_extent * 0.02) # Чуть ниже грани

                        out_vecs = f_centers - dyn_centers
                        out_vecs /= (np.linalg.norm(out_vecs, axis=1)[:, np.newaxis] + 1e-8)
                        
                        # Если нормаль смотрит строго внутрь (к оси объекта) - удаляем
                        vis_score = np.sum(f_normals * out_vecs, axis=1)
                        bad_faces = cand_idx[vis_score < -0.25] # Порог "внутренности"
                        
                        if len(bad_faces) > 0:
                            faces_to_del.extend(bad_faces)
                
                if faces_to_del:
                    f_mask = np.ones(len(mesh.faces), dtype=bool)
                    f_mask[list(set(faces_to_del))] = False
                    mesh.update_faces(f_mask)

        # --- 5. ФИНАЛИЗАЦИЯ ---
        if close_holes:
            try:
                mesh.fill_holes()
            except:
                pass # Защита от падения fill_holes на сверхсложной топологии
        
        mesh.merge_vertices()
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fix_normals(mesh)

        info_log.append(f"Final mesh: {len(mesh.faces)} faces. Outer logic applied.")
        return ("\n".join(info_log), mesh)

NODE_CLASS_MAPPINGS = {"AntonioilevCleanMesh": AntonioilevCleanMesh}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevCleanMesh": "✂ Clean Mesh (Dynamic Guard)"}