from ._anvil_designer import Form1Template
from anvil import *
import anvil.js
import anvil.server
import base64

class Form1(Form1Template):

    def __init__(self, **properties):
        self.init_components(**properties)

        # Label
        self.label_title = Label(text="Image Compression Demo", align="center", font_size=20, bold=True)
        self.add_component(self.label_title)

        # FileLoader
        self.file_loader_user = FileLoader(text="Upload & Compress User Photo")
        self.file_loader_user.set_event_handler("change", self.file_loader_user_change)
        self.add_component(self.file_loader_user)

        # Preview of compressed image
        self.image_user_preview = Image(width=200, height=200)
        self.add_component(self.image_user_preview)

        # Button to do something with self.user_media
        self.button_go = Button(text="Use This Compressed Image")
        self.button_go.set_event_handler("click", self.button_go_click)
        self.add_component(self.button_go)

        # We'll store the compressed image as anvil.Media here
        self.user_media = None

    def file_loader_user_change(self, file, **event_args):
        """
        Called when user picks a file. We'll do client-side compression 
        before storing it in self.user_media
        """
        if file is None:
            return

        # "file" is an anvil.Media object. We need to get the underlying JS File
        # The JS File is available via anvil.js.get_dom_node(file)
        js_file_obj = anvil.js.get_dom_node(file)

        # Call our JS function compressImage(js_file_obj, maxWidth=600 for instance)
        # This returns a Promise, so we handle it asynchronously
        def on_success(compressed_data_url):
            # compressed_data_url is like "data:image/png;base64,AAAA..."
            # Convert that to an anvil.BlobMedia
            # Strip the "data:image/png;base64," prefix
            prefix = "data:image/png;base64,"
            # If you used JPEG, it might be "data:image/jpeg;base64," etc.
            # So check for the prefix more robustly:
            if compressed_data_url.startswith("data:image/"):
                comma_index = compressed_data_url.find(",")
                meta_part = compressed_data_url[:comma_index]  # e.g. data:image/png;base64
                # We can glean the content_type from that meta_part
                if "image/jpeg" in meta_part:
                    content_type = "image/jpeg"
                else:
                    content_type = "image/png"
                b64_data = compressed_data_url[comma_index+1:]
            else:
                # fallback
                b64_data = compressed_data_url
                content_type = "image/png"

            raw_bytes = base64.b64decode(b64_data)
            compressed_media = BlobMedia(content_type, raw_bytes, name="compressed.png")

            # Store in self.user_media
            self.user_media = compressed_media

            # Show a preview
            self.image_user_preview.source = self.user_media

        def on_error(err):
            alert(f"Error compressing image: {err}")

        # We'll call our JS function compressImage
        p = anvil.js.call_js("compressImage", js_file_obj, 600)  # 600 max width, for example

        # p is a JS Promise. We can hook into it with p.then(...)
        # or we can use anvil.js.await_promise for a Pythonic approach:
        anvil.js.await_promise(p, on_success, on_error)

    def button_go_click(self, **event_args):
        if self.user_media:
            alert(f"Compressed image is ready, size is {len(self.user_media.get_bytes())} bytes.")
            # For example, call your stable diffusion or "try on" server function:
            # result_media = anvil.server.call('process_try_on', self.user_media, self.cloth_media)
        else:
            alert("No image selected.")
