import numpy as np
import trimesh
import time

class MeshFix:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "input_mesh": ("TRIMESH",),
            },
            "optional": {
                "remove_internal_geometry": ("BOOLEAN", {"default": True}),
                "keep_largest_only": ("BOOLEAN", {"default": True}),
                "min_component_faces": ("INT", {"default": 500, "min": 0, "max": 1000000}),
                "min_component_area_ratio": ("FLOAT", {"default": 0.02, "min": 0.0, "max": 1.0, "step": 0.01}),
                "ray_samples_per_component": ("INT", {"default": 32, "min": 4, "max": 256}),
                "normal_offset": ("FLOAT", {"default": 0.002, "min": 0.0001, "max": 0.05, "step": 0.0001}),
                "ray_distance_limit": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 10.0, "step": 0.01}),
                "fill_holes": ("BOOLEAN", {"default": True}),
                "max_hole_edges": ("INT", {"default": 200, "min": 0, "max": 10000}),
                "clean_mesh": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "repair"
    CATEGORY = "Antonioilev/Mesh/Fix"

    def _is_outer_component(self, comp, normal_offset, ray_limit, n_samples):
        """
        Быстрая проверка: внешняя ли оболочка.
        Берём несколько случайных граней и стреляем наружу.
        Если большинство лучей улетает далеко / в никуда → outer.
        """
        if len(comp.faces) < 4:
            return False

        try:
            comp.fix_normals()
        except Exception:
            pass

        # Сэмплируем грани
        n = min(n_samples, len(comp.faces))
        idx = np.random.choice(len(comp.faces), size=n, replace=False)

        origins = comp.triangles_center[idx]
        normals = comp.face_normals[idx]

        # валидные нормали
        mask = np.isfinite(normals).all(axis=1) & (np.linalg.norm(normals, axis=1) > 1e-8)
        if not np.any(mask):
            return True  # не смогли проверить — оставляем

        origins = origins[mask] + normals[mask] * normal_offset
        directions = normals[mask]

        try:
            intersector = trimesh.ray.ray_triangle.RayMeshIntersector(comp)
            locations, index_ray, _ = intersector.intersects_location(
                ray_origins=origins,
                ray_directions=directions,
                multiple_hits=False
            )
        except Exception:
            return True

        # Сколько лучей "ушли в бесконечность" или попали далеко
        hit_dist = np.full(len(origins), np.inf)
        if len(locations) > 0:
            d = np.linalg.norm(locations - origins[index_ray], axis=1)
            for i, r in enumerate(index_ray):
                if d[i] < hit_dist[r]:
                    hit_dist[r] = d[i]

        free_ratio = np.mean(hit_dist > ray_limit)
        # Если больше половины лучей свободны — считаем внешней
        return free_ratio > 0.45

    def repair(self, input_mesh,
               remove_internal_geometry=True,
               keep_largest_only=True,
               min_component_faces=500,
               min_component_area_ratio=0.02,
               ray_samples_per_component=32,
               normal_offset=0.002,
               ray_distance_limit=0.15,
               fill_holes=True,
               max_hole_edges=200,
               clean_mesh=True):

        if input_mesh is None:
            return (None, "No input mesh")

        t0 = time.time()
        mesh = input_mesh.copy()
        ops = []

        # ---------- 0. Быстрая базовая чистка ----------
        mesh.remove_infinite_values()
        try:
            mesh.update_faces(mesh.unique_faces() & mesh.nondegenerate_faces())
        except Exception:
            pass
        mesh.merge_vertices()
        mesh.remove_unreferenced_vertices()

        # ---------- 1. Удаление внутренней геометрии (быстро) ----------
        if remove_internal_geometry and len(mesh.faces) > 0:
            components = mesh.split(only_watertight=False)
            ops.append(f"components={len(components)}")

            if len(components) == 1:
                # Один кусок — пробуем ray-фильтр только если очень нужно
                # (часто после DC внутренняя уже отдельный component)
                pass
            else:
                total_area = sum(c.area for c in components) + 1e-12
                kept = []

                # Сортируем по площади (сначала большие)
                components = sorted(components, key=lambda c: c.area, reverse=True)

                for i, comp in enumerate(components):
                    if len(comp.faces) < min_component_faces:
                        continue
                    if (comp.area / total_area) < min_component_area_ratio and i > 0:
                        continue

                    # Самый большой почти всегда outer
                    if i == 0 and keep_largest_only:
                        kept.append(comp)
                        continue

                    if self._is_outer_component(comp, normal_offset, ray_distance_limit, ray_samples_per_component):
                        kept.append(comp)

                if len(kept) == 0:
                    # fallback — берём самый большой
                    kept = [components[0]]

                mesh = trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]
                ops.append(f"kept {len(kept)} outer shells")

        # ---------- 2. Финальная герметизация (pymeshfix) ----------
        if (fill_holes or clean_mesh) and len(mesh.faces) > 4:
            try:
                import pymeshfix
                tin = pymeshfix.PyTMesh()
                tin.load_array(
                    np.asarray(mesh.vertices, dtype=np.float64),
                    np.asarray(mesh.faces, dtype=np.int32)
                )
                if clean_mesh:
                    tin.clean(max_iters=8, inner_loops=2)
                if fill_holes:
                    tin.fill_small_boundaries(nbe=max_hole_edges, refine=True)
                    ops.append("sealed")

                v, f = tin.return_arrays()
                mesh = trimesh.Trimesh(vertices=v, faces=f, process=False)
            except Exception as e:
                ops.append(f"pymeshfix skip: {e}")

        # ---------- 3. Финал ----------
        mesh.merge_vertices()
        try:
            mesh.update_faces(mesh.unique_faces() & mesh.nondegenerate_faces())
        except Exception:
            pass
        mesh.remove_unreferenced_vertices()
        mesh.fix_normals()

        elapsed = time.time() - t0
        info = (f"MeshFix Fast | faces={len(mesh.faces):,} | "
                f"watertight={mesh.is_watertight} | {elapsed:.2f}s | {', '.join(ops)}")
        print(f">>> [Antonioilev] {info}")
        return (mesh, info)


NODE_CLASS_MAPPINGS = {"AntonioilevMeshFix": MeshFix}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevMeshFix": "🩺 Mesh Fixer Fast"}