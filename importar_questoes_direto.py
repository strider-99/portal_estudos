import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Conectar ao MongoDB (usando a URI do .env)
client = MongoClient(os.getenv("MONGO_URI"))
db = client.get_default_database()

pasta = "data"

print("🔍 Iniciando importação direta de questões...\n")

for arquivo in os.listdir(pasta):
    if arquivo.endswith('.json') and arquivo.startswith('questoes_'):
        caminho = os.path.join(pasta, arquivo)
        print(f"📄 Processando: {arquivo}...")
        
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            
            if not isinstance(dados, list):
                print(f"⚠️ O arquivo {arquivo} não contém uma lista de questões. Pulando...")
                continue
            
            importadas = 0
            erros = 0
            
            for item in dados:
                # Verifica se a matéria existe
                materia = db.materias.find_one({"slug": item['slug_materia']})
                if not materia:
                    print(f"   ⚠️ Matéria com slug '{item['slug_materia']}' não encontrada para: {item['enunciado'][:50]}...")
                    erros += 1
                    continue
                
                # Insere ou atualiza a questão
                db.questoes.update_one(
                    {"slug_materia": item['slug_materia'], "enunciado": item['enunciado']},
                    {"$set": item},
                    upsert=True
                )
                importadas += 1
            
            print(f"   ✅ {importadas} questões importadas (erros: {erros})")
        
        except Exception as e:
            print(f"   ❌ Erro ao processar {arquivo}: {e}")

print("\n🎉 Importação concluída!")