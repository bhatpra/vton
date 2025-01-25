import anvil.server
import anvil
import requests
import json
import time
import io
import base64
from PIL import Image

# ---------------------------------------------------------------------
# If you have separate config or environment variables in Anvil, 
# you can store your API keys there. Here, we hard-code them:
# ---------------------------------------------------------------------
API_URL = "https://modelslab.com/api/v6/image_editing/fashion"
CROP_API_URL = "https://modelslab.com/api/v3/base64_crop"
API_KEY = "TimeKtPLuNBR2UytsfQtArv6c4Wbg4dO0sBqwrIIVTQteu9e7CTbE7IzHTh1"  # Replace with your Stable Diffusion API key
IMGBB_API_KEY = "84f2702ff0a615541a76ef4b07ed0763"  # Replace with your imgbb API key

# ---------------------------------------------------------------------
# HELPER FUNCTIONS (adapted from your Flask code)
# ---------------------------------------------------------------------
def convert_image_to_base64(image_path):
    """Converts a local image file to a base64 string."""
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    return encoded_string.decode('utf-8')

def download_image(image_url, output_file):
    """Downloads an image from the given URL and saves it locally."""
    response = requests.get(image_url)
    if response.status_code == 200:
        with open(output_file, "wb") as img_file:
            img_file.write(response.content)
    else:
        raise Exception(f"Failed to fetch image. Status code: {response.status_code}")

def get_image_as_media(image_url):
    """
    Downloads the final image from 'image_url' and returns it 
    as an anvil.BlobMedia object so it can be displayed in Anvil.
    """
    output_file_png = "sdoutput.png"
    download_image(image_url, output_file_png)

    # Convert to a BytesIO stream
    with Image.open(output_file_png) as img:
        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)

    return anvil.BlobMedia(content_type="image/png", content=output.read(), name="sdoutput.png")

# ---------------------------------------------------------------------
# If you need to do an image crop before uploading:
def upload_to_sd(file_path):
    """
    Uploads an image to the 'CROP_API_URL' and returns the link from the response.
    (You have a separate function for imgbb as well, but let's keep only what we need.)
    """
    img_base64_string = convert_image_to_base64(file_path)
    payload = json.dumps({
        "key": API_KEY,
        "image": "data:image/png;base64," + img_base64_string,
        "crop": "false"
    })
    headers = {'Content-Type': 'application/json'}
    response = requests.post(CROP_API_URL, headers=headers, data=payload)

    if response.status_code == 200:
        data = response.json()
        if "link" in data:
            return data["link"]
        else:
            raise Exception(f"Unexpected response (no link field): {data}")
    else:
        raise Exception(f"Failed upload_to_sd: {response.text}")

def process_and_fetch_image(payload):
    """
    Posts payload to the main API_URL, and if the status = 'processing',
    it polls the 'fetch_result' URL until the image is ready.
    Returns the final image URL.
    """
    headers = {'Content-Type': 'application/json'}
    response = requests.post(API_URL, headers=headers, data=payload)

    if response.status_code == 200:
        api_response = response.json()
        status = api_response.get("status")
        if status == "processing":
            fetch_url = api_response["fetch_result"]
            eta = api_response.get("eta", 10)
            # We'll poll until success or max tries
            return wait_for_image(fetch_url, max_retries=10, wait_time=eta)
        elif status == "success":
            # Possibly 'proxy_links' or 'output'? 
            # This depends on the actual API response
            if "proxy_links" in api_response:
                return api_response["proxy_links"][0]
            elif "output" in api_response:
                return api_response["output"][0]
        else:
            raise Exception(f"API returned unexpected status: {status}, {api_response}")
    else:
        raise Exception(f"Failed process_and_fetch_image: {response.text}")

def wait_for_image(fetch_url, max_retries=10, wait_time=10):
    """Polls the fetch_url until the image is ready or max retries are reached."""
    for attempt in range(max_retries):
        payload = json.dumps({"key": API_KEY})
        headers = {'Content-Type': 'application/json'}
        response = requests.post(fetch_url, headers=headers, data=payload)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            if status == "success":
                # The final image link might be in data['output'][0]
                return data["output"][0] if "output" in data else None
            elif status == "processing":
                # Wait for the indicated 'eta' or fallback to wait_time
                eta = data.get("eta", wait_time)
                time.sleep(eta)
            else:
                raise Exception(f"Fetch returned unexpected status: {data}")
        else:
            raise Exception(f"Fetch request failed: {response.text}")

    raise Exception("Max retries reached; image not ready.")

# ---------------------------------------------------------------------
# MAIN ANVIL SERVER FUNCTION
# ---------------------------------------------------------------------
@anvil.server.callable
def process_try_on(user_media, cloth_media):
    """
    Anvil client calls this function, passing in two anvil.Media objects:
      - user_media (the model image)
      - cloth_media (the cloth image)

    Returns an anvil.BlobMedia containing the final composited image.
    """
    # Save the media files locally
    model_image_path = "model_image.jpg"
    cloth_image_path = "cloth_image.jpg"
    with open(model_image_path, "wb") as f:
        f.write(user_media.get_bytes())
    with open(cloth_image_path, "wb") as f:
        f.write(cloth_media.get_bytes())

    # Upload each to the stable diffusion crop API
    model_image_url = upload_to_sd(model_image_path)
    cloth_image_url = upload_to_sd(cloth_image_path)

    # Build the payload for the fashion API
    payload = json.dumps({
        "key": API_KEY,
        "prompt": "A realistic photo of the model wearing the uploaded cloth. Maintain color and texture.",
        "negative_prompt": "Low quality, unrealistic, bad cloth, warped cloth",
        "init_image": model_image_url,
        "cloth_image": cloth_image_url,
        "cloth_type": "upper_body",
        "height": 512,
        "width": 384,
        "guidance_scale": 8.0,
        "num_inference_steps": 21,
        "seed": 128915590,
        "temp": "no",
        "webhook": None,
        "track_id": None
    })

    # Call the process_and_fetch_image to generate final image
    final_image_url = process_and_fetch_image(payload)
    if not final_image_url:
        raise Exception("Could not get final image URL from the API.")

    # Download the final image and return it as an Anvil Media object
    final_image_media = get_image_as_media(final_image_url)
    return final_image_media
