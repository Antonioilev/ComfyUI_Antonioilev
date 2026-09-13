# === HF CACHE (CU130) ===
export HF_HOME=/mnt/l/AI_cache/huggingface
export HUGGINGFACE_HUB_CACHE=/mnt/l/AI_cache/huggingface

# ============================================================
# USER SETUP
# Move/copy this file to your ComfyUI root directory.
# Example:
# <your path>/ComfyUI_cu130/init_lowvram.sh
#
# Then adjust the paths below to match your local environment:
#   HF_HOME
#   HUGGINGFACE_HUB_CACHE
#   BLENDER_PATH
#
# The ComfyUI and Antonioilev paths are relative and require
# no manual configuration.
#
#   ComfyUI_cu130/
#   │
#   ├── main.py
#   ├── init_lowvram.sh
#   │
#   └── custom_nodes/
#       └── ComfyUI_Antonioilev/
#           ├── __init__.py
#           ├── nodes/
#           ├── texturing/
#           └── ...
#
# ============================================================

export TRANSFORMERS_OFFLINE=0

# === ComfyUI safe stack ===
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
#================================
# disable unstable attention
export SAGEATTENTION_DISABLE=1

# stable backend for 3090
export COMFYUI_ATTENTION_BACKEND=sdp
export FORCE_SPARSE_BACKEND=scipy

# Blender
export BLENDER_PATH="/mnt/l/Blender/blender-4.2.19-linux-x64/blender"

# GPU
export CUDA_VISIBLE_DEVICES=0

# memory tuning
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# run
python main.py \
--lowvram \
--disable-smart-memory \
--disable-pinned-memory \
--bf16-unet \
--bf16-vae \
--use-pytorch-cross-attention \
--port 8190 \
--temp-directory ./temp_cu130