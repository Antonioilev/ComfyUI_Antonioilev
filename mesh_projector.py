import numpy as np
import trimesh

class MeshProjector:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "source_mesh": ("TRIMESH",),   # чистая топология (двигается)
                "target_mesh": ("TRIMESH",),   # оригинал с деталями
                "iterations": ("INT", {"default": 25, "min": 1, "max": 500}),
            },
            "optional": {
                "step_ratio": ("FLOAT", {"default": 0.55, "min": 0.05, "max": 1.0, "step": 0.05}),
                "smooth_weight": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_distance": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "edge_update_every": ("INT", {"default": 5, "min": 1, "max": 50}),
                "final_snap_iters": ("INT", {"default": 5, "min": 0, "max": 50}),
            }
        }

    RETURN_TYPES = ("TRIMESH", "STRING")
    RETURN_NAMES = ("mesh", "info")
    FUNCTION = "project"
    CATEGORY = "Antonioilev/Research"

    def _prepare_adjacency(self, mesh):
        edges = mesh.edges_unique
        n = len(mesh.vertices)
        neighbors = [[] for _ in range(n)]
        for a, b in edges:
            neighbors[a].append(b)
            neighbors[b].append(a)

        degrees = np.array([len(nbrs) for nbrs in neighbors], dtype=np.int32)
        max_deg = max(int(degrees.max()) if len(degrees) else 1, 1)
        neigh_idx = np.full((n, max_deg), -1, dtype=np.int32)
        for i, nbrs in enumerate(neighbors):
            if nbrs:
                neigh_idx[i, :len(nbrs)] = nbrs
        return neigh_idx, degrees

    def _avg_edge_length_fast(self, vertices, neigh_idx, degrees):
        n = len(vertices)
        avg = np.zeros(n, dtype=np.float64)
        for i in range(n):
            d = degrees[i]
            if d == 0:
                avg[i] = 0.01
                continue
            nbrs = neigh_idx[i, :d]
            avg[i] = np.linalg.norm(vertices[nbrs] - vertices[i], axis=1).mean()
        return avg

    def _laplacian_fast(self, vertices, neigh_idx, degrees, weight):
        n = len(vertices)
        new_v = vertices.copy()
        for i in range(n):
            d = degrees[i]
            if d == 0:
                continue
            nbrs = neigh_idx[i, :d]
            avg_pos = vertices[nbrs].mean(axis=0)
            new_v[i] = (1.0 - weight) * vertices[i] + weight * avg_pos
        return new_v

    def project(self, source_mesh, target_mesh, iterations=25,
                step_ratio=0.55, smooth_weight=0.15,
                max_distance=0.0, edge_update_every=5,
                final_snap_iters=5):

        if source_mesh is None or target_mesh is None:
            return (None, "Missing mesh")

        res = source_mesh.copy()
        vertices = res.vertices.copy().astype(np.float64)
        start_vertices = vertices.copy()

        neigh_idx, degrees = self._prepare_adjacency(res)
        avg_edge = None

        total_iters = max(iterations, 1)
        # последние final_snap_iters — только притяжение, без сглаживания
        smooth_stop = max(total_iters - final_snap_iters, 0)

        for it in range(total_iters):
            if avg_edge is None or (it % edge_update_every == 0):
                avg_edge = self._avg_edge_length_fast(vertices, neigh_idx, degrees)

            max_step = avg_edge * step_ratio

            closest, dist, _ = target_mesh.nearest.on_surface(vertices)

            if max_distance > 0:
                too_far = dist > max_distance
                closest[too_far] = vertices[too_far]

            displacement = closest - vertices
            move_len = np.linalg.norm(displacement, axis=1)
            scale = np.ones(len(vertices), dtype=np.float64)
            over = move_len > max_step
            if np.any(over):
                scale[over] = max_step[over] / (move_len[over] + 1e-12)
            vertices = vertices + displacement * scale[:, None]

            # сглаживание только на ранних/средних итерациях
            if smooth_weight > 0.0 and it < smooth_stop:
                vertices = self._laplacian_fast(vertices, neigh_idx, degrees, smooth_weight)

        res.vertices = vertices
        res.remove_infinite_values()
        res.fix_normals()

        total_move = float(np.mean(np.linalg.norm(vertices - start_vertices, axis=1)))
        info = (f"Iterative | iters={total_iters} | step={step_ratio:.2f} | "
                f"smooth={smooth_weight:.2f} | final_snap={final_snap_iters} | "
                f"avg move={total_move:.5f}")
        return (res, info)


NODE_CLASS_MAPPINGS = {"AntonioilevMeshProjector": MeshProjector}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevMeshProjector": "🎯 Detail Recover (Iterative)"}