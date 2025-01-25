import anvil.server
import io
from PIL import Image

@anvil.server.callable
def process_try_on(user_media, cloth_media):
    """
    Receives two anvil.Media objects (for the user/model and cloth).
    Uses Pillow to overlay the cloth on the user image in a naive way.
    Returns the resulting image as an anvil.Media object.
    """
    # Convert Media objects to Pillow Images
    user_img = Image.open(io.BytesIO(user_media.get_bytes()))
    cloth_img = Image.open(io.BytesIO(cloth_media.get_bytes()))

    # Convert images to RGBA (just in case cloth has transparency)
    user_img = user_img.convert("RGBA")
    cloth_img = cloth_img.convert("RGBA")

    # Naive resizing: let's make the cloth ~1/3 the width of the user image
    user_width, user_height = user_img.size
    cloth_ratio = cloth_img.width / cloth_img.height

    new_cloth_width = user_width // 3
    new_cloth_height = int(new_cloth_width / cloth_ratio)

    # Resize the cloth
    cloth_resized = cloth_img.resize((new_cloth_width, new_cloth_height), Image.Resampling.LANCZOS)

    # Position the cloth somewhere near the top of the user image
    offset_x = (user_width - new_cloth_width) // 2
    offset_y = user_height // 4

    # Paste cloth onto user, using cloth's alpha as a mask
    user_img.paste(cloth_resized, (offset_x, offset_y), cloth_resized)

    # Convert the result back to an Anvil Media object
    output_bytes = io.BytesIO()
    user_img.save(output_bytes, format="PNG")
    output_bytes.seek(0)

    return anvil.BlobMedia(
        content_type="image/png",
        content=output_bytes.read(),
        name="virtual_try_on_result.png"
    )
