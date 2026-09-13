from .image_saver import ImageSaver
from .load_batch_images import Load_batch_images
from .save_batch_images import Save_batch_images
from .save_batch_images_alfa import SaveBatchImagesWithAlphaMask
from .glb_extractor import GLBTextureExtractor
from .uv_scaler_node import UVShellScale
from .clean_mesh import AntonioilevCleanMesh
from .mesh_hardbottom import AntonioilevHardBottomCap
from .hole_surgeon import AntonioilevHoleSurgeon
from .uv_fixer import AntonioilevUVFixer
from .uv_unwrap import AntonioilevUVUnwrap
from .normal_converter import NormalSpaceConverter
from .load_mesh import LoadMesh
from .cap_gpu import AntonioilevCapGPU
from .mesh_one_surface import MeshOneSurface
from .mesh_projector import MeshProjector
from .mesh_fixer_pro import MeshFix
from .gpu_mesh_builder import RemeshGPU
from .uv_watertight import UVWatertight
from .refine_mesh import RefineMeshNode
from .mesh_uv_watertight import mesh_uv_watertight
from .preview_mesh_uv import SafePreviewMeshUV
from .uv_safe_test import AntonioilevSafeUVTest
from .image_loader import ImageLoader
from .mesh_cutter import AntonioilevMultiMeshCutter
from .composite_saver import AntonioilevCompositeSaver
from .color_cutter_mesh import AntonioilevMultiColorizer
from .mesh_cleaner import AntonioilevMeshCleaner
from .hole_filler import AntonioilevHoleFiller
from .fix_normals import AntonioilevMeshFixNormals
from .list_batch_images import List_batch_images
from .clear_vram import AntonioilevClearVRAM
from .view_2d_save_load import View2DSaveLoad
from .long_holes import LongHoles
from .view_3d_save_load import Ultimate3DViewSaveLoad
from .image_lightness import LightAdjustment
from .suffix import SuffixNode
from .hole_hub.hole_hub import HoleHub


