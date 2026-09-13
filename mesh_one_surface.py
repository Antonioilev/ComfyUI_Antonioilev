import numpy as np
import trimesh
import time

# Попытка импорта manifold3d для герметизации
try:
    from manifold3d import Manifold, Mesh
    HAS_MANIFOLD = True
except ImportError:
    HAS_MANIFOLD = False
    print(">>> [Antonioilev] Warning: manifold3d not found. Install it for better sealing: pip install manifold3d")

class MeshOneSurface:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "merge_tolerance": ("FLOAT", {"default": 1e-6, "min": 0, "max": 0.01, "step": 1e-8}),
                "force_manifold": ("BOOLEAN", {"default": True}),
                "fix_winding": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "TRIMESH")
    RETURN_NAMES = ("info", "mesh")
    FUNCTION = "process"
    CATEGORY = "Antonioilev/Mesh"

    def process(self, mesh, merge_tolerance, force_manifold, fix_winding):
        if mesh is None: return ("No input mesh", None)
        
        start_time = time.time()
        # Работаем с копией меша
        wm = mesh.copy()
        info_parts = [f"In: {len(wm.faces)} faces"]

        try:
            # 1. Жесткий мердж вертексов (убираем микро-щели)
            wm.merge_vertices(merge_tex=False, merge_norm=False, digits=None)
            wm.remove_degenerate_faces()

            # 2. Использование Manifold для удаления "внутрянки" и герметизации
            if force_manifold and HAS_MANIFOLD:
                # Manifold требует contiguous arrays
                verts = np.ascontiguousarray(wm.vertices, dtype=np.float32)
                faces = np.ascontiguousarray(wm.faces, dtype=np.uint32)
                
                m_mesh = Mesh(vert_properties=verts, tri_verts=faces)
                m_obj = Manifold(m_mesh)
                
                # keep_largest() — КЛЮЧЕВОЙ МОМЕНТ. 
                # Он оставляет только внешнюю оболочку, удаляя все внутренние "матрешки"
                m_obj = m_obj.keep_largest()
                
                # Возврат в Trimesh
                out_raw = m_obj.to_mesh()
                wm = trimesh.Trimesh(vertices=out_raw.vert_properties, faces=out_raw.tri_verts, process=False)
                info_parts.append("Manifold Applied")
            
            # 3. Дополнительная зашивка дыр (если Manifold не справился или отключен)
            if not wm.is_watertight:
                wm.fill_holes()

            # 4. Исправление ориентации нормалей
            if fix_winding:
                trimesh.repair.fix_winding(wm)
                wm.fix_normals()

        except Exception as e:
            print(f"!!! [AntonioilevMeshOneSurface] Error: {e}")
            info_parts.append(f"Error: {str(e)}")

        total_time = time.time() - start_time
        status = "WATERTIGHT" if wm.is_watertight else "NON-MANIFOLD"
        summary = f"{status} | {', '.join(info_parts)} | {total_time:.2f}s"
        
        return (summary, wm)

# Регистрация нод (Имена должны строго совпадать с именем класса выше)
NODE_CLASS_MAPPINGS = {
    "AntonioilevMeshOneSurface": MeshOneSurface
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AntonioilevMeshOneSurface": "🌊 Mesh One Surface"
}