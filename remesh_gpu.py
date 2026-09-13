import numpy as np
import trimesh as trimesh_module
import torch
from typing import Tuple, Optional

def cumesh_dc_remesh(
    mesh: trimesh_module.Trimesh, 
    grid_resolution: int, 
    band: float, 
    project_back: float,
    thin_feature_fix: bool = True
) -> Tuple[Optional[trimesh_module.Trimesh], str]:
    import cumesh as CuMesh

    try:
        mesh = mesh.copy()
        
        # 1. Интеллектуальная очистка
        mesh.merge_vertices(merge_tex=False, merge_norm=False)
        
        # Если фиксим тонкие детали — не удаляем мелкие куски сразу
        if not thin_feature_fix:
            components = mesh.split(only_watertight=False)
            if len(components) > 1:
                mesh = max(components, key=lambda x: x.area)

        # 2. Подготовка данных
        vertices = torch.tensor(mesh.vertices, dtype=torch.float32).cuda()
        faces = torch.tensor(mesh.faces, dtype=torch.int32).cuda()

        # Центрирование
        bbox_min = vertices.min(dim=0).values
        bbox_max = vertices.max(dim=0).values
        scale = (bbox_max - bbox_min).max().item()
        center = (bbox_min + bbox_max) / 2
        vertices_centered = vertices - center

        # 3. Инициализация и герметизация
        cumesh_core = CuMesh.CuMesh()
        cumesh_core.init(vertices_centered, faces)
        
        # Для тонких деталей важна ориентация нормалей
        cumesh_core.unify_face_orientations() 
        
        if thin_feature_fix:
            # Делаем меш чуть более "толстым" для алгоритма внутри
            cumesh_core.fill_holes() 
        else:
            cumesh_core.fill_holes()

        curr_verts, curr_faces = cumesh_core.read()
        bvh = CuMesh.cuBVH(curr_verts, curr_faces)
        
        # 4. Ремешинг с расширенной полосой (band) для тонких элементов
        # Если включен фикс, увеличиваем band автоматически
        actual_band = band * 1.5 if thin_feature_fix else band
        
        new_verts, new_faces = CuMesh.remeshing.remesh_narrow_band_dc(
            curr_verts, curr_faces,
            center=torch.zeros(3, device='cuda'),
            scale=(grid_resolution + 3 * actual_band) / grid_resolution * scale,
            resolution=grid_resolution,
            band=actual_band,
            project_back=project_back,
            verbose=False,
            bvh=bvh,
        )

        del bvh, curr_verts, curr_faces, cumesh_core
        final_verts = new_verts + center

        remeshed_obj = trimesh_module.Trimesh(
            vertices=final_verts.cpu().numpy().astype(np.float32),
            faces=new_faces.cpu().numpy(),
            process=False
        )

        del new_verts, new_faces, final_verts
        torch.cuda.empty_cache()
        return remeshed_obj, ""

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, str(e)


class AntonioilevRemeshGPU:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trimesh": ("TRIMESH",),
                "grid_resolution": ("INT", {"default": 512, "min": 64, "max": 1024, "step": 64}),
                "project_back": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.1}),
                "thin_fix": (["Enabled", "Disabled"], {"default": "Enabled"}),
            },
            "optional": {
                "band_width": ("FLOAT", {"default": 1.2, "min": 0.5, "max": 5.0, "step": 0.1}),
                "target_face_count": ("INT", {"default": 0, "min": 0, "max": 2000000, "step": 100}),
            }
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "build_mesh"
    CATEGORY = "Antonioilev/Mesh"

    def build_mesh(self, trimesh, grid_resolution, project_back, thin_fix, band_width=1.2, target_face_count=0):
        import cumesh as CuMesh
        
        is_thin_fix = (thin_fix == "Enabled")
        
        # 1. Ремеш
        res_mesh, err = cumesh_dc_remesh(trimesh, grid_resolution, band_width, project_back, thin_feature_fix=is_thin_fix)
        
        if res_mesh is None:
            return (None, f"Remesh Error: {err}")

        # 2. Симплификация
        if target_face_count > 0 and len(res_mesh.faces) > target_face_count:
            verts_t = torch.tensor(res_mesh.vertices, dtype=torch.float32).cuda()
            faces_t = torch.tensor(res_mesh.faces, dtype=torch.int32).cuda()
            cumesh_obj = CuMesh.CuMesh()
            cumesh_obj.init(verts_t, faces_t)
            cumesh_obj.simplify(target_face_count)
            final_v, final_f = cumesh_obj.read()
            res_mesh = trimesh_module.Trimesh(vertices=final_v.cpu().numpy(), faces=final_f.cpu().numpy(), process=False)
            del verts_t, faces_t, cumesh_obj
            torch.cuda.empty_cache()

        return (res_mesh, "Success")

NODE_CLASS_MAPPINGS = {"AntonioilevRemeshGPU": AntonioilevRemeshGPU}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevRemeshGPU": "🧱 Antonioilev GPU Mesh Builder"}