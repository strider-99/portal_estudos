from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from datetime import datetime

from . import mongo


class User(UserMixin):
    def __init__(self, data):
        self._data = data
        self.id = str(data["_id"])
        self.email = data.get("email")
        self.password_hash = data.get("password_hash")
        self.is_admin = data.get("is_admin", False)
        self.created_at = data.get("created_at")

    def get_id(self):
        return self.id

    @staticmethod
    def create(email, password, is_admin=False):
        if mongo.db.users.find_one({"email": email}):
            return None, "E-mail já cadastrado."
        doc = {
            "email": email.lower().strip(),
            "password_hash": generate_password_hash(password),
            "is_admin": bool(is_admin),
            "created_at": datetime.utcnow()
        }
        res = mongo.db.users.insert_one(doc)
        doc["_id"] = res.inserted_id
        return User(doc), None

    @staticmethod
    def get_by_email(email):
        data = mongo.db.users.find_one({"email": email.lower().strip()})
        return User(data) if data else None

    @staticmethod
    def get_by_id(user_id):
        try:
            data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
            return User(data) if data else None
        except Exception:
            return None

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Helpers gerais
def get_materias(area=None):
    query = {}
    if area:
        query["area"] = area
    return list(mongo.db.materias.find(query).sort("titulo", 1))

def get_materia_by_slug(slug):
    return mongo.db.materias.find_one({"slug": slug})

def get_materia_by_id(id):
    return mongo.db.materias.find_one({"_id": ObjectId(id)})

def get_areas():
    return mongo.db.materias.distinct("area")

# Progresso helpers
def get_progresso_usuario(user_id):
    try:
        uid = ObjectId(user_id)
    except Exception:
        return []
    return list(mongo.db.progresso.find({"user_id": uid}))

def get_progresso_map(user_id):
    """Retorna dict slug -> doc progresso para lookup rápido"""
    progs = get_progresso_usuario(user_id)
    return {p["slug_materia"]: p for p in progs}

def is_materia_concluida(user_id, slug):
    try:
        uid = ObjectId(user_id)
    except Exception:
        return False
    doc = mongo.db.progresso.find_one({"user_id": uid, "slug_materia": slug})
    return bool(doc and doc.get("concluida"))

def toggle_progresso(user_id, slug_materia):
    uid = ObjectId(user_id)
    existing = mongo.db.progresso.find_one({"user_id": uid, "slug_materia": slug_materia})
    now = datetime.utcnow()
    if existing and existing.get("concluida"):
        mongo.db.progresso.update_one(
            {"_id": existing["_id"]},
            {"$set": {"concluida": False, "updated_at": now}}
        )
        return False
    else:
        mongo.db.progresso.update_one(
            {"user_id": uid, "slug_materia": slug_materia},
            {"$set": {"concluida": True, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True
        )
        return True

# Questoes helpers
def get_questoes_por_materia(slug_materia):
    return list(mongo.db.questoes.find({"slug_materia": slug_materia}))

# Historico helpers
def salvar_tentativa(user_id, slug_materia, acertos, total, nota, detalhes=None):
    uid = ObjectId(user_id)
    now = datetime.utcnow()
    doc = {
        "user_id": uid,
        "slug_materia": slug_materia,
        "acertos": acertos,
        "total": total,
        "nota": nota,
        "detalhes": detalhes or [],
        "created_at": now
    }
    mongo.db.historico.insert_one(doc)
    # atualiza progresso com ultima nota
    mongo.db.progresso.update_one(
        {"user_id": uid, "slug_materia": slug_materia},
        {"$set": {"ultimo_acertos": acertos, "ultimo_total": total, "ultima_nota": nota, "updated_at": now},
         "$inc": {"tentativas": 1},
         "$setOnInsert": {"concluida": False, "created_at": now}},
        upsert=True
    )
    return doc
