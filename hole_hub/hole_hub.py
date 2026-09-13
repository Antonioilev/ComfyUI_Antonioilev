from .core_finder import find_holes
from .core_grow import grow_selection
from .core_delete import delete_faces
from .core_fill import fill_holes_smart
import numpy as np

class HoleHub:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "do_find": ("BOOLEAN", {"default": False}),
                "do_grow": ("BOOLEAN", {"default": False}),
                "do_delete": ("BOOLEAN", {"default": False}),
                "do_fill_big": ("BOOLEAN", {"default": False}),
                "do_fill_small": ("BOOLEAN", {"default": False}),
                "grow_amount": ("INT", {"default": 1, "min": 0, "max": 5}),
            }
        }
    
    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "report")
    FUNCTION = "process"
    CATEGORY = "Antonioilev/Mesh/Fix"

    def process(self, mesh, do_find, do_grow, do_delete, do_fill_big, do_fill_small, grow_amount):
        result_mesh = mesh.copy()
        report_log = []

        # Базовая инициализация цветов для всех шагов
        if result_mesh.visual.vertex_colors is None:
            result_mesh.visual.vertex_colors = np.ones((len(result_mesh.vertices), 4), dtype=np.uint8) * 255

        # Выполнение цепочки действий
        if do_find:
            result_mesh = find_holes(result_mesh)
            report_log.append("Find: Holes highlighted.")
            
        if do_grow:
            result_mesh = grow_selection(result_mesh, grow_amount)
            report_log.append(f"Grow: Selection expanded by {grow_amount}.")
            
        if do_delete:
            result_mesh = delete_faces(result_mesh)
            report_log.append("Delete: Red faces removed.")
            
        if do_fill_big:
            result_mesh = fill_holes_smart(result_mesh, mode="big")
            report_log.append("Fill: Large holes closed.")
            
        if do_fill_small:
            result_mesh = fill_holes_smart(result_mesh, mode="small")
            report_log.append("Fill: Small holes cleaned.")
        
        final_report = "\n".join(report_log) if report_log else "No operations performed."
        
        return (result_mesh, final_report)

NODE_CLASS_MAPPINGS = {"HoleHub": HoleHub}
NODE_DISPLAY_NAME_MAPPINGS = {"HoleHub": "🕳️ Hole hub"}