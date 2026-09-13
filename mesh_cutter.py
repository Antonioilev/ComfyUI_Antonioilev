# SPDX-License-Identifier: GPL-3.0-or-later
# Enhanced by Antonioilev - 2026 (Sequential Multi-Cutter)

import numpy as np
import trimesh

class AntonioilevMultiMeshCutter:
    @classmethod
    def INPUT_TYPES(s):
        # ‘оздаем словарь с обЯзательным мешем
        inputs = {
            "required": {
                "mesh": ("TRIMESH",),
                "invert": ("BOOLEAN", {"default": False}),
            },
            "optional": {}
        }
        # „обавлЯем 10 опциональных слотов длЯ резаков
        for i in range(1, 11):
            inputs["optional"][f"cutter_mesh_{i}"] = ("TRIMESH",)
            
        return inputs

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "cut_sequence"
    CATEGORY = "Antonioilev/Meshes"

    def apply_math_cut(self, target_mesh, cutter_obj, invert):
        """‚нутреннЯЯ функциЯ логики вырезаниЯ (твой Math-алгоритм)"""
        if cutter_obj is None:
            return target_mesh
        
        # …сли пришел список мешей как один резак С объединЯем
        if isinstance(cutter_obj, list):
            cutter_obj = trimesh.util.concatenate(cutter_obj)

        res_mesh = target_mesh.copy()
        cutter_center = cutter_obj.centroid
        
        # ‚ычислЯем радиус
        dists_to_center = np.linalg.norm(cutter_obj.vertices - cutter_center, axis=1)
        max_radius = np.max(dists_to_center)

        face_centers = res_mesh.triangles_center
        distances = np.linalg.norm(face_centers - cutter_center, axis=1)
        
        inside = distances <= max_radius
        faces_to_keep = inside if invert else ~inside
        
        res_mesh.update_faces(faces_to_keep)
        res_mesh.remove_unreferenced_vertices()
        return res_mesh

    def cut_sequence(self, mesh, invert=False, **kwargs):
        # 1. Џодготовка основного объекта
        input_is_list = isinstance(mesh, list)
        current_meshes = mesh if input_is_list else [mesh]
        
        total_removed_faces = 0
        cutters_count = 0

        # 2. Џоследовательно применЯем каждый переданный cutter_mesh_N
        for i in range(1, 11):
            cutter_key = f"cutter_mesh_{i}"
            cutter_obj = kwargs.get(cutter_key)
            
            if cutter_obj is not None:
                cutters_count += 1
                new_results = []
                for m in current_meshes:
                    initial_count = len(m.faces)
                    # ‚ырезаем из текущего состоЯниЯ меша
                    processed = self.apply_math_cut(m, cutter_obj, invert)
                    
                    total_removed_faces += (initial_count - len(processed.faces))
                    new_results.append(processed)
                
                current_meshes = new_results

        # 3. ”ормируем результат
        result_mesh = current_meshes if input_is_list else current_meshes[0]
        info = f"?? Multi-Cut complete. Used {cutters_count} cutters. Total removed: {total_removed_faces} faces."
        
        print(f"[Antonioilev] {info}")
        return (result_mesh, info)

NODE_CLASS_MAPPINGS = {
    "AntonioilevMultiMeshCutter": AntonioilevMultiMeshCutter
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AntonioilevMultiMeshCutter": "✂️ Multi Mesh Cutter (Sequential)"
}