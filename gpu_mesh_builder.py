import numpy as np
import trimesh as trimesh_module
import torch
from typing import Tuple, Optional


def _seal_watertight(mesh: trimesh_module.Trimesh, max_hole_edges: int = 500) -> Tuple[trimesh_module.Trimesh, str]:
    """Пытается довести меш до watertight=True"""
    notes = []
    if mesh is None or len(mesh.faces) == 0:
        return mesh, "empty"

    work = mesh.copy()
    work.remove_infinite_values()
    try:
        work.update_faces(work.unique_faces() & work.nondegenerate_faces())
    except Exception:
        pass
    work.merge_vertices()
    work.remove_unreferenced_vertices()

    # 1. Оставляем крупнейшие компоненты (обычно внешняя оболочка)
    try:
        comps = work.split(only_watertight=False)
        if len(comps) > 1:
            comps = sorted(comps, key=lambda c: c.area, reverse=True)
            # берём самую большую + все относительно крупные
            total = sum(c.area for c in comps) + 1e-12
            kept = [comps[0]]
            for c in comps[1:]:
                if c.area / total > 0.05 and len(c.faces) > 200:
                    # осторожно: вторые крупные часто = внутренняя оболочка
                    # для hermetic shell обычно нужна только largest
                    pass
            work = comps[0]
            notes.append(f"kept largest of {len(comps)} comps")
    except Exception as e:
        notes.append(f"split skip: {e}")

    # 2. trimesh fill_holes
    try:
        work.fill_holes()
        notes.append("fill_holes")
    except Exception:
        pass

    # 3. pymeshfix (сильнее)
    try:
        import pymeshfix
        tin = pymeshfix.PyTMesh()
        tin.load_array(
            np.asarray(work.vertices, dtype=np.float64),
            np.asarray(work.faces, dtype=np.int32)
        )
        tin.clean(max_iters=8, inner_loops=2)
        tin.fill_small_boundaries(nbe=int(max_hole_edges), refine=True)
        v, f = tin.return_arrays()
        work = trimesh_module.Trimesh(vertices=v, faces=f, process=False)
        notes.append("pymeshfix")
    except Exception as e:
        notes.append(f"pymeshfix skip: {e}")

    # 4. финал
    work.merge_vertices()
    try:
        work.update_faces(work.unique_faces() & work.nondegenerate_faces())
    except Exception:
        pass
    work.remove_unreferenced_vertices()
    try:
        work.fix_normals()
    except Exception:
        pass

    return work, ", ".join(notes)


