import os
import re
import pymongo
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client.get_default_database()
colecao = db.materias

# Mapeamento área por nome do arquivo (sem extensão)
MAPEAMENTO_AREA = {
    "podc": "administracao",
    "financas_pessoas_materiais": "administracao",
    "relacoes_humanas": "administracao",
    "materiais": "administracao",
    "seguranca_ergonomia": "administracao",
    "qualidade_atendimento": "administracao",
    "gestao_documentos": "administracao",
    "arquivo": "administracao",
    "comportamento_organizacional": "administracao",
    "etica": "administracao",
    "atendimento_publico": "administracao",
    "recursos_patrimoniais_logistica": "administracao",
    "redacao_oficial": "administracao",
    "portugues_modulo1": "portugues",
    "portugues_modulo2": "portugues",
    "portugues_modulo3": "portugues",
    "portugues_modulo4": "portugues",
    "portugues_modulo5": "portugues",
    "portugues_modulo6": "portugues",
    "sus_cf": "sus",
    "sus_lei8080": "sus",
    "sus_humanizasus": "sus",
    "sus_nobrh": "sus",
    "sus_estatuto_idoso": "sus",
    "sus_populacao_negra": "sus",
    "sus_lgbt": "sus",
    "sus_estatuto_deficiencia": "sus",
    "sus_equidade_genero_raca": "sus",
    "sus_pnaispd_rcpd": "sus",
}

def extrair_dados(arquivo_path):
    with open(arquivo_path, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    soup = BeautifulSoup(conteudo, 'html.parser')

    # Título
    titulo_tag = soup.find('h1')
    titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Sem título"

    # Subtítulo
    subtitulo_tag = soup.find('p', style=lambda v: v and 'font-size:18px' in v) or soup.find('p', class_='subtitle')
    subtitulo = subtitulo_tag.get_text(strip=True) if subtitulo_tag else ""

    # Páginas (APENAS CONTEÚDO TEÓRICO) - remove páginas 7 e 8 com questões estáticas
    paginas = []
    for page_div in soup.find_all('div', class_='page'):
        html_str = str(page_div)
        # Filtra apenas páginas que realmente contêm questões (marcadas por questao-item)
        if 'questao-item' in html_str:
            continue
        html_interno = str(page_div.decode_contents())
        paginas.append(html_interno)

    # Extrai as questões
    questoes = []
    for q_div in soup.find_all('div', class_='questao-item'):
        p_tag = q_div.find('p')
        if not p_tag:
            continue
        enunciado = p_tag.get_text(strip=True)
        alt_div = q_div.find('div', class_='alternativas')
        alternativas = []
        if alt_div:
            for linha in alt_div.stripped_strings:
                if linha.strip():
                    alternativas.append(linha.strip())
        gabarito = ""
        for span in q_div.find_all('p'):
            texto = span.get_text()
            if 'Gabarito:' in texto:
                gabarito = texto.split('Gabarito:')[-1].strip()
                break
        if not gabarito:
            texto_completo = q_div.get_text()
            if 'Gabarito:' in texto_completo:
                gabarito = texto_completo.split('Gabarito:')[-1].strip().split('\n')[0]
        questoes.append({
            "enunciado": enunciado,
            "alternativas": alternativas,
            "gabarito": gabarito
        })

    # Opcional: gabarito completo
    gabarito_completo = ""
    gabarito_box = soup.find('div', class_='gabarito-box')
    if gabarito_box:
        gabarito_completo = gabarito_box.get_text(strip=True)

    total_paginas = len(paginas)
    # Questões estáticas removidas — usar coleção 'questoes' dinâmica via /importar_questoes
    questoes = []

    nome_base = os.path.basename(arquivo_path)
    chave = nome_base.replace('.html', '').replace('apostila_', '').lower()
    area = MAPEAMENTO_AREA.get(chave, "outros")
    slug = nome_base.replace('.html', '').lower()

    descricao = ""
    intro_tag = soup.find('h2', string=re.compile(r'INTRODUÇÃO|Introdução'))
    if intro_tag:
        next_p = intro_tag.find_next('p')
        if next_p:
            descricao = next_p.get_text(strip=True)[:200]

    icone_map = {"administracao": "📊", "portugues": "📝", "sus": "⚖️", "outros": "📄"}
    icone = icone_map.get(area, "📄")

    return {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "slug": slug,
        "area": area,
        "icone": icone,
        "descricao": descricao,
        "paginas": paginas,
        "questoes": questoes,
        "total_paginas": total_paginas
    }

def importar_apostilas(pasta):
    arquivos = [f for f in os.listdir(pasta) if f.endswith('.html') and f != 'index.html']
    if not arquivos:
        print(f"Nenhum arquivo HTML encontrado em {pasta}")
        return

    for arquivo in arquivos:
        caminho = os.path.join(pasta, arquivo)
        print(f"Processando: {arquivo}...")
        try:
            dados = extrair_dados(caminho)
            colecao.update_one(
                {"slug": dados["slug"]},
                {"$set": dados},
                upsert=True
            )
            print(f"  ✅ Inserido/Atualizado: {dados['titulo']}")
        except Exception as e:
            print(f"  ❌ Erro ao processar {arquivo}: {e}")

    print("\n🎉 Importação concluída!")

if __name__ == "__main__":
    PASTA_APOSTILAS = "/home/strider-99/Documentos/Concurso/SESRJ/Específicas/web/"
    importar_apostilas(PASTA_APOSTILAS)