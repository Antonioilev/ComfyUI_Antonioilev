import numpy as np
import trimesh

class UVWatertight:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_mesh": ("TRIMESH",),
            },
            "optional": {
                "merge_distance": ("FLOAT", {
                    "default": 0.00001,
                    "min": 0.00000001,
                    "max": 0.01,
                    "step": 0.00000001
                }),
                "fix_normals": ("BOOLEAN", {"default": True}),
                "fill_holes": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "repair_uv_mesh"
    CATEGORY = "Antonioilev/Research"

    def repair_uv_mesh(self, input_mesh, merge_distance=1e-05, fix_normals=True, fill_holes=True):
        if input_mesh is None:
            return (None, "No input mesh")

        mesh = input_mesh.copy()
        
        try:
            # 1. ЗАЩИТА ТЕТРИС-МАПИНГА
            # Перенос UV на грани, чтобы вершины могли шиться без растягивания текстуры
            if hasattr(mesh.visual, 'to_texture'):
                mesh.visual = mesh.visual.to_texture()

            # 2. ЖЕСТКИЙ ГЕОМЕТРИЧЕСКИЙ ВЕЛДИНГ (Watertight = Yes)
            precision = int(-np.log10(merge_distance))
            unique_verts, inverse = trimesh.grouping.unique_rows(
                mesh.vertices, 
                digits=precision
            )
            mesh.vertices = unique_verts
            mesh.faces = inverse[mesh.faces]

            # 3. ЧИСТКА ТОПОЛОГИИ (Лечим ValueError / TypeError)
            mesh.remove_duplicate_faces()
            valid_faces = (mesh.faces[:, 0] != mesh.faces[:, 1]) & \
                          (mesh.faces[:, 1] != mesh.faces[:, 2]) & \
                          (mesh.faces[:, 2] != mesh.faces[:, 0])
            mesh.update_faces(valid_faces)
            mesh.remove_unreferenced_vertices()

            # 4. РЕМОНТ НОРМАЛЕЙ И ДЫР
            if fix_normals:
                mesh.fix_normals()
            if fill_holes and not mesh.is_watertight:
                mesh.fill_holes()

            # 5. FORCE BOUNDS FIX (Специально для PreviewMeshUV)
            # Принудительно очищаем кэш, чтобы extents стал итерируемым массивом [x, y, z]
            mesh._cache.clear()
            if mesh.vertices.size > 0:
                # Проверка: если extents все еще сломан, считаем вручную
                bounds = mesh.bounds
                extents = bounds[1] - bounds[0]
                if not isinstance(extents, (np.ndarray, list)):
                    # Аварийная заглушка, если numpy вернул скаляр
                    extents = np.array([float(extents)] * 3)
            
            mesh.process(validate=False)
            status = "Watertight OK" if mesh.is_watertight else "Repaired"
            
        except Exception as e:
            status = f"Critical Error: {str(e)}"

        info = (f"{status} | "
                f"Watertight={mesh.is_watertight} | "
                f"V={len(mesh.vertices)} | "
                f"F={len(mesh.faces)}")

        return (mesh, info)

NODE_CLASS_MAPPINGS = {"AntonioilevUVWatertight": UVWatertight}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevUVWatertight": "🧷 UV-Safe Hard Weld "}