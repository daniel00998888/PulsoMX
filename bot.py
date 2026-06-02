import os
import json
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime

# ⚙️ CONFIGURACIÓN DEL MODO TURBO
MODO_TURBO = True 
NOTICIAS_POR_CARRERA = 10 if MODO_TURBO else 1

RSS_URL = "https://news.google.com/rss/search?q=when:1d+geo:Mexico&hl=es-419&gl=MX&ceid=MX:es-419"
JSON_PATH = "data/noticias.json"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_USERNAME = "daniel00998888"

def cargar_noticias():
    if not os.path.exists(JSON_PATH): return []
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def guardar_noticias(noticias):
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)

def extraer_imagen(item):
    """Extrae la imagen original desde el tag 'media:content' o 'enclosure' del RSS."""
    # Google News a veces mete la imagen en media:content
    media = item.find('{http://search.yahoo.com/mrss/}content')
    if media is not None and 'url' in media.attrib:
        return media.attrib['url']
    
    # Intento fallback en tag enclosure
    enclosure = item.find('enclosure')
    if enclosure is not None and 'url' in enclosure.attrib:
        return enclosure.attrib['url']
        
    return "https://tuweb.com/imagen-default.jpg" # Cambia esto por tu logo si no hay imagen

def reescribir_con_ia(titulo_orig):
    if not GROQ_API_KEY: return titulo_orig, "Noticia de última hora", "Contenido en desarrollo."
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt_texto = f"Actúa como periodista viral. Reescribe: {titulo_orig}. Devuelve JSON con 'titulo', 'resumen', 'contenido'."
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt_texto}],
        "response_format": {"type": "json_object"},
        "temperature": 0.5
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        res = r.json()
        contenido_crudo = res['choices'][0]['message']['content']
        data = json.loads(contenido_crudo)
        return data.get("titulo", titulo_orig), data.get("resumen", "Detalles aquí."), data.get("contenido", "Detalles aquí.")
    except:
        return titulo_orig, "Noticia importante.", "Revisa el enlace original."

def ejecutar():
    try:
        res = requests.get(RSS_URL, timeout=10)
        root = ET.fromstring(res.content)
    except: return
    
    noticias_guardadas = cargar_noticias()
    nuevos = 0
    
    for item in root.findall(".//item")[:NOTICIAS_POR_CARRERA]:
        t_orig = item.find("title").text
        if any(n['titulo_original'] == t_orig for n in noticias_guardadas): continue
        
        t_ia, r_ia, c_ia = reescribir_con_ia(t_orig)
        img_url = extraer_imagen(item) # EXTRAE LA ORIGINAL
        
        nuevo_id = max([n["id"] for n in noticias_guardadas], default=0) + 1
        noticias_guardadas.append({
            "id": nuevo_id, "titulo_original": t_orig, "titulo": t_ia,
            "resumen": r_ia, "contenido": c_ia, "imagen": img_url,
            "fecha": datetime.today().strftime('%Y-%m-%d')
        })
        nuevos += 1
        
    if nuevos > 0:
        guardar_noticias(noticias_guardadas)
        print(f"✅ Procesadas {nuevos} noticias con imágenes originales.")

if __name__ == "__main__":
    ejecutar()
