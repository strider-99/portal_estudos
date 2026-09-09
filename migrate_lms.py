"""
Script de migração para LMS - Cria índices e coleções necessárias.

Uso:
    python migrate_lms.py

Requisitos: MONGO_URI no .env ou env var
"""
import os
from dotenv import load_dotenv
import pymongo

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/meu_portal")

client = pymongo.MongoClient(MONGO_URI)
db = client.get_default_database()
print(f"Conectado em: {MONGO_URI} -> db: {db.name}")

# Coleções
colecoes = ["materias", "users", "questoes", "progresso", "historico"]

# Índices
print("\n--- Criando índices ---")

# users: email único
db.users.create_index("email", unique=True)
print("✅ users.email unique")

# questoes: índice por slug_materia
db.questoes.create_index("slug_materia")
db.questoes.create_index([("slug_materia", 1), ("enunciado", 1)])
print("✅ questoes.slug_materia")

# progresso: único por (user_id, slug_materia)
db.progresso.create_index([("user_id", 1), ("slug_materia", 1)], unique=True)
db.progresso.create_index("user_id")
print("✅ progresso (user_id, slug_materia) unique")

# historico: índice por user + data
db.historico.create_index([("user_id", 1), ("created_at", -1)])
db.historico.create_index("slug_materia")
print("✅ historico (user_id, created_at)")

# materias: slug único (se ainda não existir)
db.materias.create_index("slug", unique=True)
db.materias.create_index("area")
print("✅ materias.slug unique + area")

print("\n--- Verificando coleções ---")
for c in colecoes:
    count = db[c].count_documents({})
    print(f"  {c}: {count} docs")

print("\n--- Tornar primeiro usuário admin (opcional) ---")
# Se quiser promover manualmente:
# db.users.update_one({"email": "seu@email.com"}, {"$set": {"is_admin": True}})

print("\n🎉 Migração concluída!")
print("""
Instruções de migração manual (mongosh):
  // criar índices manualmente
  db.users.createIndex({email:1}, {unique:true})
  db.questoes.createIndex({slug_materia:1})
  db.progresso.createIndex({user_id:1, slug_materia:1}, {unique:true})
  db.historico.createIndex({user_id:1, created_at:-1})

  // promover usuário a admin
  db.users.updateOne({email: "admin@exemplo.com"}, {$set: {is_admin: true}})

  // verificar
  db.users.find()
  db.questoes.find({slug_materia: "nome-da-materia"})
  db.progresso.find({user_id: ObjectId("...")})

Coleções criadas:
  - users: {email, password_hash, is_admin, created_at}
  - questoes: {enunciado, alternativas[], gabarito, slug_materia, created_at}
  - progresso: {user_id, slug_materia, concluida, tentativas, ultimo_acertos, ultimo_total, ultima_nota, created_at, updated_at}
  - historico: {user_id, slug_materia, acertos, total, nota, detalhes[], created_at}
""")
