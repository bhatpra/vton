from ._anvil_designer import Form1Template
from anvil import *
import anvil.server
import time

class Form1(Form1Template):

    def __init__(self, **properties):
        # Set up the form
        self.init_components(**properties)

        # Title
        self.label_title = Label(
            text="DSI Try-On Demo",
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
    Compress ONLY the user image client-side.
    """
    if not file:
        return

    # 1) Get the DOM node of the entire FileLoader
    file_loader_node = anvil.js.get_dom_node(self.file_loader_user)

    # 2) Query inside it for the real <input type="file">
    js_file_input = file_loader_node.querySelector("input[type='file']")
    if js_file_input and js_file_input.files and js_file_input.files.length > 0:
        js_file_obj = js_file_input.files[0]  # The raw JavaScript File object

        # 3) Call our JS compression function
        promise = anvil.js.call_js("compressImage", js_file_obj, 600)  # maxWidth=600

        def on_success(data_url):
            # data_url is "data:image/jpeg;base64,..."
            comma_idx = data_url.find(",")
            if comma_idx < 0:
                alert("Invalid data URL after compression.")
                return
            meta_part = data_url[:comma_idx]  # e.g. "data:image/jpeg;base64"
            b64_data = data_url[comma_idx+1:]

            # Determine content_type from meta_part
            if "image/png" in meta_part:
                content_type = "image/png"
            else:
                content_type = "image/jpeg"

            import base64
            raw_bytes = base64.b64decode(b64_data)
            compressed_media = BlobMedia(content_type, raw_bytes, name="compressed_user.jpg")

            self.user_media = compressed_media
            self.image_user_preview.source = compressed_media
            print(f"Compressed user image size: {len(raw_bytes)} bytes")

        def on_error(err):
            alert(f"Error compressing user image: {err}")

        anvil.js.await_promise(promise, on_success, on_error)
    else:
        alert("Could not find the actual file input. No file selected?")

    def file_loader_cloth_change(self, file, **event_args):
        if file:
            self.cloth_media = file
            self.image_cloth_preview.source = file

    def button_start_click(self, **event_args):
        # Validate
        if not self.user_media or not self.cloth_media:
            alert("Please upload both user and cloth images first.")
            return

        # Clear old result
        self.image_result.source = None
        self.label_status.text = "Submitting job..."
        self.fetch_url = None

        # 1) Call 'start_try_on' server function
        try:
            result = anvil.server.call('start_try_on', self.user_media, self.cloth_media)
            if result["status"] == "success":
                # Instantly got the final image
                self.image_result.source = result["image"]
                self.label_status.text = "Done! (Instant result)"
            elif result["status"] == "processing":
                # We have a fetch_url
                self.fetch_url = result["fetch_url"]
                eta = result.get("eta", 10)
                self.label_status.text = f"Submitted job, still processing... ETA ~{eta} seconds."
                # Start the polling timer
                self.timer_poll.enabled = True
            else:
                alert(f"Unexpected status: {result}")
        except Exception as e:
            alert(f"Error starting job: {e}")
            self.label_status.text = "Error"

    def timer_poll_tick(self, **event_args):
        # This is called every 3s to poll job status
        if not self.fetch_url:
            # No fetch_url to check
            self.timer_poll.enabled = False
            return

        self.label_status.text = "Checking status..."
        try:
            check_result = anvil.server.call('check_try_on', self.fetch_url)
            if check_result["status"] == "success":
                # We have a final image
                self.image_result.source = check_result["image"]
                self.label_status.text = "Done!"
                self.timer_poll.enabled = False
                self.fetch_url = None
            elif check_result["status"] == "processing":
                # Still not ready
                eta = check_result.get("eta", 10)
                self.label_status.text = f"Still processing... Next check in 3s. (ETA ~{eta}s)"
            else:
                # Unexpected?
                alert(f"Unexpected status: {check_result}")
                self.label_status.text = "Error"
                self.timer_poll.enabled = False
                self.fetch_url = None
        except Exception as e:
            alert(f"Error polling job status: {e}")
            self.label_status.text = "Error"
            self.timer_poll.enabled = False
            self.fetch_url = None
