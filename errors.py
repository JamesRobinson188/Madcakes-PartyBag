from flask import render_template

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/error.html', code=404, message="Page not found 😕"), 404
    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/error.html', code=500, message="Something broke on our end 😓"), 500
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/error.html', code=403, message="Access denied 🚫"), 403
