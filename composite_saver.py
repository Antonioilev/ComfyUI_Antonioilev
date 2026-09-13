# SPDX-License-Identifier: GPL-3.0-or-later
# Enhanced by Antonioilev - 2026 (Pro FBX Animation-Safe Exporter)

import os
import trimesh
import subprocess
import tempfile

class AntonioilevCompositeSaver:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # Важно: если на вход пришла сцена (со скелетом), работаем с ней
                "mesh_or_scene": ("TRIMESH",), 
                "path": ("STRING", {"default": "output/my_project"}),
                "filename": ("STRING", {"default": "final_character"}),
                "file_format": (["glb", "obj", "stl", "fbx"], {"default": "fbx"}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save_composite"
    OUTPUT_NODE = True
    CATEGORY = "Antonioilev/IO"

    def save_composite(self, mesh_or_scene, path, filename, file_format):
        # 1. ОПРЕДЕЛЯЕМ, ЧТО У НАС НА ВХОДЕ
        # Если это уже готовая сцена (из нашего LoadMesh), используем её.
        # Если это одиночный меш или список, создаем новую сцену.
        if isinstance(mesh_or_scene, trimesh.Scene):
            final_scene = mesh_or_scene
        else:
            final_scene = trimesh.Scene()
            meshes_to_save = mesh_or_scene if isinstance(mesh_or_scene, list) else [mesh_or_scene]
            for i, m in enumerate(meshes_to_save):
                final_scene.add_geometry(m, node_name=f"part_{i:02d}")

        # 2. ПОДГОТОВКА ПУТЕЙ
        full_path = os.path.abspath(path)
        os.makedirs(full_path, exist_ok=True)
        final_file = os.path.join(full_path, f"{filename}.{file_format}")

        try:
            if file_format in ["glb", "obj", "stl"]:
                # Прямой экспорт. GLB сохранит скелет, если он есть в final_scene
                final_scene.export(final_file)
                print(f"[Antonioilev] Saved: {final_file}")
            
            elif file_format == "fbx":
                print(f"[Antonioilev] FBX Animation-Safe Export via Assimp...")
                
                # Создаем временный GLB, который умеет хранить иерархию и веса
                fd, temp_glb = tempfile.mkstemp(suffix='.glb')
                os.close(fd)
                
                try:
                    # Экспортируем всю сцену целиком!
                    final_scene.export(temp_glb)
                    
                    # Конвертируем в FBX. Assimp подхватит структуру узлов и ключи
                    cmd = ["assimp", "export", temp_glb, final_file]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        print(f"[Antonioilev] FBX with Bones/Anim saved: {final_file}")
                    else:
                        raise ValueError(f"Assimp Error: {result.stderr}")
                
                finally:
                    if os.path.exists(temp_glb):
                        os.remove(temp_glb)

        except Exception as e:
            print(f"!!! [Antonioilev] Export Critical Error: {str(e)}")

        return {"ui": {"text": [final_file]}}

NODE_CLASS_MAPPINGS = {
    "AntonioilevCompositeSaver": AntonioilevCompositeSaver
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AntonioilevCompositeSaver": "💾🧱 Composite Mesh Saver (Assimp FBX)"
}