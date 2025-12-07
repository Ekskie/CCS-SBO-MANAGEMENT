from flask import Flask
from config import Config
from extensions import supabase, supabase_admin
from utils import inject_user_roles
import os # <-- Need this for the app.run port
import pytz

# Import Blueprints
from auth.routes import auth_bp
from core.routes import core_bp
from admin.routes import admin_bp
from president.routes import president_bp

def create_app(config_class=Config):
    """
    Factory function to create the Flask application.
    """
    app = Flask(__name__)
    
    # Load all configurations from the Config class
    app.config.from_object(config_class)
    
    # Set the timezone to Philippines
    os.environ['TZ'] = Config.TIMEZONE
    
    # Register context processors
    app.context_processor(inject_user_roles)

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/')
    app.register_blueprint(core_bp, url_prefix='/')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(president_bp, url_prefix='/president')
    
    # A simple root route to check if the app is running
    @app.route('/_health')
    def health_check():
        return "App is running!"

    return app

# --- THIS IS THE FIX ---
# Create the 'app' instance at the global scope
# Vercel looks for this 'app' variable to run.
app = create_app()
# --- END OF FIX ---

if __name__ == '__main__':
    # The 'app' variable already exists, just run it
    app.run(debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5000))

