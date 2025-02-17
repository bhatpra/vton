import anvil.microsoft.auth
import anvil.facebook.auth
import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
import anvil
import requests
import json
import time
import io
import base64
from PIL import Image
import anvil.users

API_URL = "https://modelslab.com/api/v6/image_editing/fashion"
CROP_API_URL = "https://modelslab.com/api/v3/base64_crop"
DELETE_API_URL='https://modelslab.com/api/v3/delete_image'
API_KEY = "TimeKtPLuNBR2UytsfQtArv6c4Wbg4dO0sBqwrIIVTQteu9e7CTbE7IzHTh1"  # Replace with your Stable Diffusion API key


global_model_upload_request_id = "" 
global_cloth_upload_request_id = "" 
global_genrequest_id = ""

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
        print("response from  upload to sd:", data)
        if "link" in data:
            return data["link"], data["request_id"]
        else:
            raise Exception(f"Unexpected response: {data}")
    else:
        raise Exception(f"Failed upload_to_sd: {resp.text}")

# -------------
# Two-step approach
# -------------
@anvil.server.callable
def start_try_on(user_media, cloth_media, user_prompt="", cloth_type="dresses", guidance_scale=10.0, num_steps=21, negative_prompt=""):
    """
    1) Save images locally
    2) Upload them to the 'SD crop' endpoint => get URLs
    3) POST to the main fashion API to start the job
    4) Return either:
       - { "status": "success", "image": <BlobMedia> } if the API instantly returned a result
       - { "status": "processing", "fetch_url": <the fetch URL> } if we must poll
    
    Args:
        user_media: The user's image
        cloth_media: The clothing image
        user_prompt: Optional user-provided prompt to append to base prompt
        cloth_type: The type of clothing
        guidance_scale: The guidance scale for the Stable Diffusion model
        num_steps: The number of inference steps for the Stable Diffusion model
        negative_prompt: Optional user-provided negative prompt to append to base negative prompt
    """
    # Require authentication for this endpoint
    print("In start_try_on")
    if not anvil.users.get_user():
        raise Exception("Authentication required")
        
    # Save to local files
    model_path = "model_image.jpg"
    cloth_path = "cloth_image.jpg"
    with open(model_path, "wb") as f:
        f.write(user_media.get_bytes())
    with open(cloth_path, "wb") as f:
        f.write(cloth_media.get_bytes())

    global global_model_upload_request_id
    global global_cloth_upload_request_id

    # Upload to stable diffusion
    model_url,global_model_upload_request_id = upload_to_sd(model_path)
    print("global_model_upload_request_id:",global_model_upload_request_id)

    cloth_url,global_cloth_upload_request_id = upload_to_sd(cloth_path)  
    print("global_cloth_upload_request_id:",global_cloth_upload_request_id)
    # Build payload for the main API
    base_prompt = "A realistic photo of the model wearing the cloth, Maintain color and texture"
    final_prompt = f"{base_prompt}, {user_prompt}".strip()
    
    # Combine default negative prompt with user's negative prompt
    base_negative = "Low quality, unrealistic, warped cloth, cloth's hand length should not change"
    final_negative = f"{base_negative}, {negative_prompt}".strip()
    
    payload = json.dumps({
        "key": API_KEY,
        "prompt": final_prompt,
        "negative_prompt": final_negative,  # Using combined negative prompt
        "init_image": model_url,
        "cloth_image": cloth_url,
        "cloth_type": cloth_type,
        "height": 512,
        "width": 384,
        "guidance_scale": guidance_scale,
        "num_inference_steps": num_steps,
        "seed": 128915590,
        "temp": "no",
        "webhook": None,
        "track_id": None
    })
    headers = {"Content-Type": "application/json"}
    print ("request:\n"+payload)
    resp = requests.post(API_URL, headers=headers, data=payload)
    print(resp)

    if resp.status_code != 200:
        raise Exception(f"Failed to start job: {resp.text}")

    data = resp.json()
    print(data)
    status = data.get("status")
    global global_genrequest_id
    global_genrequest_id=data["id"]
    if status == "success":
        # The API returned an immediate result
        # Usually "proxy_links" or "output" has the final image
      #TBD
        if "future_links" in data:
            final_url = data["proxy_links"][0]
        if "proxy_links" in data:
            final_url = data["proxy_links"][0]
        elif "output" in data:
            final_url = data["output"][0]
        else:
            raise Exception("No final image link found in response!")
        # Download & return it
        final_image = get_image_as_media(final_url)

        print("Deleting input and generated images from server")

      
        delete_images_now(global_model_upload_request_id)
        delete_images_now(global_cloth_upload_request_id)
        delete_images_now(global_genrequest_id)
      
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
        print("Deleting input and generated images from server")
        global global_model_upload_request_id
        global global_cloth_upload_request_id
        global global_genrequest_id
        print(global_model_upload_request_id)
        print(global_cloth_upload_request_id)
        print(global_genrequest_id)
        delete_images_now(global_model_upload_request_id)
        delete_images_now(global_cloth_upload_request_id)
        delete_images_now(global_genrequest_id)
        return {"status": "success", "image": final_image}

    elif status == "processing":
        return {"status": "processing", "eta": data.get("eta", 10)}

    else:
        raise Exception(f"Unexpected status {status} from fetch_url: {data}")

# Optional: Add user-specific data storage
@anvil.server.callable
def save_user_preferences(preferences):
    user = anvil.users.get_user()
    if not user:
        raise Exception("Authentication required")
    
    # Save to user's row in the Users table
    user['preferences'] = preferences


@anvil.server.callable
def delete_images_now(request_id):
    """Immediately delete user images"""
    try:
      payload = json.dumps({
          "key": API_KEY,
          "request_id": request_id
      })
      headers = {"Content-Type": "application/json"}
      print ("request:\n"+payload)
      resp = requests.post(DELETE_API_URL, headers=headers, data=payload)
      print(resp)

      if resp.status_code != 200:
          raise Exception(f"Failed to deelte image: {resp.text}")

    except Exception as e:
      print(f"Delete operation error: {str(e)}")  # Debug
      raise


import os
from urllib.parse import urlparse
@anvil.server.callable
def get_basename(url):
  #url = "http://photographs.500px.com/kyle/09-09-201315-47-571378756077.jpg"
  print("in getbasename")
  a = urlparse(url)
  print(a.path)                    # Output: /kyle/09-09-201315-47-571378756077.jpg
  print(os.path.basename(a.path))  # Output: 09-09-201315-47-571378756077.jpg
  return os.path.basename(a.path)