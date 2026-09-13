# SPDX-License-Identifier: GPL-3.0-or-later
# Antonioilev - Ultimate 3D Uber Hub Visualizer - 2026

import os
import tempfile
import numpy as np
import trimesh  # Убедитесь, что он импортирован

try:
    import folder_paths
    COMFYUI_OUTPUT_FOLDER = folder_paths.get_output_directory()
except:
    COMFYUI_OUTPUT_FOLDER = None

#-----------------------------------------------------------------------
#-----------------------------------------------------------------------

from aiohttp import web
from server import PromptServer

@PromptServer.instance.routes.post("/antonioilev/execute_node")
async def execute_node(request):
    data = await request.json()

    print("EXEC NODE:", data)

    return web.json_response({
        "status": "error",
        "message": "You cannot execute a single node in ComfyUI. Send full prompt graph instead."
    })
#-----------------------------------------------------------------------
#-----------------------------------------------------------------------


class Ultimate3DViewSaveLoad:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "full_path": ("STRING", {"default": "/mnt/l/Game_2/Art/"}),
                "mode": (["Auto (Load if empty)", "Save Only", "Load Only", "Preview Only"],),
                "fallback_input_type": (["Trimesh", "Mesh", "Coords (Sparse)", "Shape Slat"], {"default": "Trimesh"}),
                "brightness": ("FLOAT", {"default": 1.2, "min": 0.1, "max": 5.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "show_preview": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "trimesh": ("TRIMESH", {"forceInput": True}),
                "mesh": ("MESH,TRIMESH,MESHWITHVOXEL", {"forceInput": True}),
                "coords": ("COORDS", {"forceInput": True}),
                "shape_slat": ("SHAPE_SLAT", {"forceInput": True}),
                "env_hdr": ("IMAGE", {"forceInput": True}),
                "sparse_structure_resolution": ("INT", {"default": 32, "min": 8, "max": 512, "step": 8}),
                "point_size": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 10.0, "step": 0.1, "display": "slider"}),
                "fix_lighting": ("BOOLEAN", {"default": True}),
                "soft_edges": ("BOOLEAN", {"default": True}),                
            },
            "hidden": {
                "node_id": "UNIQUE_ID",
            }
        }

    @classmethod
    def IS_CHANGED(cls, seed, **kwargs):
        point_size = kwargs.get("point_size", 1.0)
        resolution = kwargs.get("sparse_structure_resolution", 32)
        return f"{seed}_{point_size}_{resolution}"

    RETURN_TYPES = ("TRIMESH", "TRIMESH", "TRIMESH,MESH,MESHWITHVOXEL", "*", "SHAPE_SLAT")
    RETURN_NAMES = ("trimesh_scene", "trimesh_merged", "mesh_out", "raw_coords", "shape_slat")
    OUTPUT_NODE = True
    FUNCTION = "execute"
    CATEGORY = "Antonioilev/Viewers"

    @staticmethod
    def _extract_curvature(obj):
        """
        Extract curvature from ComfyUI mesh pipeline (Retopo-safe version).
        """

        if obj is None:
            return None

        # =========================================================
        # 1. PRIMARY SOURCE (YOUR CURVATURE NODE CONTRACT)
        # =========================================================
        if hasattr(obj, "metadata") and isinstance(obj.metadata, dict):

            if "curvature_scalar" in obj.metadata:
                return obj.metadata["curvature_scalar"]

            # fallback debug format (optional safety)
            if "curvature" in obj.metadata:
                return obj.metadata["curvature"]

        # =========================================================
        # 2. DICT PASS-THROUGH (if any internal wrapper exists)
        # =========================================================
        if isinstance(obj, dict):

            if "curvature_scalar" in obj:
                return obj["curvature_scalar"]

            if "curvature" in obj:
                return obj["curvature"]

        # =========================================================
        # 3. DIRECT NUMPY FALLBACK
        # =========================================================
        if isinstance(obj, np.ndarray):
            return obj

        # =========================================================
        # 4. LAST RESORT ATTRIBUTE (legacy / custom meshes)
        # =========================================================
        if hasattr(obj, "curvature_scalar"):
            try:
                return obj.curvature_scalar
            except:
                pass

        if hasattr(obj, "curvature"):
            try:
                return obj.curvature
            except:
                pass

        return None

    def execute(
        self,
        full_path,
        mode,
        fallback_input_type,
        brightness,
        seed,
        show_preview,
        trimesh=None,
        mesh=None,
        coords=None,
        shape_slat=None,
        env_hdr=None,
        sparse_structure_resolution=32,
        point_size=1.0,
        fix_lighting=True,
        soft_edges=True,        
        node_id=None
    ):

        ui_data = {}
        out_path = COMFYUI_OUTPUT_FOLDER or tempfile.gettempdir()
        node_colors = ["#52339b", "#2a1a4f"]
        patch_result = None

        # 1. ПАРСИНГ ПУТИ
        clean_full_path = full_path.strip().replace("\\", "/")
        target_dir = os.path.dirname(clean_full_path) or "/mnt/l/Game_2/Art/"
        filename = os.path.basename(clean_full_path)
        file_base, file_ext = os.path.splitext(filename)

        # =====================================================
        # CURVATURE LOAD (.NPZ)
        # =====================================================

        curvature_data = None
        npz_path = os.path.join(target_dir, file_base + ".npz")

        if os.path.exists(npz_path):

            try:
                npz = np.load(npz_path, allow_pickle=True)

                if "curvature" in npz.files:

                    curvature_data = np.asarray(
                        npz["curvature"],
                        dtype=np.float32
                    )

                    # SAFETY NORMALIZATION
                    if curvature_data.ndim != 1:
                        print(">>>> [3D View] CURVATURE LOAD WARNING: non-1D array, flattening")
                        curvature_data = curvature_data.reshape(-1)

                    print(">>>> [3D View] NPZ CURVATURE LOADED")
                    print("shape:", curvature_data.shape)
                    print("min:", float(np.min(curvature_data)))
                    print("max:", float(np.max(curvature_data)))
                    print("std:", float(np.std(curvature_data)))

                else:
                    print(">>>> [3D View] NPZ has no curvature key")

            except Exception as e:
                print(f">>>> [3D View] NPZ curvature load failed: {e}")

                import traceback
                traceback.print_exc()

                curvature_data = None

        file_ext = file_ext if file_ext else ".fbx"

        has_any_input = (
            (trimesh is not None)
            or (mesh is not None)
            or (coords is not None)
            or (shape_slat is not None)
        )

        should_save = (
            (mode == "Save Only")
            or (mode == "Auto (Load if empty)" and has_any_input)
        )

        # 2. ОПРЕДЕЛЕНИЕ КОНТЕКСТА
        mapping = {
            "Trimesh": "trimesh",
            "Mesh": "mesh",
            "Shape Slat": "shape_slat",
            "Coords (Sparse)": "coords"
        }

        active_context = None

        if trimesh is not None:
            active_context = "trimesh"

        elif mesh is not None:
            active_context = "mesh"

        elif coords is not None:
            active_context = "coords"

        elif shape_slat is not None:
            active_context = "shape_slat"

        else:
            active_context = mapping.get(fallback_input_type, "trimesh")

        # 3. ДИСПЕТЧЕРИЗАЦИЯ
        match (should_save, mode):

            case (True, _):
                node_colors = ["#ccaa00", "#443300"]

            case (_, "Preview Only"):
                node_colors = ["#aaaaaa", "#555555"]

            case _:
                node_colors = ["#52339b", "#2a1a4f"]

        # Выполнение патчей
        if active_context == "trimesh":

            from .view_patches.patch_trimesh import process_trimesh_data

            patch_result = process_trimesh_data(
                trimesh,
                target_dir,
                file_base,
                file_ext,
                file_ext.lower().replace(".", ""),
                mode,
                should_save,
                soft_edges,
                fix_lighting,
                out_path,
                seed
            )

        elif active_context == "mesh":

            from .view_patches.patch_mesh import process_heavy_mesh_data

            patch_result = process_heavy_mesh_data(
                mesh,
                target_dir,
                file_base,
                file_ext,
                file_ext.lower().replace(".", ""),
                mode,
                should_save,
                out_path,
                seed
            )

        elif active_context == "coords":

            from .view_patches import process_sparse_data

            patch_result = process_sparse_data(
                coords_input=coords,
                target_dir=target_dir,
                file_base=file_base,
                file_ext=file_ext,
                ext_type=file_ext.lower(),
                mode=mode,
                should_save=should_save,
                out_path=out_path,
                seed=seed,
                resolution=sparse_structure_resolution,
                point_size=point_size
            )

        elif active_context == "shape_slat":

            from .view_patches.patch_slat import process_slat_data

            patch_result = process_slat_data(
                slat_input=shape_slat,
                target_dir=target_dir,
                file_base=file_base,
                file_ext=file_ext,
                ext_type=file_ext.lower(),
                mode=mode,
                should_save=should_save,
                out_path=out_path,
                seed=seed,
                point_size=point_size
            )
        
        # 4. ФОРМИРОВАНИЕ БЕЗОПАСНОГО ВЫХОДА
        if patch_result and "result_data" in patch_result:
            res_trimesh_scene = patch_result["result_data"][0]
            res_trimesh_merged = patch_result["result_data"][1]
        else:
            res_trimesh_scene = trimesh
            res_trimesh_merged = trimesh
         
        res_mesh_out = patch_result["result_data"][1] if patch_result else mesh
        res_coords = patch_result["result_data"][2] if (patch_result and active_context == "coords") else coords
        res_slat = patch_result["result_data"][2] if (patch_result and active_context == "shape_slat") else shape_slat
        
        # =====================================================
        # EXR/HDR ENVIRONMENT MAP → disk + ключ для JS (не терять при ui_data = {})
        # =====================================================
        env_file_for_ui = None
        if env_hdr is not None:
            try:
                import imageio
                hdr_np = env_hdr[0].cpu().numpy().astype(np.float32).copy()
                hdr_np = np.nan_to_num(hdr_np, nan=0.0, posinf=0.0, neginf=0.0)
                # imageio RGBE (.hdr) обычно 3 канала
                if hdr_np.ndim == 3 and hdr_np.shape[-1] > 3:
                    hdr_np = hdr_np[..., :3]
                elif hdr_np.ndim == 2:
                    hdr_np = np.stack([hdr_np] * 3, axis=-1)

                hdr_filename = f"antonioilev_env_{seed}.hdr"
                full_hdr_path = os.path.join(out_path, hdr_filename)
                imageio.imwrite(full_hdr_path, hdr_np)
                env_file_for_ui = hdr_filename  # только имя; файл в Comfy output/

                def attach_hdr(target):
                    if target is None:
                        return
                    if hasattr(target, "__dict__"):
                        if not hasattr(target, "metadata") or target.metadata is None:
                            target.metadata = {}
                        if isinstance(target.metadata, dict):
                            target.metadata["env_hdr"] = hdr_np
                    if isinstance(target, dict):
                        target["env_hdr"] = hdr_np

                attach_hdr(res_trimesh_scene)
                attach_hdr(res_trimesh_merged)
                attach_hdr(res_mesh_out)
                attach_hdr(res_coords)
                attach_hdr(res_slat)
                print(f">>>> [3D View] HDR saved for IBL: {full_hdr_path}")
            except Exception as e:
                print(f">>>> [3D View] HDR Save/Attach Failed: {str(e)}")
                import traceback
                traceback.print_exc()
        # =====================================================

        # [ДОБАВИТЬ ЭТОТ БЛОК ДЛЯ ФИКСА ТЕКСТУРЫ В UI]
        # =====================================================
        # EMERGENCY GLB EMISSION FOR FRONTEND VISUALIZATION
        # =====================================================
        preview_mesh = res_trimesh_scene if res_trimesh_scene is not None else trimesh
        
        # Если патч не отдал имя файла, или меш текстурирован — пишем GLB принудительно
        if show_preview and preview_mesh is not None:
            try:
                # Генерируем уникальное имя для сессии в папке вывода ComfyUI
                export_filename = f"antonioilev_preview_{seed}.glb"
                full_export_path = os.path.join(out_path, export_filename)
                
                # Экспортируем всю сцену/меш целиком. GLB упакует PBR/Simple материал внутрь!
                preview_mesh.export(full_export_path, file_type="glb")
                
                # Перезаписываем имя файла для UI виджета
                if "mesh_file" not in ui_data or not ui_data["mesh_file"]:
                    ui_data["mesh_file"] = [export_filename]
                else:
                    ui_data["mesh_file"] = [export_filename]
                    
                print(f">>>> [3D View] EMERGENCY GLB EXPORT SUCCESS: {export_filename}")
            except Exception as e:
                print(f">>>> [3D View] EMERGENCY GLB EXPORT FAILED: {str(e)}")


        # =====================================================
        # CURVATURE ATTACH (NPZ -> OUTPUT PIPELINE)
        # =====================================================
        # === ВСТАВЛЯЕМ ЭТОТ ОБНОВЛЕННЫЙ БЛОК ===
        # =====================================================
        # CURVATURE ATTACH (NPZ -> OUTPUT PIPELINE)
        # =====================================================
        try:
            if curvature_data is not None:
                def attach(target):
                    if target is None: return
                    if hasattr(target, "__dict__"):
                        if not hasattr(target, "metadata") or target.metadata is None:
                            target.metadata = {}
                        if isinstance(target.metadata, dict):
                            target.metadata["curvature_scalar"] = curvature_data
                    if isinstance(target, dict):
                        target["curvature_scalar"] = curvature_data

                attach(res_trimesh_scene)
                attach(res_mesh_out)
                attach(res_coords)
                attach(res_slat)
                print(">>>> [3D View] CURVATURE ATTACHED FROM NPZ OK")
        except Exception as e:
            print(">>>> [3D View] CURVATURE ATTACH FAILED:", str(e))

        # Сначала подготавливаем структуру ui_data, чтобы её ключи были объявлены
        ui_data = {
            "color": node_colors,
            "blueprint_init": [True],
            "context": active_context,
            "viewport_context": patch_result.get("viewport_context", []) if patch_result else [],
        }
        if patch_result and patch_result.get("temp_name"):
            ui_data["mesh_file"] = [patch_result["temp_name"]]

        # IBL: JS ищет message.env_file / env_url
        if env_file_for_ui:
            ui_data["env_file"] = [env_file_for_ui]
            # на всякий случай дублируем старым ключом
            ui_data["env_hdr_file"] = [env_file_for_ui]

        # А теперь делаем жесткий оверрайд: упаковываем меш с текстурой в GLB и пишем в ui_data
        preview_mesh = res_trimesh_scene if res_trimesh_scene is not None else trimesh
        
        if show_preview and preview_mesh is not None:
            try:
                export_filename = f"antonioilev_preview_{seed}.glb"
                full_export_path = os.path.join(out_path, export_filename)
                
                # Trimesh упакует PBRMaterial/SimpleMaterial и текстуру прямо внутрь GLB
                preview_mesh.export(full_export_path, file_type="glb")
                
                # Перезаписываем mesh_file актуальным значением
                ui_data["mesh_file"] = [export_filename]
                print(f">>>> [3D View] TEXTURE PREVIEW GLB GENERATED: {export_filename}")
            except Exception as e:
                print(f">>>> [3D View] TEXTURE PREVIEW EXPORT FAILED: {str(e)}")
        # === КОНЕЦ НОВОГО БЛОКА ===
        # Интеграция логики GeometryPack для визуализации
        if preview_mesh is not None and hasattr(preview_mesh, 'vertices'):
            try:
                # Используем стандартные атрибуты trimesh, если они есть
                bounds = preview_mesh.bounds
                extents = preview_mesh.extents
            except:
                # Fallback: считаем вручную через numpy
                verts = np.array(preview_mesh.vertices)
                b_min = verts.min(axis=0)
                b_max = verts.max(axis=0)
                bounds = np.array([b_min, b_max])
                extents = b_max - b_min
            # Получаем количество граней (безопасно)
            face_count = len(preview_mesh.faces) if hasattr(preview_mesh, 'faces') else 0

            ui_data.update({
                "vertex_count": [len(preview_mesh.vertices)],
                "face_count": [face_count],
                "bounds_min": [bounds[0].tolist()],
                "bounds_max": [bounds[1].tolist()],
                "extents": [extents.tolist()],
                "max_extent": [float(max(extents))],
            })

        # =====================================================
        # CURVATURE SAVE (.NPZ)
        # =====================================================
        try:
            os.makedirs(target_dir, exist_ok=True)
            curvature = None
            # ЖЁСТКОЕ извлечение (без OR, чтобы не ломалось на numpy)
            for src in (trimesh, mesh, coords, shape_slat):
                curvature = self._extract_curvature(src)
                if curvature is not None:
                    break
            if curvature is None:
                print(">>>> [3D View] CURVATURE SAVE SKIPPED: no curvature found")
            else:
                curvature = np.asarray(curvature, dtype=np.float32)
                # SAFETY NORMALIZATION
                if curvature.ndim != 1:
                    print(">>>> [3D View] CURVATURE WARNING: non-1D array, flattening")
                    curvature = curvature.reshape(-1)
                print(">>>> [3D View] CURVATURE SAVE OK")
                print("shape:", curvature.shape)
                print("min:", float(np.min(curvature)))
                print("max:", float(np.max(curvature)))
                print("std:", float(np.std(curvature)))
                npz_path = os.path.join(target_dir, file_base + ".npz")
                print(">>>> CURVATURE SOURCE CHECK:")
                print("type:", type(curvature))
                print("has metadata:", hasattr(trimesh, "metadata"))

                if hasattr(trimesh, "metadata"):
                    print(
                        "metadata keys:",
                        list(trimesh.metadata.keys())
                        if isinstance(trimesh.metadata, dict)
                        else None
                    )
                np.savez(
                    npz_path,
                    curvature=curvature.astype(np.float32)
                )
                print(">>>> [3D View] NPZ SAVED:", npz_path)
        except Exception as e:
            print(">>>> [3D View] NPZ curvature save FAILED:", str(e))
            import traceback
            traceback.print_exc()

        # Гарантируем, что ui_data существует, даже если загрузка прошла по альтернативной ветке
        if 'ui_data' not in locals():
            ui_data = {
                "color": "#223344", 
                "blueprint_init": [True],
                "context": "mesh",
                "viewport_context": patch_result.get("viewport_context", []) if 'patch_result' in locals() and patch_result else []
            }
            if 'patch_result' in locals() and patch_result and patch_result.get("temp_name"):
                ui_data["mesh_file"] = [patch_result["temp_name"]]
                
        if env_file_for_ui:
            ui_data["env_file"] = [env_file_for_ui]
            ui_data["env_hdr_file"] = [env_file_for_ui]
        else:
            # явно: нет HDR
            ui_data["env_file"] = [""]
            ui_data["env_hdr_file"] = [""]
            
        return {
            "ui": ui_data,
            "result": (
                res_trimesh_scene,
                res_trimesh_merged,
                res_mesh_out,
                res_coords,
                res_slat
            )
        }

NODE_CLASS_MAPPINGS = {"Ultimate3DViewSaveLoad": Ultimate3DViewSaveLoad}
NODE_DISPLAY_NAME_MAPPINGS = {"Ultimate3DViewSaveLoad": "🔍📐📦 3D View Save Load"}