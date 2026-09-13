import trimesh
import numpy as np
import networkx as nx
from sklearn.cluster import KMeans

class AntonioilevSafeUVTest:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trimesh_obj": ("TRIMESH",),
                "island_count": ("INT", {"default": 50, "min": 2, "max": 300}),
                "min_island_size": ("INT", {"default": 10, "min": 1, "max": 1000}),
            }
        }

    RETURN_TYPES = ("TRIMESH",)
    FUNCTION = "apply_hybrid_uv"
    CATEGORY = "Antonioilev/research"

    def apply_hybrid_uv(self, trimesh_obj, island_count, min_island_size):
        if trimesh_obj is None: return (None,)
        
        try:
            mesh = trimesh_obj.copy()
            
            # 1. ПОДГОТОВКА ПРИЗНАКОВ
            # Добавляем вес нормалям, чтобы разрезы шли по изгибам
            features = np.hstack([mesh.triangles_center, mesh.face_normals * 0.2])
            
            # 2. ПЕРВИЧНОЕ РАЗБИЕНИЕ
            # Используем чуть меньше кластеров, так как связность потом их "размножит"
            n_clusters = max(2, island_count // 2 if island_count > 10 else island_count)
            km = KMeans(n_clusters=n_clusters, n_init=5, random_state=42)
            labels = km.fit_predict(features)

            # 3. ФИЗИЧЕСКАЯ СВЯЗНОСТЬ (Graph Theory)
            g = nx.Graph()
            g.add_edges_from(mesh.face_adjacency)
            
            refined_labels = np.full(len(mesh.faces), -1, dtype=int)
            island_idx = 0
            
            # Группируем по результатам KMeans, но разделяем несвязные куски
            for l in np.unique(labels):
                f_idx = np.where(labels == l)[0]
                sub = g.subgraph(f_idx)
                for comp in nx.connected_components(sub):
                    refined_labels[list(comp)] = island_idx
                    island_idx += 1

            # 4. СЛИЯНИЕ ДО ЦЕЛЕВОГО КОЛИЧЕСТВА (Island Reduction)
            # Если островов слишком много, сливаем самые маленькие с соседями
            while len(np.unique(refined_labels)) > island_count:
                u_lbls, counts = np.unique(refined_labels, return_counts=True)
                target_id = u_lbls[np.argmin(counts)] # Берем самый мелкий остров
                
                f_idx = np.where(refined_labels == target_id)[0]
                # Находим соседей через ребра
                adj_faces = mesh.face_adjacency[np.isin(mesh.face_adjacency, f_idx).any(axis=1)].flatten()
                neighbors = adj_faces[refined_labels[adj_faces] != target_id]
                
                if len(neighbors) > 0:
                    new_label = refined_labels[neighbors[0]]
                    refined_labels[f_idx] = new_label
                else:
                    # Если соседей нет (изолированный кусок), просто оставляем
                    break

            # 5. ГЕНЕРАЦИЯ UV И ПРОВЕРКА ЦЕЛОСТНОСТИ
            final_labels = np.unique(refined_labels)
            final_meshes = []
            
            # Texel Density Calculation
            total_3d_area = mesh.area
            # Считаем масштаб: хотим заполнить около 80% UV пространства
            uv_scale_factor = np.sqrt(0.8 / (total_3d_area + 1e-9))

            # Сортируем острова по размеру для упаковки
            island_list = []
            for lbl in final_labels:
                f_idx = np.where(refined_labels == lbl)[0]
                if len(f_idx) == 0: continue
                
                part = mesh.submesh([f_idx], append=False)
                if isinstance(part, (list, np.ndarray)): part = part[0]
                
                # Сохраняем меш и его параметры
                island_list.append(part)

            # Упаковка (простая сетка, но с сохранением пропорций)
            grid_n = int(np.ceil(np.sqrt(len(island_list))))
            slot_size = 1.0 / grid_n
            
            for i, part in enumerate(island_list):
                v = part.vertices
                v_min, v_max = v.min(axis=0), v.max(axis=0)
                ranges = v_max - v_min
                axes = np.argsort(ranges)[-2:] # Две главные оси
                
                # Проекция с сохранением пропорций (Texel Density)
                uv_raw = (v[:, axes] - v_min[axes])
                # Нормализуем по TD относительно всего меша
                uv_scaled = uv_raw * uv_scale_factor
                
                # Ограничиваем масштаб, чтобы остров не вылез за границы своего слота
                current_w = np.ptp(uv_scaled[:, 0])
                current_h = np.ptp(uv_scaled[:, 1])
                limit = slot_size * 0.9
                
                scale_fix = min(limit / (current_w + 1e-9), limit / (current_h + 1e-9), 1.0)
                uv_scaled *= scale_fix
                
                # Смещение в сетку
                col, row = i % grid_n, i // grid_n
                uv_final = uv_scaled + [col * slot_size + 0.01, row * slot_size + 0.01]
                
                part.visual = trimesh.visual.texture.TextureVisuals(uv=uv_final)
                final_meshes.append(part)

            # 6. ФИНАЛЬНЫЙ КОНКАТЕНАТ (Безопасный)
            result = trimesh.util.concatenate(final_meshes)
            
            # Проверка: не потеряли ли мы лица?
            if len(result.faces) < len(mesh.faces):
                print(f"!!! [WARNING] Lost {len(mesh.faces) - len(result.faces)} faces!")

            return (result,)

        except Exception as e:
            print(f"!!! Error: {e}")
            return (trimesh_obj,)

NODE_CLASS_MAPPINGS = {"AntonioilevSafeUVTest": AntonioilevSafeUVTest}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevSafeUVTest": "?? Topology-Safe UV (Fixed Integrity)"}