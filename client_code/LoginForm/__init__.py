from ._anvil_designer import LoginFormTemplate
from anvil import *
import anvil.users
import anvil.server

class LoginForm(LoginFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        # Initialize any UI state
        self.label_error.visible = False
    
    def button_login_click(self, **event_args):
        email = self.text_box_email.text
        password = self.text_box_password.text
        
        try:
            # Try to log in with email/password
            user = anvil.users.login_with_email(email, password)
            if user:
                # Redirect to main form on success
                open_form('Form1')
        except anvil.users.AuthenticationFailed:
            self.label_error.text = "Invalid email or password"
            self.label_error.visible = True
    
    def button_google_login_click(self, **event_args):
        try:
            # Log in with Google
            user = anvil.users.login_with_google()
            if user:
                open_form('Form1')
        except:
            self.label_error.text = "Google login failed"
            self.label_error.visible = True
            
    def link_signup_click(self, **event_args):
        open_form('SignupForm') 