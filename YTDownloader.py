import streamlit as st
import yt_dlp
import tempfile
import os
import shutil
import sys
import glob
from pathlib import Path
import re
from streamlit import rerun

# ==== Logger personalizado para erros do yt_dlp ====
class MyLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg):
        if '[Errno' in msg or 'ERROR:' in msg:
            st.error(f"Erro interno: {msg}")

# ==== Detectar ffmpeg no sistema ou embutido ====
def get_ffmpeg_path():
    ffmpeg_global = shutil.which("ffmpeg")
    if ffmpeg_global:
        return os.path.dirname(ffmpeg_global)

    # Caso não esteja no PATH, tenta usar ffmpeg/bin/ffmpeg.exe (embutido)
    base_path = os.path.dirname(__file__)
    ffmpeg_embutido = os.path.join(base_path, 'ffmpeg', 'bin', 'ffmpeg.exe')
    if os.path.isfile(ffmpeg_embutido):
        return os.path.dirname(ffmpeg_embutido)

    return None

# ==== Hook de progresso com tempo e taxa ====
def make_progress_hook(progress_bar, status_text):
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 1)
            downloaded = d.get('downloaded_bytes', 0)
            percent = min(downloaded / total, 1.0)
            progress_bar.progress(percent)

            percent_str = re.sub(r'[\x00-\x1f\x7f-\x9f]+', '', d.get('_percent_str', '')).strip()
            eta = re.sub(r'[\x00-\x1f\x7f-\x9f]+', '', d.get('_eta_str', '')).strip()
            speed = re.sub(r'[\x00-\x1f\x7f-\x9f]+', '', d.get('_speed_str', '')).strip()

            status_text.text(f"{percent_str} baixado | {speed} | ETA: {eta}")

        elif d['status'] == 'finished':
            progress_bar.progress(1.0)
            status_text.text("Finalizando...")
    return hook

# ==== Função principal de download ====
def baixar_e_gerar_arquivo(url, qualidade, apenas_audio, progress_bar, status_text):
    url = url.strip().split('&')[0]  # Limpa URL
    ffmpeg_path = get_ffmpeg_path()
    usar_ffmpeg = ffmpeg_path if ffmpeg_path else None

    if apenas_audio:
        fmt = "bestaudio/best"
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        fmt = {
            "Alta (1080p/720p)": "bestvideo[height<=1080]+bestaudio/best",
            "Média (480p)": "bestvideo[height<=480]+bestaudio/best",
            "Baixa (360p)": "bestvideo[height<=360]+bestaudio/best"
        }.get(qualidade, "best")
        postprocessors = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]

    temp_dir = tempfile.gettempdir()
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        'format': fmt,
        'merge_output_format': 'mp4' if not apenas_audio else None,
        'outtmpl': output_template,
        'postprocessors': postprocessors,
        'progress_hooks': [make_progress_hook(progress_bar, status_text)],
        'logger': MyLogger(),
        'quiet': True,
        'noplaylist': True,
        'http_chunk_size': 1048576,
        'no_warnings': True
    }

    if usar_ffmpeg:
        ydl_opts['ffmpeg_location'] = usar_ffmpeg

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        nome_arquivo = info['title']
        extensao = 'mp3' if apenas_audio else 'mp4'
        caminho_final = os.path.join(temp_dir, f"{nome_arquivo}.{extensao}")
        thumbnail_url = info.get('thumbnail')
        return caminho_final, extensao, nome_arquivo, thumbnail_url
    except Exception as e:
        st.error(f"❌ Erro no processamento: {e}")
        return None, None, None, None

# ==== Interface do Streamlit ====
st.set_page_config(page_title="YouTube Downloader", page_icon="📅")
st.title("📥 YouTube Downloader")

# Barra lateral: arquivos em temp
with st.sidebar:
    st.subheader("📂 Arquivos disponíveis para download")
    temp_dir = tempfile.gettempdir()
    filtro_tipo = st.radio("Filtrar por:", ["Todos", "Áudio", "Vídeo"])

    extensoes = {
        "Todos": (".mp3", ".mp4"),
        "Áudio": (".mp3",),
        "Vídeo": (".mp4",)
    }[filtro_tipo]

    arquivos = glob.glob(os.path.join(temp_dir, '*.*'))
    arquivos = [os.path.basename(a) for a in arquivos if a.endswith(extensoes)]

    if arquivos:
        for nome in arquivos:
            caminho = os.path.join(temp_dir, nome)
            tamanho_mb = os.path.getsize(caminho) / (1024 * 1024)
            with open(caminho, "rb") as f:
                st.download_button(f"🔍 Baixar {nome} ({tamanho_mb:.2f} MB)", data=f, file_name=nome, mime="audio/mpeg" if nome.endswith(".mp3") else "video/mp4")
    else:
        st.caption("Nenhum arquivo encontrado com esse filtro.")

    st.markdown("---")
    if arquivos:
        if st.checkbox("⚠️ Confirmar exclusão de todos os arquivos da pasta temp"):
            if st.button("❌ Limpar arquivos agora"):
                for f in arquivos:
                    try:
                        os.remove(os.path.join(temp_dir, f))
                    except:
                        pass
                rerun()

    st.markdown("---")
    st.subheader("🔖 Instalar VLC Player")
    st.markdown("[VLC (Windows 32-bit)](https://get.videolan.org/vlc/3.0.21/win32/vlc-3.0.21-win32.exe)")

url = st.text_input("🔗 Insira a URL do vídeo:")
qualidade = st.selectbox("🎮 Qualidade desejada:", [
    "Alta (1080p/720p)", "Média (480p)", "Baixa (360p)", "Somente Áudio"
])
apenas_audio = st.checkbox("🎵 Baixar apenas o áudio (MP3)", value=("Áudio" in qualidade))

if st.button("🛂 Baixar"):
    if not url.strip():
        st.warning("Informe a URL do vídeo.")
    else:
        progresso = st.progress(0)
        status = st.empty()
        caminho_final, ext, nome_arquivo, thumbnail_url = baixar_e_gerar_arquivo(url, qualidade, apenas_audio, progresso, status)

        if caminho_final and os.path.exists(caminho_final):
            st.subheader(f"🌟 {nome_arquivo}")
            if thumbnail_url:
                st.image(thumbnail_url, width=320)
            with open(caminho_final, "rb") as f:
                st.download_button(
                    label="📀 Clique aqui para baixar o arquivo",
                    data=f,
                    file_name=f"{nome_arquivo}.{ext}",
                    mime="audio/mpeg" if ext == "mp3" else "video/mp4"
                )
