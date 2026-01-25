# config.py
import os
from dotenv import load_dotenv
from collections import defaultdict
from openai import OpenAI
import anthropic

load_dotenv(override=True)
# EMAIL_ALERTS_ENABLED = os.getenv("EMAIL_ALERTS_ENABLED")
# MAX_TOKENS_PER_IP = 5_000
# token_usage = defaultdict(int)
# ABUSE_MESSAGE = (
#     "Has alcanzado el límite de uso para esta sesión.\n"
#     "Si deseas continuar, contáctame en otro momento."
# )
# DICCIONARIO_PATH="BDE-Gran diccionario de biodescodificación.pdf"
# SALIDA_JSON = "diccionario_extraido.json"
# SALIDA_ENTRADAS = "entradas_procesadas.json"
SALIDA_COMPLETA = "diccionario_completo.json"
SALIDA_ENTRADAS_COMPLETO = "entradas_completo.json"

# Definición completa de todas las secciones según el índice
# SECCIONES = {
#     "introduccion": {"inicio": 1, "fin": 3},
#     "letra_a": {"inicio": 5, "fin": 94},
#     "letra_b": {"inicio": 95, "fin": 113},
#     "letra_c": {"inicio": 114, "fin": 202},
#     "letra_d": {"inicio": 203, "fin": 238},
#     "letra_e": {"inicio": 239, "fin": 290},
#     "letra_f": {"inicio": 291, "fin": 307},
#     "letra_g": {"inicio": 308, "fin": 327},
#     "letra_h": {"inicio": 328, "fin": 361},
#     "letra_i": {"inicio": 362, "fin": 379},
#     "letra_j": {"inicio": 380, "fin": 380},
#     "letra_k": {"inicio": 381, "fin": 381},
#     "letra_l": {"inicio": 382, "fin": 398},
#     "letra_m": {"inicio": 399, "fin": 433},
#     "letra_n": {"inicio": 434, "fin": 449},
#     "letra_o": {"inicio": 450, "fin": 465},
#     "letra_p": {"inicio": 466, "fin": 512},
#     "letra_q": {"inicio": 513, "fin": 516},
#     "letra_r": {"inicio": 517, "fin": 531},
#     "letra_s": {"inicio": 532, "fin": 554},
#     "letra_t": {"inicio": 555, "fin": 582},
#     "letra_u": {"inicio": 583, "fin": 589},
#     "letra_v": {"inicio": 590, "fin": 603},
#     "letra_wxy": {"inicio": 604, "fin": 604},
#     "letra_z": {"inicio": 605, "fin": 605},
#     "bibliografia": {"inicio": 606, "fin": 606},
#     "anexo_casa": {"inicio": 608, "fin": 615},
#     "anexo_coche": {"inicio": 616, "fin": 621},
#     "anexo_mascotas": {"inicio": 622, "fin": 625},
# }
#
# # Secciones principales (letras) para procesar con GPT
# SECCIONES_GPT = [
#     "letra_b", "letra_c", "letra_d", "letra_e", "letra_f", "letra_g",
#     "letra_h", "letra_i", "letra_j", "letra_k", "letra_l", "letra_m",
#     "letra_n", "letra_o", "letra_p", "letra_q", "letra_r", "letra_s",
#     "letra_t", "letra_u", "letra_v", "letra_wxy", "letra_z"
# ]

# Archivos del diccionario procesado
DICCIONARIO_JSON = "diccionario_completo.json"
ENTRADAS_JSON = "entradas_completo.json"

# Configuración del chat
MAX_ENTRADAS_RELEVANTES = 5
MAX_TOKENS_RESPUESTA = 5000

# openai_client = OpenAI()
#
# gemini = OpenAI(
#     api_key=os.getenv("GOOGLE_API_KEY"),
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# )
#
# perplexity = OpenAI(
#     api_key=os.getenv("PERPLEXITY_API_KEY"),
#     base_url="https://api.perplexity.ai"
# )

# anthropic = anthropic.Anthropic(
#     base_url="http://localhost:11434",
#     api_key='ollama'
# )

OLLAMA_MODEL = "mistral"

OLLAMA_OPTIONS = {
    "temperature": 0.3,
    "top_p": 0.9,
    "num_predict": MAX_TOKENS_RESPUESTA,
    "repeat_penalty": 1.1,
    "num_ctx": 2048,
    "num_thread": 8
}

