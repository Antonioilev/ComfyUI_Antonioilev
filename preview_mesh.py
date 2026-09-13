# SPDX-License-Identifier: GPL-3.0-or-later
# Antonioilev - Ultimate Seed-Forced Edition - 2026
# FIX: All Soft Edges & Multi-Material Lighting & Dynamic Brightness

import trimesh as trimesh_module
import os
import uuid
import numpy as np
import tempfile
import time
import random
import string
import glob

try:
    import folder_paths
    COMFYUI_OUTPUT_FOLDER = folder_paths.get_output_directory()
except:
    COMFYUI_OUTPUT_FOLDER = None

class PreviewMeshNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trimesh": ("TRIMESH",),
                "brightness": ("FLOAT", {"default": 1.2, "min": 0.1, "max": 5.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "forceInput": False}),
            },
            "optional": {
                "fix_lighting": ("BOOLEAN", {"default": True}),
                "soft_edges": ("BOOLEAN", {"default": True}),
                "show_wireframe": ("BOOLEAN", {"default": False}),
            }
        }

    @classmethod
    def IS_CHANGED(s, trimesh, seed, brightness, **kwargs):
        # Добавляем brightness в проверку изменений, чтобы превью обновлялось при кручении ползунка
        return f"{seed}_{brightness}_{time.time()}"

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "preview_mesh"
    CATEGORY = "Antonioilev/Viewers"

    # ДОБАВЛЕНО: brightness в аргументы функции
    def preview_mesh(self, trimesh, seed, brightness=1.2, fix_lighting=True, soft_edges=True, show_wireframe=False):
        if trimesh is None:
            return {"ui": {"error": ["No mesh provided"]}}

        out_path = COMFYUI_OUTPUT_FOLDER or tempfile.gettempdir()
        
        # 1. ОЧИСТКА СТАРЫХ ФАЙЛОВ
        try:
            for old_file in glob.glob(os.path.join(out_path, "force_v*.glb")):
                try:
                    os.remove(old_file)
                except:
                    pass
        except:
            pass

        # 2. ПОДГОТОВКА ГЕОМЕТРИИ
        render_id = f"{seed}_{int(time.time() * 100)}"
        initial_meshes = trimesh if isinstance(trimesh, list) else [trimesh]
        processed_elements = []
        
        for i, m_entry in enumerate(initial_meshes):
            p = m_entry.copy()
            
            # РАЗДЕЛЕНИЕ ПО МАТЕРИАЛАМ
            sub_parts = p.split(only_watertight=False)
            
            for j, part in enumerate(sub_parts):
                m = part.copy()
                m.metadata['name'] = f"part_{render_id}_{i}_{j}"
                
                # ПРИНУДИТЕЛЬНЫЕ SOFT EDGES
                if soft_edges:
                    m.face_normals = None
                    m.vertex_normals = None 
                
                if fix_lighting:
                    m.fix_normals()
                    if hasattr(m.visual, 'material'):
                        mat = m.visual.material
                        if hasattr(mat, 'metallicFactor'): mat.metallicFactor = 0.0
                        if hasattr(mat, 'roughnessFactor'): mat.roughnessFactor = 1.0
                        if hasattr(mat, 'doubleSided'): mat.doubleSided = True
                    
                    m.process(validate=True)
                
                processed_elements.append(m)

        # 3. СБОРКА СЦЕНЫ И ЭКСПОРТ
        new_scene = trimesh_module.Scene()
        for geometry in processed_elements:
            new_scene.add_geometry(geometry)

        filename = f"force_v{render_id}.glb"
        filepath = os.path.join(out_path, filename)
        
        new_scene.export(filepath, file_type='glb')

        print(f">>> [Antonioilev] Preview Generated. Brightness: {brightness} | Seed: {seed}")

        return {
            "ui": {
                "mesh_file": [filename],
                "brightness": [brightness], # ВАЖНО: передаем в JS
                "show_wireframe": [show_wireframe],
                "seed_id": [seed]
            }
        }

NODE_CLASS_MAPPINGS = {
    "GeomPackPreviewMesh": PreviewMeshNode,
    "preview_mesh_antonioilev": PreviewMeshNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeomPackPreviewMesh": "👁️ Preview Mesh (Soft & Multi-Mat)",
    "preview_mesh_antonioilev": "👁️ Preview Mesh (Soft & Multi-Mat)"
}