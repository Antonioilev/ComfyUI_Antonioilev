import os
import re
import numpy as np
import open3d as o3d
import trimesh
from server import PromptServer
from aiohttp import web

# ==============================================================================
# ОПТИМИЗИРОВАННЫЕ МЕТОДЫ ЧТЕНИЯ ГЕОМЕТРИИ (C++ Backend через Open3D / NumPy)
# ==============================================================================

def validate(input_data):
    """Проверяет, являются ли данные мешем/тримешем"""
    if input_data is None:
        return False
    if isinstance(input_data, dict) and ("vertices" in input_data or "geometry" in input_data):
        return True
    if hasattr(input_data, "vertices") and hasattr(input_data, "faces"):
        return True
    return False

def load_mesh_fast(file_path):
    """
    Высокоскоростное чтение полигональных сеток любой плотности.
    Использует внутренние C++ парсеры Open3D, минуя накладные расходы Python.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Mesh file not found: {file_path}")

    # Чтение сцены через Open3D
    mesh = o3d.io.read_triangle_mesh(file_path)
    
    # Если сетка пустая, пробуем принудительно определить формат по расширению
    if not mesh.has_triangles():
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.obj':
            mesh = o3d.io.read_triangle_mesh(file_path, enable_post_processing=False)

    # Быстрое извлечение массивов через zero-copy MemoryView в NumPy
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.triangles, dtype=np.int32)
    
    # Извлечение текстурных координат или цветов, если они есть
    uvs = None
    if mesh.has_triangle_uvs():
        uvs = np.asarray(mesh.triangle_uvs, dtype=np.float32)

    vertex_colors = None
    if mesh.has_vertex_colors():
        vertex_colors = np.asarray(mesh.vertex_colors, dtype=np.float32)

    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs,
        "colors": vertex_colors,
        "stats": {
            "vertices_count": len(vertices),
            "faces_count": len(faces)
        }
    }


def parse_obj_metadata_ultra_fast(file_path):
    """
    Моментальный подсчет фейсов для тяжелых файлов без загрузки геометрии в RAM.
    Сканирует первые и последние блоки байт файла.
    """
    try:
        file_size = os.path.getsize(file_path)
        # Если файл меньше 10 МБ, читаем целиком, иначе сканируем буфер с конца
        if file_size < 10 * 1024 * 1024:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read()
                v_count = len(re.findall(r'^v ', content, re.M))
                f_count = len(re.findall(r'^f ', content, re.M))
                return v_count, f_count
        else:
            # Для гигантских файлов: берем выборку из конца файла для оценки структуры
            with open(file_path, 'rb') as f:
                f.seek(max(0, file_size - 5 * 1024 * 1024))
                tail = f.read().decode('utf-8', errors='ignore')
                # Находим последний индекс элемента (приблизительная оценка, если нужен точный лог)
                f_indices = re.findall(r'f\s+(\d+)', tail)
                if f_indices:
                    approx_f = max(int(idx) for idx in f_indices[:100])
                    return "Heavy Mesh", approx_f
            return "Heavy Mesh", "20M+"
    except Exception:
        return "Unknown", "Unknown"

def export_via_trimesh(mesh_obj, path, colors=None):
    import trimesh
    
    # Извлечение базовой геометрии
    if hasattr(mesh_obj, 'vertices'): 
        v = np.asarray(mesh_obj.vertices, dtype=np.float32)
        f = np.asarray(mesh_obj.triangles, dtype=np.int32)
    else: 
        v = np.array(mesh_obj.vertices, dtype=np.float32)
        f = np.array(mesh_obj.faces, dtype=np.int32)

    # ЗАЩИТА: Если цвета есть, но их количество не равно количеству вершин - отключаем их
    if colors is not None:
        colors = np.array(colors)
        if colors.ndim > 2:
            colors = colors.reshape(-1, colors.shape[-1])
        if colors.shape[0] != len(v):
            print(f">>>> [Antonioilev Heavy Mesh] EXPORT WARNING: Color mismatch ({colors.shape[0]} vs {len(v)} verts). Dropping colors.")
            colors = None

    mesh_t = trimesh.Trimesh(vertices=v, faces=f, vertex_colors=colors, process=False)
    
    if mesh_t.vertex_normals is None or len(mesh_t.vertex_normals) == 0:
        mesh_t.fix_normals()
        
    mesh_t.export(path, file_type='glb')


# ==============================================================================
# ИНТЕРФЕЙС ДЛЯ НОДЫ (Входная точка для 3D View Save Load - Стабильная GLB схема)
# ==============================================================================

def process_heavy_mesh_data(mesh_input=None, target_dir=None, file_base=None, file_ext=None, ext_type=None, mode=None, should_save=False, out_path=None, seed=0, **kwargs):
    """
    Высокоскоростной процессор тяжелых мешей (До 20млн+ фейсов) через Open3D.
    Экспортирует оптимизированный бинарный GLB напрямую в папку превью ComfyUI.
    """
    import time
    
    mesh = None
    
    # =====================================================
    # 1. ОПРЕДЕЛЕНИЕ ИСТОЧНИКА ГЕОМЕТРИИ
    # =====================================================

    # -----------------------------------------------------
    # CASE A: ВХОДНОЙ MESH OBJECT
    # -----------------------------------------------------

    if mesh_input is not None:

        # OPEN3D INPUT
        if isinstance(mesh_input, o3d.geometry.TriangleMesh):
            mesh = mesh_input

        # TRIMESH INPUT
        elif hasattr(mesh_input, "faces") and hasattr(mesh_input, "vertices"):

            print(">>>> [Antonioilev Heavy Mesh] Converting Trimesh -> Open3D")

            mesh = o3d.geometry.TriangleMesh()

            # Попытка стандартного чтения, fallback на CPU через detach()
            try:
                v_data = np.asarray(mesh_input.vertices, dtype=np.float64)
            except TypeError:
                v_data = mesh_input.vertices.detach().cpu().numpy().astype(np.float64)
                
            try:
                f_data = np.asarray(mesh_input.faces, dtype=np.int32)
            except TypeError:
                f_data = mesh_input.faces.detach().cpu().numpy().astype(np.int32)

            mesh.vertices = o3d.utility.Vector3dVector(v_data)
            mesh.triangles = o3d.utility.Vector3iVector(f_data)

            # VERTEX COLOR SYNC
            try:
                if hasattr(mesh_input, 'visual') and hasattr(mesh_input.visual, 'vertex_colors'):

                    vc = np.asarray(mesh_input.visual.vertex_colors)

                    if len(vc) == len(mesh_input.vertices):

                        if vc.dtype != np.float32 and vc.dtype != np.float64:
                            vc = vc.astype(np.float32) / 255.0

                        if vc.shape[1] >= 3:
                            vc = vc[:, :3]

                        vc = np.nan_to_num(vc, nan=1.0, posinf=1.0, neginf=0.0)

                        mesh.vertex_colors = o3d.utility.Vector3dVector(vc)

            except Exception as e:
                print(f">>>> Vertex color transfer failed: {e}")

        # Dict mesh
        elif isinstance(mesh_input, dict):

            print(">>>> [Antonioilev Heavy Mesh] Converting Dict -> Open3D")

            verts = mesh_input.get("vertices")
            faces = mesh_input.get("faces")

            if verts is None or faces is None:
                print("[Antonioilev Heavy Mesh] Dict mesh missing verts/faces")
                return None

            mesh = o3d.geometry.TriangleMesh()

            # Аналогичный fallback для Dict-меша
            try:
                v_data = np.asarray(verts, dtype=np.float64)
            except TypeError:
                v_data = verts.detach().cpu().numpy().astype(np.float64)
                
            try:
                f_data = np.asarray(faces, dtype=np.int32)
            except TypeError:
                f_data = faces.detach().cpu().numpy().astype(np.int32)

            mesh.vertices = o3d.utility.Vector3dVector(v_data)
            mesh.triangles = o3d.utility.Vector3iVector(f_data)

        # String path
        elif isinstance(mesh_input, str) and os.path.exists(mesh_input):

            print(f">>>> [Antonioilev Heavy Mesh] Open3D C++ Core Loading: {mesh_input}")

            mesh = o3d.io.read_triangle_mesh(mesh_input)

            if not mesh.has_triangles() and mesh_input.lower().endswith('.obj'):
                mesh = o3d.io.read_triangle_mesh(
                    mesh_input,
                    enable_post_processing=False
                )

        else:
            print("[Antonioilev Heavy Mesh] Unsupported mesh_input type")
            return None

    # -----------------------------------------------------
    # CASE B: LOAD FROM FILE (Синхронизировано с Trimesh)
    # -----------------------------------------------------

    else:
        found_file = None
        if target_dir and file_base and file_ext:
            test_path = os.path.join(target_dir, file_base + file_ext)
            if os.path.exists(test_path):
                found_file = test_path

        if found_file:
            print(f">>>> [Antonioilev Heavy Mesh] Open3D C++ Core Loading: {found_file}")
            try:
                # Основная попытка чтения через Open3D
                mesh = o3d.io.read_triangle_mesh(found_file)
                
                # Если Open3D вернул пустой объект (ошибка Assimp) - пробуем fallback
                if not mesh.has_triangles():
                    print(f">>>> [Antonioilev Heavy Mesh] Open3D read failed, attempting Trimesh fallback...")
                    import trimesh
                    t_mesh = trimesh.load(found_file, force='mesh')
                    mesh = o3d.geometry.TriangleMesh()
                    mesh.vertices = o3d.utility.Vector3dVector(t_mesh.vertices)
                    mesh.triangles = o3d.utility.Vector3iVector(t_mesh.faces)
            except Exception as e:
                print(f">>>> [Antonioilev Heavy Mesh] Loading error: {e}. Attempting Trimesh fallback...")
                import trimesh
                t_mesh = trimesh.load(found_file, force='mesh')
                mesh = o3d.geometry.TriangleMesh()
                mesh.vertices = o3d.utility.Vector3dVector(t_mesh.vertices)
                mesh.triangles = o3d.utility.Vector3iVector(t_mesh.faces)

        # Если меш не пришел с входа и не загрузился с диска - отдаем пустой ответ
        if mesh is None:
            return {
                "temp_name": None,
                "tri_count": [0],
                "data_type": "mesh",
                "result_data": (None, None),
                "has_geometry": False,
                "viewport_context": []
            }

    # Далее проверка геометрии и экспорт
    try:
        # 0. УНИВЕРСАЛЬНАЯ ОЧИСТКА И НОРМАЛИЗАЦИЯ
        if hasattr(mesh, 'remove_degenerate_faces'):
            # Это Open3D
            mesh.remove_degenerate_faces()
            mesh.remove_unreferenced_vertices()
            
            # Обработка NaN для Open3D
            v_clean = np.asarray(mesh.vertices)
            if not np.isfinite(v_clean).all():
                v_clean = np.nan_to_num(v_clean, nan=0.0, posinf=0.0, neginf=0.0)
                mesh.vertices = o3d.utility.Vector3dVector(v_clean)
            
            mesh.translate(-mesh.get_center())
            max_bound = np.max(mesh.get_max_bound() - mesh.get_min_bound())
            if max_bound > 0:
                mesh.scale(1.0 / max_bound, center=(0, 0, 0))
        
        elif hasattr(mesh, 'vertices'):
            # Если это Open3D объект (мы создали его в fallback)
            if isinstance(mesh, o3d.geometry.TriangleMesh):
                v = np.asarray(mesh.vertices, dtype=np.float64)
                if not np.isfinite(v).all():
                    v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
                    mesh.vertices = o3d.utility.Vector3dVector(v)
                
                # Нормализация для Open3D
                mesh.translate(-mesh.get_center())
                max_bound = np.max(mesh.get_max_bound() - mesh.get_min_bound())
                if max_bound > 0:
                    mesh.scale(1.0 / max_bound, center=(0, 0, 0))
            
            # Если это настоящий Trimesh объект
            elif hasattr(mesh, 'apply_translation'):
                v = np.array(mesh.vertices, dtype=np.float64)
                if not np.isfinite(v).all():
                    mesh.vertices = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
                mesh.apply_translation(-mesh.centroid)
                scale = 1.0 / mesh.extents.max()
                mesh.apply_scale(scale)

        # Проверка на случай, если fallback вернул пустой объект
        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise ValueError("Mesh geometry is empty")

        total_verts = len(mesh.vertices)

        if isinstance(mesh, o3d.geometry.TriangleMesh):
            total_tris = len(mesh.triangles)
            faces_array = np.asarray(mesh.triangles, dtype=np.int64)

            # --- SAFE VALIDATION ONLY (NO MUTATION) ---
            if faces_array.size == 0:
                raise ValueError("Empty face array")

            if faces_array.ndim != 2 or faces_array.shape[1] != 3:
                raise ValueError(f"Invalid face shape: {faces_array.shape}")

            if not np.isfinite(faces_array).all():
                raise ValueError("Invalid face data (NaN/Inf detected)")
            
        else:
            total_tris = len(mesh.faces)
            faces_array = np.asarray(mesh.faces, dtype=np.int64)

        # =====================================================
        # 2. PREVIEW CACHE EXPORT & COLOR SYNC
        # =====================================================
        render_id = f"{seed}_{int(time.time() * 100)}"
        temp_name = f"antonio_preview_{render_id}.glb"
        full_preview_path = os.path.join(out_path, temp_name)
        
        # --- ПРИОРИТЕТНОЕ ИЗВЛЕЧЕНИЕ ЦВЕТОВ ---
        # Сначала ищем в visual (там, где RefineMeshNode), потом в объекте
        v_colors = None
        if hasattr(mesh, 'visual') and hasattr(mesh.visual, 'vertex_colors') and len(mesh.visual.vertex_colors) > 0:
            v_colors = np.asarray(mesh.visual.vertex_colors)
        elif hasattr(mesh, 'vertex_colors') and len(mesh.vertex_colors) > 0:
            v_colors = np.asarray(mesh.vertex_colors)

        # Нормализация
        if v_colors is not None:
            if v_colors.dtype.kind == 'f':
                v_colors = (np.clip(v_colors, 0.0, 1.0) * 255).astype(np.uint8)
            if v_colors.ndim > 2:
                v_colors = v_colors.reshape(-1, v_colors.shape[-1])

        # Экспорт превью
        export_via_trimesh(mesh, full_preview_path, colors=v_colors)

        # 3. USER SAVE EXPORT
        if should_save:
            os.makedirs(target_dir, exist_ok=True)
            final_export_path = os.path.join(target_dir, file_base + file_ext)
            print(f">>>> [Antonioilev Heavy Mesh] Saving User Mesh: {final_export_path}")
            try:
                export_via_trimesh(mesh, final_export_path, colors=v_colors)
                print(">>>> [Antonioilev Heavy Mesh] USER SAVE SUCCESS")
            except Exception as e:
                print(f">>>> [Antonioilev Heavy Mesh] USER SAVE FAILED: {e}")

        # --- ФИНАЛЬНЫЙ ОБЪЕКТ ДЛЯ COMFYUI ---
        import trimesh
        
        # 1. Приводим типы данных к безопасным
        v_arr = np.asarray(mesh.vertices, dtype=np.float64)
        f_arr = faces_array
        
        # 2. Создаем меш без авто-процессинга, чтобы не искажать геометрию
        # Force-safe mesh construction (CRITICAL FIX for adjacency stability)
        final_mesh = trimesh.Trimesh(
            vertices=v_arr,
            faces=f_arr,
            process=False,
        )

        # =====================================================
        # 🔥 CURVATURE PIPELINE PRESERVATION FIX
        # =====================================================

        try:
            # Open3D path → vertex colors often carry curvature indirectly
            if isinstance(mesh, o3d.geometry.TriangleMesh):
                if mesh.has_vertex_colors():
                    vc = np.asarray(mesh.vertex_colors)
                    if len(vc) == len(v_arr):
                        final_mesh.visual.vertex_colors = vc

        except:
            pass


        # =====================================================
        # 🔥 CRITICAL: METADATA PASS-THROUGH
        # =====================================================

        try:
            if hasattr(mesh_input, "metadata") and isinstance(mesh_input.metadata, dict):
                final_mesh.metadata = dict(mesh_input.metadata)
        except:
            final_mesh.metadata = {}
        
        # 3. КРИТИЧЕСКИ БЕЗОПАСНАЯ СИНХРОНИЗАЦИЯ ЦВЕТОВ
        # Если цвета есть, проверяем их размер перед присвоением.
        if v_colors is not None:
            # Приводим цвета к форме (N, 3) или (N, 4)
            if v_colors.ndim > 2:
                v_colors = v_colors.reshape(-1, v_colors.shape[-1])
            
            # Если количество цветов в точности совпадает с количеством вершин, назначаем.
            # Если нет — выбрасываем предупреждение и игнорируем цвета, чтобы не упасть.
            if v_colors.shape[0] == len(final_mesh.vertices):
                final_mesh.visual.vertex_colors = v_colors
            else:
                print(f">>>> [Antonioilev Heavy Mesh] WARNING: Color mismatch! Mesh: {len(final_mesh.vertices)} verts, Colors: {v_colors.shape[0]}. Colors disabled.")
                v_colors = None # Сбрасываем флаг, чтобы UI не пытался отобразить отсутствующие цвета

        print(f">>>> [Antonioilev Heavy Mesh] Geometry Processed: {len(v_arr)} verts")
        
        # FORCE adjacency initialization (prevents lazy crash in vertex_faces)
        _ = final_mesh.vertices
        _ = final_mesh.faces


        # 4. ФОРМИРОВАНИЕ СТРОГОГО ОТВЕТА
        return {
            "temp_name": temp_name,
            "tri_count": [total_tris],
            "data_type": "mesh",
            "result_data": (final_mesh, final_mesh), 
            "has_geometry": len(v_arr) > 0,
            "viewport_context": [{
                "mode": "mesh",
                "metrics_string": f"Tris: {total_tris:,} | Colors: {'Yes' if v_colors is not None else 'No'}", 
                "vertex_count": len(v_arr),            
                "triangle_count": total_tris,          
                "controls": {
                    "show_textured_checkbox": False,
                    "show_wireframe_checkbox": True,    
                    "enable_vertex_colors": v_colors is not None
                }
            }]
        }

    except Exception as e:
        print(f">>>> [Antonioilev Heavy Mesh] FATAL ERROR: {str(e)}")
        return {
            "temp_name": None,
            "tri_count": [0],
            "data_type": "mesh",
            "result_data": (None, None),
            "has_geometry": False,
            "viewport_context": []
        }