import numpy as np
import trimesh
import networkx as nx
from trimesh.triangles import normals as triangle_normals

class AntonioilevHoleFiller:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "min_hole_dim": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 50.0, "step": 0.01}),
                "max_hole_dim": ("FLOAT", {"default": 50.0, "min": 0.01, "max": 500.0, "step": 0.1}),
                "max_points": ("INT", {"default": 300, "min": 3, "max": 2000}),
                "iterations": ("INT", {"default": 5, "min": 1, "max": 15}),
                "relax_steps": ("INT", {"default": 0, "min": 0, "max": 30}),
            }
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "fill"
    CATEGORY = "Antonioilev/Mesh/Fix"

    # ---------- вспомогательные методы ----------
    def _project_to_plane(self, points):
        """Проецирует 3D-точки на лучшую плоскость, возвращает 2D + нормаль плоскости"""
        centroid = points.mean(axis=0)
        centered = points - centroid
        # SVD для нормали
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        normal = vh[2]
        # Базис плоскости
        u = vh[0]
        v = vh[1]
        # 2D координаты
        pts_2d = np.column_stack([centered @ u, centered @ v])
        return pts_2d, normal, centroid, u, v

    def _earclip_2d(self, pts_2d):
        """Простой ear-clipping для 2D полигона (без дыр). Возвращает список треугольников (индексы)."""
        n = len(pts_2d)
        if n < 3:
            return []
        if n == 3:
            return [[0, 1, 2]]

        indices = list(range(n))
        triangles = []

        def area(i, j, k):
            a, b, c = pts_2d[i], pts_2d[j], pts_2d[k]
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def is_ear(i, j, k, remaining):
            # выпуклость
            if area(i, j, k) <= 1e-12:
                return False
            # нет точек внутри треугольника
            for m in remaining:
                if m in (i, j, k):
                    continue
                # barycentric
                a = area(i, j, m)
                b = area(j, k, m)
                c = area(k, i, m)
                if a >= -1e-10 and b >= -1e-10 and c >= -1e-10:
                    return False
            return True

        remaining = indices[:]
        guard = 0
        while len(remaining) > 3 and guard < n * 3:
            guard += 1
            ear_found = False
            m = len(remaining)
            for idx in range(m):
                i = remaining[(idx - 1) % m]
                j = remaining[idx]
                k = remaining[(idx + 1) % m]
                if is_ear(i, j, k, remaining):
                    triangles.append([i, j, k])
                    remaining.pop(idx)
                    ear_found = True
                    break
            if not ear_found:
                # fallback — просто fan
                for i in range(1, len(remaining) - 1):
                    triangles.append([remaining[0], remaining[i], remaining[i + 1]])
                break

        if len(remaining) == 3:
            triangles.append(remaining)

        return triangles

    def _triangulate_cycle(self, mesh, cycle):
        """Триангулирует один граничный цикл"""
        cycle = np.asarray(cycle, dtype=np.int64)
        if len(cycle) < 3:
            return []

        pts = mesh.vertices[cycle]
        pts_2d, normal, _, _, _ = self._project_to_plane(pts)

        # 2D триангуляция
        tris_local = self._earclip_2d(pts_2d)
        if not tris_local:
            return []

        # Переводим локальные индексы обратно в глобальные
        faces = []
        for t in tris_local:
            faces.append([cycle[t[0]], cycle[t[1]], cycle[t[2]]])

        faces = np.asarray(faces, dtype=np.int64)

        # Правильная ориентация (нормаль новой грани должна быть близка к нормали плоскости)
        # Берём первую грань и проверяем
        if len(faces) > 0:
            tri_pts = mesh.vertices[faces[0]]
            face_n = np.cross(tri_pts[1] - tri_pts[0], tri_pts[2] - tri_pts[0])
            if np.dot(face_n, normal) < 0:
                faces = faces[:, ::-1]  # разворачиваем все

        return faces

    # ---------- основной метод ----------
    def fill(self, mesh, min_hole_dim, max_hole_dim, max_points, iterations, relax_steps):
        if mesh is None:
            return (None, "No input")

        work = mesh.copy()

        # Сброс визуала
        try:
            work.visual = trimesh.visual.ColorVisuals()
        except:
            pass

        work.remove_infinite_values()
        work.merge_vertices(merge_tex=True, merge_norm=True)

        if len(work.faces) > 0:
            work.update_faces(work.unique_faces() & work.nondegenerate_faces())

        faces_before = len(work.faces)
        total_added = 0

        for it in range(iterations):
            # 1. Сначала пробуем встроенный (хорошо закрывает 1-3 треугольника)
            before = len(work.faces)
            try:
                trimesh.repair.fill_holes(work, use_fan=True)
            except:
                pass
            total_added += max(0, len(work.faces) - before)

            # 2. Ручной проход по всем boundary-циклам с нормальной триангуляцией
            if not hasattr(work, "edges_boundary") or len(work.edges_boundary) < 3:
                break

            boundary = work.edges_boundary
            G = nx.from_edgelist(boundary)
            cycles = nx.cycle_basis(G)

            new_faces_all = []
            for cycle in cycles:
                n = len(cycle)
                if n < 3 or n > max_points:
                    continue

                pts = work.vertices[cycle]
                size = float(np.max(pts.max(axis=0) - pts.min(axis=0)))
                if size < min_hole_dim or size > max_hole_dim:
                    continue

                faces = self._triangulate_cycle(work, cycle)
                if len(faces) > 0:
                    new_faces_all.append(faces)
                    total_added += len(faces)

            if new_faces_all:
                all_new = np.vstack(new_faces_all)
                work.faces = np.vstack([work.faces, all_new])
                work._cache.clear()
            else:
                # больше нечего добавлять
                if len(work.faces) == before:
                    break

        # Финальная очистка
        work.merge_vertices(merge_tex=True, merge_norm=True)
        if len(work.faces) > 0:
            work.update_faces(work.unique_faces() & work.nondegenerate_faces())

        if relax_steps > 0:
            try:
                trimesh.smoothing.filter_laplacian(work, iterations=relax_steps)
            except:
                pass

        work.fix_normals()

        info = (f"Added ~{total_added} faces | "
                f"{faces_before} → {len(work.faces)} | "
                f"watertight={work.is_watertight}")

        print(f">>> [Antonioilev HoleFiller] {info}")
        return (work, info)


NODE_CLASS_MAPPINGS = {"AntonioilevHoleFiller": AntonioilevHoleFiller}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevHoleFiller": "🧵 Hole Filler"}