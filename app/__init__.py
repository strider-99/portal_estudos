from flask import Flask
from flask_pymongo import PyMongo
from flask_login import LoginManager
import os

mongo = PyMongo()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "Faça login para acessar essa página."
login_manager.login_message_category = "warning"

def create_app():
    app = Flask(__name__)
    app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/meu_portal")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    mongo.init_app(app)
    login_manager.init_app(app)

    from .models import User
    from bson import ObjectId

    @login_manager.user_loader
    def load_user(user_id):
        try:
            data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
            if data:
                return User(data)
        except Exception:
            return None
        return None

    from . import routes
    app.register_blueprint(routes.bp)

    return app
