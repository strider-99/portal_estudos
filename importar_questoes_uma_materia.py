import json
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
client = MongoClient(os.getenv('MONGO_URI'))
db = client.get_default_database()

with open('data/questoes_informatica_windows.json', 'r') as f:
    dados = json.load(f)

for item in dados:
    db.questoes.update_one(
        {'slug_materia': item['slug_materia'], 'enunciado': item['enunciado']},
        {'$set': item},
        upsert=True
    )
print('Importado!')