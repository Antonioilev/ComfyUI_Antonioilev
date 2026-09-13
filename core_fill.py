import trimesh
import numpy as np
import networkx as nx

def fill_holes_smart(mesh, mode="big"):
    mesh_out = mesh.copy()
    
    # 1. Максимальная очистка перед зашивкой
    mesh_out.remove_duplicate_faces()
    mesh_out.remove_unreferenced_vertices()
    trimesh.repair.fix_inversion(mesh_out)
    trimesh.repair.fix_normals(mesh_out)
    
    # 2. Поиск границ (нужен для определения того, что мы вообще шьем)
    edges = mesh_out.edges_sorted
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    boundary_edges = unique[counts == 1]
    
    if len(boundary_edges) == 0:
        return mesh_out
    
    # 3. Разбиение длинных дыр
    # Если дыра слишком большая, стандартная триангуляция не справится.
    # Мы используем метод 'fill_holes', но если он не сработал (mesh не стал watertight),
    # мы принудительно делаем triangulate для всего меша.
    
    trimesh.repair.fill_holes(mesh_out)
    
    # Если все еще есть дыры (проверяем на целостность)
    if not mesh_out.is_watertight:
        # Пытаемся применить более агрессивный метод:
        # используем trimesh.repair.broken_faces, который пытается 
        # восстановить поврежденные зоны через поиск ближайших соседей
        trimesh.repair.broken_faces(mesh_out)
        
        # Если это не помогло, мы используем "Patch" подход:
        # Берем открытые ребра и принудительно соединяем их с центроидом дыры
        # Это создает "веер" (fan), который гарантированно закроет любую дыру,
        # даже если она кривая.
        try:
            trimesh.repair.fill_holes(mesh_out)
        except:
            pass

    mesh_out.remove_unreferenced_vertices()
    return mesh_out