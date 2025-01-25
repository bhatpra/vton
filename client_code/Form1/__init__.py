from ._anvil_designer import Form1Template
from anvil import *
import anvil.server

class Form1(Form1Template):

    def __init__(self, **properties):
        # Set Form properties and Data Bindings.
        self.init_components(**properties)

        # -------------------------------------------------------------
        # Title Label
        # -------------------------------------------------------------
        self.label_title = Label(
            text="Virtual Try-On (Python Example)",
            align="center",
            font_size=20,
            bold=True
        )
        self.add_component(self.label_title)

        # -------------------------------------------------------------
        # FileLoader & Preview for USER (MODEL) PHOTO
        # -------------------------------------------------------------
        self.file_loader_user = FileLoader(text="Upload User Photo")
        self.file_loader_user.set_event_handler("change", self.file_loader_user_change)
        self.add_component(self.file_loader_user)

        self.image_user_preview = Image(
            width=200,
            height=200,
            align="center",
            tooltip="User Photo Preview"
        )
        self.add_component(self.image_user_preview)

        # -------------------------------------------------------------
        # FileLoader & Preview for CLOTH PHOTO
        # -------------------------------------------------------------
        self.file_loader_cloth = FileLoader(text="Upload Cloth Photo")
        self.file_loader_cloth.set_event_handler("change", self.file_loader_cloth_change)
        self.add_component(self.file_loader_cloth)

        self.image_cloth_preview = Image(
            width=200,
            height=200,
            align="center",
            tooltip="Cloth Photo Preview"
        )
        self.add_component(self.image_cloth_preview)

        # -------------------------------------------------------------
        # BUTTON to initiate "Try On"
        # -------------------------------------------------------------
        self.button_try_on = Button(
            text="Try On",
            background="#2196F3",
            foreground="#FFFFFF"
        )
        self.button_try_on.set_event_handler("click", self.button_try_on_click)
        self.add_component(self.button_try_on)

        # -------------------------------------------------------------
        # IMAGE to display the FINAL RESULT
        # -------------------------------------------------------------
        self.image_result = Image(
            width=400,
            height=400,
            align="center",
            tooltip="Result goes here"
        )
        self.add_component(self.image_result)

        # -------------------------------------------------------------
        # Variables to store the Media objects in memory
        # -------------------------------------------------------------
        self.user_media = None
        self.cloth_media = None

    def file_loader_user_change(self, file, **event_args):
        """
        Called when the user picks a user/model image.
        """
        print("User file selected:", file)
        if file:
            self.user_media = file
            # Show a quick preview
            self.image_user_preview.source = file

    def file_loader_cloth_change(self, file, **event_args):
        """
        Called when the user picks the cloth image.
        """
        print("Cloth file selected:", file)
        if file:
            self.cloth_media = file
            # Show a quick preview
            self.image_cloth_preview.source = file

    def button_try_on_click(self, **event_args):
        """
        Naively overlay cloth on user image (server-side) and display.
        """
        if not self.user_media or not self.cloth_media:
            alert("Please upload both the user photo and the cloth photo.")
            return

        try:
            # Call the server function to process/overlay
            result_media = anvil.server.call('process_try_on', self.user_media, self.cloth_media)
            # Show final composited image
            self.image_result.source = result_media
        except Exception as e:
            alert(f"Error: {e}")
