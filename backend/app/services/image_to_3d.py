import io
import json
import math
from abc import ABC, abstractmethod

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.services.image_service import encode_webp
from app.services.storage_service import StorageService

FRAME_SIZE = 420      # animated preview is 420 x 420 pixels
FRAME_COUNT = 24      # frames in one loop
FRAME_MS = 60         # milliseconds per frame
SWAY_PIXELS = 26      # how far the fruit "turns"


class ImageTo3DService(ABC):
    """Today: LayeredImageService. Later: a real local image-to-3D model producing GLB."""

    @abstractmethod
    def generate(self, image: Image.Image, base_key: str, storage: StorageService) -> str:
        """Saves the generated files and returns the storage key of the manifest."""


class LayeredImageService(ImageTo3DService):
    def generate(self, image: Image.Image, base_key: str, storage: StorageService) -> str:
        work = image.copy()
        work.thumbnail((512, 512))
        mask = self._make_mask(work)

        full_mask = mask.resize(image.size, Image.LANCZOS)
        cutout = image.convert("RGBA")
        cutout.putalpha(full_mask)

        # Pseudo-depth: the middle of the fruit is "closer" than its edges
        depth_small = mask.filter(ImageFilter.GaussianBlur(radius=max(work.size) / 14))
        depth = depth_small.resize(image.size, Image.LANCZOS).convert("RGB")

        storage.save(f"{base_key}/cutout.webp", encode_webp(cutout, 88))
        storage.save(f"{base_key}/depth.webp", encode_webp(depth, 80))

        manifest = {
            "type": "LAYERED_IMAGE",
            "version": 2,
            "cutout": storage.url(f"{base_key}/cutout.webp"),
            "depth": storage.url(f"{base_key}/depth.webp"),
        }

        # Animated preview. If it fails, the still images above still work.
        try:
            animated = self._make_animation(cutout, depth_small)
            storage.save(f"{base_key}/animated.webp", animated)
            manifest["animated"] = storage.url(f"{base_key}/animated.webp")
        except Exception:
            pass

        manifest_key = f"{base_key}/manifest.json"
        storage.save(manifest_key, json.dumps(manifest).encode("utf-8"))
        return manifest_key

    # ---------- animation ----------

    def _make_animation(self, cutout: Image.Image, depth_small: Image.Image) -> bytes:
        size = FRAME_SIZE

        fruit = cutout.copy()
        fruit.thumbnail((int(size * 0.78), int(size * 0.78)), Image.LANCZOS)
        depth_fruit = depth_small.resize(fruit.size, Image.LANCZOS)

        ox = (size - fruit.width) // 2
        oy = int(size * 0.08)
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        layer.paste(fruit, (ox, oy))
        depth_layer = Image.new("L", (size, size), 0)
        depth_layer.paste(depth_fruit, (ox, oy))

        rgba = np.asarray(layer).astype(np.float32)
        depth = np.asarray(depth_layer).astype(np.float32) / 255.0
        ys, xs = np.mgrid[0:size, 0:size]
        x_norm = (xs / (size - 1)) * 2 - 1          # -1 (left) to +1 (right)

        shadow_y = oy + fruit.height + 10
        center_x = size // 2

        frames = []
        for i in range(FRAME_COUNT):
            t = 2 * math.pi * i / FRAME_COUNT
            sway = math.sin(t)                       # -1 to +1, the "turn"
            bob = math.sin(2 * t)                    # gentle up/down

            # Parallax: the middle of the fruit moves more than its edges
            src_x = np.clip(xs - sway * SWAY_PIXELS * depth, 0, size - 1)
            src_y = np.clip(ys - int(round(bob * 5)), 0, size - 1).astype(np.int32)
            x0 = np.floor(src_x).astype(np.int32)
            x1 = np.clip(x0 + 1, 0, size - 1)
            frac = (src_x - x0)[..., None]
            out = rgba[src_y, x0] * (1 - frac) + rgba[src_y, x1] * frac

            # Moving light: one side brightens while the other darkens
            light = 1.0 + 0.14 * sway * x_norm
            out[..., :3] = np.clip(out[..., :3] * light[..., None], 0, 255)

            fruit_frame = Image.fromarray(out.astype(np.uint8), "RGBA")

            # Shadow gets smaller and lighter when the fruit rises
            shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            half_w = fruit.width * (0.34 - 0.03 * bob)
            half_h = 9 - 1.5 * bob
            alpha = int(80 - 15 * bob)
            ImageDraw.Draw(shadow).ellipse(
                (center_x - half_w, shadow_y - half_h, center_x + half_w, shadow_y + half_h),
                fill=(0, 0, 0, alpha),
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(6))

            frames.append(Image.alpha_composite(shadow, fruit_frame))

        buf = io.BytesIO()
        frames[0].save(
            buf, "WEBP", save_all=True, append_images=frames[1:],
            duration=FRAME_MS, loop=0, quality=70, method=4,
        )
        return buf.getvalue()

    # ---------- background removal ----------

    def _make_mask(self, work: Image.Image) -> Image.Image:
        marker = (255, 0, 255)
        flood = work.copy()
        w, h = flood.size
        for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            if flood.getpixel(xy) != marker:
                ImageDraw.floodfill(flood, xy, marker, thresh=40)

        diff = ImageChops.difference(flood, Image.new("RGB", flood.size, marker)).convert("L")
        mask = diff.point(lambda v: 255 if v > 0 else 0)

        # If background removal clearly failed, fall back to a soft oval
        foreground = mask.histogram()[255] / (w * h)
        if foreground < 0.03 or foreground > 0.97:
            mask = Image.new("L", work.size, 0)
            ImageDraw.Draw(mask).ellipse(
                (w * 0.08, h * 0.08, w * 0.92, h * 0.92), fill=255
            )

        return mask.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.5))


def get_image_to_3d_service() -> ImageTo3DService:
    return LayeredImageService()