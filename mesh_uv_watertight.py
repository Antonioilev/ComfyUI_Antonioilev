import os
import uuid
import json
import tempfile
import numpy as np
import trimesh

# ---------------- SAFE IMPORT ----------------
try:
    from .mesh_helpers import is_point_cloud
except Exception:
    def is_point_cloud(mesh):
        try:
            return mesh is None or not hasattr(mesh, "faces") or len(mesh.faces) == 0
        except:
            return True


try:
    import folder_paths
    COMFYUI_OUTPUT_FOLDER = folder_paths.get_output_directory()
except Exception:
    COMFYUI_OUTPUT_FOLDER = None


class mesh_uv_watertight:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
            },
            "optional": {
                "show_checker": ("BOOLEAN", {"default": False}),
                "show_wireframe": ("BOOLEAN", {"default": True}),
                "show_seams": ("BOOLEAN", {"default": True}),
                "show_chart_ids": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("TRIMESH",)
    RETURN_NAMES = ("mesh",)

    FUNCTION = "preview"
    OUTPUT_NODE = True
    CATEGORY = "Antonioilev/UV"

    def _compute_watertight(self, mesh):
        try:
            # более надежная проверка чем mesh.is_watertight
            return bool(mesh.is_watertight and mesh.euler_number == 2)
        except:
            try:
                return bool(mesh.is_watertight)
            except:
                return False

    def _estimate_uv_islands(self, uv):
        """
        Примитивная оценка islands:
        кластеризация по разрыву UV координат
        """
        if uv is None or len(uv) < 3:
            return 0

        uv = np.asarray(uv)

        # сортируем по proximity (очень грубо)
        diffs = np.linalg.norm(np.diff(uv, axis=0), axis=1)

        threshold = np.mean(diffs) + np.std(diffs)

        islands = np.sum(diffs > threshold) + 1

        return int(max(1, islands))

    def preview(
        self,
        mesh,
        show_checker=False,
        show_wireframe=True,
        show_seams=True,
        show_chart_ids=False,
    ):

        print("\n" + "=" * 60)
        print("[mesh_uv_watertight] Preparing preview")

        # ---------------- SAFETY ----------------
        if mesh is None or is_point_cloud(mesh):
            return (mesh,)

        if not hasattr(mesh, "vertices") or len(mesh.vertices) == 0:
            return (mesh,)

        V = mesh.vertices
        F = mesh.faces

        # 🔥 REAL watertight computation
        is_watertight = self._compute_watertight(mesh)

        print(f"[Mesh] V={len(V)} F={len(F)} watertight={is_watertight}")

        # ---------------- UV EXTRACTION ----------------
        has_uvs = False
        uv_v = None
        uv_min = None
        uv_max = None
        in_unit_square = False
        uv_islands = 0

        try:
            if hasattr(mesh.visual, "uv") and mesh.visual.uv is not None:
                uv_v = np.asarray(mesh.visual.uv, dtype=np.float32)

                if len(uv_v) > 0:
                    has_uvs = True
                    uv_v = np.nan_to_num(uv_v)

                    uv_min = uv_v.min(axis=0)
                    uv_max = uv_v.max(axis=0)

                    in_unit_square = bool(
                        np.all(uv_min >= -1e-6) and np.all(uv_max <= 1.0 + 1e-6)
                    )

                    # 🔥 island estimation
                    uv_islands = self._estimate_uv_islands(uv_v)

        except Exception as e:
            print(f"[UV ERROR] {e}")
            has_uvs = False

        # ---------------- METRICS ----------------
        try:
            bounds = mesh.bounds
            extents = mesh.extents
        except Exception:
            bounds = np.zeros((2, 3))
            extents = np.zeros(3)

        # ---------------- UI ----------------
        ui_data = {
            "vertex_count": [int(len(V))],
            "face_count": [int(len(F))],

            "is_watertight": [is_watertight],
            "has_uvs": [has_uvs],

            "uv_islands": [uv_islands],

            "show_checker": [show_checker],
            "show_wireframe": [show_wireframe],
            "show_seams": [show_seams],
            "show_chart_ids": [show_chart_ids],

            "bounds_min": [bounds[0].tolist()],
            "bounds_max": [bounds[1].tolist()],
            "extents": [extents.tolist()],
            "max_extent": [float(np.max(extents))],
        }

        if has_uvs:
            ui_data["uv_payload"] = [{
                "uvs": uv_v.tolist(),
                "bounds": {
                    "min": uv_min.tolist(),
                    "max": uv_max.tolist()
                },
                "in_unit_square": in_unit_square,
                "islands_proxy": uv_islands
            }]

        print("[mesh_uv_watertight] Done")
        print("=" * 60 + "\n")

        return (mesh,)


NODE_CLASS_MAPPINGS = {
    "mesh_uv_watertight": mesh_uv_watertight,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "mesh_uv_watertight": "🧭 Mesh UV Watertight",
}