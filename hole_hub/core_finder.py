import trimesh
import numpy as np
import networkx as nx

def find_holes(mesh):
    """
    Находит границы дырок и красит ИСКЛЮЧИТЕЛЬНО вертексы границы в красный.
    """
    mesh_out = mesh.copy()
    
    # 1. Принудительный расчет топологии
    mesh_out.process(validate=False)
    
    # 2. Поиск граничных ребер (те, что примыкают к одному фейсу)
    edges = mesh_out.edges_sorted
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    boundary_edges = unique[counts == 1]
    
    if len(boundary_edges) == 0:
        mesh_out.metadata['num_holes'] = 0
        return mesh_out
        
    # 3. Получаем уникальные индексы ВЕРТЕКСОВ границ
    # boundary_edges это массив (N, 2), нам нужно просто взять все индексы
    boundary_vertex_indices = np.unique(boundary_edges.flatten())
    
    # 4. Визуализация
    # Инициализируем или сбрасываем цвета
    # Устанавливаем белый цвет всем вершинам по умолчанию
    mesh_out.visual.vertex_colors = np.ones((len(mesh_out.vertices), 4), dtype=np.uint8) * 255
    
    # Красим ТОЛЬКО вертексы границ в красный [255, 0, 0, 255]
    mesh_out.visual.vertex_colors[boundary_vertex_indices] = [255, 0, 0, 255]
    
    # Сохраняем информацию о количестве вершин границы
    mesh_out.metadata['num_holes'] = len(boundary_vertex_indices)
        
    return mesh_out