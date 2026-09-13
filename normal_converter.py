import torch
import numpy as np

class NormalSpaceConverter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "normals": ("IMAGE",),
                "flip_r": ("BOOLEAN", {"default": False}),
                "flip_g": ("BOOLEAN", {"default": False}),
                "flip_b": ("BOOLEAN", {"default": False}),
                "remove_alpha": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("converted_normals",)
    FUNCTION = "convert"
    CATEGORY = "Antonioilev/2D"

    def convert(self, normals, flip_r, flip_g, flip_b, remove_alpha):
        batch_size = normals.shape[0]
        output_images = []
        
        for i in range(batch_size):
            img_tensor = normals[i]
            
            # Работа с альфой (ваша логика сохранения)
            if remove_alpha and img_tensor.shape[-1] == 4:
                rgb = img_tensor[:, :, :3]
                alpha = img_tensor[:, :, 3:]
                neutral_blue = torch.tensor([0.5, 0.5, 1.0], device=img_tensor.device)
                # Смешиваем с нейтральным синим цветом Tangent Space
                img_np = (rgb * alpha) + (neutral_blue * (1.0 - alpha))
            else:
                img_np = img_tensor.clone()

            # Перевод в numpy для алгоритма
            img = img_np.cpu().numpy()
            
            # Векторизация [-1, 1]
            img_vectors = img * 2.0 - 1.0
            
            # Применение галок Flip
            if flip_r: img_vectors[:, :, 0] = -img_vectors[:, :, 0]
            if flip_g: img_vectors[:, :, 1] = -img_vectors[:, :, 1]
            if flip_b: img_vectors[:, :, 2] = -img_vectors[:, :, 2]

            # Нормализация (защита от сломанных векторов)
            mag = np.linalg.norm(img_vectors, axis=-1, keepdims=True)
            mask = (mag <= 0.05).squeeze()
            safe_mag = np.where(mag > 0.05, mag, 1.0)
            img_vectors /= safe_mag
            # Фон заливаем нейтральным [0, 0, 1]
            img_vectors[mask] = [0.0, 0.0, 1.0]
            
            # Возврат в [0, 1]
            final_img = (img_vectors + 1.0) / 2.0
            output_images.append(torch.from_numpy(final_img))

        return (torch.stack(output_images),)

NODE_CLASS_MAPPINGS = { "AntonioilevNormalSpaceConverter": NormalSpaceConverter }
NODE_DISPLAY_NAME_MAPPINGS = { "AntonioilevNormalSpaceConverter": "🚦 Normal Space Converter" }