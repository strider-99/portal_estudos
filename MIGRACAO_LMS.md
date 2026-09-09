# Migração LMS — Meu Portal de Estudos

## Resumo
Evolução do portal para LMS simples com:
- Cadastro/login (Flask-Login, `users`)
- Dashboard pessoal (`progresso`, `historico`)
- Questões interativas na última página (coleção `questoes`)
- Importação de questões via `POST /importar_questoes`
- Progresso por matéria/área

## Pré-requisitos
- Flask + MongoDB + Jinja2 mantidos
- Novos requisitos: `Flask-Login==0.6.3`
```bash
pip install -r requirements.txt
```

- Variáveis `.env`:
```
MONGO_URI=mongodb://localhost:27017/meu_portal
SECRET_KEY=sua-chave-secreta-forte
```

## Migração automática
```bash
python migrate_lms.py
```
Cria índices:
- `users.email` unique
- `questoes.slug_materia`
- `progresso (user_id, slug_materia)` unique
- `historico (user_id, created_at)`
- `materias.slug` unique

Coleções criadas automaticamente ao inserir primeiro doc; script apenas garante índices.

## Migração manual (mongosh)
```js
db.users.createIndex({email:1}, {unique:true})
db.questoes.createIndex({slug_materia:1})
db.progresso.createIndex({user_id:1, slug_materia:1}, {unique:true})
db.historico.createIndex({user_id:1, created_at:-1})
db.materias.createIndex({slug:1}, {unique:true})

// promover admin
db.users.updateOne({email:"seu@email.com"}, {$set:{is_admin:true}})
```

## Fluxo de uso
1. Primeiro cadastro vira `is_admin=true` automaticamente.
2. Outros usuários: admin promove via `db.users.updateOne(...)`.
3. Login → Dashboard (`/dashboard`) mostra: concluídas, % por área, histórico.
4. Na matéria: botão “Marcar como concluída” → `POST /api/progresso/<slug>/toggle`
5. Na última página: quiz → “Corrigir” salva em `POST /api/questoes/responder` → cria `historico` + atualiza `progresso`.
6. Admin na matéria: botão “Importar Questões” → modal upload JSON → `POST /importar_questoes`.

## Rota /importar_questoes
- Método: `POST`
- Auth: `login_required` + `is_admin`
- Formato: `multipart/form-data` campo `arquivo` (JSON) ou JSON raw.
- Payload exemplo:
```json
[
  {
    "enunciado": "O que é PODC?",
    "alternativas": ["a) Planejar", "b) Organizar", "c) Dirigir", "d) Controlar", "e) Todas"],
    "gabarito": "E",
    "slug_materia": "podc"
  }
]
```
- Validação: enunciado obrigatório, alternativas ≥2, gabarito A-E dentro do range, slug_materia existe em `materias`.
- Comportamento: para cada `slug_materia` com itens válidos, `delete_many` antigas e `insert_many` novas (sobrescreve).
- Retorno:
```json
{"importadas": 5, "erros": [{"index":2,"erro":"...","slug_materia":"x"}], "slugs_afetados": ["podc"]}
```

Teste via curl:
```bash
curl -X POST http://localhost:5000/importar_questoes \
  -H "Cookie: session=..." \
  -F arquivo=@questoes.json
```

## Coleções
### users
```js
{ _id, email, password_hash, is_admin:false, created_at }
```
### questoes
```js
{ _id, enunciado, alternativas:["a) ..."], gabarito:"A", slug_materia, created_at }
```
### progresso
```js
{ _id, user_id:ObjectId, slug_materia, concluida:bool, tentativas:int, ultimo_acertos, ultimo_total, ultima_nota, created_at, updated_at }
```
### historico
```js
{ _id, user_id, slug_materia, acertos, total, nota, detalhes:[{index,gabarito,resposta,correto}], created_at }
```

## Notas
- Questões dinâmicas agora vêm da coleção `questoes`, não mais de `materias.questoes` (mantido fallback).
- Sem breaking change: `importar_apostilas.py` continua funcionando; questões antigas em `materias` ainda exibidas se `questoes` vazia.
