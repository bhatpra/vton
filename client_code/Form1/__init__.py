"""
Main form for the Virtual Try-On application.
Handles image uploads, parameter configuration, and try-on process.
Uses ModelsLab API for virtual clothing try-on functionality.
"""

from ._anvil_designer import Form1Template
from anvil import *
from anvil.js.window import jQuery
import anvil.microsoft.auth
import anvil.facebook.auth
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
import anvil.js
import base64
import time
import anvil.users
from anvil import Button, TextBox, Label, DropDown, ColumnPanel, XPanel

class Form1(Form1Template):
    """
    Main form class that handles the virtual try-on interface and logic.
    Manages user inputs, image processing, and result display.
    Includes background state handling for mobile devices.
    """

    def __init__(self, **properties):
        """
        Initialize the form and its components.
        Sets up input fields, labels, and checks for any pending jobs.
        
        Args:
            **properties: Form properties passed from Anvil
        """
        # Check if user is logged in
        if not anvil.users.get_user():
          anvil.users.login_with_form()

          print('This user has logged in: ' + anvil.users.get_user()['email'])
            # Redirect to login if not authenticated
            #open_form('LoginForm')
           # return
            
        self.init_components(**properties)
        
        # Create header panel
        self.flow_panel_header = FlowPanel(
            align="right",
            width="100%",
            background="theme:primary"
        )
        # Set padding using spacing_above/below properties
        self.flow_panel_header.spacing_above = "small"
        self.flow_panel_header.spacing_below = "small"
        
        # Create logout button
        self.button_logout = Button(
            text="Logout",
            icon="fa:sign-out",
            role="secondary-color",
            font_size=14
        )
        self.button_logout.set_event_handler('click', self.button_logout_click)
        
        # Add button to panel
        self.flow_panel_header.add_component(self.button_logout)
        
        # Add panel to form (at the top)
        self.add_component(self.flow_panel_header, index=0)
        
        # Set up logout button text
        self.setup_logout_button()

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

        # Add guidance scale input
        self.text_box_guidance = TextBox(
            placeholder="Guidance Scale (default: 10)",
            type="number",
            width=200,
            text="10"
        )
        
        # Add cloth type dropdown with valid ModelsLab API options
        self.dropdown_cloth_type = DropDown(
            items=['upper_body', 'lower_body', 'dresses'],
            selected_value='dresses',
            width=200
        )
        
        # Add inference steps dropdown with valid API values
        self.dropdown_steps = DropDown(
            items=[str(x) for x in [21, 31, 41]],
            selected_value="21",
            width=200
        )
        
        # Create input panel for form organization
        self.column_panel_inputs = ColumnPanel(
            spacing_above="small",
            spacing_below="small"
        )
        
        # Create prompt input fields
        if not hasattr(self, 'text_box_prompt'):
            self.text_box_prompt = TextBox(
                placeholder="Enter your prompt here...",
                width="100%",
                spacing_above="small",
                spacing_below="small"
            )
        
        if not hasattr(self, 'text_box_negative_prompt'):
            self.text_box_negative_prompt = TextBox(
                placeholder="Enter negative prompt here (what to avoid)...",
                width="100%",
                spacing_above="small",
                spacing_below="small"
            )
        
        # Create labels for input fields
        labels = {
            'prompt': Label(text="Custom Prompt:", font_size=14, bold=True),
            'negative': Label(text="Negative Prompt (what to avoid):", font_size=14, bold=True),
            'cloth_type': Label(text="Clothing Type:", font_size=14, bold=True),
            'guidance': Label(text="Guidance Scale (1-20):", font_size=14, bold=True),
            'steps': Label(text="Inference Steps:", font_size=14, bold=True)
        }
        
        # Remove components from any existing parents
        for component in [self.text_box_prompt, self.text_box_negative_prompt, 
                         self.dropdown_cloth_type, self.text_box_guidance, 
                         self.dropdown_steps]:
            if component.parent:
                component.remove_from_parent()
        
        # Create an expandable panel for advanced options
        self.advanced_panel = XPanel(
            title="Advanced Options",
            collapsed=True,  # Start collapsed
            spacing_above="small",
            spacing_below="small"
        )
        
        # Create a column panel inside expansion panel for advanced options
        self.advanced_column = ColumnPanel(
            spacing_above="small",
            spacing_below="small"
        )
        
        # Add advanced options to their panel
        self.advanced_column.add_component(labels['guidance'])
        self.advanced_column.add_component(self.text_box_guidance)
        self.advanced_column.add_component(labels['steps'])
        self.advanced_column.add_component(self.dropdown_steps)
        
        # Add components to main panel in the desired order
        self.column_panel_inputs.add_component(labels['prompt'])
        self.column_panel_inputs.add_component(self.text_box_prompt)
        self.column_panel_inputs.add_component(labels['negative'])
        self.column_panel_inputs.add_component(self.text_box_negative_prompt)
        
        # Cloth type right after cloth display
        self.column_panel_inputs.add_component(labels['cloth_type'])
        self.column_panel_inputs.add_component(self.dropdown_cloth_type)
        
        # Add the expandable advanced options panel
        self.column_panel_inputs.add_component(self.advanced_panel)
        
        # Add the panel to the form
        self.add_component(self.column_panel_inputs)

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

        # Check for any pending jobs from previous sessions
        stored_url = anvil.js.window.localStorage.getItem('pending_job_url')
        if stored_url:
            self.fetch_url = stored_url
            self.label_status.text = "Processing..."
            self.timer_poll.enabled = True

    def setup_logout_button(self):
        current_user = anvil.users.get_user()
        user_email = current_user['email'] if current_user else ''
        self.button_logout.text = f"Logout ({user_email})"
    
    def button_logout_click(self, **event_args):
        """This method is called when the logout button is clicked"""
        try:
            print("Attempting to logout...")  # Debug print
            current_user = anvil.users.get_user()
            print(f"Current user: {current_user}")  # Debug print
            
            anvil.users.logout()
            print("Logout successful")  # Debug print
            
            # Add a small delay before form transition
            #anvil.js.window.setTimeout(lambda: open_form('LoginForm'), 100)
            anvil.js.window.setTimeout(lambda: open_form('Form1'), 100)

            
        except Exception as e:
            print(f"Logout error: {str(e)}")  # Debug print
            alert(f"Logout failed: {str(e)}")

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
        """
        Handle the start button click event.
        Validates inputs, starts the try-on process, and manages job state.
        
        Args:
            **event_args: Event arguments from Anvil
        """
        # Validate image uploads
        if not self.user_media or not self.cloth_media:
            alert("Please upload both user and cloth images first.")
            return
        
        # Get all input values
        cloth_type = self.dropdown_cloth_type.selected_value
        user_prompt = self.text_box_prompt.text
        negative_prompt = self.text_box_negative_prompt.text
        num_steps = int(self.dropdown_steps.selected_value)
        
        try:
            guidance_scale = float(self.text_box_guidance.text or "10")
            if guidance_scale <= 0:
                raise ValueError("Guidance scale must be positive")
        except ValueError:
            alert("Please enter a valid positive number for guidance scale")
            return
        
        # Pass all parameters to server
        result = anvil.server.call('start_try_on', 
                                 self.user_media, 
                                 self.cloth_media,
                                 user_prompt,
                                 cloth_type,
                                 guidance_scale,
                                 num_steps,
                                 negative_prompt)
        
        # Clear old result
        self.image_result.source = None
        self.label_status.text = "Submitting job..."
        self.fetch_url = None

        try:
            if result["status"] == "success":
                self.image_result.source = result["image"]
                self.label_status.text = "Done!"
                self.button_start.enabled = True
                anvil.js.window.localStorage.removeItem('pending_job_url')
                self.fetch_url = None
            elif result["status"] == "processing":
                self.fetch_url = result["fetch_url"]
                eta = result.get("eta", 10)
                self.label_status.text = f"Submitted job, still processing... ETA ~{eta} seconds."
                self.timer_poll.enabled = True
                anvil.js.window.localStorage.setItem('pending_job_url', result["fetch_url"])
            else:
                alert(f"Unexpected status: {result}")
        except Exception as e:
            alert(f"Error submitting job: {e}")
            self.label_status.text = "Error"

        # Add just this one line to scroll to bottom
        anvil.js.window.scrollTo(0, anvil.js.window.document.body.scrollHeight)

    def timer_poll_tick(self, **event_args):
        """
        Poll for job completion status.
        Handles success, failure, and updates UI accordingly.
        Manages background state persistence.
        
        Args:
            **event_args: Event arguments from Anvil
        """
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
                self.button_start.enabled = True
                anvil.js.window.localStorage.removeItem('pending_job_url')
                self.fetch_url = None
            elif check_result["status"] == "processing":
                eta = check_result.get("eta", 10)
                self.label_status.text = f"Still processing... Next check in 3s. (ETA ~{eta}s)"
            elif check_result["status"] == "failed":
                self.label_status.text = "Failed: " + check_result.get("error", "Unknown error")
                self.timer_poll.enabled = False
                self.button_start.enabled = True
                anvil.js.window.localStorage.removeItem('pending_job_url')
                self.fetch_url = None
            else:
                alert(f"Unexpected status: {check_result}")
                self.label_status.text = "Error"
                self.timer_poll.enabled = False
                self.button_start.enabled = True
                anvil.js.window.localStorage.removeItem('pending_job_url')
                self.fetch_url = None
        except Exception as e:
            alert(f"Error polling job status: {e}")
            self.label_status.text = "Error"
            self.timer_poll.enabled = False
            self.button_start.enabled = True
            anvil.js.window.localStorage.removeItem('pending_job_url')
            self.fetch_url = None
