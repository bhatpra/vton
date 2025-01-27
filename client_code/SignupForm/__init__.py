from ._anvil_designer import SignupFormTemplate
from anvil import *
import anvil.users
import anvil.server

class SignupForm(SignupFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.label_error.visible = False
    
    def button_signup_click(self, **event_args):
        email = self.text_box_email.text
        password = self.text_box_password.text
        confirm_password = self.text_box_confirm_password.text
        
        if password != confirm_password:
            self.label_error.text = "Passwords don't match"
            self.label_error.visible = True
            return
            
        try:
            # Create a new user
            user = anvil.users.signup_with_email(email, password)
            # Log them in automatically
            anvil.users.login_with_email(email, password)
            # Redirect to main form
            open_form('Form1')
        except anvil.users.UserExists:
            self.label_error.text = "Email already registered"
            self.label_error.visible = True 