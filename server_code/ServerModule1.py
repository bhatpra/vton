import anvil.server
import anvil
import requests
import json
import time
import io
import base64
from PIL import Image

API_URL = "https://modelslab.com/api/v6/image_editing/fashion"
CROP_API_URL = "https://modelslab.com/api/v3/base64_crop"
API_KEY = "TimeKtPLuNBR2UytsfQtArv6c4Wbg4dO0sBqwrIIVTQteu9e7CTbE7IzHTh1"  # Replace with your Stable Diffusion API key

# -------------
# Helper funcs
# -------------
def convert_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    return encoded_string.decode("utf-8")

def download_image(image_url, output_file):
    """Downloads 'image_url' to local 'output_file'."""
    resp = requests.get(image_url)
    if resp.status_code == 200:
        with open(output_file, "wb") as f:
            f.write(resp.content)
    else:
        raise Exception(f"Failed to download image. Status: {resp.status_code}")

def get_image_as_media(image_url):
    """Download the final image from 'image_url' and return as anvil.BlobMedia."""
    temp_file = "sdoutput.png"
    download_image(image_url, temp_file)
    with Image.open(temp_file) as img:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
    return anvil.BlobMedia("image/png", buf.read(), name="sdoutput.png")

def upload_to_sd(file_path):
    """
    Upload an image for cropping (or just uploading) and return the link.
    If the API requires 'key' in JSON body, we do it here.
    """
    img_b64 = convert_image_to_base64(file_path)
    payload = json.dumps({
        "key": API_KEY,
        "image": "data:image/png;base64," + img_b64,
        "crop": "false"
    })
    headers = {"Content-Type": "application/json"}
    resp = requests.post(CROP_API_URL, headers=headers, data=payload)
    if resp.status_code == 200:
        data = resp.json()
        if "link" in data:
            return data["link"]
        else:
            raise Exception(f"Unexpected response: {data}")
    else:
        raise Exception(f"Failed upload_to_sd: {resp.text}")

# -------------
# Two-step approach
# -------------
@anvil.server.callable
def start_try_on(user_media, cloth_media):
    """
    1) Save images locally
    2) Upload them to the 'SD crop' endpoint => get URLs
    3) POST to the main fashion API to start the job
    4) Return either:
       - { "status": "success", "image": <BlobMedia> } if the API instantly returned a result
       - { "status": "processing", "fetch_url": <the fetch URL> } if we must poll
    """
    # Save to local files
    model_path = "model_image.jpg"
    cloth_path = "cloth_image.jpg"
    with open(model_path, "wb") as f:
        f.write(user_media.get_bytes())
    with open(cloth_path, "wb") as f:
        f.write(cloth_media.get_bytes())

    # Upload to stable diffusion
    model_url = upload_to_sd(model_path)
    cloth_url = upload_to_sd(cloth_path)

    # Build payload for the main API
    payload = json.dumps({
        "key": API_KEY,
        "prompt": "A realistic photo of the model wearing the cloth. Maintain color and texture.",
        "negative_prompt": "Low quality, unrealistic, warped cloth",
        "init_image": model_url,
        "cloth_image": cloth_url,
        "cloth_type": "dresses",
        "height": 512,
        "width": 384,
        "guidance_scale": 8.0,
        "num_inference_steps": 21,
        "seed": 128915590,
        "temp": "no",
        "webhook": None,
        "track_id": None
    })
    headers = {"Content-Type": "application/json"}
    resp = requests.post(API_URL, headers=headers, data=payload)
    print(resp)

    if resp.status_code != 200:
        raise Exception(f"Failed to start job: {resp.text}")

    data = resp.json()
    print(resp)
    status = data.get("status")
    if status == "success":
        # The API returned an immediate result
        # Usually "proxy_links" or "output" has the final image
        if "proxy_links" in data:
            final_url = data["proxy_links"][0]
        elif "output" in data:
            final_url = data["output"][0]
        else:
            raise Exception("No final image link found in response!")
        # Download & return it
        final_image = get_image_as_media(final_url)
        return {"status": "success", "image": final_image}

    elif status == "processing":
        # The API gave us a fetch_url to poll for final image
        return {"status": "processing", "fetch_url": data["fetch_result"], "eta": data.get("eta", 10)}

    else:
        raise Exception(f"Unexpected status from API: {status} -- {data}")


@anvil.server.callable
def check_try_on(fetch_url):
    """
    Poll the 'fetch_url' once. 
    - If still processing, return {"status": "processing"}
    - If success, return {"status": "success", "image": <BlobMedia>}
    - If error, raise exception or return a dict with error info
    """
    headers = {"Content-Type": "application/json"}
    payload = json.dumps({"key": API_KEY})
    resp = requests.post(fetch_url, headers=headers, data=payload)

    if resp.status_code != 200:
        raise Exception(f"Failed to check job status: {resp.text}")

    data = resp.json()
    status = data.get("status")

    if status == "success":
        # final link in data['output'][0], presumably
        final_url = None
        if "output" in data:
            final_url = data["output"][0]
        elif "proxy_links" in data:
            final_url = data["proxy_links"][0]
        if not final_url:
            raise Exception("No final image link found in success response!")
        final_image = get_image_as_media(final_url)
        return {"status": "success", "image": final_image}

    elif status == "processing":
        return {"status": "processing", "eta": data.get("eta", 10)}

    else:
        raise Exception(f"Unexpected status {status} from fetch_url: {data}")
