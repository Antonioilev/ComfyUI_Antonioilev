# SPDX-License-Identifier: GPL-3.0-or-later
# Antonioilev - 3D View Save Load Pipeline (Shape Slat / Gaussians Patch) - 2026

import os
import time
import json
import torch
import numpy as np
import struct
import trimesh as trimesh_module

# =========================================================
# CPU SAFE MOVE (LOSSLESS)
# =========================================================
def move_to_cpu(obj):
    if isinstance(obj, torch.Tensor):
        return obj.detach().cpu()
    elif isinstance(obj, dict):
        return {k: move_to_cpu(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [move_to_cpu(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(move_to_cpu(v) for v in obj)
    return obj

# =========================================================
# BASE PATH
# =========================================================
def get_base(target_dir, file_base):
    return os.path.join(target_dir, file_base)

# =========================================================
# MAIN PIPELINE PROCESSOR
# =========================================================
def process_slat_data(
    slat_input,
    target_dir,
    file_base,
    file_ext,
    ext_type,
    mode,
    should_save,
    out_path,
    seed,
    point_size=1.0  # <--- Добавили аргумент
):
    # ОБЯЗАТЕЛЬНО ИНИЦИАЛИЗИРУЕМ ВСЕ ПЕРЕМЕННЫЕ
    slat_data = None
    preview_filename = "antonio_preview.glb"
    preview_glb = os.path.join(out_path, preview_filename)
    ply_file = os.path.join(target_dir, file_base + ".ply") # ДОБАВЬ ЭТО
    meta_file = os.path.join(target_dir, file_base + ".meta.json") # И ЭТО
    # 1. ПОДГОТОВКА ПУТЕЙ
    try:
        os.makedirs(target_dir, exist_ok=True)
        # Определяем переменные до того, как они понадобятся
        preview_filename = "antonio_preview.glb"
        preview_glb = os.path.join(out_path, preview_filename)
        # Если get_base не определена в патче, используй os.path.join
        base = os.path.join(target_dir, file_base)
    except Exception as e:
        print(f">>>> [Antonioilev-Slat] Path preparation failed: {str(e)}")
        return None

    # 2. ЛОГИКА ЗАГРУЗКИ / ПРОВЕРКИ
    tslat_file = os.path.join(target_dir, file_base + ".tslat")
    
    if slat_input is None:
        if mode in ["Auto (Load if empty)", "Load Only"] and os.path.exists(tslat_file):
            try:
                print(f">>>> [Antonioilev-Slat] Loading from disk: {tslat_file}")
                loaded = torch.load(tslat_file, map_location="cpu", weights_only=False)
                if isinstance(loaded, dict) and "slat" in loaded:
                    slat_input = loaded["slat"]
                    seed = loaded.get("seed", seed)
                else:
                    slat_input = loaded
            except Exception as e:
                print(f">>>> [Antonioilev-Slat] Error reading TSLAT: {str(e)}")
                return None
        elif mode == "Save Only":
            # В режиме Save Only мы продолжаем выполнение, даже если вход None.
            # Патч просто перейдет к логике сохранения, когда данные поступят.
            print(f">>>> [Antonioilev-Slat] Save Only mode: Waiting for input...")
        else:
            # Если не Save Only и данных нет - это критическая ошибка
            print(">>>> [Antonioilev-Slat] ERROR: Input data is None and no file to load!")
            return None

    # 3. ЭКСТРАКЦИЯ И ОБРАБОТКА ДАННЫХ
    if slat_input is not None:
        raw_positions = None
        raw_colors = None

        if hasattr(slat_input, "coords"): raw_positions = slat_input.coords
        elif hasattr(slat_input, "positions"): raw_positions = slat_input.positions
        elif isinstance(slat_input, dict):
            raw_positions = slat_input.get("coords") or slat_input.get("position")
            raw_colors = slat_input.get("rgb") or slat_input.get("color")

        if hasattr(slat_input, "colors"): raw_colors = slat_input.colors
        elif hasattr(slat_input, "rgb"): raw_colors = slat_input.rgb

        if raw_positions is None:
            print(">>>> [Antonioilev-Slat] ERROR: Positions data is missing!")
            return None

    if isinstance(raw_positions, torch.Tensor):
        positions = raw_positions.detach().cpu().numpy()
    else:
        positions = np.array(raw_positions)

    if raw_colors is not None:
        if isinstance(raw_colors, torch.Tensor):
            colors = raw_colors.detach().cpu().numpy()
        else:
            colors = np.array(raw_colors)
    else:
        colors = None

    # Корректировка размерностей координат (сброс батч-индекса, если есть)
    if len(positions.shape) == 2 and positions.shape[1] == 4:
        positions = positions[:, 1:]

    # Быстрая нормализация цвета по контракту пайплайна
    if colors is None:
        colors = np.ones_like(positions) * 0.8
    elif colors.max() > 1.0:
        colors = colors / 255.0

    positions = positions.astype(np.float32)
    colors = colors.astype(np.float32)
    num_splats = len(positions)

    # =====================================================
    # SAVE MASTER TSLAT
    # =====================================================
    if should_save and mode != "load":
        try:
            # Предотвращаем утечку памяти: чистим тензоры перед дампом на диск
            clean_slat = move_to_cpu(slat_input)
            torch.save(
                {
                    "version": 1,
                    "type": "trellis_shape_slat",
                    "seed": seed,
                    "splat_count": num_splats,
                    "slat": clean_slat
                },
                tslat_file
            )
        except Exception as e:
            print(f">>>> [Antonioilev-Slat] Master save failed: {str(e)}")

    # =====================================================
    # PRODUCTION READY FAST GLB BUILD
    # =====================================================
    interleaved = np.empty((num_splats, 6), dtype=np.float32)
    interleaved[:, 0:3] = positions
    interleaved[:, 3:6] = colors

    buffer_data = interleaved.tobytes()  

    gltf_json = {
        "asset": {"version": "2.0", "generator": "Antonioilev_Slat_Fast_Path"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "COLOR_0": 1
                },
                "mode": 0  # POINTS
            }]
        }],
        "accessors": [
            {
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5126,
                "count": num_splats,
                "type": "VEC3",
                "max": positions.max(axis=0).tolist() if num_splats > 0 else [0, 0, 0],
                "min": positions.min(axis=0).tolist() if num_splats > 0 else [0, 0, 0]
            },
            {
                "bufferView": 0,
                "byteOffset": 12,
                "componentType": 5126,
                "count": num_splats,
                "type": "VEC3"
            }
        ],
        "bufferViews": [{
            "buffer": 0,
            "byteOffset": 0,
            "byteLength": len(buffer_data),
            "byteStride": 24
        }],
        "buffers": [{
            "byteLength": len(buffer_data)
        }]
    }

    json_str = json.dumps(gltf_json, separators=(",", ":")).encode("utf-8")
    while len(json_str) % 4:
        json_str += b" "

    # Формируем структуру GLB: Заголовок + JSON чанк + BIN чанк
    glb_content = (
        struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(json_str) + 8 + len(buffer_data))
        + struct.pack("<II", len(json_str), 0x4E4F534A) 
        + json_str 
        + struct.pack("<II", len(buffer_data), 0x004E4942) 
        + buffer_data
    )

    # Безопасная запись превью на диск
    try:
        with open(preview_glb, "wb") as f:
            f.write(glb_content)
    except Exception as e:
        print(f">>>> [Antonioilev-Slat] GLB Preview write failed: {str(e)}")

    # =====================================================
    # PLY EXPORT
    # =====================================================
    if should_save and mode != "load":
        try:
            pc = trimesh_module.points.PointCloud(positions, colors)
            pc.export(ply_file)
        except Exception as e:
            print(f">>>> [Antonioilev-Slat] PLY Export failed: {str(e)}")

    # =====================================================
    # META EXPORT
    # =====================================================
    if should_save and mode != "load":
        try:
            with open(meta_file, "w") as f:
                json.dump({
                    "tslat": tslat_file,
                    "ply": ply_file,
                    "splat_count": num_splats,
                    "seed": seed
                }, f, indent=2)
        except Exception:
            pass

    # =====================================================
    # DATA PACKAGING FOR COMFYUI VIZUALIZATION WITH ANALYTICS
    # =====================================================
    unique_filename = f"{file_base}_{int(time.time())}.glb"
    uncompressed_size = round((positions.nbytes + colors.nbytes) / (1024 * 1024), 2)

    # Инициализация переменных для безопасности
    verdict, verdict_color = "Успешно загружено", "#ffffff"

    try:
        red_mask = (colors[:, 0] > 0.7) & (colors[:, 1] < 0.3) & (colors[:, 2] < 0.3)
        purple_mask = (colors[:, 0] > 0.4) & (colors[:, 1] < 0.3) & (colors[:, 2] > 0.4)
        red_pct = np.sum(red_mask) / num_splats if num_splats > 0 else 0
        purple_pct = np.sum(purple_mask) / num_splats if num_splats > 0 else 0

        if red_pct < 0.03 and purple_pct < 0.10:
            verdict, verdict_color = "Перспективная (Манифолд, Плавная)", "#00ffff"
        elif red_pct < 0.08:
            verdict, verdict_color = "Пограничная (Гранёная, мелкие дефекты)", "#ffa500"
        else:
            verdict, verdict_color = "Не перспективная (Много шума / Не-манифолд)", "#ff4500"
    except Exception:
        pass

    # Экспорт GLB
    preview_glb = os.path.join(out_path, unique_filename)
    try:
        scene = trimesh_module.Scene()
        scene.add_geometry(trimesh_module.points.PointCloud(positions, colors))
        scene.export(preview_glb, file_type='glb')
        print(f">>>> [Antonioilev-Slat] Preview exported to: {preview_glb}")
    except Exception as e:
        print(f">>>> [Antonioilev-Slat] Export error: {e}")

    # Формирование UI и финальный возврат
    ui_output = {
        "viewport_context": [{
            "metrics_string": f"Splats: {num_splats} ({uncompressed_size} MB)",
            "controls": {
                "show_textured_checkbox": False,
                "show_wireframe_checkbox": False,
                "verdict_text": verdict,
                "verdict_color": verdict_color,
                "point_size": point_size  # <--- Теперь берет переданное значение
            }
        }]
    }

    print(f">>>> [Antonioilev-Slat] SUCCESS: Returning geometry for {file_base}")

    return {
        "result_data": (trimesh_module.Scene(), trimesh_module.points.PointCloud(positions, colors), slat_input),
        "temp_name": unique_filename,
        "has_geometry": True,
        "viewport_context": ui_output["viewport_context"]
    }