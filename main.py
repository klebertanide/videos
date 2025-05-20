# main.py - Fábrica de Shorts Cristãos Motivacionais totalmente automatizada
# Gera 15 vídeos por dia com texto, narração, imagens, música e upload opcional

import os
import json
import requests
import random
from datetime import datetime
from pathlib import Path
from time import sleep
import subprocess

print("🚀 Iniciando pipeline de geração de vídeos...")

# Debug: verifique se as env vars estão carregadas
print(f"DEBUG: OPENAI_API_KEY set? {bool(OPENAI_KEY)}")
print(f"DEBUG: ELEVENLABS_API_KEY set? {bool(ELEVEN_KEY)}")
print(f"DEBUG: IDEOGRAM_API_KEY set? {bool(IDEOGRAM_KEY)}")

# Diretórios
ROOT = Path(__file__).parent
CONFIG_DIR = ROOT / "config"
CANAIS_DIR = ROOT / "canais"
VIDEOS_DIR = ROOT / "videos" / datetime.now().strftime("%Y-%m-%d")
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Carregar configuração principal e canal ativo
with open(CONFIG_DIR / "config.json") as f:
    config = json.load(f)
with open(CONFIG_DIR / "canal_ativo.txt") as f:
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
    headers = {"Authorization": f"Bearer {config['openai_api_key']}"}
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
    headers = {"xi-api-key": config['elevenlabs_api_key'], "Content-Type": "application/json"}
    resp = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voz_config['voice_id']}", json=payload, headers=headers)
    resp.raise_for_status()
    audio_path = VIDEOS_DIR / f"audio_{idx}.mp3"
    with open(audio_path, "wb") as f:
        f.write(resp.content)
    return audio_path


def obter_duracao(audio_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    output = subprocess.check_output(cmd).decode().strip()
    return float(output)


def gerar_imagens(texto, duracao):
    n_imgs = max(1, int(duracao // 4))
    imagens = []
    for i in range(n_imgs):
        body = {"prompt": texto, **visual_config}
        headers = {"Authorization": f"Bearer {config['ideogram_api_key']}", "Content-Type": "application/json"}
        resp = requests.post("https://api.ideogram.ai/v1/generate", json=body, headers=headers)
        resp.raise_for_status()
        url = resp.json().get("image_url")
        if url:
            img_data = requests.get(url).content
            img_path = VIDEOS_DIR / f"img_{i}.jpg"
            with open(img_path, 'wb') as f:
                f.write(img_data)
            imagens.append(img_path)
        sleep(0.5)
    return imagens


def escolher_musica():
    musicas = list(MUSICAS_DIR.glob("*.mp3"))
    return random.choice(musicas) if musicas else None


def montar_video(idx, audio_path, imagens, musica_path):
    base_video = VIDEOS_DIR / f"base_{idx}.mp4"
    concat_file = VIDEOS_DIR / f"in_{idx}.txt"
    dur = obter_duracao(audio_path)
    tempo = dur / len(imagens) if imagens else dur
    with open(concat_file, "w") as f:
        for img in imagens:
            f.write(f"file '{img}'\n")
            f.write(f"duration {tempo}\n")
        if imagens:
            f.write(f"file '{imagens[-1]}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-vf", "scale=1080:1920,format=yuv420p",
        str(base_video)
    ], check=True)
    final = VIDEOS_DIR / f"video_{idx}.mp4"
    cmd = ["ffmpeg", "-y", "-i", str(base_video), "-i", str(audio_path)]
    if musica_path:
        cmd += ["-i", str(musica_path),
                "-filter_complex", "[1:a]volume=1[a1];[2:a]volume=0.2[a2];[a1][a2]amix=inputs=2:duration=first"]
    cmd += ["-c:v", "libx264", "-c:a", "aac", "-shortest", str(final)]
    subprocess.run(cmd, check=True)

# Execução principal
NUM_VIDEOS = 15
for i in range(NUM_VIDEOS):
    print(f"[{i+1}/{NUM_VIDEOS}] Gerando vídeo...")
    try:
        texto = gerar_texto()
        audio = gerar_audio(texto, i)
        dur = obter_duracao(audio)
        imgs = gerar_imagens(texto, dur)
        musica = escolher_musica()
        montar_video(i, audio, imgs, musica)
        print(f"Vídeo {i+1} concluído.")
    except Exception as e:
        print(f"Erro no vídeo {i+1}: {e}")
