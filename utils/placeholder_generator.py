from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os

def create_placeholder_image(width=300, height=300, text="📄", bg_color="#f0f0f0"):
    """Create a simple placeholder image"""
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to use a font, fallback to default if not available
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 48)
    except:
        font = ImageFont.load_default()
    
    # Get text size and center it
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), text, fill="#666666", font=font)
    
    return img

def get_placeholder_bytes(file_type="image"):
    """Get placeholder image as bytes"""
    emoji = "🖼️" if file_type == "image" else "🎥" if file_type == "video" else "📄"
    img = create_placeholder_image(text=emoji)
    
    img_io = BytesIO()
    img.save(img_io, 'JPEG', quality=85)
    img_io.seek(0)
    
    return img_io

def ensure_placeholder_files(static_folder):
    """Ensure placeholder files exist in static folder"""
    images_dir = os.path.join(static_folder, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    placeholders = [
        ('placeholder.jpg', '📄'),
        ('image-placeholder.jpg', '🖼️'),
        ('video-placeholder.jpg', '🎥')
    ]
    
    for filename, emoji in placeholders:
        filepath = os.path.join(images_dir, filename)
        if not os.path.exists(filepath):
            img = create_placeholder_image(text=emoji)
            img.save(filepath, 'JPEG', quality=85)