import os

class SuffixNode:
    """
    Нода Suffix для добавления префикса и/или суффикса к имени файла 
    с сохранением расширения (файл.расширение -> префикс_файл_суффикс.расширение).
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": False}),
            },
            "optional": {
                "prefix": ("STRING", {"default": ""}),
                "suffix": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("string",)
    FUNCTION = "process"
    CATEGORY = "Antonioilev/Utils"

    def process(self, text: str, prefix: str = "", suffix: str = "") -> tuple:
        # Разделяем путь/имя файла на основную часть и расширение
        file_name, file_ext = os.path.splitext(text)
        
        # Собираем новую строку: префикс + имя + суффикс + расширение
        result = f"{prefix}{file_name}{suffix}{file_ext}"
        
        return (result, )


# Регистрация ноды для ComfyUI
NODE_CLASS_MAPPINGS = {"Suffix": SuffixNode}
NODE_DISPLAY_NAME_MAPPINGS = {"Suffix": "🏷️ Suffix"}