from flask import Flask
from config import Config  # Import the Config class, not SECRET_KEY
from extensions import supabase, supabase_admin
from utils import inject_user_roles

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
    
    # --- THIS IS THE FIX ---
    # Load all configurations from the Config class
    app.config.from_object(config_class)
    
    # --- DELETED ---
    # We no longer need these lines because they are loaded by app.config.from_object()
    # app.secret_key = Config.SECRET_KEY 
    # app.config["SUPABASE_URL"] = Config.SUPABASE_URL
    # app.config["SUPABASE_KEY"] = Config.SUPABASE_KEY
    # app.config["SUPABASE_SERVICE_KEY"] = Config.SUPABASE_SERVICE_KEY
    # app.config["MAX_FILE_SIZE"] = Config.MAX_FILE_SIZE
    
    # Initialize extensions (though they are already initialized, this is good practice if they needed the app context)
    # In our case, extensions.py doesn't need the app object, so this is fine.
    
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

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)

