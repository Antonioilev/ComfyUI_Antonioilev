import os
import trimesh
import numpy as np
import subprocess
import tempfile

class LoadMesh:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh_path": ("STRING", {"default": "", "tooltip": "Path to .glb or .fbx"}),
            }
        }

    RETURN_TYPES = ("MESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "load"
    CATEGORY = "Mesh"

    def load(self, mesh_path):
        # Очистка пути
        mesh_path = mesh_path.strip().replace('"', '').replace("'", '')
        
        # Обработка путей WSL/Windows
        if ":" in mesh_path and not mesh_path.startswith('/'):
            drive = mesh_path[0].lower()
            path_part = mesh_path[2:].replace('\\', '/')
            mesh_path = f"/mnt/{drive}{path_part}"
        mesh_path = os.path.normpath(mesh_path)

        if not os.path.exists(mesh_path):
            raise FileNotFoundError(f"[LoadMesh] File not found: {mesh_path}")

        ext = os.path.splitext(mesh_path)[1].lower()
        loaded = None

        # --- ЛОГИКА ЗАГРУЗКИ FBX ЧЕРЕЗ CLI ASSIMP ---
        if ext == '.fbx':
            print(f"[LoadMesh] FBX detected. Converting via Assimp CLI...")
            
            # Создаем временный файл во временной папке системы
            fd, temp_glb = tempfile.mkstemp(suffix='.glb')
            os.close(fd) # Закрываем дескриптор, чтобы assimp мог писать в файл
            
            try:
                # Команда конвертации (та же, что в твоем Saver)
                cmd = ["assimp", "export", mesh_path, temp_glb]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0 and os.path.exists(temp_glb):
                    loaded = trimesh.load(temp_glb, process=False)
                    print(f"[LoadMesh] FBX successfully converted and loaded.")
                else:
                    error_out = result.stderr if result.stderr else "Assimp returned non-zero code"
                    raise ValueError(f"Assimp CLI failed to convert FBX: {error_out}")
            
            finally:
                # В любом случае удаляем временный файл
                if os.path.exists(temp_glb):
                    os.remove(temp_glb)
        
        # --- СТАНДАРТНАЯ ЗАГРУЗКА ДЛЯ ПРОЧИХ ФОРМАТОВ ---
        if loaded is None:
            try:
                loaded = trimesh.load(mesh_path, process=False)
            except Exception as e:
                raise ValueError(f"Failed to load mesh: {str(e)}")

        # --- ТВОЙ СКАНЕР (БЕЗ ИЗМЕНЕНИЙ) ---
        print("\n" + "="*50)
        print(f"DEBUG SCAN FOR: {os.path.basename(mesh_path)}")
        
        has_weights = False
        
        if isinstance(loaded, trimesh.Scene):
            if len(loaded.geometry) == 0:
                raise ValueError("Scene is empty!")
                
            for name, geom in loaded.geometry.items():
                print(f"-> Checking geometry: {name}")
                
                # Проверка весов (скиннинга)
                if hasattr(geom, 'visual') and hasattr(geom.visual, 'vertex_attributes'):
                    attrs = geom.visual.vertex_attributes.keys()
                    print(f"   Vertex Attributes: {list(attrs)}")
                    if any(key in attrs for key in ['joints', 'weights', 'joint_indices']):
                        has_weights = True
                
                # Проверка метаданных
                if 'skeleton' in geom.metadata or 'skin' in geom.metadata:
                    print(f"   Found skin/skeleton in metadata!")
                    has_weights = True
            
            # Объединяем сцену в один меш для выхода
            mesh = trimesh.util.concatenate(list(loaded.geometry.values()))
        else:
            mesh = loaded
            if hasattr(mesh.visual, 'vertex_attributes'):
                print(f"Vertex Attributes: {list(mesh.visual.vertex_attributes.keys())}")

        print("="*50 + "\n")

        skin_status = "STRICT_YES" if has_weights else "NOT_FOUND"
        info = f"Mesh: {len(mesh.vertices)}v | Skin Data: {skin_status}"
        # =========================================================
        # SAFE PASS-THROUGH CLEANUP (CRITICAL FIX FOR CURVATURE)
        # =========================================================

        v = np.asarray(mesh.vertices, dtype=np.float32)
        f = np.asarray(mesh.faces, dtype=np.int32)

        # ---------------------------------------------------------
        # 1. BASIC VALIDATION (NO TOPOLOGY MODIFICATION)
        # ---------------------------------------------------------
        if len(v) == 0:
            raise ValueError("Mesh has no vertices")

        if f is None or len(f) == 0:
            raise ValueError("Mesh has no faces")

        # ---------------------------------------------------------
        # 2. FIX NaN / INF (ONLY GEOMETRY SANITIZATION)
        # ---------------------------------------------------------
        if not np.isfinite(v).all():
            v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)

        # ---------------------------------------------------------
        # 3. FACE INDEX SANITY (NO RESTRUCTURE)
        # ---------------------------------------------------------
        valid_faces = np.all((f >= 0) & (f < len(v)), axis=1)
        f = f[valid_faces]

        if len(f) == 0:
            # DO NOT CRASH PIPELINE
            # fallback: dummy triangle (prevents Open3D fatal)
            f = np.array([[0, 1, 2]], dtype=np.int32)

        # ---------------------------------------------------------
        # 4. DO NOT REMOVE VERTICES (CRITICAL FOR FEATURE_MAP ALIGNMENT)
        # ---------------------------------------------------------
        # mesh.remove_unreferenced_vertices()  ❌ DO NOT DO THIS

        # ---------------------------------------------------------
        # 5. REBUILD MINIMAL TRIMESH (PRESERVE ATTRIBUTES)
        # ---------------------------------------------------------
        clean_mesh = trimesh.Trimesh(
            vertices=v,
            faces=f,
            process=False,
            maintain_order=True
        )

        # ---------------------------------------------------------
        # 6. RESTORE VISUAL DATA IF EXISTS (CRITICAL FIX)
        # ---------------------------------------------------------
        if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None:
            try:
                clean_mesh.visual.vertex_colors = mesh.visual.vertex_colors
            except Exception:
                pass

        # ---------------------------------------------------------
        # 7. FINAL OUTPUT
        # ---------------------------------------------------------
        mesh = clean_mesh

        return (mesh, info)

NODE_CLASS_MAPPINGS = { "LoadMesh": LoadMesh }
NODE_DISPLAY_NAME_MAPPINGS = { "LoadMesh": "📦 Load Mesh (Scanner + FBX)" }