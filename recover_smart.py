import numpy as np
import trimesh as tri
from scipy.spatial import cKDTree

class AntonioilevRecoverSmart:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "simplified": ("TRIMESH",),
                "reference": ("TRIMESH",),
                "snap_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "dist_limit": ("FLOAT", {"default": 0.03, "min": 0.001, "max": 0.5, "step": 0.001}),
            }
        }

    RETURN_TYPES = ("TRIMESH",)
    FUNCTION = "execute"
    CATEGORY = "Antonioilev/Mesh"

    def execute(self, simplified, reference, snap_strength, dist_limit):
        res = simplified.copy()
        
        try:
            v_colors = np.array(res.visual.vertex_colors)
            if v_colors.size == 0: raise ValueError
        except:
            return (simplified,)

        mask = v_colors[:, 0] / 255.0  # Красный канал
        crease_indices = np.where(mask > 0.1)[0]
        
        if len(crease_indices) == 0:
            return (simplified,)

        tree = cKDTree(reference.vertices)
        dists, idxs = tree.query(res.vertices[crease_indices], workers=-1)
        
        valid = dists < dist_limit
        target_indices = crease_indices[valid]
        target_positions = reference.vertices[idxs[valid]]
        
        res.vertices[target_indices] += (target_positions - res.vertices[target_indices]) * snap_strength
        
        return (res,)

NODE_CLASS_MAPPINGS = {"AntonioilevRecoverSmart": AntonioilevRecoverSmart}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevRecoverSmart": "Smart Recover Creases (via Colors)"}