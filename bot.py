import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup

# ⚙️ CONFIGURACIÓN
MODO_TURBO = True
NOTICIAS_POR_CARRERA = 10 if MODO_TURBO else 1
RSS_URL = "https://news.google.com/rss/search?q=when:1d+geo:Mexico&hl=es-419&gl=MX&ceid=MX:es-419"
JSON_PATH = "data/noticias.json"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}

def cargar_noticias():
    if not os.path.exists(JSON_PATH): return []
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def guardar_noticias(noticias):
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)

def obtener_imagen_real(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Usamos attrs para evitar el error de "multiple values"
        img_tag = soup.find("meta", attrs={"property": "og:image"})
        if img_tag and img_tag.get("content"):
            return img_tag["content"]
            
        return "https://images.unsplash.com/photo-1504711434269-d0385429813a?q=80&w=800&auto=format&fit=crop"
    except Exception:
        return "https://images.unsplash.com/photo-1504711434269-d0385429813a?q=80&w=800&auto=format&fit=crop"

def reescribir_con_ia(titulo_orig):
    if not GROQ_API_KEY:
        return titulo_orig, "Noticia reciente.", "Detalles en el enlace original."

    prompt = f"""Eres un periodista profesional. Escribe una noticia basada en: {titulo_orig}.
    Responde ÚNICAMENTE con un JSON con estas claves exactas: "titulo", "resumen", "contenido". 
    El "contenido" debe tener al menos 300 palabras."""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.7
    }

    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                          headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                          json=payload, timeout=45)
        res = r.json()
        
        if 'choices' in res:
            data = json.loads(res['choices'][0]['message']['content'])
            return data.get("titulo", titulo_orig), data.get("resumen", "Noticia importante."), data.get("contenido", "Detalles en el enlace.")
        return titulo_orig, "Noticia importante.", "Detalles en el enlace."
    except Exception as e:
        print(f"⚠️ Error IA: {e}")
        return titulo_orig, "Noticia importante.", "Detalles en el enlace."

def ejecutar():
    try:
        res = requests.get(RSS_URL, timeout=10)
        root = ET.fromstring(res.content)
    except Exception as e:
        print(f"❌ Error RSS: {e}")
        return

    noticias_guardadas = cargar_noticias()
    nuevos = 0

    for item in root.findall(".//item")[:NOTICIAS_POR_CARRERA]:
        t_orig = item.find("title").text
        link = item.find("link").text if item.find("link") is not None else "#"

        if any(n.get('titulo_original') == t_orig for n in noticias_guardadas):
            continue

        print(f"🔄 Procesando: {t_orig[:50]}...")
        t_ia, r_ia, c_ia = reescribir_con_ia(t_orig)
        img_url = obtener_imagen_real(link)

        noticias_guardadas.append({
            "id": len(noticias_guardadas) + 1,
            "titulo_original": t_orig,
            "titulo": t_ia,
            "resumen": r_ia,
            "contenido": c_ia,
            "imagen": img_url,
            "fecha": datetime.today().strftime('%Y-%m-%d'),
            "url_origen": link
        })
        nuevos += 1
    
    if nuevos > 0:
        guardar_noticias(noticias_guardadas[-100:])
        print(f"✅ Guardadas {nuevos} noticias.")

if __name__ == "__main__":
    ejecutar()
