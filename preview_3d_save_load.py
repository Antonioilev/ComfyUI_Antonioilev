# SPDX-License-Identifier: GPL-3.0-or-later
# Antonioilev - Ultimate 3D IO Edition - 2026
# FINAL REPAIR: Assimp FBX Input/Output & Preview Toggle + UI Sync
# POLISHED: Combined Path, Removed Wireframe, Maintained Full Logic

import trimesh as trimesh_module
import os
import time
import tempfile
import subprocess

try:
    import folder_paths
    COMFYUI_OUTPUT_FOLDER = folder_paths.get_output_directory()
except:
    COMFYUI_OUTPUT_FOLDER = None

class Preview3DSaveLoad:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "full_path": ("STRING", {"default": "/mnt/l/Game_2/Art/Chars/Char2/5_Textured/52_char2_textured.fbx"}),
                "mode": (["Auto (Load if empty)", "Save Only", "Load Only", "Preview Only"],),
                "brightness": ("FLOAT", {"default": 1.2, "min": 0.1, "max": 5.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "show_preview": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "trimesh": ("*", {"forceInput": False}),
                "fix_lighting": ("BOOLEAN", {"default": True}),
                "soft_edges": ("BOOLEAN", {"default": True}),
                # Параметр show_wireframe полностью удален отсюда
            }
        }

    @classmethod
    def IS_CHANGED(cls, seed, **kwargs):
        # Используем seed для форсирования обновления при каждом запуске
        return seed

    # Новая чистая архитектура выходов trimesh данных
    RETURN_TYPES = ("TRIMESH", "TRIMESH")
    RETURN_NAMES = ("trimesh_scene", "trimesh_merged")
    OUTPUT_NODE = True
    FUNCTION = "execute"
    CATEGORY = "Antonioilev/Viewers"

    def execute(self, full_path, mode, brightness, seed, show_preview, trimesh=None, fix_lighting=True, soft_edges=True):
        out_path = COMFYUI_OUTPUT_FOLDER or tempfile.gettempdir()
        
        # 1. ЧИСТКА И АВТОРАЗБИВКА ЕДИНОГО ПУТИ (WSL/Windows)
        clean_full_path = full_path.strip().replace("\\", "/")
        
        # Вытаскиваем папку и имя файла из одной строки автоматикой
        path = os.path.dirname(clean_full_path)
        filename = os.path.basename(clean_full_path)
        
        # Защита на случай, если указали только имя файла без папки
        if not path:
            path = "L:/AI_3d/output"  # Твой дефолт по умолчанию, если путь пустой
            
        raw_path = path.strip().replace("\\", "/")
        if raw_path.endswith("/"): raw_path = raw_path[:-1]
        target_dir = os.path.abspath(raw_path)
        
        raw_filename = filename.strip().replace("\\", "/")
        file_base, file_ext = os.path.splitext(raw_filename)
        if not file_ext:
            file_ext = ".fbx"
        
        ext_type = file_ext.lower().replace(".", "")
        
        # 2. ОПРЕДЕЛЕНИЕ РЕЖИМА И ЦВЕТА НОДЫ
        
        # Определяем, сохраняем мы сейчас или нет
        should_save = mode == "Save Only" or (mode == "Auto (Load if empty)" and trimesh is not None)
        
        # Точное определение цветов для каждого режима
        if mode == "Preview Only":
            node_colors = ["#aaaaaa", "#555555"]  # Серый
        elif should_save:
            #node_colors = ["#ccaa00", "#443300"]  # Золотистый
            node_colors = ["#ff0000", "#443300"]  # Золотистый
        elif mode == "Load Only":
            node_colors = ["#52339b", "#2a1a4f"]  # Фиолетовый
        elif mode == "Auto (Load if empty)":
            # В Auto, если мы НЕ сохраняем (значит, будем грузить), цвет фиолетовый
            node_colors = ["#52339b", "#2a1a4f"]  # Фиолетовый
        else:
            # Защитный цвет на случай ошибки (оставим фиолетовым)
            node_colors = ["#52339b", "#2a1a4f"]
        
        current_meshes = []
        info_status = ""

        # === ЖЕЛЕЗОБЕТОННЫЙ АДАПТЕР ДЛЯ МЕШЕЙ ИЗ TRELLIS 2.0 ===
        if trimesh is not None:
            # Если пришел словарь от Trellis (например, {'vertices': ..., 'faces': ...})
            if isinstance(trimesh, dict) and "vertices" in trimesh and "faces" in trimesh:
                trimesh = trimesh_module.Trimesh(vertices=trimesh["vertices"], faces=trimesh["faces"])
            # Если пришел словарь, где меши лежат внутри вложенных ключей (Trellis Scene Dict)
            elif isinstance(trimesh, dict):
                extracted_meshes = []
                for k, v in trimesh.items():
                    if isinstance(v, dict) and "vertices" in v and "faces" in v:
                        extracted_meshes.append(trimesh_module.Trimesh(vertices=v["vertices"], faces=v["faces"]))
                    elif hasattr(v, "vertices") and hasattr(v, "faces"):
                        extracted_meshes.append(trimesh_module.Trimesh(vertices=v.vertices, faces=v.faces))
                if extracted_meshes:
                    trimesh = extracted_meshes if len(extracted_meshes) > 1 else extracted_meshes[0]
            # Если пришел кастомный объект меша Trellis, у которого атрибуты доступны через точку
            elif hasattr(trimesh, "vertices") and hasattr(trimesh, "faces") and not hasattr(trimesh, "center"):
                trimesh = trimesh_module.Trimesh(vertices=trimesh.vertices, faces=trimesh.faces)

        # --- БЛОК СОХРАНЕНИЯ (SAVE) ---
        if should_save and trimesh is not None:
            try:
                os.makedirs(target_dir, exist_ok=True)
                full_save_path = os.path.join(target_dir, file_base + file_ext)
                
                if isinstance(trimesh, trimesh_module.Scene):
                    export_scene = trimesh
                else:
                    export_scene = trimesh_module.Scene()
                    meshes = trimesh if isinstance(trimesh, list) else [trimesh]
                    for i, m in enumerate(meshes):
                        export_scene.add_geometry(m, node_name=f"part_{i:02d}")

                if ext_type == "fbx":
                    fd, temp_glb = tempfile.mkstemp(suffix='.glb')
                    os.close(fd)
                    try:
                        export_scene.export(temp_glb)
                        # Используем Assimp для конвертации в FBX (сохранение костей/весов если есть)
                        cmd = ["assimp", "export", temp_glb, full_save_path]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode != 0: raise Exception(result.stderr)
                        print(f">>> [Antonioilev] SUCCESS FBX SAVE: {full_save_path}")
                    finally:
                        if os.path.exists(temp_glb): os.remove(temp_glb)
                else:
                    export_scene.export(full_save_path)
                    print(f">>> [Antonioilev] SUCCESS SAVED: {full_save_path}")

                current_meshes = list(export_scene.geometry.values())
                info_status = f"Saved {ext_type.upper()}"
            except Exception as e:
                print(f">>> [Antonioilev] SAVE ERROR: {str(e)}")
                current_meshes = trimesh if isinstance(trimesh, list) else [trimesh]
                info_status = "Save Error"

        # --- БЛОК ЗАГРУЗКИ (LOAD) ---
        else:
            found_file = None
            # Если режим "Preview Only", мы полностью игнорируем диск и файлы
            if mode != "Preview Only":
                potential_exts = [file_ext, ".fbx", ".glb", ".obj", ".FBX", ".GLB", ".OBJ"]
                for ext in potential_exts:
                    test_path = os.path.join(target_dir, file_base + ext)
                    if os.path.exists(test_path):
                        found_file = test_path
                        break
            
            if found_file:
                try:
                    f_ext = os.path.splitext(found_file)[1].lower()
                    if f_ext == ".fbx":
                        print(f">>> [Antonioilev] FBX Load via Assimp Bridge...")
                        fd, temp_glb = tempfile.mkstemp(suffix='.glb')
                        os.close(fd)
                        try:
                            cmd = ["assimp", "export", found_file, temp_glb]
                            result = subprocess.run(cmd, capture_output=True, text=True)
                            if result.returncode == 0:
                                loaded = trimesh_module.load(temp_glb)
                            else:
                                raise Exception(result.stderr)
                        finally:
                            if os.path.exists(temp_glb): os.remove(temp_glb)
                    else:
                        loaded = trimesh_module.load(found_file)
                    
                    if isinstance(loaded, trimesh_module.Scene):
                        current_meshes = list(loaded.geometry.values())
                    else:
                        current_meshes = [loaded]
                    print(f">>> [Antonioilev] SUCCESS LOADED: {found_file}")
                    info_status = f"Loaded {f_ext.upper()}"
                except Exception as e:
                    print(f">>> [Antonioilev] LOAD FAILED: {str(e)}")
                    if trimesh is None:
                        return {"ui": {"color": node_colors}, "result": (None, None)}
            
            # Если файл на диске не найден/пропущен, но на входе ЕСТЬ меш
            if not found_file or not current_meshes:
                if trimesh is not None:
                    if isinstance(trimesh, trimesh_module.Scene):
                        current_meshes = list(trimesh.geometry.values())
                    else:
                        current_meshes = trimesh if isinstance(trimesh, list) else [trimesh]
                    
                    if mode == "Preview Only":
                        info_status = "Pure Preview Mode (No Touch Disk)"
                    else:
                        info_status = "Trellis Live Stream Preview"
                else:
                    return {"ui": {"color": node_colors}, "result": (None, None)}

        # --- ПОДГОТОВКА СТРУКТУР ДАННЫХ ВЫХОДОВ ---
        trimesh_scene = trimesh_module.Scene()
        processed_elements = []
        total_verts = 0
        total_tris = 0  # Инициализируем счетчик треугольников

        for i, m_entry in enumerate(current_meshes):
            total_verts += len(m_entry.vertices)
            total_tris += len(m_entry.faces)  # Считаем полигоны (поли-меши в trimesh всегда триангулированы)
            
            # Упаковываем в полноценную PBR-сцену для верхнего технологичного выхода
            trimesh_scene.add_geometry(m_entry, node_name=f"node_{i}")

            # Подготовка копии для потенциального превью
            m = m_entry.copy()
            if soft_edges:
                m.face_normals = None
                m.vertex_normals = None 
            if fix_lighting:
                m.fix_normals()
                if hasattr(m.visual, 'material'):
                    mat = m.visual.material
                    if hasattr(mat, 'metallicFactor'): mat.metallicFactor = 0.0
                    if hasattr(mat, 'roughnessFactor'): mat.roughnessFactor = 1.0
            m.process(validate=True)
            processed_elements.append(m)

        # Сшиваем нижний совместимый trimesh_merged выход
        try:
            if len(current_meshes) == 1:
                trimesh_merged = current_meshes[0]
            else:
                trimesh_merged = trimesh_module.util.concatenate(current_meshes)
        except Exception as e:
            print(f">>> [Antonioilev] CONCATENATE WARNING: {str(e)}")
            trimesh_merged = current_meshes[0] if current_meshes else None

        # Вывод технической инфы в логи сервера вместо захламления графа портами
        print(f">>>> [Antonioilev] Geometry Processed: {total_verts} verts | {info_status}")

        # --- ИЗОЛИРОВАННОЕ ОТКЛЮЧЕНИЕ ПРЕВЬЮ ---
        # Если превью выключено пользователем, мы возвращаем ТОЛЬКО цвет ноды.
        # Никаких пустых списков ['mesh_file'], чтобы полностью убрать триггеры с фронтенда.
        if not show_preview or not current_meshes:
            return {
                "ui": {"color": node_colors},
                "result": (trimesh_scene, trimesh_merged)
            }

        # --- ЭКСПОРТ ВРЕМЕННОГО ФАЙЛА ДЛЯ СОБСТВЕННОГО JS-ВЬЮВЕРА ---
        render_id = f"{seed}_{int(time.time() * 100)}"
        preview_scene = trimesh_module.Scene()
        for i, g in enumerate(processed_elements):
            preview_scene.add_geometry(g, node_name=f"p_{i}")

        temp_name = f"antonio_preview_{render_id}.glb"
        preview_scene.export(os.path.join(out_path, temp_name), file_type='glb')

        return {
            "ui": {
                "mesh_file": [temp_name],
                "brightness": [brightness],
                "color": node_colors,
                "tri_count": [total_tris]  # Передаем количество треугольников фронтенду
            },
            "result": (trimesh_scene, trimesh_merged)
        }

NODE_CLASS_MAPPINGS = { "Preview3DSaveLoad": Preview3DSaveLoad }
NODE_DISPLAY_NAME_MAPPINGS = { "Preview3DSaveLoad": "👁️💾📂 Preview 3D Save Load" }