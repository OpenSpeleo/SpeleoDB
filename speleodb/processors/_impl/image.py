# -*- coding: utf-8 -*-

from __future__ import annotations

from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import FileFormat

# ruff: noqa: E501


class ImageFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [
        # ------------------------ Common raster image formats ----------------------- #
        #
        ".jpg",  # JPEG format, commonly used for photos and web graphics.
        ".jpeg",  # Alternate extension for JPEG.
        ".png",  # PNG format, supports transparency, widely used on the web.
        ".gif",  # GIF format, supports animations and low-color images.
        ".bmp",  # BMP format, uncompressed and large files.
        ".webp",  # WebP format, modern, efficient, supports animations and transparency.
        ".tif",  # TIFF format, often used in professional settings.
        ".tiff",  # Alternate extension for TIFF.
        #
        # -------------------- Less common or older raster formats ------------------- #
        #
        ".ico",  # Icon files, used for favicons and desktop icons.
        ".heic",  # High Efficiency Image Format, common on Apple devices.
        ".heif",  # High Efficiency Image File, a modern container format.
        ".jp2",  # JPEG 2000 format, an advanced but less popular variant.
        ".jpx",  # JPEG 2000 extensions with advanced features.
        ".xbm",  # XBM format, used in X Window systems for monochrome graphics.
        #
        # ---------------------------  Vector image formats -------------------------- #
        #
        ".svg",  # Scalable Vector Graphics, used widely in responsive web design.
        ".svgz",  # Compressed SVG format.
        ".dxf",  # CAD drawings in the DXF format.
        ".eps",  # Encapsulated PostScript, used in publishing and printing.
        ".emf",  # Enhanced Metafile, vector graphics format in Windows.
        #
        # --------------------------- Specialized formats ---------------------------- #
        #
        ".pict",  # Legacy Apple format for graphics.
        ".ras",  # CMU Raster format, used in scientific imaging.
        ".ppm",  # Portable Pixmap, a simple Netpbm format.
        ".pbm",  # Portable Bitmap, monochrome image format.
        ".pgm",  # Portable Graymap, grayscale Netpbm format.
        ".pam",  # Portable Arbitrary Map, a flexible Netpbm format.
        ".icns",  # macOS icon files.
        ".pcx",  # PCX format, an older raster graphics format.
        ".xpm",  # XPM format, an X Window System format for color images.
        #
        # ---------------------- HDR and high-bit-depth formats ---------------------- #
        #
        ".exr",  # OpenEXR, used in visual effects for HDR images.
        ".hdr",  # Radiance HDR format, common in architectural visualization.
        ".dds",  # DirectDraw Surface, often used in 3D textures.
        #
        # ----------------------- Animation and hybrid formats ----------------------- #
        #
        ".apng",  # Animated PNG, supports advanced PNG animations.
        ".mng",  # MNG, an animated variant of PNG (rarely used).
        ".flif",  # FLIF format, an experimental lossless image format.
        ".g3",  # G3 fax format, used in fax systems.
        #
        # ---------------- Image formats with embedded layers or data ---------------- #
        #
        ".psd",  # Adobe Photoshop Document, supports layers and advanced features.
        ".xcf",  # GIMP native file format.
        ".ai",  # Adobe Illustrator files, sometimes considered an image file for vectors
        #
        # --------------------- Miscellaneous and exotic formats --------------------- #
        #
        ".djvu",  # DjVu format, often used for scanned documents.
        ".fits",  # FITS format, widely used in astronomy.
        ".tga",  # TGA format, common in early graphics applications and games.
        ".jbig2",  # JBIG2 format, used for high compression of binary images.
        ".wbmp",  # Wireless Bitmap, used in early mobile devices.
        ".raw",  # Generic RAW format for unprocessed camera data.
        ".fpx",  # FlashPix format, for large, scalable images.
        ".palm",  # Palm Pix format, used in Palm OS devices.
        ".dwg",  # AutoCAD drawing files (sometimes considered graphical).
        ".sgi",  # SGI format, for Silicon Graphics workstations.
        ".vst",  # VST format, used in early graphic design tools.
        ".sun",  # Sun Raster files, for Sun Microsystems systems.
        ".cgm",  # Computer Graphics Metafile, for technical diagrams.
        ".vtf",  # Valve Texture Format, used in gaming (Source engine).
        #
        # ------------------------ Historical or niche formats ----------------------- #
        #
        ".koala",  # Koala Paint format, used on Commodore systems.
        ".ani",  # Animated cursor files on Windows (technically hybrid with images).
        ".cur",  # Cursor files on Windows, similar to ICO.
        ".pix",  # PIX format, a proprietary format used in specific graphics systems.
        ".imgw",  # IMGW, a weather-related visualization format.
    ]

    ALLOWED_MIMETYPES = ["*"]
    ASSOC_FILEFORMAT = FileFormat.OTHER

    TARGET_FOLDER = "images"
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None
