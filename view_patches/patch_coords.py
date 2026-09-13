# SPDX-License-Identifier: GPL-3.0-or-later
# Antonioilev - 3D View Save Load Pipeline (Vectorized Diagnostic Stack) - 2026

import os
import time
import glob
import numpy as np
import trimesh as trimesh_module

def validate(input_data):
    """Проверяет, являются ли данные координатами (массив, тензор или список)"""
    if input_data is None:
        return False
    if hasattr(input_data, "shape") or isinstance(input_data, (list, np.ndarray)):
        return True
    return False

def process_sparse_data(coords_input, target_dir, file_base, file_ext, ext_type, mode, should_save, out_path, seed, resolution=128, point_size=1.0):
    """
    Унифицированный процесс для работы с разреженными структурами (Coords/Voxels) через PLY.
    """
    preview_mesh = None
    info_status = ""
    coords = None
    output_coords_payload = None

    coords_ply_file = os.path.join(target_dir, f"{file_base}_coords.ply")

    # --- БЛОК А: ЕСЛИ ДАННЫЕ ПРИШЛИ НА ВХОД (ГЕНЕРАЦИЯ ИЗ ЛИНКА) ---
    if coords_input is not None:
        if hasattr(coords_input, "cpu"):  # PyTorch
            coords = coords_input.detach().cpu().numpy()
        else:
            coords = np.array(coords_input)

        if len(coords.shape) == 2 and coords.shape[1] >= 3:
            coords = coords[:, :3]
        else:
            print(">>> [Antonioilev-Sparse] Error: Invalid coords shape!")
            return None
            
        output_coords_payload = coords_input

    # --- БЛОК Б: ОПЕРАЦИИ С ДИСКОМ (SAVE / LOAD ЧЕРЕЗ PLY) ---
    if should_save and coords is not None:
        try:
            os.makedirs(target_dir, exist_ok=True)
            point_cloud = trimesh_module.points.PointCloud(vertices=coords)
            point_cloud.export(coords_ply_file, file_type='ply')
            
            preview_mesh = _build_voxel_mesh(coords, resolution, point_size)
            print(f">>>> [Antonioilev-Sparse] SUCCESS: Raw Coords saved to PLY: {coords_ply_file}")
            info_status = "Saved Coords (.ply)"
        except Exception as e:
            print(f">>>> [Antonioilev-Sparse] SAVE ERROR: {str(e)}")
            info_status = "Save Error"
    
    elif mode in ["Auto (Load if empty)", "Load Only"] and coords is None:
        if os.path.exists(coords_ply_file):
            try:
                # Используем низкоуровневый загрузчик PLY для чтения только точек
                from trimesh.exchange.ply import load_ply
                with open(coords_ply_file, 'rb') as f:
                    ply_data = load_ply(f)
                
                if 'vertices' in ply_data:
                    coords = ply_data['vertices']
                    output_coords_payload = coords
                    preview_mesh = _build_voxel_mesh(coords, resolution, point_size)
                    print(f">>>> [Antonioilev-Sparse] SUCCESS: Coords loaded from PLY: {coords_ply_file}")
                    info_status = "Loaded Coords (.ply)"
                else:
                    raise ValueError("PLY file does not contain 'vertices' data")
            except Exception as e:
                print(f">>>> [Antonioilev-Sparse] LOAD ERROR: {str(e)}")
                raise RuntimeError(f"[Antonioilev-Sparse] Failed to parse PLY file: {str(e)}")
        else:
            info_status = "File Not Found"
            raise FileNotFoundError(f"[Antonioilev-Sparse] Critical Error: Target Coords file NOT found at path: {coords_ply_file}")
        
    if preview_mesh is None and coords is not None:
        preview_mesh = _build_voxel_mesh(coords, resolution, point_size)
        info_status = "Live Sparse Preview"

    if preview_mesh is None:
        return None

    # --- БЛОК В: СБОРКА РЕЗУЛЬТАТОВ И ПРЕВЬЮ ДЛЯ EDGE ---
    trimesh_scene = trimesh_module.Scene()
    trimesh_scene.add_geometry(preview_mesh, node_name="sparse_voxels")
    trimesh_merged = preview_mesh

    try:
        old_previews = glob.glob(os.path.join(out_path, "antonio_preview_*.glb"))
        for old_f in old_previews:
            if time.time() - os.path.getmtime(old_f) > 300:
                os.remove(old_f)
    except:
        pass

    render_id = f"{seed}_{int(time.time() * 100)}"
    temp_name = f"antonio_preview_{render_id}.glb"
    trimesh_scene.export(os.path.join(out_path, temp_name), file_type='glb')

    calculated_voxels = len(coords) if coords is not None else 0

    try:
        from server import PromptServer
        PromptServer.instance.send_sync("comfy_3d_viewer_message", {
            "type": "SET_VOXEL_SCALE",
            "scale": point_size
        })
    except Exception as e:
        print(f">>>> [Antonioilev-Sparse] WebSocket Sync Error: {str(e)}")
    
    return {
        "temp_name": temp_name,
        "voxel_count": calculated_voxels,
        "data_type": "coords",  
        "result_data": (trimesh_scene, trimesh_merged, output_coords_payload), 
        "has_geometry": True,
        "viewport_context": [{
            "mode": "coords",  # <--- ДОБАВЬТЕ ЭТО
            #"metrics_string": "LATENT MICROSCOPE: VECTOR ACTIVE", 
            "controls": {
                "show_textured_checkbox": False,  
                "show_wireframe_checkbox": False, 
                "show_voxel_scale_slider": True   
            },
            "legend_items": [
                # --- Заголовок 1 ---
                { "label": "Forecast Stable", "type": "header" }, 
                { "label": "Occlusion", "color": "#4affff" },
                { "label": "Density", "color": "#4aff4a" },
                { "label": "Normal Z", "color": "#4a4aff" },
                { "label": "Shell Depth", "color": "#ffff4a" },
                { "label": "Curvature", "color": "#ff4a4a" },
                
                # --- Заголовок 2 (с отступом) ---
                { "label": "Forecast Unstable", "type": "header"},
                { "label": "Self-Overlap", "color": "#371b1b" },
                { "label": "Flipped Normals", "color": "#201068" },
                { "label": "Floating Islands", "color": "#b61598" },
                { "label": "Broken Seams", "color": "#f11843" },
                { "label": "Noise Hazard", "color": "#250259" }
            ]
        }]
    }

