import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

RSS_URL = "https://news.google.com/rss/search?q=when:1d+geo:Mexico&hl=es-419&gl=MX&ceid=MX:es-419"
JSON_PATH = "data/noticias.json"

# CREDENCIALES
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
GITHUB_USERNAME = "daniel00998888" # ⚠️ CAMBIA ESTO por tu nombre de usuario de GitHub

def cargar_noticias():
    if not os.path.exists(JSON_PATH): return []
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def guardar_noticias(noticias):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)

def reescribir_con_ia(titulo_orig, resumen_orig):
    if not GROQ_API_KEY: return titulo_orig, resumen_orig, resumen_orig
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    Actúa como un periodista digital mexicano enfocado en tráfico viral. Reescribe esta noticia.
    Devuelve ESTRICTAMENTE un objeto JSON con tres llaves:
    1. 'titulo': Un titular muy llamativo y clickbait ético.
    2. 'resumen': Un gancho corto de 2 líneas para redes sociales.
    3. 'contenido': El desarrollo completo de la noticia en 3 párrafos amplios y profesionales para leer en web.
    
    Noticia: {titulo_orig} - {resumen_orig}
    """
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15).json()
        data = json.loads(res['choices'][0]['message']['content'])
        return data.get("titulo"), data.get("resumen"), data.get("contenido")
    except:
        return titulo_orig, resumen_orig, resumen_orig

def publicar_en_facebook(titulo, resumen, id_noticia, imagen_url):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        print("⚠️ Configuración de Facebook incompleta. Saltando posteo.")
        return
    
    url_web = f"https://{GITHUB_USERNAME}.github.io/pulsomx/noticia.html?id={id_noticia}"
    mensaje = f"🚨 {titulo} 🚨\n\n{resumen}\n\n👉 Enterate de todos los detalles aquí: {url_web}"
    
    fb_url = f"https://graph.facebook.com/v20.0/{FB_PAGE_ID}/photos"
    payload = {
        "url": imagen_url,
        "caption": mensaje,
        "access_token": FB_ACCESS_TOKEN
    }
    try:
        r = requests.post(fb_url, data=payload, timeout=15)
        if r.status_code == 200: print("📢 ¡Publicado en Facebook con éxito!")
        else: print(f"❌ Error al publicar en FB: {r.text}")
    except Exception as e:
        print(f"❌ Fallo de conexión con Meta API: {e}")

def ejecutar():
    print("Buscando noticias en México...")
    res = requests.get(RSS_URL, timeout=10)
    if res.status_code != 200: return
    
    root = ET.fromstring(res.content)
    noticias_guardadas = cargar_noticias()
    titulos_viejos = {n["titulo_original"] for n in noticias_guardadas if "titulo_original" in n}
    
    nuevos = 0
    for item in root.findall(".//item")[:4]: # Procesamos máximo 2 noticias por tanda para cuidar la cuota
        t_orig = item.find("title").text
        link = item.find("link").text
        desc = item.find("description").text or t_orig
        
        if t_orig in titulos_viejos: continue
        
        t_ia, r_ia, c_ia = reescribir_con_ia(t_orig, desc)
        
        prompt_img = requests.utils.quote(f"dramatic news photo style, professional capture, {t_ia[:50]}")
        img_url = f"https://image.pollinations.ai/prompt/{prompt_img}?width=800&height=500&nologo=true"
        
        nuevo_id = max([n["id"] for n in noticias_guardadas], default=0) + 1
        
        # Guardar en base de datos
        noticias_guardadas.append({
            "id": nuevo_id, "titulo_original": t_orig, "titulo": t_ia,
            "resumen": r_ia, "contenido": c_ia, "imagen": img_url,
            "fecha": datetime.today().strftime('%Y-%m-%d'), "url_origen": link
        })
        nuevos += 1
        print(f"✅ Noticia generada de forma interna: {t_ia[:40]}")
        
        # Enviar directo a tu FanPage
        publicar_en_facebook(t_ia, r_ia, nuevo_id, img_url)
        
    if nuevos > 0:
        guardar_noticias(noticias_guardadas)

if __name__ == "__main__":
    ejecutar()
