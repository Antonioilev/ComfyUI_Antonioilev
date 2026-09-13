# SPDX-License-Identifier: GPL-3.0-or-later
# Antonioilev - 3D View Save Load Pipeline (Trimesh & FBX Patch) - 2026

import trimesh as trimesh_module
import os
import time
import tempfile
import subprocess
import glob
import numpy as np

def validate(input_data):
    """Проверяет, являются ли данные мешем/тримешем"""
    if input_data is None:
        return False
    if isinstance(input_data, dict) and ("vertices" in input_data or "geometry" in input_data):
        return True
    if hasattr(input_data, "vertices") and hasattr(input_data, "faces"):
        return True
    return False

def process_trimesh_data(trimesh_input, target_dir, file_base, file_ext, ext_type, mode, should_save, soft_edges, fix_lighting, out_path, seed, env_hdr=None):
    import trimesh as trimesh_module
    current_meshes = []
    info_status = ""

    # === ЖЕЛЕЗОБЕТОННЫЙ АДАПТЕР ДЛЯ МЕШЕЙ ИЗ TRELLIS 2.0 ===
    # ================================
    # 🚨 SINGLE MESH FAST PASS (UV SAFE & SAVE FIXED)
    # ================================
    if isinstance(trimesh_input, trimesh_module.Trimesh):
        if hasattr(trimesh_input, "visual"):
            # ПРИНУДИТЕЛЬНЫЙ ПЕРЕХВАТ PBR-СЕТА ДЛЯ FAST PASS
            if hasattr(trimesh_input.visual, 'material') and trimesh_input.visual.material is not None:
                src_mat = trimesh_input.visual.material
                pbr_mat = src_mat if isinstance(src_mat, trimesh_module.visual.material.PBRMaterial) else trimesh_module.visual.material.PBRMaterial()

                # Универсальный перенос всех текстурных каналов PBR
                if hasattr(src_mat, 'image') and src_mat.image is not None:
                    pbr_mat.baseColorTexture = src_mat.image

                # Мапаем все возможные варианты названий текстур в Trimesh PBRMaterial
                texture_mappings = {
                    'baseColorTexture': ['baseColorTexture', 'base_color_texture', 'image'],
                    'metallicRoughnessTexture': [
                        'metallicRoughnessTexture', 
                        'metallic_roughness_texture',
                        'metallicTexture',      # на всякий случай
                        'roughnessTexture'
                    ],
                    'normalTexture': ['normalTexture', 'normal_texture'],
                    'emissiveTexture': ['emissiveTexture', 'emissive_texture']
                }

                for target_attr, source_attrs in texture_mappings.items():
                    for attr in source_attrs:
                        if hasattr(src_mat, attr):
                            val = getattr(src_mat, attr)
                            if val is not None:
                                setattr(pbr_mat, target_attr, val)
                                break
                
                # Корректируем множители, если текстуры подключены
                if getattr(pbr_mat, 'metallicRoughnessTexture', None) is not None:
                    pbr_mat.metallicFactor = 1.0
                    pbr_mat.roughnessFactor = 1.0
                
                # Защита emissiveFactor: если текстура есть, а фактора нет или он ноль — ставим единицы
                if getattr(pbr_mat, 'emissiveTexture', None) is not None:
                    if getattr(pbr_mat, 'emissiveFactor', None) is None or \
                       (isinstance(pbr_mat.emissiveFactor, (list, tuple, np.ndarray)) and \
                        np.allclose(pbr_mat.emissiveFactor, 0)):
                        pbr_mat.emissiveFactor = [1.0, 1.0, 1.0]
                
                trimesh_input.visual.material = pbr_mat

            current_meshes = [trimesh_input]
            info_status = ""

            # ХИРУРГИЧЕСКИЙ ВШИТЫЙ БЛОК СОХРАНЕНИЯ ДЛЯ FAST PASS
            if should_save:
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    full_save_path = os.path.join(target_dir, file_base + file_ext)
                    
                    if ext_type == "glb":
                        trimesh_input.export(full_save_path, file_type="glb")
                        print(f">>> [Antonioilev FastSave] SUCCESS SAFE GLB: {full_save_path}")
                    elif ext_type == "fbx":
                        fd, temp_glb = tempfile.mkstemp(suffix='.glb')
                        os.close(fd)
                        try:
                            trimesh_input.export(temp_glb, file_type="glb")
                            cmd = ["assimp", "export", temp_glb, full_save_path]
                            result = subprocess.run(cmd, capture_output=True, text=True)
                            if result.returncode != 0: raise Exception(result.stderr)
                            print(f">>> [Antonioilev FastSave] SUCCESS FBX SAVE via GLB Bridge: {full_save_path}")
                        finally:
                            if os.path.exists(temp_glb): os.remove(temp_glb)
                    info_status = f"Saved {ext_type.upper()}"
                except Exception as e:
                    print(f">>> [Antonioilev FastSave] ERROR: {str(e)}")
                    info_status = "Save Error"

            # Генерируем превью для вьюпорта, как и раньше
            render_id = f"{seed}_{int(time.time() * 100)}"
            temp_name = f"antonio_preview_{render_id}.glb"
            preview_scene = trimesh_module.Scene([trimesh_input])
            preview_scene.export(os.path.join(out_path, temp_name), file_type='glb')

            panel_display_text = f"Tris: {len(trimesh_input.faces):,}"
            if info_status: panel_display_text += f" | {info_status}"
            
            # 1. Достаем имя файла EXR, если он передан в ноду (например, через вход env_hdr)
            env_url_path = ""
            if env_hdr is not None:
                # Здесь берется имя файла из объекта или параметров (подставь свою логику получения имени файла EXR)
                env_filename = getattr(env_hdr, "filename", "studio.exr") 
                # Формируем стандартный для ComfyUI путь для скачивания файла через веб-сервер
                env_url_path = f"/view?filename={env_filename}&type=output&subfolder="
            
            return {
                "temp_name": temp_name,
                "tri_count": [len(trimesh_input.faces)],
                "data_type": "mesh",
                "result_data": (trimesh_module.Scene([trimesh_input]), trimesh_input),
                "has_geometry": True,
                "viewport_context": [{
                    "mode": "trimesh",
                    "metrics_string": panel_display_text,
                    "vertex_count": len(trimesh_input.vertices),
                    "triangle_count": len(trimesh_input.faces),
                    "controls": {
                        "show_textured_checkbox": True,
                        "show_wireframe_checkbox": True,
                        "show_voxel_scale_slider": False,
                        "env_url": env_url_path,
                        "env_exposure": 1.2,
                        "env_intensity": 1.8
                    }
                }]
            }
    
    
    if trimesh_input is not None:
        if isinstance(trimesh_input, dict) and "vertices" in trimesh_input and "faces" in trimesh_input:
            trimesh_input = trimesh_module.Trimesh(vertices=trimesh_input["vertices"], faces=trimesh_input["faces"])
        elif isinstance(trimesh_input, dict):
            extracted_meshes = []
            for k, v in trimesh_input.items():
                if isinstance(v, dict) and "vertices" in v and "faces" in v:
                    extracted_meshes.append(trimesh_module.Trimesh(vertices=v["vertices"], faces=v["faces"]))
                elif hasattr(v, "vertices") and hasattr(v, "faces"):
                    extracted_meshes.append(trimesh_module.Trimesh(vertices=v.vertices, faces=v.faces))
            if extracted_meshes:
                trimesh_input = extracted_meshes if len(extracted_meshes) > 1 else extracted_meshes[0]
        elif hasattr(trimesh_input, "vertices") and hasattr(trimesh_input, "faces") and not hasattr(trimesh_input, "center"):
            trimesh_input = trimesh_module.Trimesh(vertices=trimesh_input.vertices, faces=trimesh_input.faces)

    # --- БЛОК СОХРАНЕНИЯ (SAVE) ---
    if should_save and trimesh_input is not None:
        try:
            os.makedirs(target_dir, exist_ok=True)
            full_save_path = os.path.join(target_dir, file_base + file_ext)
            
            # 1. АВТОМАТИЧЕСКАЯ РАСПАКОВКА: Нам нужен именно меш, в чем бы он ни лежал
            target_mesh = None
            is_single_mesh = False

            if isinstance(trimesh_input, trimesh_module.Trimesh):
                target_mesh = trimesh_input
                is_single_mesh = True
            elif isinstance(trimesh_input, trimesh_module.Scene):
                if len(trimesh_input.geometry) == 1:
                    target_mesh = list(trimesh_input.geometry.values())[0]
                    is_single_mesh = True
            elif isinstance(trimesh_input, list) and len(trimesh_input) == 1:
                if isinstance(trimesh_input[0], trimesh_module.Trimesh):
                    target_mesh = trimesh_input[0]
                    is_single_mesh = True
            elif isinstance(trimesh_input, dict) and len(trimesh_input) == 1:
                first_val = list(trimesh_input.values())[0]
                if isinstance(first_val, trimesh_module.Trimesh):
                    target_mesh = first_val
                    is_single_mesh = True

            # 2. КЕЙС ОДИНОЧНОГО МЕША (Твой персонаж / кусок пайплайна)
            if is_single_mesh and target_mesh is not None:
                print(">>> [Antonioilev Save] DETECTED: Single Mesh extracted. Using ultra-safe GLB bridge.")
                
                # ПРИНУДИТЕЛЬНЫЙ ПЕРЕХВАТ PBR-СЕТА ПРИ СОХРАНЕНИИ
                if hasattr(target_mesh, 'visual') and hasattr(target_mesh.visual, 'material') and target_mesh.visual.material is not None:
                    src_mat = target_mesh.visual.material
                    if not isinstance(src_mat, trimesh_module.visual.material.PBRMaterial):
                        pbr_mat = trimesh_module.visual.material.PBRMaterial()
                        if hasattr(src_mat, 'image') and src_mat.image is not None:
                            pbr_mat.baseColorTexture = src_mat.image
                        
                        texture_mappings = {
                            'baseColorTexture': ['baseColorTexture', 'base_color_texture', 'image'],
                            'metallicRoughnessTexture': [
                                'metallicRoughnessTexture', 
                                'metallic_roughness_texture',
                                'metallicTexture',
                                'roughnessTexture'
                            ],
                            'normalTexture': ['normalTexture', 'normal_texture'],
                            'emissiveTexture': ['emissiveTexture', 'emissive_texture']
                        }
                        for target_attr, source_attrs in texture_mappings.items():
                            for attr in source_attrs:
                                if hasattr(src_mat, attr) and getattr(src_mat, attr) is not None:
                                    setattr(pbr_mat, target_attr, getattr(src_mat, attr))
                                    break
                        
                        # Корректируем множители, если текстуры подключены
                        if getattr(pbr_mat, 'metallicRoughnessTexture', None) is not None:
                            pbr_mat.metallicFactor = 1.0
                            pbr_mat.roughnessFactor = 1.0
                        
                        # Защита emissiveFactor: если текстура есть, а фактора нет или он ноль — ставим единицы
                        if getattr(pbr_mat, 'emissiveTexture', None) is not None:
                            if getattr(pbr_mat, 'emissiveFactor', None) is None or \
                               (isinstance(pbr_mat.emissiveFactor, (list, tuple, np.ndarray)) and \
                                np.allclose(pbr_mat.emissiveFactor, 0)):
                                pbr_mat.emissiveFactor = [1.0, 1.0, 1.0]
                        
                        trimesh_input.visual.material = pbr_mat

                if ext_type == "glb":
                    # Прямой экспорт меша без оберток
                    target_mesh.export(full_save_path, file_type="glb")
                    print(f">>> [Antonioilev] SUCCESS SAFE GLB: {full_save_path}")
                elif ext_type == "fbx":
                    # Пишем временный идеальный GLB и конвертим его через assimp
                    fd, temp_glb = tempfile.mkstemp(suffix='.glb')
                    os.close(fd)
                    try:
                        target_mesh.export(temp_glb, file_type="glb")
                        cmd = ["assimp", "export", temp_glb, full_save_path]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode != 0: raise Exception(result.stderr)
                        print(f">>> [Antonioilev] SUCCESS FBX SAVE via GLB Bridge: {full_save_path}")
                    finally:
                        if os.path.exists(temp_glb): os.remove(temp_glb)
                        
                # Нам нужно воссоздать сцену для последующего кода отображения вьюпорта
                export_scene = trimesh_module.Scene()
                export_scene.add_geometry(target_mesh, node_name="part_00")

            # 3. СЛОЖНЫЙ КЕЙС (Если реально пришла сцена из кучи объектов — оставляем старый путь)
            else:
                print(">>> [Antonioilev Save] DETECTED: True Complex Scene. Using standard pipeline.")
                if isinstance(trimesh_input, trimesh_module.Scene):
                    export_scene = trimesh_input
                else:
                    export_scene = trimesh_module.Scene()
                    meshes = trimesh_input if isinstance(trimesh_input, list) else [trimesh_input]
                    for i, m in enumerate(meshes):
                        export_scene.add_geometry(m, node_name=f"part_{i:02d}")

                if ext_type == "fbx":
                    fd, temp_glb = tempfile.mkstemp(suffix='.glb')
                    os.close(fd)
                    try:
                        export_scene.export(temp_glb)
                        cmd = ["assimp", "export", temp_glb, full_save_path]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode != 0: raise Exception(result.stderr)
                        print(f">>> [Antonioilev] SUCCESS FBX SCENE SAVE: {full_save_path}")
                    finally:
                        if os.path.exists(temp_glb): os.remove(temp_glb)
                else:
                    export_scene.export(full_save_path)
                    print(f">>> [Antonioilev] SUCCESS SAVED: {full_save_path}")

            current_meshes = list(export_scene.geometry.values())
            info_status = f"Saved {ext_type.upper()}"
            
        except Exception as e:
            print(f">>> [Antonioilev] SAVE ERROR: {str(e)}")
            current_meshes = trimesh_input if isinstance(trimesh_input, list) else [trimesh_input]
            info_status = "Save Error"

    # --- БЛОК ЗАГРУЗКИ (LOAD) ---
    else:
        found_file = None
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
                if trimesh_input is None:
                    return None
        
        if not found_file or not current_meshes:
            if trimesh_input is not None:
                if isinstance(trimesh_input, trimesh_module.Scene):
                    current_meshes = list(trimesh_input.geometry.values())
                else:
                    current_meshes = trimesh_input if isinstance(trimesh_input, list) else [trimesh_input]
                
                if mode == "Preview Only":
                    info_status = "Pure Preview Mode (No Touch Disk)"
                else:
                    info_status = "Trellis Live Stream Preview"
            else:
                return None

    # --- ПОДГОТОВКА СТРУКТУР ДАННЫХ ВЫХОДОВ ---
    trimesh_scene = trimesh_module.Scene()
    processed_elements = []
    total_verts = 0
    total_tris = 0

    for i, m_entry in enumerate(current_meshes):
        # Жесткая распаковка под-сцен, если assimp/trellis закинул сцену внутрь списка мешей
        if isinstance(m_entry, trimesh_module.Scene):
            sub_meshes = list(m_entry.geometry.values())
        else:
            sub_meshes = [m_entry]

        for sub_m in sub_meshes:
            # Считаем только то, у чего реально есть вершины и грани
            if hasattr(sub_m, "vertices") and hasattr(sub_m, "faces"):
                total_verts += len(sub_m.vertices)
                total_tris += len(sub_m.faces)
            
            # Сохраняем визуальные данные перед манипуляциями
            visual_data = sub_m.visual.copy() if hasattr(sub_m, "visual") else None
            
            trimesh_scene.add_geometry(sub_m, node_name=f"node_{i}_{len(processed_elements)}")

            m = sub_m.copy()
            # ПРИНУДИТЕЛЬНО ВОССТАНАВЛИВАЕМ ВИЗУАЛЬНЫЕ ДАННЫЕ (TEXTUREС/UV)
            if visual_data is not None:
                m.visual = visual_data

            # ПРИНУДИТЕЛЬНЫЙ ПЕРЕХВАТ PBR-СЕТА ПРИ ОБРАБОТКЕ ЭЛЕМЕНТОВ
            if hasattr(m, 'visual') and hasattr(m.visual, 'material') and m.visual.material is not None:
                src_mat = m.visual.material
                if not isinstance(src_mat, trimesh_module.visual.material.PBRMaterial):
                    pbr_mat = trimesh_module.visual.material.PBRMaterial()
                    if hasattr(src_mat, 'image') and src_mat.image is not None:
                        pbr_mat.baseColorTexture = src_mat.image
                    
                    texture_mappings = {
                        'baseColorTexture': ['baseColorTexture', 'base_color_texture', 'image'],
                        'metallicRoughnessTexture': [
                            'metallicRoughnessTexture', 
                            'metallic_roughness_texture',
                            'metallicTexture',
                            'roughnessTexture'
                        ],
                        'normalTexture': ['normalTexture', 'normal_texture'],
                        'emissiveTexture': ['emissiveTexture', 'emissive_texture']
                    }
                    for target_attr, source_attrs in texture_mappings.items():
                        for attr in source_attrs:
                            if hasattr(src_mat, attr) and getattr(src_mat, attr) is not None:
                                setattr(pbr_mat, target_attr, getattr(src_mat, attr))
                                break
                    
                    if getattr(pbr_mat, 'metallicRoughnessTexture', None) is not None:
                            pbr_mat.metallicFactor = 1.0
                            pbr_mat.roughnessFactor = 1.0
                        
                    if getattr(pbr_mat, 'emissiveTexture', None) is not None:
                        if getattr(pbr_mat, 'emissiveFactor', None) is None or \
                           (isinstance(pbr_mat.emissiveFactor, (list, tuple, np.ndarray)) and \
                            np.allclose(pbr_mat.emissiveFactor, 0)):
                            pbr_mat.emissiveFactor = [1.0, 1.0, 1.0]
                    
                    target_mesh.visual.material = pbr_mat
            
            if soft_edges:
                m.face_normals = None
                m.vertex_normals = None 
            
            if fix_lighting:
                m.fix_normals()
                # Безопасно проверяем PBR-факторы только если текстуры не заданы явно
                if hasattr(m.visual, 'material') and m.visual.material is not None:
                    mat = m.visual.material
                    if hasattr(mat, 'metallicFactor') and getattr(mat, 'metallicRoughnessTexture', None) is None: 
                        mat.metallicFactor = 0.1
                    if hasattr(mat, 'roughnessFactor') and getattr(mat, 'metallicRoughnessTexture', None) is None: 
                        mat.roughnessFactor = 0.8
            
            m.process(validate=True)
            processed_elements.append(m)

    try:
        if len(current_meshes) == 1:
            trimesh_merged = current_meshes[0]
        else:
            trimesh_merged = trimesh_module.util.concatenate(current_meshes)
    except Exception as e:
        print(f">>> [Antonioilev] CONCATENATE WARNING: {str(e)}")
        trimesh_merged = current_meshes[0] if current_meshes else None

    print(f">>>> [Antonioilev] Geometry Processed: {total_verts} verts | {info_status}")

    # МЯГКАЯ ОЧИСТКА СТАРЫХ КЭШЕЙ ПРЕВЬЮ ПЕРЕД ЗАПИСЬЮ НОВОГО
    try:
        old_previews = glob.glob(os.path.join(out_path, "antonio_preview_*.glb"))
        for old_f in old_previews:
            if time.time() - os.path.getmtime(old_f) > 300:
                os.remove(old_f)
    except:
        pass

    # Экспорт временного .glb для фронтенда
    render_id = f"{seed}_{int(time.time() * 100)}"
    preview_scene = trimesh_module.Scene()
    for i, g in enumerate(processed_elements):
        preview_scene.add_geometry(g, node_name=f"p_{i}")

    temp_name = f"antonio_preview_{render_id}.glb"
    preview_scene.export(os.path.join(out_path, temp_name), file_type='glb')

    # Формируем чистую строку статуса на бэкенде
    panel_display_text = f"Tris: {total_tris:,}"
    if info_status:
        panel_display_text += f" | {info_status}"

    assert not hasattr(trimesh_input, "Scene") or True
    print("[UV CHECK] merged type:", type(trimesh_input))
    if hasattr(trimesh_input, "visual"):
        print("[UV CHECK] has uv:", hasattr(trimesh_input.visual, "uv"))
        
    # =====================================================
    # ПРИЕМ И ПРИМЕНЕНИЕ HDR В МЕТАДАННЫЕ
    # =====================================================
    if env_hdr is not None:
        try:
            hdr_np = env_hdr[0].cpu().numpy().copy()
            # Применяем к сцене и к объединенному мешу на всякий случай
            for target_obj in [trimesh_scene, trimesh_merged]:
                if target_obj is not None:
                    if not hasattr(target_obj, "metadata") or target_obj.metadata is None:
                        target_obj.metadata = {}
                    if isinstance(target_obj.metadata, dict):
                        target_obj.metadata["env_hdr"] = hdr_np
            print(">>>> [3D View Patch] HDR Environment Map attached successfully")
        except Exception as e:
            print(f">>>> [3D View Patch] HDR attach failed: {str(e)}")
    
    # 1. Достаем имя файла EXR, если он передан в ноду (например, через вход env_hdr)
    env_url_path = ""
    if env_hdr is not None:
        # Здесь берется имя файла из объекта или параметров (подставь свою логику получения имени файла EXR)
        env_filename = getattr(env_hdr, "filename", "studio.exr") 
        # Формируем стандартный для ComfyUI путь для скачивания файла через веб-сервер
        env_url_path = f"/view?filename={env_filename}&type=output&subfolder="


    # ВОЗВРАЩАЕМ СТАНДАРТИЗИРОВАННЫЙ СЛОВАРЬ С ИНКАПСУЛИРОВАННЫМ UI КОНТЕКСТОМ
    return {
        "temp_name": temp_name,
        "tri_count": [total_tris],
        "data_type": "mesh",
        "result_data": (trimesh_scene, trimesh_merged),
        "has_geometry": bool(current_meshes),
                
        # СИНХРОНИЗИРОВАННЫЙ СЛОВАРЬ С НОВЫМ JS-МЕНЕДЖЕРОМ ВЬЮПОРТА
        "viewport_context": [{
            "mode": "trimesh",
            "metrics_string": panel_display_text, 
            "vertex_count": total_verts,            # Передаем точное число вершин
            "triangle_count": total_tris,           # Передаем точное число полигонов (tris)
            "controls": {
                "show_textured_checkbox": True,     
                "show_wireframe_checkbox": True,    
                "show_voxel_scale_slider": False,
                "env_url": env_url_path,
                "env_exposure": 1.2,
                "env_intensity": 1.8                
            }
        }]
    }