def _build_voxel_mesh(coords, resolution_val, point_size=1.0):
    """
    Внутренний высокоскоростной хелпер декомпрессии и векторного спектрального анализа.
    """
    voxel_count = len(coords)
    if voxel_count == 0:
        return trimesh_module.Trimesh()

    raw_coords = coords.astype(np.float32)
    min_bound = np.min(raw_coords, axis=0)
    max_bound = np.max(raw_coords, axis=0)
    size_dims = max_bound - min_bound

    # Определение проекционного сжатия латента
    dead_axis = -1
    for axis_idx in range(3):
        if size_dims[axis_idx] <= 0.1:
            dead_axis = axis_idx
            break

    # Восстановление объемной оболочки (3D Volumetric Shell)
    if dead_axis != -1:
        live_axes = [i for i in range(3) if i != dead_axis]
        base_shell_radius = (size_dims[live_axes[0]] + size_dims[live_axes[1]]) / 6.0
        
        pos_keys = [f"{int(p[live_axes[0]])}_{int(p[live_axes[1]])}" for p in raw_coords]
        from collections import Counter
        density_map = Counter(pos_keys)
        
        visual_coords_list = np.zeros((voxel_count * 2, 3), dtype=np.float32)
        axis_center = min_bound[dead_axis]
        
        # Векторизованно заполняем дублирующие точки объемной оболочки
        for i in range(voxel_count):
            key = f"{int(raw_coords[i, live_axes[0]])}_{int(raw_coords[i, live_axes[1]])}"
            thickness = base_shell_radius * (min(density_map[key], 12) / 12.0)
            
            pt_pos = raw_coords[i].copy()
            pt_pos[dead_axis] = axis_center + thickness
            visual_coords_list[i * 2] = pt_pos
            
            pt_neg = raw_coords[i].copy()
            pt_neg[dead_axis] = axis_center - thickness
            visual_coords_list[i * 2 + 1] = pt_neg
            
        visual_coords = visual_coords_list
    else:
        visual_coords = raw_coords

    final_voxel_count = len(visual_coords)

    # --- ВЕКТОРНЫЙ АНАЛИЗ ПРОСТРАНСТВЕННЫХ МЕТРИК (Scipy cKDTree) ---
    k_neighbors = min(12, final_voxel_count - 1)
    planarity_scores = np.zeros(final_voxel_count, dtype=np.float32)
    density_scores = np.zeros(final_voxel_count, dtype=np.float32)

    if k_neighbors > 3:
        try:
            from scipy.spatial import cKDTree
            kdtree = cKDTree(visual_coords)
        except ImportError:
            from trimesh.voxel.ops import KDTree
            kdtree = KDTree(visual_coords)
        
        # Получаем дистанции и индексы всех соседей за один проход на Си-уровне
        neighbor_dists, neighbor_indices = kdtree.query(visual_coords, k=k_neighbors)

        # 1. Расчет плотности (Green) через среднее расстояние до 6 ближайших соседей
        mean_dists = np.mean(neighbor_dists[:, :6], axis=1)
        d_min, d_max = np.min(mean_dists), np.max(mean_dists)
        if d_max > d_min:
            density_scores = 1.0 - (mean_dists - d_min) / (d_max - d_min + 1e-5)
        else:
            density_scores = np.ones(final_voxel_count, dtype=np.float32)

        # 2. Тензорный анализ планарности (Red)
        for i in range(final_voxel_count):
            neighbor_pts = visual_coords[neighbor_indices[i]]
            centered = neighbor_pts - np.mean(neighbor_pts, axis=0)
            cov = np.dot(centered.T, centered) / k_neighbors
            eigenvalues = np.linalg.eigvalsh(cov)
            
            l3, l2, l1 = eigenvalues[0], eigenvalues[2], eigenvalues[1] # Сортировка по осям
            if l1 > 1e-7:
                planarity_scores[i] = (l2 - l3) / l1

    # Нормализация планарности
    p_max, p_min = np.max(planarity_scores), np.min(planarity_scores)
    normalized_planarity = (planarity_scores - p_min) / (p_max - p_min + 1e-5) if p_max > p_min else planarity_scores

    # 3. Анатомический Z-градиент (Blue) для подмены тяжелой кластеризации
    z_vals = visual_coords[:, 2]
    z_min, z_max = z_vals.min(), z_vals.max()
    normalized_z = (z_vals - z_min) / (z_max - z_min + 1e-5) if z_max > z_min else np.zeros(final_voxel_count)

    # --- ВЕКТОРНЫЙ ЦВЕТОВОЙ ДВИЖОК (БЕЗ ЦИКЛОВ FOR) ---
    r_channel = (normalized_planarity * 255).astype(np.uint8) # Высокий SLTI риск -> Краснее
    g_channel = (density_scores * 160).astype(np.uint8)       # Высокая плотность массы -> Зеленее
    b_channel = (normalized_z * 255).astype(np.uint8)         # Высота объекта (Ноги -> Голова) -> Синее
    a_channel = np.full(final_voxel_count, 255, dtype=np.uint8)

    # Склеиваем каналы в один массив цветов face_colors [N, 4]
    voxel_rgba = np.stack([r_channel, g_channel, b_channel, a_channel], axis=1)

    # --- БЫСТРАЯ СБОРКА ГЕОМЕТРИИ ---
    box_scale = float(point_size)
    base_box = trimesh_module.creation.box(extents=[box_scale, box_scale, box_scale])
    
    translations = np.eye(4)[np.newaxis, :, :].repeat(final_voxel_count, axis=0)
    translations[:, :3, 3] = visual_coords

    voxel_meshes = []
    for i in range(final_voxel_count):
        box_copy = base_box.copy().apply_transform(translations[i])
        box_copy.visual.face_colors = voxel_rgba[i]
        voxel_meshes.append(box_copy)

    return trimesh_module.util.concatenate(voxel_meshes)