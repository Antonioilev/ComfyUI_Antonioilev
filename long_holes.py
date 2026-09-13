import trimesh
import numpy as np

class LongHoles:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("TRIMESH",),
                "fill_holes": ("BOOLEAN", {"default": False}),
                "min_edges": ("INT", {"default": 3, "min": 3, "max": 1000}),
            }
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "report")
    FUNCTION = "process"
    CATEGORY = "Antonioilev/Mesh/Fix"

    def process(self, mesh, fill_holes, min_edges):
        mesh_out = mesh.copy()
        
        # 1. Поиск границ (работает в 4.12)
        # Получаем уникальные ребра и их счетчик
        edges = mesh_out.edges_sorted
        unique, counts = np.unique(edges, axis=0, return_counts=True)
        # Границы - это ребра, которые встречаются только 1 раз
        boundary_edges = unique[counts == 1]
        
        # 2. ГАРАНТИРОВАННЫЙ СПОСОБ ПОЛУЧЕНИЯ ПЕТЕЛЬ (в 4.12)
        # В этой версии Trimesh работа с путями вынесена в trimesh.path
        # Если edges_to_path отсутствует в trimesh.graph, используем этот алгоритм:
        
        import networkx as nx
        # Создаем граф из граничных ребер
        g = nx.Graph()
        g.add_edges_from(boundary_edges)
        # networkx собирает циклы (петли) из графа
        paths = list(nx.cycle_basis(g))
        
        report_lines = []
        
        if fill_holes:
            trimesh.repair.fill_holes(mesh_out)
            report_lines.append("Holes filled.")
        else:
            if mesh_out.visual.vertex_colors is None:
                mesh_out.visual.vertex_colors = np.ones((len(mesh_out.vertices), 4), dtype=np.uint8) * 255
            
            for path in paths:
                if len(path) >= min_edges:
                    # path в networkx - это список индексов вершин
                    mesh_out.visual.vertex_colors[path] = [255, 0, 0, 255]
        
        for i, path in enumerate(paths):
            report_lines.append(f"Hole {i}: {len(path)} vertices")
            
        return (mesh_out, "\n".join(report_lines))

NODE_CLASS_MAPPINGS = {"LongHoles": LongHoles}
NODE_DISPLAY_NAME_MAPPINGS = {"LongHoles": "🕳️ Long Holes Finder"}