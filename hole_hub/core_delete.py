import numpy as np

def delete_faces(mesh):
    """
    Удаляет все фейсы, у которых хотя бы одна вершина помечена как красная.
    """
    mesh_out = mesh.copy()
    
    if mesh_out.visual.vertex_colors is None:
        return mesh_out

    # 1. Определяем красные вершины
    colors = mesh_out.visual.vertex_colors
    # Добавили проверку на альфа-канал, если он используется
    is_red = (colors[:, 0] == 255) & (colors[:, 1] == 0) & (colors[:, 2] == 0)
    
    # 2. Определяем маску фейсов
    faces_to_delete_mask = is_red[mesh_out.faces].any(axis=1)
    faces_to_keep = ~faces_to_delete_mask
    
    # 3. ПРОВЕРКА НА БЕЗОПАСНОСТЬ: 
    # Если мы пытаемся удалить абсолютно всё, вернем предупреждение или пустой меш, 
    # чтобы не вызвать краш всей системы ComfyUI
    if not np.any(faces_to_keep):
        print("!!! Warning: Attempting to delete all faces! Returning empty mesh.")
        mesh_out.faces = np.array([])
        mesh_out.vertices = np.array([])
        return mesh_out
    
    # 4. Применяем изменения
    mesh_out.update_faces(faces_to_keep)
    mesh_out.remove_unreferenced_vertices()
    
    # Сбрасываем цвета, так как операция удаления завершена
    mesh_out.visual.vertex_colors = None
    
    return mesh_out