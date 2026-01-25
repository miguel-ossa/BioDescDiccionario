import json
from typing import List, Dict, Tuple
import unicodedata
import re
import gradio as gr
import os
os.environ["OLLAMA_HOST"] = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
import ollama
from config import *

# ============================================================
# SISTEMA DE BÚSQUEDA
# ============================================================

def normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[\d\-_/]", " ", texto)
    texto = re.sub(r"[^a-z\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()

def singularizar(palabra: str) -> str:
    if palabra.endswith("es"):
        return palabra[:-2]
    if palabra.endswith("s"):
        return palabra[:-1]
    return palabra

PALABRAS_GENERICAS = {
    "problema", "problemas",
    "emocion", "emociones",
    "conflicto", "conflictos",
    "trastorno", "trastornos",
    "alteracion", "alteraciones",
    "sintoma", "sintomas"
}

def buscar_entradas(termino: str, datos_diccionario: Dict, limite: int = 10) -> List[Dict]:
    """
    Búsqueda con múltiples estrategias.
    """
    termino_norm = normalizar(termino)
    resultados = []
    resultados_ids = set()

    palabras_consulta = termino_norm.split()

    GENERICAS_EN_CONSULTA = [
        p for p in palabras_consulta
        if p in PALABRAS_GENERICAS
    ]

    BUSQUEDA_GENERICA_INTENCIONAL = (
            len(GENERICAS_EN_CONSULTA) == 1 and
            len(palabras_consulta) <= 2
    )

    print(f"  Buscando: '{termino_norm}'")

    # =====================================================
    # Estrategia 1: Coincidencia exacta y núcleo semántico
    # =====================================================

    for clave, entrada in datos_diccionario["indice_exacto"].items():
        if id(entrada) in resultados_ids:
            continue

        # clave normalizada completa
        if termino_norm == clave or termino_norm in clave:
            resultados.insert(0, entrada)
            resultados_ids.add(id(entrada))
            print(f"    ★ Encontrado por coincidencia exacta: {entrada.get('termino')}")
            # Si se encuentra una coincidencia exacta, eliminar todas las demás
            # TODO: ¿Por qué encuentra ANTES por núcleo semántico?
            print(f"  Total encontrados: {len(resultados)}")
            return resultados[:limite]
            # continue

        palabras_consulta = set(termino_norm.split())
        # núcleo semántico (primera palabra del término)
        # núcleo semántico (palabra completa)
        nucleo = clave.split()[0]

        if (len(nucleo) < 5 or
                nucleo in PALABRAS_GENERICAS):
            continue

        if nucleo in palabras_consulta:
            resultados.insert(0, entrada)
            resultados_ids.add(id(entrada))
            print(f"    ★ Encontrado por núcleo semántico: {entrada.get('termino')}")

    # =====================================================
    # Preparar referencias cruzadas desde términos nucleares
    # =====================================================
    referencias = set()
    for e in resultados:
        referencias.update(e.get("referencias_cruzadas", []))

    # Estrategia 2: Búsqueda por palabras individuales
    # palabras = termino_norm.split()
    palabras = []
    for p in termino_norm.split():
        if len(p) <= 3:
            continue

        if (p in PALABRAS_GENERICAS
                and not BUSQUEDA_GENERICA_INTENCIONAL):
            continue

        palabras.append(singularizar(p))

    for palabra in palabras:
        if len(palabra) > 2 and palabra in datos_diccionario["indice_palabras"]:
            for entrada in datos_diccionario["indice_palabras"][palabra]:
                if id(entrada) in resultados_ids:
                    continue
                if referencias and entrada.get("termino") not in referencias:
                    continue
                if len(resultados) < limite * 3:
                    resultados.append(entrada)
                    resultados_ids.add(id(entrada))
                    print(f"    ✓ Encontrado por palabra '{palabra}': {entrada.get('termino')}")

    # Detectar núcleo semántico principal (singularizado)
    nucleos = set()
    for p in termino_norm.split():
        if len(p) > 4:
            # nucleos.add(p)
            nucleos.add(singularizar(p))

    NUCLEOS_REALES = {
        p for p in nucleos
        if (p in datos_diccionario["indice_palabras"]
                and p not in PALABRAS_GENERICAS)
    }

    if not NUCLEOS_REALES:
        for palabra in termino_norm.split():
            if palabra not in PALABRAS_GENERICAS and len(palabra) > 4:
                NUCLEOS_REALES.add(palabra)

    # Estrategia 3: Búsqueda por keywords normalizadas (semántica ligera)
    keywords = extraer_keywords(termino)

    for entrada in datos_diccionario["entradas"]:
        if id(entrada) in resultados_ids:
            continue

        # 🔒 Filtro semántico guiado por referencias cruzadas
        if referencias and entrada.get("termino") not in referencias:
            continue

        texto_entrada = normalizar(" ".join([
            entrada.get("termino", ""),
            entrada.get("definicion", ""),
            entrada.get("conflicto", ""),
            entrada.get("sentido_biologico", ""),
            entrada.get("tecnico", "")
        ]))

        texto_entrada = limpiar_texto(texto_entrada)

        coincidencias = sum(1 for k in keywords if f" {k} " in f" {texto_entrada} ")

        if (coincidencias >= 1 and
                any(n in texto_entrada for n in NUCLEOS_REALES) and
                len(texto_entrada) < 3000):
            resultados.append(entrada)
            resultados_ids.add(id(entrada))
            print(
                f"    ✓ Encontrado por keywords ({coincidencias}): "
                f"{entrada.get('termino')}"
            )

        if len(resultados) >= limite * 3:
            break

    print(f"  Total encontrados: {len(resultados)}")
    return resultados[:limite]

# ============================================================
# CARGAR DICCIONARIO
# ============================================================

def cargar_diccionario() -> Dict:
    try:
        with open(ENTRADAS_JSON, 'r', encoding='utf-8') as f:
            entradas = json.load(f)

        # Crear índice de búsqueda mejorado
        indice_exacto = {}
        indice_palabras = {}

        for entrada in entradas:
            termino_norm = normalizar(entrada.get("termino", ""))
            indice_exacto[termino_norm] = entrada

            for palabra in termino_norm.split():
                if len(palabra) > 3:
                    indice_palabras.setdefault(palabra, []).append(entrada)

        return {
            "entradas": entradas,
            "indice_exacto": indice_exacto,
            "indice_palabras": indice_palabras,
            "total": len(entradas)
        }
    except FileNotFoundError:
        return {"entradas": [], "indice_exacto": {}, "indice_palabras": {}, "total": 0}


# Cargar diccionario al iniciar
print(f"Cargando diccionario...")
diccionario_data = cargar_diccionario()
print(f"✓ Diccionario cargado: {diccionario_data['total']} entradas")

def construir_contexto(entradas: List[Dict]) -> str:
    """
    Construye el contexto para el modelo a partir de las entradas encontradas.
    """
    if not entradas:
        return "No se encontró información relevante en el diccionario."

    contexto = "INFORMACIÓN DEL DICCIONARIO DE BIODESCODIFICACIÓN:\n\n"

    for i, entrada in enumerate(entradas, 1):
        contexto += f"--- Entrada {i}: {entrada.get('termino', 'N/A')} ---\n"
        contexto += f"Definición: {entrada.get('definicion', 'N/A')}\n"
        contexto += f"Técnico: {entrada.get('tecnico', 'N/A')}\n"
        contexto += f"Sentido Biológico: {entrada.get('sentido_biologico', 'N/A')}\n"
        contexto += f"Conflicto: {entrada.get('conflicto', 'N/A')}\n"
        if entrada.get("referencias_cruzadas"):
            contexto += f"Referencias: {', '.join(entrada['referencias_cruzadas'])}\n"
        contexto += "\n"

    return contexto

STOPWORDS = {
    "se", "puede", "ser", "a", "la", "el", "los", "las",
    "un", "una", "de", "que", "y", "o", "es"
}

def extraer_keywords(pregunta: str) -> list[str]:
    texto = limpiar_texto(pregunta)
    palabras = texto.split()
    return [p for p in palabras if p not in STOPWORDS and len(p) > 3]

def limpiar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

# ============================================================
# GENERACIÓN DE RESPUESTAS
# ============================================================

def generar_respuesta_ollama(
        pregunta: str,
        contexto: str
) -> str:

    prompt = f"""Eres un asistente de biodescodificación.

    INFORMACIÓN:
    {contexto}

    PREGUNTA: {pregunta}

    Responde de forma completa, clara y estructurada, siendo fiel a la INFORMACIÓN proporcionada.
    NO inventes nada, ni te repitas."""

    try:
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "Responde únicamente con la información proporcionada."},
                {"role": "user", "content": prompt}
            ],
            options=OLLAMA_OPTIONS
        )
        return resp["message"]["content"]
    except Exception as e:
        return f"Error al generar respuesta local: {e}"

