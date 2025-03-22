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
from datetime import datetime, timedelta
import anvil.http

API_URL = "https://modelslab.com/api/v6/image_editing/fashion"
CROP_API_URL = "https://modelslab.com/api/v3/base64_crop"

# Get API key from Anvil Secrets
API_KEY = anvil.secrets.get_secret('modelslab_api_key')  # Store your API key in Anvil Secrets

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
def start_try_on(user_image, cloth_image, prompt="", cloth_type="dresses", guidance_scale=10.0, num_steps=21, negative_prompt=""):
    """
    1) Save images locally
    2) Upload them to the 'SD crop' endpoint => get URLs
    3) POST to the main fashion API to start the job
    4) Return either:
       - { "status": "success", "image": <BlobMedia> } if the API instantly returned a result
       - { "status": "processing", "fetch_url": <the fetch URL> } if we must poll
    
    Args:
        user_image: The user's image
        cloth_image: The clothing image
        prompt: Optional user-provided prompt to append to base prompt
        cloth_type: The type of clothing
        guidance_scale: The guidance scale for the Stable Diffusion model
        num_steps: The number of inference steps for the Stable Diffusion model
        negative_prompt: Optional user-provided negative prompt to append to base negative prompt
    """

    # Require authentication for this endpoint
    if not anvil.users.get_user():
        raise Exception("Authentication required")
    
    user = anvil.users.get_user()               


    # Build payload for the main API
    base_prompt = "A realistic photo of the model wearing the cloth, Maintain color and texture"
    final_prompt = f"{base_prompt}, {prompt}".strip()
    
    # Combine default negative prompt with user's negative prompt
    base_negative = "Low quality, unrealistic, warped cloth, cloth's hand length should not change"
    final_negative = f"{base_negative}, {negative_prompt}".strip()
    row=app_tables.try_on_jobs.get(user=anvil.users.get_user()['email'])
    model_url=row['user_url']
    cloth_url=row['cloth_url']
    row['updated']=datetime.now()
    row['status']="processing"
    row['prompt']=prompt
    row['negative_prompt']=negative_prompt
    row['guidance_scale']=guidance_scale
    row['num_steps']=num_steps
    row['cloth_type']=cloth_type
    row['height']=512
    row['width']=384
    row['seed']=128915590


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
    if status == "success":
        # The API returned an immediate result
        # Usually "proxy_links" or "output" has the final image
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
        # Store just the request_id and creation time
        row=app_tables.try_on_jobs.get(user=anvil.users.get_user()['email'])
        row['request_id']=data["request_id"]
        row['created']=datetime.now()
        row['user']=anvil.users.get_user()

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

# Optional: Add user-specific data storage
@anvil.server.callable
def save_user_preferences(preferences):
    user = anvil.users.get_user()
    if not user:
        raise Exception("Authentication required")
    
    # Save to user's row in the Users table
    user['preferences'] = preferences

@anvil.server.background_task
def cleanup_old_images():
    """Delete images older than 24 hours"""
    while True:
        try:
            # Run every 24 hours
            anvil.server.wait(24*60*60)  # Wait 24 hours
            
            # Get cutoff time
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            # Get jobs older than cutoff time
            old_jobs = app_tables.try_on_jobs.search(
                created=q.less_than(cutoff_time)
            )
            
            for job in old_jobs:
                try:
                    # Call ModelsLab delete API
                    response = anvil.http.request(
                        "https://modelslab.com/api/v3/delete_image",
                        method="POST",
                        json={
                            "key": app_secrets.modelslab_api_key,
                            "request_id": job["request_id"]
                        }
                    )
                    if response.get('status') == 'success':
                        job.delete()
                except Exception as e:
                    print(f"Failed to delete job {job['request_id']}: {str(e)}")
                    
        except Exception as e:
            print(f"Cleanup task error: {str(e)}")
            # Wait before retrying on error
            anvil.server.wait(3600)  # Wait 1 hour before retry

# Start the cleanup task when server starts
#anvil.server.launch_background_task('cleanup_old_images')

def delete_from_sd(cutoff_time):
    """Delete images from Stable Diffusion API older than cutoff time"""
    try:
        # Get the API endpoint for deletion
        api_url = "https://stablediffusionapi.com/api/v4/delete"
        
        # Call the API to delete old images
        response = anvil.http.request(
            api_url,
            method="POST",
            json={
                "key": app_secrets.sd_api_key,
                "timestamp": cutoff_time.timestamp()
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if response.get('status') == 'success':
            print(f"Successfully deleted images before {cutoff_time}")
        else:
            print(f"Error from SD API: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Failed to delete from SD: {str(e)}")
        raise

@anvil.server.callable
def delete_images_now(request_id):
    """Immediately delete user images"""
    try:
        user = anvil.users.get_user()
        print(f"Looking for job with request_id: {request_id}")  # Debug
        
        # Get job for this user using correct method
        job = app_tables.try_on_jobs.get(
            request_id=request_id,
            user=user
        )
        print(f"Found job: {job}")  # Debug
        
        if job:
            # Call ModelsLab delete API
            response = anvil.http.request(
                "https://modelslab.com/api/v3/delete_image",
                method="POST",
                json={
                    "key": app_secrets.modelslab_api_key,
                    "request_id": request_id
                }
            )
            
            if response.get('status') == 'success':
                # Delete from our database
                job.delete()
                print("Job deleted from table")  # Debug
                return True
            else:
                raise Exception("Failed to delete from ModelsLab")
            
    except Exception as e:
        print(f"Table operation error: {str(e)}")  # Debug
        raise

# Create try_on_jobs table if it doesn't exist
try:
    app_tables.try_on_jobs
except AttributeError:
    app_tables.create_table(
        'try_on_jobs',
        [
            ('request_id', str),
            ('created', datetime),
            ('user', str)
        ]
    )

@anvil.server.background_task
def upload_image(image_type, image_data):
    """Store image in database"""
    try:
        # Store in appropriate table
        if image_type == 'user':
            # Save to local files
            model_path = "model_image.jpg"

            with open(model_path, "wb") as f:
                f.write(image_data.get_bytes())

            # Upload to stable diffusion
            model_url = upload_to_sd(model_path)
            try:
                row=app_tables.try_on_Jobs.get(user=anvil.users.get_user()['email'])
                row['user_url']=model_url
            except Exception as e:
                app_tables.try_on_Jobs.add_row(user=anvil.users.get_user()['email'],user_url=model_url)

                print(f"Adding recordd try_on_Jobs after error: {str(e)}")
            return model_url

        else:
            cloth_path = "cloth_image.jpg"
            with open(cloth_path, "wb") as f:
                f.write(image_data.get_bytes())
            cloth_url = upload_to_sd(cloth_path)
            row=app_tables.try_on_Jobs.get(user=anvil.users.get_user()['email'])
            row['cloth_url']=cloth_url
            return cloth_url
    except Exception as e:

        print(f"Error uploading {image_type} image: {str(e)}")

        raise

@anvil.server.callable
def get_latest_user_images(user):
    """Get the latest images for a user"""
    user_image = app_tables.user_images.search(user=user)[-1] if app_tables.user_images.search(user=user) else None
    cloth_image = app_tables.cloth_images.search(user=user)[-1] if app_tables.cloth_images.search(user=user) else None
    return user_image, cloth_image

@anvil.server.callable
def start_background_upload(image_type, image_data):
    """Start background upload from server side"""
    anvil.server.launch_background_task('upload_image', image_type, image_data)
