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
    detalhes = detalhes or []
    # Normaliza detalhes e extrai apenas as erradas (para revisão)
    erros = []
    for d in detalhes:
        if not isinstance(d, dict):
            continue
        correto = bool(d.get("correto"))
        if not correto:
            erros.append({
                "index": d.get("index"),
                "enunciado": (d.get("enunciado") or "")[:1000],
                "alternativas": (d.get("alternativas") or [])[:5],
                "gabarito": d.get("gabarito", ""),
                "gabarito_texto": (d.get("gabarito_texto") or "")[:500],
                "resposta": d.get("resposta", ""),
                "resposta_texto": (d.get("resposta_texto") or "")[:500],
                "slug_materia": slug_materia,
            })
    doc = {
        "user_id": uid,
        "slug_materia": slug_materia,
        "acertos": acertos,
        "total": total,
        "nota": nota,
        "detalhes": detalhes,
        "erros": erros,
        "qtd_erros": len(erros),
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

def reset_progresso_usuario(user_id):
    """Apaga todo o progresso + histórico do usuário. Retorna contadores."""
    uid = ObjectId(user_id)
    r1 = mongo.db.progresso.delete_many({"user_id": uid})
    r2 = mongo.db.historico.delete_many({"user_id": uid})
    return {"progresso_removido": r1.deleted_count, "historico_removido": r2.deleted_count}

def get_questoes_para_revisar(user_id, slug_materia=None, limit=50):
    """Agrega questões erradas do histórico, deduplicando por (slug, enunciado).

    Mantém a ocorrência mais recente de cada questão. Suporta docs antigos
    sem campo 'erros' (deriva de 'detalhes').
    Se slug_materia for informado, filtra apenas questões daquela matéria.
    """
    try:
        uid = ObjectId(user_id)
    except Exception:
        return []
    historico = list(mongo.db.historico.find({"user_id": uid}).sort("created_at", -1).limit(200))
    vistas = set()
    revisao = []
    for h in historico:
        erros = h.get("erros")
        # fallback para docs antigos: deriva de detalhes
        if not erros and h.get("detalhes"):
            erros = [d for d in h["detalhes"] if isinstance(d, dict) and not d.get("correto")]
        for e in erros or []:
            if not isinstance(e, dict):
                continue
            enunciado = (e.get("enunciado") or "").strip()
            slug = e.get("slug_materia") or h.get("slug_materia")
            if slug_materia and slug != slug_materia:
                continue
            chave = (slug, enunciado[:200])
            if chave in vistas:
                continue
            vistas.add(chave)
            revisao.append({
                "slug_materia": slug,
                "enunciado": e.get("enunciado", ""),
                "alternativas": e.get("alternativas", []),
                "gabarito": e.get("gabarito", ""),
                "gabarito_texto": e.get("gabarito_texto", ""),
                "resposta": e.get("resposta", ""),
                "resposta_texto": e.get("resposta_texto", ""),
                "tentativa_em": h.get("created_at"),
                "nota_tentativa": h.get("nota"),
            })
            if len(revisao) >= limit:
                return revisao
    return revisao

def get_revisao_por_materia(user_id):
    """Retorna dict slug -> lista de questões erradas para cada matéria."""
    revisao = get_questoes_para_revisar(user_id, limit=200)
    por_materia = {}
    for r in revisao:
        slug = r["slug_materia"]
        por_materia.setdefault(slug, []).append(r)
    return por_materia
