"""
Module for cropping and processing images.

The crop_images function reads images from a source folder, crops them,
applies resizing and filtering based on configuration options, and saves them
into the designated crop folder.
"""

import os
from PIL import Image, ImageFilter

def crop_images(source_folder: str, crop_folder: str, config) -> None:
    """
    Crop and process images from the source folder to the crop folder,
    applying a vibrance filter if enabled in the configuration.

    Parameters:
        source_folder (str): Folder containing the original images.
        crop_folder (str): Folder where the cropped images will be saved.
        config: A configparser object containing configuration options.
    """
    if not os.path.exists(crop_folder):
        os.mkdir(crop_folder)

    # Prepare LUT for vibrance if enabled
    if config.getboolean("Vibrance.Bump", fallback=False):
        try:
            cube_path = os.path.join(os.path.dirname(__file__), "vibrance.CUBE")
            with open(cube_path) as f:
                lut_raw = f.read().splitlines()[11:]
            lsize = round(len(lut_raw) ** (1/3))
            def row2val(row: str):
                return tuple(float(val) for val in row.split())
            lut_table = [row2val(row) for row in lut_raw]
            lut = ImageFilter.Color3DLUT(lsize, lut_table)
        except Exception:
            lut = None
    else:
        lut = None

    for img_file in os.listdir(source_folder):
        ext = os.path.splitext(img_file)[1].lower()
        if ext not in [".gif", ".jpg", ".jpeg", ".png"]:
            continue
        target_path = os.path.join(crop_folder, img_file)
        if os.path.exists(target_path):
            continue
        try:
            with Image.open(os.path.join(source_folder, img_file)) as im:
                w, h = im.size
                c = round(0.12 * min(w / 2.72, h / 3.7))
                dpi = c * (1 / 0.12)
                crop_im = im.crop((c, c, w - c, h - c))
                max_dpi = config.getint("Max.DPI", fallback=300)
                if dpi > max_dpi:
                    new_w = int(round(crop_im.size[0] * max_dpi / dpi))
                    new_h = int(round(crop_im.size[1] * max_dpi / dpi))
                    crop_im = crop_im.resize((new_w, new_h), Image.Resampling.BICUBIC)
                    crop_im = crop_im.filter(ImageFilter.UnsharpMask(1, 20, 8))
                if lut:
                    crop_im = crop_im.filter(lut)
                crop_im.save(target_path, quality=98)
        except Exception as e:
            print(f"Error processing {img_file}: {e}")
