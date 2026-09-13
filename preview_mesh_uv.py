# SPDX-License-Identifier: GPL-3.0-or-later
# Optimized for Antonioilev Nodes Pack - 2026

import trimesh as trimesh_module
import os
import uuid
import json
import numpy as np

try:
    import folder_paths
    COMFYUI_OUTPUT_FOLDER = folder_paths.get_output_directory()
except:
    COMFYUI_OUTPUT_FOLDER = None

class SafePreviewMeshUV:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trimesh": ("TRIMESH",),
            },
            "optional": {
                "show_checker": ("BOOLEAN", {"default": False}),
                "show_wireframe": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "execute_safe_preview"
    CATEGORY = "Antonioilev/Viewers"

    def execute_safe_preview(self, trimesh, show_checker=False, show_wireframe=True):
        if trimesh is None:
            return {"ui": {"error": ["No mesh provided"]}}

        # 1. ЗАЩИТА: Работаем с копией
        preview_mesh = trimesh.copy()
        is_it_watertight = preview_mesh.is_watertight
        
        # 2. СТРОГАЯ ПРОВЕРКА UV (Без самодеятельности)
        has_uvs = False
        try:
            # Проверяем, что visual — это именно TextureVisuals, а не просто цвета
            from trimesh.visual.texture import TextureVisuals
            if isinstance(preview_mesh.visual, TextureVisuals):
                if hasattr(preview_mesh.visual, 'uv') and preview_mesh.visual.uv is not None:
                    if len(preview_mesh.visual.uv) > 0:
                        # Проверяем, что это не пустой массив из нулей
                        if not np.all(preview_mesh.visual.uv == 0):
                            has_uvs = True
        except:
            has_uvs = False

        if not has_uvs:
            # Если мапинга нет — ПРИНУДИТЕЛЬНО очищаем визуализацию
            # Это гарантирует, что в GLB не будет "мусорных" или авто-генерируемых координат
            preview_mesh.visual = trimesh_module.visual.ColorVisuals()
            print(">>> [ANTONIOILEV MONITOR] INFO: No UV data detected. Passive diagnostic mode.")

        # 3. ЭКСПОРТ GLB (JS ожидает именно этот формат)
        mesh_filename = f"preview_uv_{uuid.uuid4().hex[:8]}.glb"
        mesh_filepath = os.path.join(COMFYUI_OUTPUT_FOLDER, mesh_filename) if COMFYUI_OUTPUT_FOLDER else mesh_filename
        preview_mesh.export(mesh_filepath, file_type='glb')

        # Подготовка данных UV для JSON (нужно для 2D вьюпорта справа)
        uv_json_filename = None
        uv_coverage = 0.0
        in_unit_square = False
        uv_min, uv_max = [0.0, 0.0], [1.0, 1.0]

        if has_uvs:
            uvs = preview_mesh.visual.uv
            uv_data = {
                "uvs": uvs.tolist(),
                "faces": preview_mesh.faces.tolist(),
            }
            uv_json_filename = f"preview_uv_{uuid.uuid4().hex[:8]}_uvdata.json"
            uv_json_filepath = os.path.join(COMFYUI_OUTPUT_FOLDER, uv_json_filename)
            with open(uv_json_filepath, 'w') as f:
                json.dump(uv_data, f)
            
            # Расчет охвата для статистики
            uv_min = uvs.min(axis=0).tolist()
            uv_max = uvs.max(axis=0).tolist()
            in_unit_square = bool(uv_min[0] >= 0 and uv_min[1] >= 0 and uv_max[0] <= 1 and uv_max[1] <= 1)

        # 4. ФОРМИРОВАНИЕ UI_DATA (Строго под логику JS-скрипта GeomPack)
        ui_data = {
            "mesh": [{
                "filename": mesh_filename,
                "type": "output",
                "subfolder": "",
            }],
            "mesh_file": [mesh_filename], 
            "uv_data_file": [uv_json_filename] if uv_json_filename else [],
            "vertex_count": [len(preview_mesh.vertices)],
            "face_count": [len(preview_mesh.faces)],
            "has_uvs": [has_uvs],
            "is_watertight": [is_it_watertight],
            "show_checker": [show_checker],
            "show_wireframe": [show_wireframe],
            "uv_coverage": [uv_coverage],
            "uv_in_unit_square": [in_unit_square],
            "uv_min": [uv_min],
            "uv_max": [uv_max],
        }

        # Контрольный вывод в лог сервера
        color = "?" if is_it_watertight else "?"
        status = "YES" if is_it_watertight else "NO"
        print(f"\n>>> [ANTONIOILEV MONITOR] Safe Preview: {mesh_filename}")
        print(f">>> [ANTONIOILEV MONITOR] UV Detected: {has_uvs}")
        print(f">>> [ANTONIOILEV MONITOR] Watertight Integrity: {status} {color}\n")

        return {"ui": ui_data}

NODE_CLASS_MAPPINGS = {
    #"GeomPackPreviewMeshUV": SafePreviewMeshUV    
    "preview_mesh_uv": SafePreviewMeshUV
}

NODE_DISPLAY_NAME_MAPPINGS = {
    #"GeomPackPreviewMeshUV": "?? UV unwrap Preview (Safe)"    
    "preview_mesh_uv": "?? UV preview"
}