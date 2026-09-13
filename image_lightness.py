import torch

class LightAdjustment:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "shadows": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "midtones": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "highlights": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "adjust_tones"
    CATEGORY = "Antonioilev/2D"

    def adjust_tones(self, image, shadows, midtones, highlights):
        # Переносим на корректное устройство и тип данных
        img = image.to(dtype=torch.float32)
        
        # Вычисление яркости (Luminance Rec.709)
        lum = 0.2126 * img[..., 0] + 0.7152 * img[..., 1] + 0.0722 * img[..., 2]
        lum = lum.unsqueeze(-1) 

        # Функция плавного перехода (Smoothstep) для четкого разделения зон
        def smoothstep(edge0, edge1, x):
            t = torch.clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
            return t * t * (3.0 - 2.0 * t)

        # Создаем маски:
        # Shadows: 0.0 - 0.4 (тени внизу)
        # Midtones: зона между ними
        # Highlights: 0.6 - 1.0 (блики наверху)
        mask_s = 1.0 - smoothstep(0.0, 0.4, lum)
        mask_h = smoothstep(0.6, 1.0, lum)
        mask_m = 1.0 - (mask_s + mask_h)
        
        # Коэффициенты коррекции: 0.5 = 0 (нет изменений)
        s_val = (shadows - 0.5) * 2.0
        m_val = (midtones - 0.5) * 2.0
        h_val = (highlights - 0.5) * 2.0

        # Применяем коррекцию
        adjustment = (mask_s * s_val + mask_m * m_val + mask_h * h_val)
        out_img = torch.clamp(img + adjustment, 0.0, 1.0)

        return (out_img,)

NODE_CLASS_MAPPINGS = {"ToneAdjustment": LightAdjustment}
NODE_DISPLAY_NAME_MAPPINGS = {"ToneAdjustment": "🌓 Lightness Shadows/Mid/High"}