NODE_CLASS_MAPPINGS = {
    "ImageSaver": ImageSaver,
    "AntonioilevLoadBatchImages": Load_batch_images,
    "AntonioilevSaveBatchImages": Save_batch_images,
    "AntonioilevSaveBatchImagesWithAlpha": SaveBatchImagesWithAlphaMask,
    "AntonioilevGLBTextureExtractor": GLBTextureExtractor,
    "AntonioilevUVShellScale": UVShellScale,
    "AntonioilevUVWatertight": UVWatertight,
    "AntonioilevCleanMesh": AntonioilevCleanMesh,
    "AntonioilevHardBottomCap": AntonioilevHardBottomCap,
    "AntonioilevHoleSurgeon": AntonioilevHoleSurgeon,
    "AntonioilevUVFixer": AntonioilevUVFixer,
    "AntonioilevUVUnwrap": AntonioilevUVUnwrap,
    "AntonioilevNormalSpaceConverter": NormalSpaceConverter,
    "LoadMesh": LoadMesh,
    "AntonioilevCapGPU": AntonioilevCapGPU,
    "AntonioilevMeshOneSurface": MeshOneSurface,
    "AntonioilevMeshProjector": MeshProjector,
    "AntonioilevMeshFix": MeshFix,
    "AntonioilevRemeshGPU": RemeshGPU,    
    "AntonioilevRefineMesh": RefineMeshNode,
    "mesh_uv_watertight": mesh_uv_watertight,
    "preview_mesh_uv": SafePreviewMeshUV,    
    "ImageLoader": ImageLoader,
    "AntonioilevMultiMeshCutter": AntonioilevMultiMeshCutter,
    "AntonioilevCompositeSaver": AntonioilevCompositeSaver,
    "AntonioilevMultiColorizer": AntonioilevMultiColorizer,
    "AntonioilevMeshCleaner": AntonioilevMeshCleaner,
    "AntonioilevHoleFiller": AntonioilevHoleFiller,
    "AntonioilevMeshFixNormals": AntonioilevMeshFixNormals,
    "AntonioilevListBatchImages": List_batch_images,
    "AntonioilevClearVRAM": AntonioilevClearVRAM,
    "View2DSaveLoad": View2DSaveLoad,
    "LongHoles": LongHoles,
    "Ultimate3DViewSaveLoad": Ultimate3DViewSaveLoad,
    "ToneAdjustment": LightAdjustment,
    "Suffix": SuffixNode,
    "HoleHub": HoleHub,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageSaver": "💾 Image + Mask Saver",
    "AntonioilevLoadBatchImages": "📂 Load Batch Images (BC/NM/POS)",
    "AntonioilevSaveBatchImages": "💾 Save Batch Images (BC/NM/POS)",
    "AntonioilevSaveBatchImagesWithAlphaMask": "💾 Save Batch Images with Alpha Mas",
    "AntonioilevGLBTextureExtractor": "📦 GLB Texture Extractor",
    "AntonioilevUVShellScale": "📐 UV Shell Scaler",
    "AntonioilevUVWatertight": "🧷 UV-Safe Hard Weld",
    "AntonioilevCleanMesh": "✂ Clean Mesh (Dynamic Guard)",
    "AntonioilevHardBottomCap": "⚓ Hard Bottom Cap (Strict)",
    "AntonioilevHoleSurgeon": "💉 Hole Surgeon (Hair Safe)",
    "AntonioilevUVFixer": "🌀 UV Fixer & Packer",
    "AntonioilevUVUnwrap": "🌀 UV Unwrap (Standard Xatlas)",
    "AntonioilevNormalSpaceConverter": "🚦 Normal Space Converter",
    "LoadMesh": "📦 Load Mesh (Scanner + FBX)",
    "AntonioilevCapGPU": "🧩 CapGPU (Advanced Sealer)",
    "AntonioilevMeshOneSurface": "🌊 Mesh One Surface",
    "AntonioilevMeshProjector": "🎯 Detail Recover (Iterative)",
    "AntonioilevMeshFix": "🩺 Mesh Fixer Fast",
    "AntonioilevRemeshGPU": "🧱 GPU Mesh Builder (Watertight)",    
    "AntonioilevRefineMesh": "💎 Refine Mesh Structural V3.5",
    "mesh_uv_watertight": "🧭 Mesh UV Watertight",
    "preview_mesh_uv": "🌀 UV preview",
    "AntonioilevSafeUVTest": "?? Topology-Safe UV (Fixed Integrity)",
    "ImageLoader": "📥 Image + Mask Loader",
    "AntonioilevMultiMeshCutter": "✂️ Multi Mesh Cutter (Sequential)",
    "AntonioilevCompositeSaver": "💾🧱 Composite Mesh Saver (Assimp FBX)",
    "AntonioilevMultiColorizer": "🎨 Multi Mesh Colorizer (10 Slots)",
    "AntonioilevMeshCleaner": "🧹 Mesh Cleaner (Pre-op)",
    "AntonioilevHoleFiller": "🧵 Hole Filler",
    "AntonioilevMeshFixNormals": "🚀 Fix Normals Conform",
    "AntonioilevListBatchImages": "📚 List Batch Images",
    "AntonioilevClearVRAM": "🧹 Clear VRAM",
    "View2DSaveLoad": "👁️💾📂 2D View Save Load",
    "LongHoles": "🕳️ Long Holes Finder",
    "Ultimate3DViewSaveLoad": "🔍📐📦 3D View Save Load",
    "ToneAdjustment": "🌓 Lightness Shadows/Mid/High",
    "Suffix": "🏷️ Suffix",
    "HoleHub": "🕳️ Hole hub",
}

print(f"[Antonioilev_Light_pack] Loaded {len(NODE_CLASS_MAPPINGS)} nodes.")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
WEB_DIRECTORY = "./web"