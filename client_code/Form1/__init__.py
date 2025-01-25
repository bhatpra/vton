from ._anvil_designer import Form1Template
from anvil import *
import anvil.js
import base64

class Form1(Form1Template):
    def __init__(self, **properties):
        self.init_components(**properties)

        self.file_loader_1.set_event_handler("change", self.file_loader_1_change)

    def file_loader_1_change(self, file, **event_args):
        # file is an anvil.FileMedia, but we need the raw JavaScript file
        if not file:
            return
        
        # Get the DOM node of the FileLoader (the <input type="file">)
        js_file_input = anvil.js.get_dom_node(self.file_loader_1)
        # If user picked at least one file...
        if js_file_input.files and js_file_input.files.length > 0:
            js_file_obj = js_file_input.files[0]
            # Call the JS function compressImage (defined in Native Libraries or Custom HTML)
            promise = anvil.js.call_js("compressImage", js_file_obj, 600)  # e.g. maxWidth=600

            def on_success(data_url):
                # data_url = "data:image/jpeg;base64,..."
                # Let's parse out the base64 part
                comma_index = data_url.find(",")
                if comma_index == -1:
                    alert("Invalid data URL")
                    return
                meta_part = data_url[:comma_index]  # e.g. "data:image/jpeg;base64"
                b64_data = data_url[comma_index + 1:]
                
                # Determine content type from meta_part
                if "image/png" in meta_part:
                    content_type = "image/png"
                else:
                    content_type = "image/jpeg"

                raw_bytes = base64.b64decode(b64_data)
                compressed_media = BlobMedia(content_type, raw_bytes, name="compressed.jpg")
                
                self.image_1.source = compressed_media
                print(f"Compressed image size: {len(raw_bytes)} bytes")

            def on_error(err):
                alert(f"Compression error: {err}")

            anvil.js.await_promise(promise, on_success, on_error)
        else:
            alert("No JS file in the file loader.")
