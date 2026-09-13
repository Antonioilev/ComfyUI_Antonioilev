import numpy as np
import trimesh

def grow_selection(mesh, iterations=1):
    """
    Увеличивает область красных вершин (покрашенных нодой finder)
    на N итераций (соседей).
    """
    mesh_out = mesh.copy()
    
    if mesh_out.visual.vertex_colors is None:
        return mesh_out

    # Получаем текущие цвета
    colors = mesh_out.visual.vertex_colors.copy()
    
    # 1. Кэшируем соседей, чтобы не вызывать метод каждый раз в цикле
    neighbors = mesh_out.vertex_neighbors
    
    # 2. Итерации роста
    for _ in range(iterations):
        # Находим маску всех красных вершин
        is_red = (colors[:, 0] == 255) & (colors[:, 1] == 0) & (colors[:, 2] == 0)
        red_indices = np.where(is_red)[0]
        
        # ОПТИМИЗАЦИЯ: используем np.concatenate для быстрого объединения соседей
        if len(red_indices) == 0:
            break
            
        # Получаем всех соседей красных вершин одним махом
        # neighbors[red_indices] вернет список списков, нам нужно их объединить
        all_neighbors = np.concatenate([neighbors[i] for i in red_indices])
        
        # ОПТИМИЗАЦИЯ: используем unique, чтобы исключить дубликаты
        new_reds = np.unique(all_neighbors)
        
        # Применяем новые красные вершины
        colors[new_reds] = [255, 0, 0, 255]
            
    mesh_out.visual.vertex_colors = colors
    return mesh_out