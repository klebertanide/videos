```python
# main.py - Fábrica de Shorts Cristãos Motivacionais totalmente automatizada
# Gera 15 vídeos por dia com texto, narração, imagens, música e upload opcional

from dotenv import load_dotenv
import os
import json
import requests
import random
from datetime import datetime
from pathlib import Path
from time import sleep
import subprocess

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
IDEOGRAM_KEY = os.getenv("IDEOGRAM_API_KEY")

if not OPENAI_KEY:
    raise RuntimeError("⚠️ OPENAI_API_KEY não definido!")
if not ELEVEN_KEY:
    raise RuntimeError("⚠️ ELEVENLABS_API_KEY não definido!")
if not IDEOGRAM_KEY:
    raise RuntimeError("⚠️ IDEOGRAM_API_KEY não definido!")

print("🚀 Iniciando pipeline de geração de vídeos...")
print(f"DEBUG: OPENAI_KEY set? {bool(OPENAI_KEY)}")
print(f"DEBUG: ELEVEN_KEY set? {bool(ELEVEN_KEY)}")
print(f"DEBUG: IDEOGRAM_KEY set? {bool(IDEOGRAM_KEY)}")

# Diretórios
ROOT = Path(__file__).parent
CONFIG_DIR = ROOT / "config"
CANAIS_DIR = ROOT / "canais"
VIDEOS_DIR = ROOT / "videos" / datetime.now().strftime("%Y-%m-%d")
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Carregar canal ativo
txt = CONFIG_DIR / "canal_ativo.txt"
with open(txt) as f:
    canal = f.read().strip()
CANAL_DIR = CANAIS_DIR / canal

# Carregar configs específicas do canal
with open(CANAL_DIR / "prompt.txt") as f:
    prompt_base = f.read().strip()
with open(CANAL_DIR / "visual.json") as f:
    visual_config = json.load(f)
with open(CANAL_DIR / "voz.json") as f:
    voz_config = json.load(f)
MUSICAS_DIR = CANAL_DIR / "musicas"

# Funções auxiliares
def gerar_texto():
    payload = {
        "model": "gpt-4-turbo",
        "messages": [{"role": "user", "content": prompt_base}],
        "max_tokens": 150
    }
    headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
    resp = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def gerar_audio(texto, idx):
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": voz_config.get("stability", 0.6),
            "similarity_boost": voz_config.get("similarity_boost", 0.9),
            "style": voz_config.get("style", 0.15),
            "use_speaker_boost": voz_config.get("use_speaker_boost", True)
        }
    }
    headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voz_config['voice_id']}"
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    path = VIDEOS_DIR / f"audio_{idx}.mp3"
    with open(path, "wb") as f:
        f.write(resp.content)
    return path

def obter_duracao(audio_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    out = subprocess.check_output(cmd).decode().strip()
    return float(out)

def gerar_imagens(texto, duracao):
    n = max(1, int(duracao // 4))
    imgs = []
    for i in range(n):
        body = {"prompt": texto, **visual_config}
        headers = {"Authorization": f"Bearer {IDEOGRAM_KEY}", "Content-Type": "application/json"}
        resp = requests.post("https://api.ideogram.ai/v1/generate", json=body, headers=headers)
        resp.raise_for_status()
        url = resp.json().get("image_url")
        if url:
            data = requests.get(url).content
            path = VIDEOS_DIR / f"img_{i}.jpg"
            with open(path, 'wb') as f:
                f.write(data)
            imgs.append(path)
        sleep(0.5)
    return imgs

def escolher_musica():
    lista = list(MUSICAS_DIR.glob("*.mp3"))
    return random.choice(lista) if lista else None

def montar_video(idx, audio_path, imagens, musica_path):
    base = VIDEOS_DIR / f"base_{idx}.mp4"
    concat = VIDEOS_DIR / f"in_{idx}.txt"
    dur = obter_duracao(audio_path)
    tempo = dur / len(imagens) if imagens else dur
    with open(concat, "w") as f:
        for img in imagens:
            f.write(f"file '{img}'\n")
            f.write(f"duration {tempo}\n")
        if imagens: f.write(f"file '{imagens[-1]}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", "scale=1080:1920,format=yuv420p", str(base)
    ], check=True)
    final = VIDEOS_DIR / f"video_{idx}.mp4"
    cmd = ["ffmpeg", "-y", "-i", str(base), "-i", str(audio_path)]
    if musica_path:
        cmd += ["-i", str(musica_path),
                "-filter_complex", "[1:a]volume=1[a1];[2:a]volume=0.2[a2];[a1][a2]amix=inputs=2:duration=first"]
    cmd += ["-c:v", "libx264", "-c:a", "aac", "-shortest", str(final)]
    subprocess.run(cmd, check=True)

# Execução principal
TOTAL = 15
for i in range(TOTAL):
    print(f"[{i+1}/{TOTAL}] Gerando vídeo...")
    try:
        txt = gerar_texto()
        aud = gerar_audio(txt, i)
        d = obter_duracao(aud)
        imgs = gerar_imagens(txt, d)
        mus = escolher_musica()
        montar_video(i, aud, imgs, mus)
        print(f"Vídeo {i+1} concluído.")
    except Exception as e:
        print(f"Erro no vídeo {i+1}: {e}")
```
