from ._anvil_designer import Form1Template
from anvil import *
import anvil.server
import anvil.js
import base64
import time
import anvil.users

class Form1(Form1Template):

    def __init__(self, **properties):
        # Check if user is logged in
        if not anvil.users.get_user():
            # Redirect to login if not authenticated
            open_form('LoginForm')
            return
            
        # Set up the form
        self.init_components(**properties)

        # Title
        self.label_title = Label(
            text="EZ Apparel Try On Demo v0.27",
            align="center",
            font_size=20,
            bold=True
        )
        self.add_component(self.label_title)

        # FileLoader for user image
        self.file_loader_user = FileLoader(text="Upload User Photo")
        self.file_loader_user.set_event_handler("change", self.file_loader_user_change)
        self.add_component(self.file_loader_user)

        self.image_user_preview = Image(width=200, height=200, align="center")
        self.add_component(self.image_user_preview)

        # FileLoader for cloth image
        self.file_loader_cloth = FileLoader(text="Upload Cloth Photo")
        self.file_loader_cloth.set_event_handler("change", self.file_loader_cloth_change)
        self.add_component(self.file_loader_cloth)

        self.image_cloth_preview = Image(width=200, height=200, align="center")
        self.add_component(self.image_cloth_preview)

        # Add TextBox for user prompt
        self.text_box_prompt = TextBox(
            placeholder="Enter your extra prompt here...",
            width="100%",
            align="center"
        )
        self.add_component(self.text_box_prompt)

        # "Start Try-On" Button
        self.button_start = Button(text="Start Try-On", background="#2196F3", foreground="#FFFFFF")
        self.button_start.set_event_handler("click", self.button_start_click)
        self.add_component(self.button_start)

        # Label to show status
        self.label_status = Label(text="", align="center", font_size=14)
        self.add_component(self.label_status)

        # Timer to poll job status
        self.timer_poll = Timer(interval=3)
        self.timer_poll.enabled = False
        self.timer_poll.set_event_handler("tick", self.timer_poll_tick)
        self.add_component(self.timer_poll)

        # Final result image
        self.image_result = Image(width=400, height=400, align="center")
        self.add_component(self.image_result)

        # Store media & fetch_url
        self.user_media = None
        self.cloth_media = None
        self.fetch_url = None

    def file_loader_user_change(self, file, **event_args):
        """
        Compress the user image client-side.
        """
        if not file:
            return

        file_loader_node = anvil.js.get_dom_node(self.file_loader_user)
        js_file_input = file_loader_node.querySelector("input[type='file']")

        if js_file_input and js_file_input.files and js_file_input.files.length > 0:
            js_file_obj = js_file_input.files[0]
            promise = anvil.js.call_js("compressImage", js_file_obj, 600)  # maxWidth=600

            def on_success(data_url):
                comma_idx = data_url.find(",")
                if comma_idx < 0:
                    alert("Invalid data URL after compression.")
                    return

                meta_part = data_url[:comma_idx]  # e.g. "data:image/jpeg;base64"
                b64_data = data_url[comma_idx+1:]

                if "image/png" in meta_part:
                    content_type = "image/png"
                else:
                    content_type = "image/jpeg"

                raw_bytes = base64.b64decode(b64_data)
                compressed_media = BlobMedia(content_type, raw_bytes, name="compressed_user.jpg")

                self.user_media = compressed_media
                self.image_user_preview.source = compressed_media
                print(f"Compressed user image size: {len(raw_bytes)} bytes")

            def on_error(err):
                alert(f"Error compressing user image: {err}")

            # Await the promise
            try:
                data_url = anvil.js.await_promise(promise)
                on_success(data_url)
            except Exception as e:
                on_error(e)
        else:
            alert("Could not find the user file input. No file selected?")

    def file_loader_cloth_change(self, file, **event_args):
        """
        Compress the cloth image client-side.
        """
        if not file:
            return

        file_loader_node = anvil.js.get_dom_node(self.file_loader_cloth)
        js_file_input = file_loader_node.querySelector("input[type='file']")

        if js_file_input and js_file_input.files and js_file_input.files.length > 0:
            js_file_obj = js_file_input.files[0]
            promise = anvil.js.call_js("compressImage", js_file_obj, 600)  # maxWidth=600

            def on_success(data_url):
                comma_idx = data_url.find(",")
                if comma_idx < 0:
                    alert("Invalid data URL after compression.")
                    return

                meta_part = data_url[:comma_idx]  # e.g. "data:image/jpeg;base64"
                b64_data = data_url[comma_idx+1:]

                if "image/png" in meta_part:
                    content_type = "image/png"
                else:
                    content_type = "image/jpeg"

                raw_bytes = base64.b64decode(b64_data)
                compressed_media = BlobMedia(content_type, raw_bytes, name="compressed_cloth.jpg")

                self.cloth_media = compressed_media
                self.image_cloth_preview.source = compressed_media
                print(f"Compressed cloth image size: {len(raw_bytes)} bytes")

            def on_error(err):
                alert(f"Error compressing cloth image: {err}")

            # Await the promise
            try:
                data_url = anvil.js.await_promise(promise)
                on_success(data_url)
            except Exception as e:
                on_error(e)
        else:
            alert("Could not find the cloth file input. No file selected?")

    def button_start_click(self, **event_args):
        if not self.user_media or not self.cloth_media:
            alert("Please upload both user and cloth images first.")
            return
        
        # Assuming you have a text_box_prompt TextBox component
        user_prompt = self.text_box_prompt.text
        
        # Pass the prompt to the server function
        result = anvil.server.call('start_try_on', self.user_media, self.cloth_media, user_prompt)
        
        # Clear old result
        self.image_result.source = None
        self.label_status.text = "Submitting job..."
        self.fetch_url = None

        try:
            if result["status"] == "success":
                self.image_result.source = result["image"]
                self.label_status.text = "Done! (Instant result)"
            elif result["status"] == "processing":
                self.fetch_url = result["fetch_url"]
                eta = result.get("eta", 10)
                self.label_status.text = f"Submitted job, still processing... ETA ~{eta} seconds."
                self.timer_poll.enabled = True
            else:
                alert(f"Unexpected status: {result}")
        except Exception as e:
            alert(f"Error submitting job: {e}")
            self.label_status.text = "Error"

    def timer_poll_tick(self, **event_args):
        if not self.fetch_url:
            self.timer_poll.enabled = False
            return

        self.label_status.text = "Checking status..."
        try:
            check_result = anvil.server.call('check_try_on', self.fetch_url)
            if check_result["status"] == "success":
                self.image_result.source = check_result["image"]
                self.label_status.text = "Done!"
                self.timer_poll.enabled = False
                self.fetch_url = None
            elif check_result["status"] == "processing":
                eta = check_result.get("eta", 10)
                self.label_status.text = f"Still processing... Next check in 3s. (ETA ~{eta}s)"
            else:
                alert(f"Unexpected status: {check_result}")
                self.label_status.text = "Error"
                self.timer_poll.enabled = False
                self.fetch_url = None
        except Exception as e:
            alert(f"Error polling job status: {e}")
            self.label_status.text = "Error"
            self.timer_poll.enabled = False
            self.fetch_url = None

    def button_logout_click(self, **event_args):
        anvil.users.logout()
        open_form('LoginForm')
