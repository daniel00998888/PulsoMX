import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup
import base64
import re

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

def desencriptar_url_google(google_url):
    """Desencripta la URL real del periódico oculta en el enlace de Google News"""
    try:
        if "news.google.com/rss/articles" not in google_url:
            return google_url
        
        id_articulo = google_url.split("/")[-1].split("?")[0]
        # Añadir el padding necesario para base64 si falta
        id_articulo += "=" * ((4 - len(id_articulo) % 4) % 4)
        
        decoded_bytes = base64.b64decode(id_articulo.encode('utf-8'), validate=False)
        decoded_text = decoded_bytes.decode('utf-8', errors='ignore')
        
        # Buscar patrones de URLs válidas dentro del texto decodificado
        urls = re.findall(r'https?://[^\s"\n]+', decoded_text)
        if urls:
            # Limpiar caracteres extraños al final de la URL si los hay
            url_real = urls[0].split('')[0].split('')[0]
            return url_real
    except Exception:
        pass
    return google_url

def obtener_imagen_real(google_url):
    url_real = desencriptar_url_google(google_url)
    print(f"🔗 Visitando web original: {url_real[:60]}...")
    
    try:
        response = requests.get(url_real, headers=HEADERS, timeout=12)
        if response.status_code != 200:
            # Si falla, intentar seguir redirecciones normales
            response = requests.get(url_real, headers=HEADERS, timeout=12, allow_redirects=True)
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Buscar en las etiquetas meta del periódico real
        img_tag = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
        
        if img_tag and img_tag.get("content"):
            imagen = img_tag["content"]
            # Si es una ruta relativa, la convertimos en absoluta
            if imagen.startswith("/"):
                from urllib.parse import urljoin
                imagen = urljoin(url_real, imagen)
            return imagen
            
    except Exception as e:
        print(f"⚠️ Error al extraer imagen de la fuente real: {e}")
        
    # Imagen por defecto si no se encuentra nada
    return "https://images.unsplash.com/photo-1504711434269-d0385429813a?q=80&w=800&auto=format&fit=crop"

def reescribir_con_ia(titulo_orig):
    if not GROQ_API_KEY:
        return titulo_orig, "Noticia reciente.", "Detalles en el enlace original."

    prompt = f"""Eres un periodista profesional mexicano. Escribe una noticia basada en este titular: {titulo_orig}.
    Responde ÚNICAMENTE con un JSON con estas claves exactas: "titulo", "resumen", "contenido". 
    El "contenido" debe tener al menos 300 palabras separados por saltos de línea."""

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
        
        # Obtenemos la imagen procesando el link encriptado de Google News
        img_url = obtener_imagen_real(link)
        url_final = desencriptar_url_google(link)

        noticias_guardadas.append({
            "id": len(noticias_guardadas) + 1,
            "titulo_original": t_orig,
            "titulo": t_ia,
            "resumen": r_ia,
            "contenido": c_ia,
            "imagen": img_url,
            "fecha": datetime.today().strftime('%Y-%m-%d'),
            "url_origen": url_final
        })
        nuevos += 1
    
    if nuevos > 0:
        guardar_noticias(noticias_guardadas[-100:])
        print(f"✅ Guardadas {nuevos} noticias.")

if __name__ == "__main__":
    ejecutar()
