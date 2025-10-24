from flask import Flask, session, render_template, redirect, url_for
from config import SECRET_KEY

# Import blueprints
from auth.routes import auth_bp
from core.routes import core_bp
from admin.routes import admin_bp
from president.routes import president_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    # Register all blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(president_bp, url_prefix='/president')

    # --- Helper to check user roles (for templates) ---
    @app.context_processor
    def inject_user_roles():
        is_admin = False
        is_president = False
        if 'account_type' in session:
            if session['account_type'] == 'admin':
                is_admin = True
                is_president = True # Admins can do everything presidents can
            elif session['account_type'] == 'president':
                is_president = True
        return dict(is_admin=is_admin, is_president=is_president)
        
    # --- Main Route (Moved from core) ---
    @app.route('/')
    def home():
        if 'user_id' in session:
            return redirect(url_for('core.profile'))
        # This is now the default "home" page if not logged in
        return redirect(url_for('auth.login'))

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
