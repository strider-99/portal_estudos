from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from .models import get_materias, get_materia_by_slug, get_areas, User, get_questoes_por_materia, salvar_tentativa, get_progresso_map
from . import mongo
import re
import json
from datetime import datetime
from bson import ObjectId

bp = Blueprint("main", __name__)

def extrair_modulo(titulo):
    match = re.search(r'Módulo (\d+)', titulo)
    return int(match.group(1)) if match else 0

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"erro": "Autenticação necessária"}), 401
        if not getattr(current_user, "is_admin", False):
            return jsonify({"erro": "Acesso restrito a administradores"}), 403
        return func(*args, **kwargs)
    return wrapper

# ---------- Páginas públicas ----------
@bp.route("/")
def index():
    materias = list(mongo.db.materias.find())
    materias.sort(key=lambda m: extrair_modulo(m['titulo']) if 'Módulo' in m['titulo'] else 0)
    areas = set(m['area'] for m in materias if m['area'] != "outros") if materias else set()
    materias_por_area = {}
    for area in areas:
        materias_por_area[area] = [m for m in materias if m['area'] == area]

    progresso_map = {}
    if current_user.is_authenticated:
        progresso_map = get_progresso_map(current_user.get_id())

    return render_template("index.html", materias_por_area=materias_por_area, progresso_map=progresso_map)

@bp.route("/materia/<slug>")
def materia(slug):
    materia = mongo.db.materias.find_one({"slug": slug})
    if not materia:
        abort(404)
    # Busca questões da coleção questoes (LMS) + fallback legado materias.questoes
    questoes_raw = get_questoes_por_materia(slug)
    if not questoes_raw and materia.get("questoes"):
        questoes_raw = materia["questoes"]
    # Sanitiza para JSON (ObjectId/datetime não serializáveis)
    questoes = []
    for q in questoes_raw:
        questoes.append({
            "enunciado": q.get("enunciado"),
            "alternativas": q.get("alternativas", []),
            "gabarito": q.get("gabarito", ""),
            "slug_materia": q.get("slug_materia", slug)
        })

    concluida = False
    historico_usuario = []
    if current_user.is_authenticated:
        prog = mongo.db.progresso.find_one({"user_id": ObjectId(current_user.get_id()), "slug_materia": slug})
        concluida = bool(prog and prog.get("concluida"))
        historico_usuario = list(mongo.db.historico.find({"user_id": ObjectId(current_user.get_id()), "slug_materia": slug}).sort("created_at", -1).limit(5))

    return render_template("materia.html", materia=materia, questoes=questoes, concluida=concluida, historico_usuario=historico_usuario)

