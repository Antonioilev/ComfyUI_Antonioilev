import torch

class List_batch_images:
    _buffer = {}
    _counts = {}

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "batch_id": ("STRING", {"default": "mv_batch"}),
                "expected_count": ("INT", {"default": 6}),
                "reset": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("batch",)
    FUNCTION = "list_to_batch"
    CATEGORY = "Antonioilev/IO"

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("nan")

    def list_to_batch(self, images, batch_id="mv_batch", expected_count=6, reset=False):
        if batch_id not in List_batch_images._buffer:
            List_batch_images._buffer[batch_id] = []
            List_batch_images._counts[batch_id] = 0

        if reset:
            List_batch_images._buffer[batch_id] = []
            List_batch_images._counts[batch_id] = 0
            print(f"[ListBatchImages] RESET: {batch_id}")

        # Добавляем входящие кадры
        if isinstance(images, torch.Tensor):
            if images.ndim == 4:
                for i in range(images.shape[0]):
                    List_batch_images._buffer[batch_id].append(images[i])
                    List_batch_images._counts[batch_id] += 1
            else:
                List_batch_images._buffer[batch_id].append(images)
                List_batch_images._counts[batch_id] += 1

        print(f"[ListBatchImages] ID: {batch_id} | Progress: {List_batch_images._counts[batch_id]}/{expected_count}")

        # ГЛАВНОЕ ИЗМЕНЕНИЕ:
        # Если батч готов — выдаем все 6 ракурсов
        if List_batch_images._counts[batch_id] >= expected_count:
            final_batch = torch.stack(List_batch_images._buffer[batch_id][:expected_count], dim=0)
            
            # Чистим за собой
            List_batch_images._buffer[batch_id] = []
            List_batch_images._counts[batch_id] = 0
            
            print(f"[ListBatchImages] SENDING FULL BATCH: {final_batch.shape}")
            return (final_batch,)

        # Если НЕ готов — НЕ возвращаем ничего. 
        # ComfyUI поймет, что данных нет, и не пойдет выполнять Save Batch Images.
        return (None,)

NODE_CLASS_MAPPINGS = {"AntonioilevListBatchImages": List_batch_images}
NODE_DISPLAY_NAME_MAPPINGS = {"AntonioilevListBatchImages": "📚 List Batch Images"}
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']