def responder_pregunta(pregunta: str, datos_diccionario: Dict) -> Dict:
    """
    Función principal que responde una pregunta.
    """
    # Paso 1: Buscar entradas relevantes
    entradas_encontradas = buscar_entradas(pregunta, datos_diccionario, MAX_ENTRADAS_RELEVANTES)

    if not entradas_encontradas:
        return {
            "respuesta": "No encontré información específica sobre ese tema en el diccionario. ¿Podrías reformular tu pregunta o usar términos diferentes?",
            "fuentes": [],
            "auditoria": None,
            "es_relevante": False
        }

    # Paso 2: Construir contexto
    contexto = construir_contexto(entradas_encontradas)

    # Paso 3: Generar respuesta con ChatGPT
    # respuesta_chatgpt = generar_respuesta_chatgpt(pregunta, contexto)
    respuesta = generar_respuesta_ollama(pregunta, contexto)

    return {
        "respuesta": respuesta,
        "fuentes": [e.get("termino") for e in entradas_encontradas],
        "es_relevante": True
    }


# ============================================================
# INTERFAZ GRADIO
# ============================================================

def chat_con_diccionario(mensaje: str, estado_chat: Dict) -> Dict:
    """
    Función principal del chat para Gradio.
    """
    # Inicializar estado si no existe
    if "historial" not in estado_chat:
        estado_chat["historial"] = []
    if "conversacion" not in estado_chat:
        estado_chat["conversacion"] = []

    # Añadir mensaje del usuario
    estado_chat["conversacion"].append({"role": "user", "content": mensaje})

    resultado = responder_pregunta(
        mensaje,
        diccionario_data
    )
    # Añadir respuesta al historial
    estado_chat["historial"].append(f"Usuario: {mensaje}")
    estado_chat["historial"].append(f"Asistente: {resultado['respuesta'][:200]}...")

    # Añadir al historial visible
    estado_chat["conversacion"].append({
        "role": "assistant",
        "content": resultado["respuesta"],
        "sources": resultado["fuentes"]
    })

    # Mostrar fuentes si hay
    fuentes_texto = ""
    if resultado["fuentes"]:
        fuentes_texto = "\n\n**Fuentes consultadas:** " + ", ".join(resultado["fuentes"])

    respuesta_completa = resultado["respuesta"] + fuentes_texto

    return respuesta_completa, estado_chat


