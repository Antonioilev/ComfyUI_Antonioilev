# SPDX-License-Identifier: GPL-3.0-or-later
# Part of the Antonioilev Nodes Pack
# V3.5: KDTree Taubin with Topological Neighborhood Averaging (Smooth & No Chatter)

import numpy as np
import trimesh as trimesh_module
import scipy.sparse

class RefineMeshNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trimesh": ("TRIMESH",),
                "smooth_iterations": ("INT", {"default": 100, "min": 0, "max": 1000, "step": 1}),
                "smooth_factor": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.0, "step": 0.05}),
                "analysis_radius": ("INT", {"default": 5, "min": 0, "max": 100, "step": 1}),
                "logic_mode": ([
                    "semantic_hc_smooth", 
                    "edge_tension_laplace",
                    "standard_taubin"
                ], {"default": "standard_taubin"}),
                "crease_angle": ("FLOAT", {"default": 35.0, "min": 0.0, "max": 180.0, "step": 1.0}),
                "feature_protection": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "ridge_multiplier": ("FLOAT", {"default": 1.5, "min": 1.0, "max": 5.0, "step": 0.1}), 
                "thickness_threshold": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("refined_mesh", "info")
    FUNCTION = "execute"
    CATEGORY = "Antonioilev/Mesh"

    def execute(self, trimesh, smooth_iterations, smooth_factor, analysis_radius, logic_mode, crease_angle, feature_protection, ridge_multiplier, thickness_threshold):
        mesh = trimesh.copy()
        mesh.merge_vertices()
        
        # Фикс для совместимости версий trimesh
        if hasattr(mesh, 'remove_duplicate_faces'):
            mesh.remove_duplicate_faces()
        else:
            mesh.update_faces(mesh.nondegenerate_faces())
            mesh.remove_infinite_values()
        
        original_vertices = mesh.vertices.copy()
        num_verts = len(mesh.vertices)
        if smooth_iterations <= 0:
            return (mesh, "No iterations")

        # 1. БАЗОВЫЙ АНАЛИЗ (Кризы и Кривизна)
        v_mask = np.zeros(num_verts, dtype=np.float32)
        curvatures = np.zeros(num_verts)
        
        try:
            curvatures = trimesh_module.curvature.discrete_mean_curvature_weighted(mesh)
            if len(curvatures) > 0:
                c_low, c_high = np.percentile(curvatures, 0.5), np.percentile(curvatures, 99.5)
                curvatures = np.clip(curvatures, c_low, c_high)
            
            abs_curv = np.abs(curvatures)
            perc_95 = np.percentile(abs_curv, 95) if len(abs_curv) > 0 else 1.0
            curv_mask = np.clip(abs_curv / (perc_95 + 1e-6), 0.0, 1.0)
        except:
            curv_mask = np.zeros(num_verts)

        # Логика Crease Angle (Красная зона)
        angle_rad = np.radians(crease_angle)
        adj_angles = mesh.face_adjacency_angles
        is_crease_pair = adj_angles > angle_rad
        
        if len(is_crease_pair) > 0:
            edge_idx = mesh.face_adjacency_edges[is_crease_pair]
            avg_edge_length = np.mean(mesh.edges_unique_length)
            v0, v1 = mesh.vertices[edge_idx[:, 0]], mesh.vertices[edge_idx[:, 1]]
            edge_lengths = np.linalg.norm(v1 - v0, axis=1)
            crease_edges = edge_idx[edge_lengths < avg_edge_length * 2.5]
            
            if len(crease_edges) > 0:
                start_v = np.unique(crease_edges)
                counts = np.bincount(crease_edges.flatten(), minlength=num_verts)
                v_mask[start_v] = np.clip((counts[start_v] / 2.0) * ridge_multiplier, 0.5, 1.0)
                v_mask = np.maximum(v_mask, curv_mask * feature_protection)

                if analysis_radius > 0:
                    current_frontier = set(np.where(v_mask > 0.1)[0])
                    visited = set(current_frontier)
                    neighbors = mesh.vertex_neighbors
                    for r in range(1, analysis_radius + 1):
                        next_frontier = set()
                        decay = np.power(1.0 - (r / (analysis_radius + 1)), 3)
                        for v in current_frontier:
                            for n in neighbors[v]:
                                if n not in visited:
                                    next_frontier.add(n)
                                    v_mask[n] = max(v_mask[n], v_mask[v] * decay)
                        if not next_frontier: break
                        visited.update(next_frontier)
                        current_frontier = next_frontier

        # 2. ЛОКАЛЬНЫЙ ПОИСК ПАЛЬЦЕВ (Thickness Threshold)
        finger_mask = np.zeros(num_verts, dtype=np.float32)
        seeds = []
        
        if thickness_threshold > 0.001:
            tip_threshold = np.percentile(curvatures, 99) if len(curvatures) > 0 else 1.0
            seeds = np.where(curvatures > tip_threshold)[0]
            
            if len(seeds) > 0:
                neighbors = mesh.vertex_neighbors
                q = list(seeds)
                visited_f = set(seeds)
                max_finger_steps = analysis_radius * 10 
                
                step = 0
                while q and step < max_finger_steps:
                    new_q = []
                    for v in q:
                        finger_mask[v] = 1.0
                        for n in neighbors[v]:
                            if n not in visited_f:
                                if curvatures[n] > (tip_threshold * (1.0 - thickness_threshold)):
                                    visited_f.add(n)
                                    new_q.append(n)
                    q = new_q
                    step += 1

        # Финальный синтез
        combined_protection = np.maximum(v_mask, finger_mask)

        # ---------------------------------------------------------
        # 3. СГЛАЖИВАНИЕ (Твой базовый V3.3 алгоритм)
        # ---------------------------------------------------------
        smooth_multiplier = (1.0 - np.clip(combined_protection * feature_protection, 0.0, 1.0))[:, np.newaxis]
        laplacian_matrix = trimesh_module.smoothing.laplacian_calculation(mesh)

        if logic_mode == "edge_tension_laplace":
            for _ in range(smooth_iterations):
                delta = laplacian_matrix.dot(mesh.vertices)
                mesh.vertices += delta * (smooth_factor * smooth_multiplier)
        elif logic_mode == "semantic_hc_smooth":
            alpha, beta = 0.1, 0.5
            for _ in range(smooth_iterations):
                temp_v = mesh.vertices.copy()
                delta = laplacian_matrix.dot(mesh.vertices)
                mesh.vertices += delta * smooth_multiplier
                b = mesh.vertices - (alpha * temp_v + (1.0 - alpha) * original_vertices)
                mesh.vertices -= (beta * b + (1.0 - beta) * delta) * smooth_multiplier
        else:
            # Встроенный Таубин
            lamb = smooth_factor * 0.5 
            nu = -(lamb + 0.04)
            
            smoothed_mesh = trimesh_module.smoothing.filter_taubin(
                mesh, 
                lamb=lamb, 
                nu=nu, 
                iterations=smooth_iterations
            )
            
            # Перепривязка по KDTree
            _, aligned_indices = smoothed_mesh.kdtree.query(original_vertices)
            aligned_smoothed_vertices = smoothed_mesh.vertices[aligned_indices]
            
            # Предварительный перенос
            final_weights = np.clip(combined_protection * feature_protection, 0.0, 1.0)[:, np.newaxis]
            mesh.vertices = (original_vertices * final_weights) + (aligned_smoothed_vertices * (1.0 - final_weights))

        # ---------------------------------------------------------
        # КРИТИЧЕСКИЙ ГЕОМЕТРИЧЕСКИЙ УСРЕДНИТЕЛЬ (Фикс прострелов мелкой дробью)
        # ---------------------------------------------------------
        # Если есть незащищенные (белые) зоны, убираем дребезг через топологический snap-back
        if logic_mode == "standard_taubin":
            current_vertices = mesh.vertices.copy()
            vertex_neighbors = mesh.vertex_neighbors
            
            # Строим маску незащищенных поверхностей (где должна быть идеальная гладкость)
            unprotected_mask = (1.0 - final_weights).flatten()
            
            if np.sum(unprotected_mask > 0.5) > 0:
                for i in range(num_verts):
                    # Применяем только к белым (незащищенным) участкам с дребезгом
                    if unprotected_mask[i] > 0.5:
                        nb = vertex_neighbors[i]
                        if len(nb) > 0:
                            # Центроида сглаженных соседей по оригинальной топологии
                            neighbor_center = np.mean(current_vertices[nb], axis=0)
                            
                            # Проверяем локальное отклонение вертекса от плоскости соседей
                            v_offset = current_vertices[i] - neighbor_center
                            offset_dist = np.linalg.norm(v_offset)
                            
                            # Если вертекс выстрелил из-за KDTree (смещение больше микро-порога), гасим его шум
                            if offset_dist > 0.001: 
                                # Мягко возвращаем его в плоскость окружения
                                mesh.vertices[i] = neighbor_center + (v_offset * 0.1)

        # ---------------------------------------------------------
        # 4. ВИЗУАЛЬНЫЙ ДЕБАГ
        # ---------------------------------------------------------
        v_colors = np.ones((num_verts, 4), dtype=np.uint8) * 255 
        c_int = np.clip(v_mask * feature_protection, 0.0, 1.0)
        f_int = np.clip(finger_mask, 0.0, 1.0)
        
        v_colors[:, 0] = (255 * (1.0 - f_int * 0.9)).astype(np.uint8)
        v_colors[:, 1] = (255 * (1.0 - c_int * 0.9)).astype(np.uint8)
        v_colors[:, 2] = (255 * (1.0 - np.maximum(c_int, f_int))).astype(np.uint8)
        
        mesh.visual.vertex_colors = v_colors
        return (mesh, f"V3.5 | Aligned & Averaged | Neighborhood Noise Filtered")

NODE_CLASS_MAPPINGS = {"AntonioilevRefineMesh": RefineMeshNode}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevRefineMesh": "💎 Refine Mesh Structural V3.5"}