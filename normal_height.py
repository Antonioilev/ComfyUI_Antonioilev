import torch
import numpy as np

class NormalToHeightNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "amplitude": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.1}),
                "contrast": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 5.0, "step": 0.1}),
                "offset": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "Antonioilev/2D"

    def execute(self, image, amplitude, contrast, offset):
        # image shape: [B, H, W, 3]
        img = image.squeeze(0).cpu().numpy()
        
        # 1. Приводим нормали к диапазону [-1, 1]
        nx = img[..., 0] * 2.0 - 1.0
        ny = img[..., 1] * 2.0 - 1.0
        nz = img[..., 2] * 2.0 - 1.0
        
        # 2. Отношение градиентов
        gx = nx / (nz + 1e-6)
        gy = ny / (nz + 1e-6)
        
        # 3. Интегрирование через FFT
        H, W = gx.shape
        u = np.fft.fftfreq(W)
        v = np.fft.fftfreq(H)
        U, V = np.meshgrid(u, v)
        
        denom = (U**2 + V**2)
        denom[0, 0] = 1.0
        
        FX = np.fft.fft2(gx)
        FY = np.fft.fft2(gy)
        
        H_freq = (1j * U * FX + 1j * V * FY) / (2 * np.pi * denom)
        height_map = np.real(np.fft.ifft2(H_freq))
        
        # 4. Исходная нормализация (база)
        h_min = height_map.min()
        h_max = height_map.max()
        height_map = (height_map - h_min) / (h_max - h_min + 1e-6)
        
        # 5. Применение регулировок (строго после базовой логики)
        # При дефолтных значениях (1, 1, 0) эти операции возвращают исходную карту
        # Контраст и амплитуда применяются относительно центра 0.5
        height_map = (height_map - 0.5) * contrast + 0.5
        height_map = (height_map - 0.5) * amplitude + 0.5
        height_map = height_map + offset
        
        # Финальный клип
        height_map = np.clip(height_map, 0.0, 1.0)
        
        # Возвращаем как RGB IMAGE
        out = np.stack([height_map]*3, axis=-1)
        return (torch.from_numpy(out).unsqueeze(0).float(),)

# Регистрация нод
NODE_CLASS_MAPPINGS = {"NormalHeight": NormalToHeightNode, "normal_height_antonioilev": NormalToHeightNode}

NODE_DISPLAY_NAME_MAPPINGS = {"NormalHeight": "Normal height", "normal_height_antonioilev": "📏 Normal Height (for MV) "}