def chat_fn(mensaje: str, historia: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Función del chat con formato de mensajes (Gradio moderno).
    """
    if not mensaje or not mensaje.strip():
        return "", historia

    # Generar respuesta
    resultado = responder_pregunta(mensaje, diccionario_data)

    # Construir respuesta con fuentes
    fuentes = ""
    if resultado["fuentes"]:
        fuentes = f"\n\n**Fuentes:** {', '.join(resultado['fuentes'])}"
    respuesta_completa = resultado["respuesta"] + fuentes

    # Añadir al historial en formato mensajes
    mensaje_user = {"role": "user", "content": mensaje}
    mensaje_assistant = {"role": "assistant", "content": respuesta_completa}

    historia.append(mensaje_user)
    historia.append(mensaje_assistant)

    return "", historia  # Limpia el input, devuelve el historial actualizado

def limpiar_fn() -> List[Dict]:
    """
    Limpia el historial del chat.
    """
    return []

def crear_interfaz():
    with gr.Blocks(title="Chat Biodescodificación (mossa 2026)") as interfaz:
        gr.Markdown("# 🧬 Chat de Biodescodificación (mossa 2026)")
        gr.Markdown(f"📚 Diccionario cargado: {diccionario_data['total']} entradas")

        chat = gr.Chatbot(
            label="Conversación",
            height=400
        )

        mensaje = gr.Textbox(
            label="Tu pregunta",
            placeholder="Ej: ¿Qué conflictos están relacionados con problemas digestivos?",
            scale=4
        )

        with gr.Row():
            boton_enviar = gr.Button("Enviar", variant="primary", scale=1)
            boton_limpiar = gr.Button("Limpiar", variant="secondary", scale=1)

        gr.Markdown("### 💡 Preguntas de ejemplo")
        gr.Examples(
            examples=[
                "¿Qué es la biodescodificación?",
                "¿Conflictos emocionales del estómago?",
                "Sentido biológico de las alergias",
                "Emociones y problemas de piel",
                "¿Qué sentido biológico tiene el covid?"
            ],
            inputs=mensaje
        )

        # Conectar eventos
        boton_enviar.click(
            fn=chat_fn,
            inputs=[mensaje, chat],
            outputs=[mensaje, chat]
        )

        mensaje.submit(
            fn=chat_fn,
            inputs=[mensaje, chat],
            outputs=[mensaje, chat]
        )

        boton_limpiar.click(
            fn=limpiar_fn,
            outputs=chat
        )

    return interfaz

# ============================================================
# MODO CONSOLA (alternativo)
# ============================================================

def modo_consola():
    """
    Chat en modo consola.
    """
    print("=" * 50)
    print("CHAT DE BIODESCODIFICACIÓN")
    print("=" * 50)
    print("Escribe 'salir' para terminar\n")

    # historial = []

    while True:
        pregunta = input("Tu pregunta: ").strip()

        if pregunta.lower() in ["salir", "exit", "quit"]:
            print("¡Hasta luego!")
            break

        if not pregunta:
            continue

        print("\nBuscando información...")
        resultado = responder_pregunta(pregunta, diccionario_data)

        print("\n" + "=" * 50)
        print("RESPUESTA:")
        print("=" * 50)
        print(resultado["respuesta"])

        if resultado["fuentes"]:
            print(f"\nFuentes: {', '.join(resultado['fuentes'])}")

        if resultado.get("auditoria"):
            nota = resultado["auditoria"].get("nota_final", "?")
            print(f"Evaluación: {nota}/10")

        print("\n" + "-" * 50)

# ============================================================
# ENTRADA PRINCIPAL
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--console":
        modo_consola()
    else:
        interface = crear_interfaz()
        interface.launch(server_name="0.0.0.0", server_port=7860, share=True)