# ---------- Auth ----------
@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("password", "")
        senha2 = request.form.get("password2", "")
        if not email or not senha:
            flash("Preencha e-mail e senha.", "danger")
        elif senha != senha2:
            flash("Senhas não conferem.", "danger")
        elif len(senha) < 6:
            flash("Senha deve ter ao menos 6 caracteres.", "danger")
        else:
            # primeiro usuário vira admin automaticamente
            is_first = mongo.db.users.count_documents({}) == 0
            user, err = User.create(email, senha, is_admin=is_first)
            if err:
                flash(err, "danger")
            else:
                login_user(user)
                flash("Cadastro realizado com sucesso!" + (" Você é admin." if is_first else ""), "success")
                return redirect(url_for("main.dashboard"))
    return render_template("register.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("password", "")
        user = User.get_by_email(email)
        if user and user.check_password(senha):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            flash("Login realizado!", "success")
            return redirect(next_page or url_for("main.dashboard"))
        flash("E-mail ou senha inválidos.", "danger")
    return render_template("login.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu.", "info")
    return redirect(url_for("main.index"))

# ---------- Dashboard ----------
@bp.route("/dashboard")
@login_required
def dashboard():
    user_id = ObjectId(current_user.get_id())
    materias = list(mongo.db.materias.find())
    total_materias = len(materias)
    progresso_list = list(mongo.db.progresso.find({"user_id": user_id}))
    concluidas_slugs = {p["slug_materia"] for p in progresso_list if p.get("concluida")}
    qtd_concluidas = len(concluidas_slugs)

    # Progresso por área
    areas = sorted(set(m["area"] for m in materias if m))
    progresso_por_area = []
    for area in areas:
        materias_area = [m for m in materias if m["area"] == area]
        total_area = len(materias_area)
        concluidas_area = len([m for m in materias_area if m["slug"] in concluidas_slugs])
        pct = round(concluidas_area / total_area * 100, 1) if total_area else 0
        progresso_por_area.append({"area": area, "total": total_area, "concluidas": concluidas_area, "pct": pct})

    progresso_geral_pct = round(qtd_concluidas / total_materias * 100, 1) if total_materias else 0

    # Histórico recente
    historico = list(mongo.db.historico.find({"user_id": user_id}).sort("created_at", -1).limit(20))
    # Enriquecer com título da matéria
    slug_to_titulo = {m["slug"]: m["titulo"] for m in materias}
    for h in historico:
        h["titulo_materia"] = slug_to_titulo.get(h["slug_materia"], h["slug_materia"])

    # Materias estudadas detalhadas
    materias_estudadas = [m for m in materias if m["slug"] in concluidas_slugs]

    return render_template("dashboard.html",
                           total_materias=total_materias,
                           qtd_concluidas=qtd_concluidas,
                           progresso_geral_pct=progresso_geral_pct,
                           progresso_por_area=progresso_por_area,
                           historico=historico,
                           materias_estudadas=materias_estudadas,
                           progresso_map={p["slug_materia"]: p for p in progresso_list})

# ---------- Progresso API ----------
@bp.route("/api/progresso/<slug>/toggle", methods=["POST"])
@login_required
def toggle_progresso(slug):
    materia = mongo.db.materias.find_one({"slug": slug})
    if not materia:
        return jsonify({"erro": "Matéria não encontrada"}), 404
    from .models import toggle_progresso as tp
    concluida = tp(current_user.get_id(), slug)
    return jsonify({"slug": slug, "concluida": concluida})

@bp.route("/api/questoes/responder", methods=["POST"])
@login_required
def responder_questoes():
    data = request.get_json() or {}
    slug = data.get("slug_materia")
    acertos = data.get("acertos")
    total = data.get("total")
    nota = data.get("nota")
    detalhes = data.get("detalhes", [])

    if not slug or acertos is None or total is None:
        return jsonify({"erro": "Dados incompletos: slug_materia, acertos, total são obrigatórios"}), 400
    try:
        acertos = int(acertos)
        total = int(total)
        nota = float(nota) if nota is not None else round(acertos/total*10, 1) if total else 0
    except Exception:
        return jsonify({"erro": "acertos/total/nota devem ser numéricos"}), 400

    if not mongo.db.materias.find_one({"slug": slug}):
        return jsonify({"erro": "Matéria não encontrada"}), 404

    doc = salvar_tentativa(current_user.get_id(), slug, acertos, total, nota, detalhes)
    return jsonify({"ok": True, "acertos": acertos, "total": total, "nota": nota, "id": str(doc["_id"])})

# ---------- Importar Questões ----------
@bp.route("/importar_questoes", methods=["POST"])
@login_required
def importar_questoes():
    if not getattr(current_user, "is_admin", False):
        # retorna JSON se for AJAX, senão flash
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"erro": "Acesso restrito a administradores"}), 403
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for("main.index"))

    # Aceita upload de arquivo ou JSON raw
    questoes_data = None
    erros = []
    arquivo = request.files.get("arquivo")

    try:
        if arquivo and arquivo.filename:
            conteudo = arquivo.read().decode("utf-8")
            questoes_data = json.loads(conteudo)
        elif request.is_json:
            questoes_data = request.get_json()
        else:
            # tenta ler form field 'json'
            raw = request.form.get("json")
            if raw:
                questoes_data = json.loads(raw)
    except Exception as e:
        return jsonify({"importadas": 0, "erros": [{"erro": f"JSON inválido: {e}"}]}), 400

    if questoes_data is None:
        return jsonify({"importadas": 0, "erros": [{"erro": "Nenhum arquivo ou JSON enviado. Envie campo 'arquivo' com JSON."}]}), 400

    if not isinstance(questoes_data, list):
        return jsonify({"importadas": 0, "erros": [{"erro": "JSON deve ser uma lista de questões"}]}), 400

    # Validação
    validas_por_slug = {}
    erros = []
    letras_validas = {"A", "B", "C", "D", "E"}

    for idx, q in enumerate(questoes_data):
        prefix = f"Índice {idx}"
        if not isinstance(q, dict):
            erros.append({"index": idx, "erro": "Item deve ser objeto", "slug_materia": None})
            continue
        enunciado = (q.get("enunciado") or "").strip()
        alternativas = q.get("alternativas")
        gabarito = (q.get("gabarito") or "").strip().upper()
        slug_materia = (q.get("slug_materia") or "").strip()

        if not enunciado:
            erros.append({"index": idx, "erro": "enunciado obrigatório", "slug_materia": slug_materia})
            continue
        if not isinstance(alternativas, list) or len(alternativas) < 2:
            erros.append({"index": idx, "erro": "alternativas deve ser lista com ao menos 2 itens", "slug_materia": slug_materia})
            continue
        # normaliza alternativas
        alternativas = [str(a).strip() for a in alternativas if str(a).strip()]
        if len(alternativas) < 2:
            erros.append({"index": idx, "erro": "alternativas vazias", "slug_materia": slug_materia})
            continue
        if gabarito not in letras_validas:
            erros.append({"index": idx, "erro": "gabarito deve ser uma letra A-E", "slug_materia": slug_materia})
            continue
        # verifica se letra existe dentro das alternativas
        idx_gab = ord(gabarito) - ord("A")
        if idx_gab >= len(alternativas):
            erros.append({"index": idx, "erro": f"gabarito {gabarito} fora do range das alternativas ({len(alternativas)} itens)", "slug_materia": slug_materia})
            continue
        if not slug_materia:
            erros.append({"index": idx, "erro": "slug_materia obrigatório", "slug_materia": None})
            continue
        if not mongo.db.materias.find_one({"slug": slug_materia}):
            erros.append({"index": idx, "erro": f"Matéria com slug '{slug_materia}' não encontrada", "slug_materia": slug_materia})
            continue

        validas_por_slug.setdefault(slug_materia, []).append({
            "enunciado": enunciado,
            "alternativas": alternativas,
            "gabarito": gabarito,
            "slug_materia": slug_materia,
            "created_at": datetime.utcnow()
        })

    # Inserção: sobrescrever por slug
    total_importadas = 0
    for slug_materia, lista in validas_por_slug.items():
        # remove existentes
        mongo.db.questoes.delete_many({"slug_materia": slug_materia})
        if lista:
            res = mongo.db.questoes.insert_many(lista)
            total_importadas += len(res.inserted_ids)

    return jsonify({"importadas": total_importadas, "erros": erros, "slugs_afetados": list(validas_por_slug.keys())})
