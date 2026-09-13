import re
import os
import torch
import numpy as np
from PIL import Image
import folder_paths
import random
import glob

# --- EXR support (optional, graceful fallback) ---
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"  # must be before cv2 import
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import imageio.v3 as iio
    IMAGEIO_AVAILABLE = True
except ImportError:
    try:
        import imageio as iio
        IMAGEIO_AVAILABLE = True
    except ImportError:
        IMAGEIO_AVAILABLE = False


class View2DSaveLoad:
    def __init__(self):
        self.temp_dir = folder_paths.get_temp_directory()
        self.type = "temp"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "path": ("STRING", {"default": "L:/AI_3d/output"}),
                "filename": ("STRING", {"default": "view"}),
                "index_list": ("STRING", {"default": "1,2,3,4,5,6"}),
                "mode": (["Auto (Load if empty)", "Save Only", "Load Only", "Preview"],),
            },
            "optional": {
                "bc": ("IMAGE",),
                "nm": ("IMAGE",),
                "pos": ("IMAGE",),
                "save_toggle": ("BOOLEAN", {"default": True}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "exr_exposure": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 100.0, "step": 0.05}),
            }
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("nan")

    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "IMAGE", "MASK")
    RETURN_NAMES = ("bc_out", "nm_out", "pos_out", "full_batch", "IMAGE", "MASK")
    FUNCTION = "execute"
    OUTPUT_NODE = True
    CATEGORY = "Antonioilev/Viewers"

    # =====================================================================
    #  EXR HELPERS  (полностью отдельная ветка)
    # =====================================================================
    def _is_exr(self, filename: str) -> bool:
        return filename.lower().endswith(".exr")

    def _load_exr(self, filepath: str):
        """Load single EXR → torch float32 tensor [1, H, W, C] (C=3 or 4). Values can be >1.0"""
        if not os.path.exists(filepath):
            print(f"[EXR] File not found: {filepath}")
            return None

        img = None
        # Prefer OpenCV
        if CV2_AVAILABLE:
            try:
                data = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
                if data is not None:
                    if data.ndim == 2:
                        data = data[..., None]
                    # BGR(A) → RGB(A)
                    if data.shape[-1] == 3:
                        data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)
                    elif data.shape[-1] == 4:
                        data = cv2.cvtColor(data, cv2.COLOR_BGRA2RGBA)
                    img = data.astype(np.float32)
            except Exception as e:
                print(f"[EXR] cv2 failed: {e}")

        # Fallback to imageio
        if img is None and IMAGEIO_AVAILABLE:
            try:
                img = iio.imread(filepath).astype(np.float32)
                if img.ndim == 2:
                    img = img[..., None]
            except Exception as e:
                print(f"[EXR] imageio failed: {e}")

        if img is None:
            print(f"[EXR] Could not load: {filepath}")
            return None

        # Ensure channels
        if img.shape[-1] == 1:
            img = np.repeat(img, 3, axis=-1)
        elif img.shape[-1] > 4:
            img = img[..., :4]

        # Гарантируем форму [H, W, C]
        img = np.ascontiguousarray(img)
        while img.ndim > 3:
            img = img[0]

        tensor = torch.from_numpy(img).unsqueeze(0)  # → [1, H, W, C]
        print(f"[EXR] Loaded shape: {tensor.shape}, min={tensor.min():.4f}, max={tensor.max():.4f}")
        return tensor


    def _exr_to_preview_png(self, tensor: torch.Tensor, temp_name: str, exr_exposure: float = 1.0):
        """
        Создаёт PNG-превью с автоматическим сжатием диапазона (без жёсткого клипа теней).
        Использует percentile-based exposure + soft Reinhard.
        """
        if tensor is None:
            return None

        data = tensor.detach().cpu().numpy()

        # → [H, W, C]
        while data.ndim > 3 and data.shape[0] == 1:
            data = data[0]
        if data.ndim == 2:
            data = data[..., None]
        if data.ndim != 3:
            print(f"[EXR Preview] Unexpected shape: {data.shape}")
            return None

        # Берём только RGB для тонемапа
        rgb = data[..., :3].astype(np.float32)

        # Если значения выглядят как 0-255 (а не 0-1 / HDR) — нормализуем
        if rgb.max() > 2.0:
            print(f"[EXR Preview] Detected 0-255 range (max={rgb.max():.1f}), normalizing /255")
            rgb = rgb / 255.0
        
        # --- Авто-экспозиция по перцентилям (сохраняем тени, сжимаем хайлайты) ---
        # Игнорируем совсем чёрные пиксели
        valid = rgb[rgb > 1e-6]
        if valid.size > 0:
            # 99-й перцентиль — почти максимум без выбросов
            p99 = np.percentile(valid, 99.5)
            # 50-й — медиана (для дополнительной стабильности)
            p50 = np.percentile(valid, 50)
            # Целевая яркость середины ≈ 0.18 (примерно 18% серый)
            if p50 > 1e-6:
                exposure = 0.18 / p50                
            else:
                exposure = 1.0 / max(p99, 1e-6)
            # Ограничиваем, чтобы не перекрутить
            exposure = np.clip(exposure, 0.05, 20.0)
        else:
            exposure = 1.0

        hdr = rgb * exposure
        hdr = hdr * exr_exposure

        # Soft Reinhard (лучше сохраняет контраст, чем простой / (1+x))
        # Вариант: hdr / (1 + hdr)  — классика
        # Более мягкий:  hdr * (1 + hdr / (white²)) / (1 + hdr)
        white = 4.0          # насколько высоко уходят хайлайты
        tonemapped = hdr * (1.0 + hdr / (white * white)) / (1.0 + hdr)

        tonemapped = np.clip(tonemapped, 0.0, 1.0)

        # Гамма для отображения (приблизительно sRGB)
        tonemapped = np.power(tonemapped, 1.0 / 2.2)

        # Собираем PNG
        if data.shape[-1] >= 4:
            alpha = np.clip(data[..., 3:4], 0.0, 1.0)
            png = np.concatenate([tonemapped, alpha], axis=-1)
            png = (png * 255.0).astype(np.uint8)
            mode = "RGBA"
        else:
            png = (tonemapped * 255.0).astype(np.uint8)
            mode = "RGB"

        if png.ndim != 3 or png.shape[2] not in (3, 4):
            print(f"[EXR Preview] Bad png shape: {png.shape}")
            return None

        img = Image.fromarray(png, mode=mode)
        img.save(os.path.join(self.temp_dir, temp_name), compress_level=1)
        print(f"[EXR Preview] exposure={exposure:.3f}  p50≈{p50 if 'p50' in locals() else 0:.4f}")
        return {"filename": temp_name, "subfolder": "", "type": self.type}

    def _save_exr(self, tensor: torch.Tensor, filepath: str, exr_exposure: float = 1.0):
        """Save float32 tensor as real EXR."""
        if tensor is None:
            print("[EXR] Nothing to save")
            return

        data = tensor.detach().cpu().numpy()
        while data.ndim > 3 and data.shape[0] == 1:
            data = data[0]
        if data.ndim == 2:
            data = data[..., None]
            
        # Применяем экспозицию для сохранения в HDR (если экспозиция != 1.0)
        if exr_exposure != 1.0:
            data = data * exr_exposure

        data = np.ascontiguousarray(data.astype(np.float32))
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

        success = False

        # --- 1. imageio + FreeImage (самый рабочий путь сейчас) ---
        if IMAGEIO_AVAILABLE:
            try:
                # Явно указываем плагин FreeImage
                if hasattr(iio, "imwrite"):
                    iio.imwrite(filepath, data, plugin="EXR-FI")
                else:
                    iio.imwrite(filepath, data, format="EXR-FI")
                
                if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                    #print(f"[EXR] Saved OK (imageio/FreeImage): {filepath}  "
                    #      f"size={os.path.getsize(filepath)} bytes  shape={data.shape}")
                    print(f"[EXR] Saved OK (imageio/FreeImage): {filepath}  size={os.path.getsize(filepath)} bytes  shape={data.shape}")
                    success = True
            except Exception as e:
                print(f"[EXR] imageio/FreeImage failed: {e}")

        # --- 2. Чистый OpenEXR (если установлен) ---
        if not success:
            try:
                import OpenEXR
                import Imath

                h, w = data.shape[:2]
                channels = {}
                header = OpenEXR.Header(w, h)
                header['compression'] = Imath.Compression(Imath.Compression.ZIP_COMPRESSION)

                if data.shape[-1] >= 3:
                    channels['R'] = data[..., 0].astype(np.float32).tobytes()
                    channels['G'] = data[..., 1].astype(np.float32).tobytes()
                    channels['B'] = data[..., 2].astype(np.float32).tobytes()
                if data.shape[-1] >= 4:
                    channels['A'] = data[..., 3].astype(np.float32).tobytes()

                out = OpenEXR.OutputFile(filepath, header)
                out.writePixels(channels)
                out.close()

                if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                    print(f"[EXR] Saved OK (OpenEXR): {filepath}  size={os.path.getsize(filepath)} bytes")
                    success = True
            except Exception as e:
                print(f"[EXR] pure OpenEXR failed: {e}")

        # --- 3. OpenCV (на 5.0 почти наверняка не сработает) ---
        if not success and CV2_AVAILABLE:
            try:
                if data.shape[-1] == 3:
                    out = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)
                elif data.shape[-1] == 4:
                    out = cv2.cvtColor(data, cv2.COLOR_RGBA2BGRA)
                else:
                    out = data
                ok = cv2.imwrite(filepath, out.astype(np.float32))
                if ok and os.path.getsize(filepath) > 100:
                    print(f"[EXR] Saved OK (cv2): {filepath}")
                    success = True
                else:
                    print(f"[EXR] cv2.imwrite returned {ok}")
            except Exception as e:
                print(f"[EXR] cv2 failed: {e}")

        if not success:
            print(f"[EXR] !!! FAILED to save: {filepath}")
            if os.path.exists(filepath) and os.path.getsize(filepath) == 0:
                try:
                    os.remove(filepath)
                except:
                    pass

    # =====================================================================
    #  MAIN EXECUTE
    # =====================================================================
    def execute(self, path, filename, mode, index_list, bc=None, nm=None, pos=None, save_toggle=True, seed=0, exr_exposure=1.0):
        clean_path = os.path.normpath(path)
        ui_images = list()

        is_preview = (mode == "Preview")
        is_save_only = (mode == "Save Only") or (is_preview and save_toggle)
        is_load_mode = (mode == "Load Only") or (mode == "Auto (Load if empty)" and bc is None and nm is None and pos is None)

        colors = ["#aaaaaa", "#555555"] if (is_preview and not save_toggle) else (
            ["#3355ff", "#112255"] if is_load_mode else ["#33aa33", "#115511"])

        out_tensors = {"bc": bc, "nm": nm, "pos": pos}
        prefix_rand = "".join(random.choice("abcdef") for x in range(5))

        # =================================================================
        #  ★★★  ОТДЕЛЬНАЯ ВЕТКА EXR  ★★★
        #  Если filename заканчивается на .exr — работаем только здесь
        # =================================================================
        if self._is_exr(filename):
            exr_path = os.path.join(clean_path, filename)

            # --- LOAD EXR ---
            if is_load_mode:
                loaded = self._load_exr(exr_path)
                if loaded is not None:
                    # Кладём в bc (основной слот)
                    out_tensors["bc"] = loaded
                    # Создаём превью для UI
                    prev = self._exr_to_preview_png(loaded, f"exr_preview_{prefix_rand}.png", exr_exposure)
                    if prev:
                        ui_images.append(prev)

            # --- SAVE EXR ---
            elif is_save_only:
                # Берём то, что пришло через bc (или nm/pos как fallback)
                source = bc if bc is not None else (nm if nm is not None else pos)
                if source is not None:
                    self._save_exr(source, exr_path, exr_exposure)
                    # Превью тоже создаём
                    prev = self._exr_to_preview_png(source, f"exr_preview_{prefix_rand}.png", exr_exposure)
                    if prev:
                        ui_images.append(prev)
                    out_tensors["bc"] = source  # пробрасываем дальше

            # --- PREVIEW only ---
            elif is_preview:
                source = bc if bc is not None else (nm if nm is not None else pos)
                if source is not None:
                    prev = self._exr_to_preview_png(source, f"exr_preview_{prefix_rand}.png", exr_exposure)
                    if prev:
                        ui_images.append(prev)
                    out_tensors["bc"] = source
                else:
                    # Попробовать загрузить с диска для превью
                    loaded = self._load_exr(exr_path)
                    if loaded is not None:
                        prev = self._exr_to_preview_png(loaded, f"exr_preview_{prefix_rand}.png", exr_exposure)
                        if prev:
                            ui_images.append(prev)
                        out_tensors["bc"] = loaded

            # --- OUTPUT для EXR-ветки ---
            bc_out = out_tensors["bc"]
            nm_out = out_tensors["nm"]
            pos_out = out_tensors["pos"]
            final_out = bc_out  # для EXR основной канал — bc

            return {
                "ui": {"images": ui_images, "color": colors},
                "result": (
                    bc_out.cpu() if bc_out is not None else None,
                    nm_out.cpu() if nm_out is not None else None,
                    pos_out.cpu() if pos_out is not None else None,
                    final_out.cpu() if final_out is not None else None,
                    final_out[..., :3].cpu() if final_out is not None else None,
                    torch.ones_like(final_out[..., 0]).cpu() if final_out is not None else None
                )
            }

        # =================================================================
        #  ДАЛЬШЕ ИДЁТ СТАРАЯ ЛОГИКА (PNG) — НИЧЕГО НЕ ТРОГАЕМ
        # =================================================================

        def generate_channel_atlas(bc_t, nm_t, pos_t):
            # Фильтруем только те каналы, которые не None и содержат хотя бы одну картинку
            active_channels = []
            if bc_t is not None and bc_t.shape[0] > 0: active_channels.append(("bc", bc_t))
            if nm_t is not None and nm_t.shape[0] > 0: active_channels.append(("nm", nm_t))
            if pos_t is not None and pos_t.shape[0] > 0: active_channels.append(("pos", pos_t))
            
            if not active_channels: return
            # Ищем максимальное количество картинок среди всех активных каналов
            max_imgs = max(ch[1].shape[0] for ch in active_channels)
            
            # Берем размеры первого доступного тензора
            _, h, w, _ = active_channels[0][1].shape
            
            # Создаем холст: (количество активных каналов) строк на max_imgs столбцов
            num_rows = len(active_channels)
            atlas = np.zeros((num_rows * h, max_imgs * w, 4), dtype=np.uint8)
            for row_idx, (suffix, batch) in enumerate(active_channels):
                data = (batch.detach().cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
                for col_idx in range(data.shape[0]):
                    if data.shape[-1] == 4:
                        atlas[
                            row_idx*h:(row_idx+1)*h,
                            col_idx*w:(col_idx+1)*w,
                            :
                        ] = data[col_idx]
                    else:
                        atlas[
                            row_idx*h:(row_idx+1)*h,
                            col_idx*w:(col_idx+1)*w,
                            :3
                        ] = data[col_idx]
                        atlas[
                            row_idx*h:(row_idx+1)*h,
                            col_idx*w:(col_idx+1)*w,
                            3
                        ] = 255
            img = Image.fromarray(atlas, mode="RGBA")
            temp_name = f"atlas_{prefix_rand}.png"
            img.save(os.path.join(self.temp_dir, temp_name))
            ui_images.append({"filename": temp_name, "subfolder": "", "type": self.type})

        # --- SAVE LOGIC ---
        if is_save_only and (bc is not None or nm is not None or pos is not None):
            os.makedirs(clean_path, exist_ok=True)
            def save_channel(batch, suffix):
                if batch is None: return None
                # Если batch — это словарь (ошибка), берем тензор, иначе работаем с batch
                tensor = batch['uv_proj'] if isinstance(batch, dict) else batch
                data = (tensor.detach().cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
                for i in range(data.shape[0]):
                    if data.shape[-1] == 4:
                        img = Image.fromarray(data[i], mode="RGBA")
                    else:
                        img = Image.fromarray(data[i][..., :3], mode="RGB")
                    # Если имя уже с .png, сохраняем как есть (или с индексом, если батч > 1)
                    if filename.lower().endswith('.png'):
                        save_name = filename if data.shape[0] == 1 else filename.replace('.png', f'_{i+1}.png')
                    else:
                        save_name = f"{filename}_{suffix}_{i+1}.png"
                    img.save(os.path.join(clean_path, save_name), compress_level=1)
                return batch
            out_tensors["bc"] = save_channel(bc, "bc")
            out_tensors["nm"] = save_channel(nm, "nm")
            out_tensors["pos"] = save_channel(pos, "pos")
            generate_channel_atlas(out_tensors["bc"], out_tensors["nm"], out_tensors["pos"])

        # --- PREVIEW LOGIC ---
        elif is_preview:
            # Если пользователь указал конкретный файл с .png, берем только его
            if filename.lower().endswith('.png'):
                target_batch = bc if bc is not None else (nm if nm is not None else pos)
                if target_batch is not None:
                    generate_channel_atlas(target_batch[0:1], None, None)
            else:
                # В обычном режиме показываем полный атлас
                generate_channel_atlas(bc, nm, pos)

        # --- LOAD LOGIC ---
        elif is_load_mode:
            def load_single_file(filepath):
                if os.path.exists(filepath):
                    try:
                        src = Image.open(filepath)
                        has_alpha = (
                            src.mode in ("RGBA", "LA")
                            or (src.mode == "P" and "transparency" in src.info)
                        )
                        img = src.convert("RGBA" if has_alpha else "RGB")
                        return torch.from_numpy(np.array(img).astype(np.float32) / 255.0).unsqueeze(0)
                    except Exception as e:
                        print(f"DEBUG: Error loading {filepath}: {e}")
                return None

            def load_sequence(base_name, suffix):
                pattern = os.path.join(clean_path, f"{base_name}_{suffix}_*.png")
                files = glob.glob(pattern)
                if not files: return None
                files.sort(key=lambda f: int(os.path.basename(f).split('_')[-1].split('.')[0]))
                
                # --- ВНЕДРЕНИЕ ЛОГИКИ ИНДЕКСОВ ---
                if index_list and index_list.strip():
                    try:
                        indices_str = re.split(r'[,\s]+', index_list.strip())
                        requested_indices = [int(x) for x in indices_str if x.strip()]
                        
                        filtered_files = []
                        for idx in requested_indices:
                            for f in files:
                                file_idx = int(os.path.basename(f).split('_')[-1].split('.')[0])
                                if file_idx == idx:
                                    filtered_files.append(f)
                        files = filtered_files
                    except Exception as e:
                        print(f"DEBUG: Index list parsing error: {e}. Loading all.")
                # ---------------------------------
                
                imgs = []
                for f in files:
                    try:
                        src = Image.open(f)
                        has_alpha = (
                            src.mode in ("RGBA", "LA")
                            or (src.mode == "P" and "transparency" in src.info)
                        )
                        img = src.convert("RGBA" if has_alpha else "RGB")
                        imgs.append(
                            torch.from_numpy(
                                np.array(img).astype(np.float32) / 255.0
                            ).unsqueeze(0)
                        )
                    except Exception as e:
                        print(f"DEBUG: Error loading {f}: {e}")
                return torch.cat(imgs, dim=0) if imgs else None

            out_tensors = {"bc": None, "nm": None, "pos": None}
            # РАЗДЕЛЕНИЕ ЛОГИКИ
            if filename.lower().endswith('.png'):
                # 1. Режим одного файла: определяем канал по имени файла
                single_img = load_single_file(os.path.join(clean_path, filename))
                if single_img is not None:
                    if "_bc_" in filename: out_tensors["bc"] = single_img
                    elif "_nm_" in filename: out_tensors["nm"] = single_img
                    elif "_pos_" in filename: out_tensors["pos"] = single_img
                    else: out_tensors["bc"] = single_img
            else:
                # 2. Режим серии
                parts = filename.split('_')
                requested_suffix = parts[-1] if parts[-1] in ["bc", "nm", "pos"] else None
                base_name = "_".join(parts[:-1]) if requested_suffix else filename
                suffixes = [requested_suffix] if requested_suffix else ["bc", "nm", "pos"]
                for s in suffixes:
                    out_tensors[s] = load_sequence(base_name, s)
            # Генерируем атлас
            generate_channel_atlas(out_tensors["bc"], out_tensors["nm"], out_tensors["pos"])

        # --- OUTPUT ---
        bc_out = out_tensors["bc"]
        nm_out = out_tensors["nm"]
        pos_out = out_tensors["pos"]
        final_out = pos_out if pos_out is not None else (nm_out if nm_out is not None else bc_out)

        return {
            "ui": {"images": ui_images, "color": colors},
            "result": (
                bc_out.cpu() if bc_out is not None else None,
                nm_out.cpu() if nm_out is not None else None,
                pos_out.cpu() if pos_out is not None else None,
                final_out.cpu() if final_out is not None else None,
                final_out[..., :3].cpu() if final_out is not None else None,
                torch.ones_like(final_out[..., 0]).cpu() if final_out is not None else None
            )
        }


NODE_CLASS_MAPPINGS = {"View2DSaveLoad": View2DSaveLoad}
NODE_DISPLAY_NAME_MAPPINGS = {"View2DSaveLoad": "👁️💾📂 2D View Save Load"}