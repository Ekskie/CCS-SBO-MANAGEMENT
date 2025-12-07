import os
import io
from PIL import Image, ImageOps

def compress_image_bytes(image_data, quality=60, max_size=(1024, 1024), output_format='JPEG'):
    """
    Compresses image bytes (e.g. from a database/cloud storage).
    
    Args:
        image_data (bytes): The raw image data.
        quality (int): Compression quality (1-95).
        max_size (tuple): Max (width, height).
        output_format (str): 'JPEG' (default) or 'WEBP'.
        
    Returns:
        bytes: Compressed image data, or None if compression failed.
    """
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(image_data))
        
        # 1. Fix Orientation: Apply EXIF orientation (rotation) before stripping metadata
        # Critical for phone photos so they don't end up sideways
        img = ImageOps.exif_transpose(img)
        
        # 2. Convert mode
        # Convert to RGB if saving as JPEG, or if image is Palette based
        if output_format.upper() == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        elif output_format.upper() == 'WEBP' and img.mode == 'P':
            img = img.convert('RGBA') # WebP handles transparency
            
        # 3. Resize with High Quality Downsampling
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        output_buffer = io.BytesIO()
        
        # 4. Save with Optimizations
        if output_format.upper() == 'JPEG':
            # progressive=True: Loads gradually on slow connections & often smaller
            # optimize=True: Extra pass to find best encoding
            img.save(output_buffer, format='JPEG', quality=quality, optimize=True, progressive=True)
        elif output_format.upper() == 'WEBP':
            # WebP is generally 25-34% smaller than JPEG
            img.save(output_buffer, format='WEBP', quality=quality, optimize=True)
            
        return output_buffer.getvalue()
        
    except Exception as e:
        print(f"Error compressing image bytes: {e}")
        return None

def compress_and_archive_image(source_path, destination_path, quality=60, max_size=(1024, 1024)):
    """
    Compresses an image from a file path and saves it to a destination path.
    """
    try:
        # Check if source exists
        if not os.path.exists(source_path):
            print(f"Error: Source file not found at {source_path}")
            return False

        # Create destination directory if it doesn't exist
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        with Image.open(source_path) as img:
            # 1. Fix Orientation
            img = ImageOps.exif_transpose(img)
            
            # 2. Convert to RGB for JPEG
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # 3. Resize
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 4. Save with Progressive JPEG
            img.save(destination_path, "JPEG", quality=quality, optimize=True, progressive=True)
            
        return True
        
    except Exception as e:
        print(f"Error compressing image: {e}")
        return False