def cumesh_strong_remesh(
    mesh: trimesh_module.Trimesh,
    grid_resolution: int = 512,
    band: float = 4.0,
    project_back: float = 0.15,
    max_input_faces: int = 2_000_000,
    repair_holes: bool = True,
    force_watertight: bool = True,
    max_hole_edges: int = 500,
) -> Tuple[Optional[trimesh_module.Trimesh], str]:
    import cumesh as CuMesh

    try:
        work = mesh.copy()

        # --- 1. CPU prep ---
        if repair_holes:
            try:
                work.fill_holes()
            except Exception:
                pass
            work.remove_infinite_values()
            try:
                work.update_faces(work.unique_faces() & work.nondegenerate_faces())
            except Exception:
                pass

        if max_input_faces > 0 and len(work.faces) > max_input_faces:
            print(f">>> [RemeshGPU] Pre-simplify {len(work.faces):,} → {max_input_faces:,}")
            try:
                work = work.simplify_quadric_decimation(face_count=int(max_input_faces))
            except Exception:
                try:
                    import open3d as o3d
                    o3d_mesh = o3d.geometry.TriangleMesh()
                    o3d_mesh.vertices = o3d.utility.Vector3dVector(work.vertices)
                    o3d_mesh.triangles = o3d.utility.Vector3iVector(work.faces)
                    o3d_mesh = o3d_mesh.simplify_quadric_decimation(
                        target_number_of_triangles=int(max_input_faces)
                    )
                    work = trimesh_module.Trimesh(
                        vertices=np.asarray(o3d_mesh.vertices),
                        faces=np.asarray(o3d_mesh.triangles),
                        process=False
                    )
                    print(">>> [RemeshGPU] Simplified via Open3D fallback")
                except Exception as e:
                    print(f">>> [RemeshGPU] Simplify skipped: {e}")

        work.merge_vertices(merge_tex=False, merge_norm=False)

        # --- 2. GPU ---
        vertices = torch.tensor(work.vertices, dtype=torch.float32, device="cuda")
        faces = torch.tensor(work.faces, dtype=torch.int32, device="cuda")

        bbox_min = vertices.min(dim=0).values
        bbox_max = vertices.max(dim=0).values
        scale = (bbox_max - bbox_min).max().item()
        center = (bbox_min + bbox_max) * 0.5
        vertices_centered = vertices - center

        c_core = CuMesh.CuMesh()
        c_core.init(vertices_centered, faces)
        try:
            c_core.unify_face_orientations()
        except Exception:
            pass
        try:
            c_core.fill_holes()
        except Exception:
            pass

        curr_v, curr_f = c_core.read()
        bvh = CuMesh.cuBVH(curr_v, curr_f)

        domain_scale = scale * (1.0 + 4.0 * band / max(grid_resolution, 1))

        new_v, new_f = CuMesh.remeshing.remesh_narrow_band_dc(
            curr_v, curr_f,
            center=torch.zeros(3, device="cuda"),
            scale=domain_scale,
            resolution=grid_resolution,
            band=band,
            project_back=project_back,
            verbose=False,
            bvh=bvh,
        )

        del bvh, curr_v, curr_f, c_core
        torch.cuda.empty_cache()

        final_v = (new_v + center).cpu().numpy().astype(np.float32)
        final_f = new_f.cpu().numpy().astype(np.int64)
        result = trimesh_module.Trimesh(vertices=final_v, faces=final_f, process=False)

        result.merge_vertices()
        try:
            result.update_faces(result.unique_faces() & result.nondegenerate_faces())
        except Exception:
            pass
        result.remove_infinite_values()
        result.fix_normals()

        seal_info = ""
        if force_watertight:
            result, seal_info = _seal_watertight(result, max_hole_edges=max_hole_edges)

        wt = bool(result.is_watertight)
        try:
            comps = len(result.split(only_watertight=False)) if len(result.faces) else 0
        except Exception:
            comps = -1

        info = (
            f"Strong Remesh | res={grid_resolution} band={band:.1f} proj={project_back:.2f} | "
            f"faces {len(mesh.faces):,} → {len(result.faces):,} | "
            f"watertight={wt} | components={comps}"
        )
        if seal_info:
            info += f" | seal: {seal_info}"

        print(f">>> [Antonioilev RemeshGPU] {info}")
        return result, info

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"ERROR: {str(e)}"


class RemeshGPU:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trimesh": ("TRIMESH",),
                "grid_resolution": ("INT", {"default": 512, "min": 64, "max": 2048, "step": 64}),
                "band_width": ("FLOAT", {"default": 3.0, "min": 1.0, "max": 16.0, "step": 0.5}),
                "project_back": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 1.0, "step": 0.05}),
                "repair_holes": ("BOOLEAN", {"default": True}),
                "force_watertight": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "pre_simplify_limit": ("INT", {"default": 2000000, "min": 0, "max": 20000000, "step": 100000}),
                "max_hole_edges": ("INT", {"default": 500, "min": 0, "max": 20000, "step": 50}),
            }
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "build_mesh"
    CATEGORY = "Antonioilev/Mesh"

    def build_mesh(self, trimesh, grid_resolution, band_width, project_back,
                   repair_holes, force_watertight=True,
                   pre_simplify_limit=2000000, max_hole_edges=500):

        res_mesh, info = cumesh_strong_remesh(
            trimesh,
            grid_resolution=grid_resolution,
            band=band_width,
            project_back=project_back,
            max_input_faces=pre_simplify_limit,
            repair_holes=repair_holes,
            force_watertight=force_watertight,
            max_hole_edges=max_hole_edges,
        )
        if res_mesh is None:
            return (trimesh, info)
        return (res_mesh, info)


NODE_CLASS_MAPPINGS = {"AntonioilevRemeshGPU": RemeshGPU}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevRemeshGPU": "🧱 GPU Strong Remesh (Watertight)"}