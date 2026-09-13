import trimesh
import numpy as np

class AntonioilevMeshFixNormals:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "invert_result": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    
    FUNCTION = "fix_normals_conform" 
    CATEGORY = "Antonioilev/Mesh/Fix"

    def fix_normals_conform(self, mesh, invert_result):
        if mesh is None:
            return (None, "No mesh input")
        
        mesh = mesh.copy()
        
        # Слияние близких вершин
        mesh.merge_vertices(merge_tex=True, merge_norm=True)
        
        # Корректное удаление дубликатов граней
        if len(mesh.faces) > 0:
            sorted_faces = np.sort(mesh.faces, axis=1)
            _, unique_idx = np.unique(sorted_faces, axis=0, return_index=True)
            mesh.update_faces(unique_idx)
        
        mesh.remove_infinite_values()
        
        # Главное: делаем нормали согласованными + направленными наружу
        # (работает и на не-watertight мешах для связанных компонентов)
        mesh.fix_normals()
        
        # Если нужна инверсия всего результата
        if invert_result:
            mesh.invert()
        
        # На всякий случай принудительно сбрасываем кэш нормалей
        # (хотя fix_normals и invert уже это делают правильно)
        mesh.face_normals = None
        mesh.vertex_normals = None
        
        return (mesh, "Success")

NODE_CLASS_MAPPINGS = { "AntonioilevMeshFixNormals": AntonioilevMeshFixNormals }
NODE_DISPLAY_NAME_MAPPINGS = { "AntonioilevMeshFixNormals": "🚀 Smart Normals Conform" }