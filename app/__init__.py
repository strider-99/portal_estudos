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
    # SECRET_KEY obrigatória no Render: defina env SECRET_KEY
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    if app.config["SECRET_KEY"] == "dev-secret-key-change-me" and os.getenv("RENDER"):
        import warnings
        warnings.warn("SECRET_KEY usando valor default - defina SECRET_KEY no Render!")

    # Fix Atlas TLS no Render (certifi) + timeouts menores para falhar rápido no healthcheck
    mongo_kwargs = {
        "connect": False,
        "serverSelectionTimeoutMS": 5000,
        "connectTimeoutMS": 10000,
    }
    # Atlas (mongodb+srv) precisa de CA file - evita SSL handshake failed
    if "mongodb+srv" in app.config["MONGO_URI"]:
        try:
            import certifi
            mongo_kwargs["tlsCAFile"] = certifi.where()
            # força TLS (pymongo já faz, mas explícito ajuda)
            mongo_kwargs["tls"] = True
            mongo_kwargs["retryWrites"] = True
        except ImportError:
            pass

    mongo.init_app(app, **mongo_kwargs)
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

    # handler global para falha de Mongo (evita 500 no HEAD / healthcheck do Render)
    @app.errorhandler(500)
    def handle_500(e):
        # se for ServerSelectionTimeoutError, já foi tratado nas rotas; fallback genérico
        return "Erro interno - verifique logs e MONGO_URI", 500

    return app
