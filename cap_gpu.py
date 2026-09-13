import numpy as np
import trimesh
import networkx as nx
import time

class AntonioilevCapGPU:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "mode": (["simple_triangulate", "advanced_cap"], {"default": "simple_triangulate"}),
                "offset_down": ("FLOAT", {"default": 0.15, "min": -2.0, "max": 2.0, "step": 0.01}),
                "bottom_segments": ("INT", {"default": 24, "min": 3, "max": 128, "step": 1}),
                "relaxation_rings": ("INT", {"default": 4, "min": 0, "max": 20, "step": 1}),
                "squeeze_power": ("FLOAT", {"default": 1.2, "min": 0.1, "max": 10.0, "step": 0.1}),
                "bottom_radius_xy": ("FLOAT", {"default": 0.6, "min": 0.01, "max": 3.0, "step": 0.05}),
                "cap_scale_x": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 5.0, "step": 0.05}),
                "cap_scale_z": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 5.0, "step": 0.05}),
                "cap_rotate": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 360.0, "step": 1.0}),
                "cap_flip_direction": ("BOOLEAN", {"default": False}),
                "cap_shift_x": ("FLOAT", {"default": 0.0, "min": -2.0, "max": 2.0, "step": 0.01}),
                "cap_shift_z": ("FLOAT", {"default": 0.0, "min": -2.0, "max": 2.0, "step": 0.01}),
                "invert_cap": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING", "TRIMESH")
    RETURN_NAMES = ("info", "mesh")
    FUNCTION = "process"
    CATEGORY = "Antonioilev/Mesh"

    # ---------- вспомогательные ----------
    def _get_boundary_loops(self, mesh):
        """Надёжно возвращает список циклов (списки индексов вершин)"""
        if mesh is None or len(mesh.faces) == 0:
            return []

        try:
            _ = mesh.edges
        except Exception:
            pass

        # Способ 1: готовый edges_boundary
        try:
            if hasattr(mesh, "edges_boundary") and mesh.edges_boundary is not None and len(mesh.edges_boundary) >= 3:
                G = nx.Graph()
                G.add_edges_from(mesh.edges_boundary)
                cycles = nx.cycle_basis(G)
                return [c for c in cycles if len(c) >= 3]
        except Exception:
            pass

        # Способ 2: ручной подсчёт
        try:
            edges = mesh.edges_sorted
            unique_edges, counts = np.unique(edges, axis=0, return_counts=True)
            boundary = unique_edges[counts == 1]
            if len(boundary) < 3:
                return []
            G = nx.Graph()
            G.add_edges_from(boundary)
            cycles = nx.cycle_basis(G)
            return [c for c in cycles if len(c) >= 3]
        except Exception as e:
            print(f"[CapGPU] Failed to find boundary loops: {e}")
            return []

    def _project_to_plane(self, points):
        centroid = points.mean(axis=0)
        centered = points - centroid
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        normal = vh[2]
        # нормализуем
        normal = normal / (np.linalg.norm(normal) + 1e-12)
        u, v = vh[0], vh[1]
        pts_2d = np.column_stack([centered @ u, centered @ v])
        return pts_2d, normal, centroid

    def _earclip_2d(self, pts_2d):
        n = len(pts_2d)
        if n < 3:
            return []
        if n == 3:
            return [[0, 1, 2]]

        indices = list(range(n))
        triangles = []

        def signed_area(i, j, k):
            a, b, c = pts_2d[i], pts_2d[j], pts_2d[k]
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def point_in_tri(i, j, k, m):
            a = signed_area(i, j, m)
            b = signed_area(j, k, m)
            c = signed_area(k, i, m)
            return (a >= -1e-10 and b >= -1e-10 and c >= -1e-10) or \
                   (a <=  1e-10 and b <=  1e-10 and c <=  1e-10)

        remaining = indices[:]
        guard = 0
        while len(remaining) > 3 and guard < n * 4:
            guard += 1
            ear_found = False
            m = len(remaining)
            for idx in range(m):
                i = remaining[(idx - 1) % m]
                j = remaining[idx]
                k = remaining[(idx + 1) % m]
                if signed_area(i, j, k) <= 1e-12:
                    continue
                is_ear = True
                for p in remaining:
                    if p in (i, j, k):
                        continue
                    if point_in_tri(i, j, k, p):
                        is_ear = False
                        break
                if is_ear:
                    triangles.append([i, j, k])
                    remaining.pop(idx)
                    ear_found = True
                    break
            if not ear_found:
                for i in range(1, len(remaining) - 1):
                    triangles.append([remaining[0], remaining[i], remaining[i + 1]])
                remaining = []
                break

        if len(remaining) == 3:
            triangles.append(remaining)
        return triangles

    def _cap_with_center(self, mesh, loop, offset_down, invert_cap):
        """
        Создаёт центральный вертекс, сдвигает его по нормали плоскости
        и строит треугольники от края к центру.
        """
        loop = np.asarray(loop, dtype=np.int64)
        pts = mesh.vertices[loop]

        # Плоскость + нормаль + центроид
        _, normal, centroid = self._project_to_plane(pts)

        # Масштаб смещения: относительно среднего радиуса дыры
        avg_radius = np.linalg.norm(pts - centroid, axis=1).mean()
        # offset_down = 0.15 означает 15% от радиуса
        move = normal * (offset_down * avg_radius)

        if invert_cap:
            move = -move

        center_pos = centroid + move

        # Добавляем новую вершину
        new_vertices = np.vstack([mesh.vertices, center_pos.reshape(1, 3)])
        center_idx = len(mesh.vertices)

        # Треугольники: каждая пара соседних вершин loop → центр
        new_faces = []
        n = len(loop)
        for i in range(n):
            a = loop[i]
            b = loop[(i + 1) % n]
            # Ориентация: a → b → center
            new_faces.append([a, b, center_idx])

        new_faces = np.asarray(new_faces, dtype=np.int64)

        # Проверяем ориентацию относительно нормали
        if len(new_faces) > 0:
            tri = new_vertices[new_faces[0]]
            fn = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            if np.dot(fn, normal) < 0:
                new_faces = new_faces[:, ::-1]

        return new_vertices, new_faces

    # ---------- основной процесс ----------
    def process(self, mesh, mode, offset_down, bottom_segments, relaxation_rings,
                squeeze_power, bottom_radius_xy, cap_scale_x, cap_scale_z,
                cap_rotate, cap_flip_direction, cap_shift_x, cap_shift_z, invert_cap):

        if mesh is None:
            return ("No input", None)

        start = time.time()
        work = mesh.copy()
        work.merge_vertices(merge_tex=True, merge_norm=True)
        work.remove_infinite_values()

        try:
            work._cache.clear()
            _ = work.edges
            _ = work.faces
        except Exception:
            pass

        # 1. Самый большой loop
        loops = self._get_boundary_loops(work)
        if not loops:
            return ("No boundary loops found", work)

        best_loop = max(loops, key=len)
        num_orig = len(best_loop)
        boundary_pts = work.vertices[best_loop]
        center = boundary_pts.mean(axis=0)
        bounds_size = work.bounds[1] - work.bounds[0]
        avg_radius = np.linalg.norm(boundary_pts - center, axis=1).mean()

        info_parts = [f"Largest loop: {num_orig} verts"]

        # ============================================================
        # РЕЖИМ 1: Простая триангуляция + центральный вертекс
        # ============================================================
        if mode == "simple_triangulate" or relaxation_rings == 0:

            new_vertices, new_faces = self._cap_with_center(
                work, best_loop, offset_down, invert_cap
            )

            if len(new_faces) == 0:
                return ("Failed to create center cap", work)

            work = trimesh.Trimesh(
                vertices=new_vertices,
                faces=np.vstack([work.faces, new_faces]),
                process=False
            )
            info_parts.append(f"Center cap | offset={offset_down:.3f} | faces+={len(new_faces)}")

        # ============================================================
        # РЕЖИМ 2: Advanced Cap (кольца + дно)
        # ============================================================
        else:
            mod_center = center.copy()
            mod_center[0] += cap_shift_x * bounds_size[0]
            mod_center[2] += cap_shift_z * bounds_size[2]

            target_y_offset = bounds_size[1] * abs(offset_down)
            rot_rad = np.radians(cap_rotate)
            dir_m = -1.0 if cap_flip_direction else 1.0

            rings = [boundary_pts]
            ring_counts = [num_orig]

            for r in range(1, relaxation_rings + 1):
                t = r / (relaxation_rings + 1)
                t_shape = t ** squeeze_power
                ring_count = int(np.interp(r, [0, relaxation_rings + 1], [num_orig, bottom_segments]))
                ring_count = max(3, ring_count)

                ring_verts = np.zeros((ring_count, 3))
                for j in range(ring_count):
                    angle = (2 * np.pi * j / ring_count) * dir_m + rot_rad
                    orig_idx = int(round(j * num_orig / ring_count)) % num_orig
                    orig_pt = boundary_pts[orig_idx]

                    target_rx = avg_radius * bottom_radius_xy * cap_scale_x
                    target_rz = avg_radius * bottom_radius_xy * cap_scale_z
                    target = mod_center + np.array([
                        np.cos(angle) * target_rx,
                        0,
                        np.sin(angle) * target_rz
                    ])

                    pos = orig_pt * (1.0 - t_shape) + target * t_shape
                    pos[1] = orig_pt[1] - target_y_offset * t
                    ring_verts[j] = pos

                rings.append(ring_verts)
                ring_counts.append(ring_count)

            # Финальное дно
            bottom_y = mod_center[1] - target_y_offset
            bottom = np.zeros((bottom_segments, 3))
            for j in range(bottom_segments):
                angle = (2 * np.pi * j / bottom_segments) * dir_m + rot_rad
                bottom[j] = mod_center + np.array([
                    np.cos(angle) * avg_radius * bottom_radius_xy * cap_scale_x,
                    0,
                    np.sin(angle) * avg_radius * bottom_radius_xy * cap_scale_z
                ])
                bottom[j, 1] = bottom_y
            rings.append(bottom)
            ring_counts.append(bottom_segments)

            tip = mod_center.copy()
            tip[1] = bottom_y

            all_verts = [work.vertices]
            offsets = []
            curr = len(work.vertices)
            for r in range(1, len(rings)):
                offsets.append(curr)
                all_verts.append(rings[r])
                curr += ring_counts[r]
            all_verts.append(tip.reshape(1, 3))
            tip_idx = curr

            new_vertices = np.vstack(all_verts)

            def bridge(cnt_a, idx_a, cnt_b, idx_b, is_first=False):
                faces = []
                steps = max(cnt_a, cnt_b)
                for i in range(steps):
                    ia  = (i * cnt_a) // steps
                    ian = ((i + 1) * cnt_a) // steps
                    ib  = (i * cnt_b) // steps
                    ibn = ((i + 1) * cnt_b) // steps

                    va  = best_loop[ia % cnt_a] if is_first else (idx_a + ia % cnt_a)
                    van = best_loop[ian % cnt_a] if is_first else (idx_a + ian % cnt_a)
                    vb  = idx_b + ib % cnt_b
                    vbn = idx_b + ibn % cnt_b

                    if va != van:
                        faces.append([va, van, vb])
                    if vb != vbn:
                        faces.append([van, vbn, vb])
                return faces

            new_faces = []
            new_faces.extend(bridge(num_orig, None, ring_counts[1], offsets[0], is_first=True))
            for r in range(len(offsets) - 1):
                new_faces.extend(bridge(ring_counts[r+1], offsets[r],
                                        ring_counts[r+2], offsets[r+1]))

            last = offsets[-1]
            for j in range(bottom_segments):
                new_faces.append([last + j, last + (j + 1) % bottom_segments, tip_idx])

            new_faces = np.asarray(new_faces, dtype=np.int64)

            work = trimesh.Trimesh(
                vertices=new_vertices,
                faces=np.vstack([work.faces, new_faces]),
                process=False
            )
            info_parts.append(f"Advanced cap | rings={relaxation_rings} | segs={bottom_segments}")

        # ============================================================
        # Финальная доводка
        # ============================================================
        work.merge_vertices(merge_tex=True, merge_norm=True)
        if len(work.faces) > 0:
            work.update_faces(work.unique_faces() & work.nondegenerate_faces())

        work.fix_normals()

        if invert_cap and mode != "simple_triangulate":
            # в simple режиме invert уже учтён при создании центра
            work.invert()

        elapsed = time.time() - start
        wt = work.is_watertight
        info = f"CapGPU | {' | '.join(info_parts)} | watertight={wt} | {elapsed:.2f}s"
        print(f">>> [Antonioilev] {info}")

        return (info, work)


NODE_CLASS_MAPPINGS = {"AntonioilevCapGPU": AntonioilevCapGPU}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevCapGPU": "🧩 CapGPU (Advanced Sealer)"}