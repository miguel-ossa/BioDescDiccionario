from pydantic import BaseModel
import pdfplumber
import json
from config import *
from typing import List

# ============================================================
# MODELOS PYDANTIC PARA ESTRUCTURAR LA EXTRACCIÓN
# ============================================================

class EntradaDiccionario(BaseModel):
    """Modelo para una entrada del diccionario"""
    termino: str
    definicion: str
    tecnico: str
    sentido_biologico: str
    conflicto: str
    referencias_cruzadas: list[str]
    pagina_inicio: int
    pagina_fin: int


class SeccionExtraida(BaseModel):
    """Modelo para una sección extraída del PDF"""
    nombre_seccion: str
    paginas: str
    contenido_raw: str
    entradas: list[EntradaDiccionario]


def extraer_seccion_pdf(ruta_pdf: str, pagina_inicio: int, pagina_fin: int) -> str:
    """
    Extrae texto de un rango de páginas del PDF usando pdfplumber.
    """
    contenido = ""
    with pdfplumber.open(ruta_pdf) as pdf:
        for num_pagina in range(pagina_inicio - 1, pagina_fin):  # pdfplumber usa índice 0
            pagina = pdf.pages[num_pagina]
            texto_pagina = pagina.extract_text() or ""
            contenido += f"--- Página {num_pagina + 1} ---\n{texto_pagina}\n\n"
    return contenido

def estructurar_con_gpt(contenido: str, nombre_seccion: str = "desconocida") -> List[dict]:
    """
    Usa GPT-4 para estructurar el contenido extraído en entradas del diccionario.
    Procesa el contenido en chunks que terminan en límites de entradas.
    """
    # Buscar patrones de inicio de entradas (términos en mayúsculas)

    # Patrones que indican inicio de nueva entrada
    # Buscamos líneas que contengan solo mayúsculas (términos del diccionario)
    lineas = contenido.split('\n')

    # Encontrar índices de líneas que son títulos de entradas
    indices_titulos = []
    for i, linea in enumerate(lineas):
        # Un título de entrada típica: mayúsculas, posiblemente con espacios, sin números al inicio
        if linea.strip() and linea.strip().isupper() and len(linea.strip()) > 2:
            indices_titulos.append(i)

    print(f"  Encontrados {len(indices_titulos)} posibles títulos de entradas...")

    # Crear chunks que terminen en títulos de entradas
    chunks = []
    chunk_actual = ""

    for idx, linea in enumerate(lineas):
        chunk_actual += linea + "\n"

        # Si esta línea es un título Y el chunk tiene suficiente contenido, guardar chunk
        if idx in indices_titulos and len(chunk_actual) > 10000:
            chunks.append(chunk_actual)
            chunk_actual = ""

    # Agregar el último chunk si tiene contenido
    if chunk_actual.strip():
        chunks.append(chunk_actual)

    print(f"  Dividido en {len(chunks)} chunks (evitando cortar entradas)...")

    todas_entradas = []

    for idx, chunk in enumerate(chunks):
        # Reducir tamaño del chunk si es muy grande
        if len(chunk) > 18000:
            # Truncar inteligentemente: cortar al final de una entrada
            ultimas_lineas = chunk.split('\n')
            chunk_reducido = ""
            for linea in ultimas_lineas:
                chunk_reducido += linea + "\n"
                if len(chunk_reducido) > 15000:
                    break
            chunk = chunk_reducido

        prompt = f"""
        El siguiente texto contiene entradas de un diccionario de biodescodificación.
        Por cada entrada identificada, extrae la información y estructúrala en formato JSON.

        Cada entrada del diccionario tiene estas secciones:
        - Definición: Explicación médica del término
        - Técnico: Etapa embrionaria, tipo de conflicto, fases de la enfermedad
        - Sentido Biológico: Por qué el cuerpo responde así
        - Conflicto: Conflictos emocionales asociados
        - Referencias cruzadas: Términos relacionados (después de "Ver:")

        Devuelve un objeto JSON con una clave "entradas" que contenga un array de objetos, 
        donde cada objeto tenga:
        - termino: nombre del término
        - definicion: texto de la sección Definición (completo)
        - tecnico: texto de la sección Técnico (completo)
        - sentido_biologico: texto de esa sección (completo)
        - conflicto: texto de esa sección (completo)
        - referencias_cruzadas: array con los términos de las referencias cruzadas

        IMPORTANTE: Asegúrate de que TODOS los campos estén COMPLETOS. 
        Si una entrada parece estar incompleta (cortada a mitad de oración), NO la incluyas.

        SOLO RESPONDE CON JSON VÁLIDO, sin texto adicional.

        Chunk {idx + 1}/{len(chunks)} de la sección '{nombre_seccion}':
        {chunk}
        """

        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system",
                     "content": "Eres un asistente especializado en estructurar contenido de diccionarios médicos. Responde SIEMPRE con JSON válido dentro de un objeto con clave 'entradas'. NO incluyas markdown, NO incluyas explicaciones, SOLO JSON. ASEGURATE de que todos los campos estén completos."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            contenido_respuesta = response.choices[0].message.content

            # Limpiar markdown
            contenido_limpio = contenido_respuesta.strip()
            if contenido_limpio.startswith("```json"):
                contenido_limpio = contenido_limpio[7:]
            if contenido_limpio.startswith("```"):
                contenido_limpio = contenido_limpio[3:]
            if contenido_limpio.endswith("```"):
                contenido_limpio = contenido_limpio[:-3]
            contenido_limpio = contenido_limpio.strip()

            # Parsear JSON
            data = json.loads(contenido_limpio)
            entradas_chunk = data.get("entradas", [])

            # Filtrar entradas incompletas
            entradas_validas = []
            for entrada in entradas_chunk:
                campos_requeridos = ['termino', 'definicion', 'tecnico', 'sentido_biologico', 'conflicto']
                # Verificar que los campos principales no estén vacíos o truncados
                if (entrada.get('termino') and
                        entrada.get('definicion') and
                        len(entrada.get('definicion', '')) > 20 and  # Al menos 20 chars
                        len(entrada.get('tecnico', '')) > 10 and  # Al menos 10 chars
                        len(entrada.get('sentido_biologico', '')) > 20):  # Al menos 20 chars
                    entradas_validas.append(entrada)

            todas_entradas.extend(entradas_validas)

            print(f"    Chunk {idx + 1}/{len(chunks)}: {len(entradas_validas)} entradas válidas")

        except json.JSONDecodeError as e:
            print(f"    Error JSON en chunk {idx + 1}: {e}")
            continue
        except Exception as e:
            print(f"    Error en chunk {idx + 1}: {e}")
            continue

    print(f"  Total: {len(todas_entradas)} entradas estructuradas")
    return todas_entradas

# ============================================================
# PROCESADOR COMPLETO
# ============================================================

def procesar_diccionario_completo():
    """
    Procesa todo el diccionario y guarda el resultado.
    """
    print("=" * 60)
    print("PROCESADOR DEL DICCIONARIO COMPLETO")
    print("=" * 60)

    todas_las_entradas = []
    estadisticas = {}

    # Ya tenemos la introducción y A procesados
    print("\nCargando introducción y capítulo A ya procesados...")
    try:
        with open("entradas_procesadas.json", 'r', encoding='utf-8') as f:
            entradas_a = json.load(f)
        todas_las_entradas.extend(entradas_a)
        print(f"  ✓ Capítulo A: {len(entradas_a)} entradas")
        estadisticas["letra_a"] = len(entradas_a)
    except FileNotFoundError:
        print("  ✗ No se encontró entradas_procesadas.json")

    # Procesar el resto de secciones
    print("\n" + "=" * 60)
    print("PROCESANDO SECCIONES RESTANTES")
    print("=" * 60)

    total_llamadas = 0
    costo_estimado = 0

    for seccion in SECCIONES_GPT:
        if seccion in ["letra_a"]:  # Saltar A que ya está procesada
            continue

        paginas = SECCIONES[seccion]
        print(f"\n[{seccion}] Páginas {paginas['inicio']}-{paginas['fin']}...")

        try:
            contenido = extraer_seccion_pdf(DICCIONARIO_PATH, paginas["inicio"], paginas["fin"])
            print(f"  Extraído: {len(contenido)} caracteres")

            if len(contenido) < 100:
                print(f"  ⚠ Sección vacía o muy corta, saltando...")
                continue

            # Estructurar con GPT
            print("  Estructurando con GPT-4...")
            entradas = estructurar_con_gpt(contenido, seccion)

            if entradas:
                todas_las_entradas.extend(entradas)
                estadisticas[seccion] = len(entradas)
                print(f"  ✓ {len(entradas)} entradas añadidas")
            else:
                print(f"  ✗ No se extrajeron entradas")

            total_llamadas += 1

        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue

    # Guardar resultado completo
    print("\n" + "=" * 60)
    print("GUARDANDO RESULTADOS")
    print("=" * 60)

    resultado_final = {
        "introduccion": {"contenido": "ya procesada"},
        "entradas": todas_las_entradas,
        "estadisticas": {
            "total_entradas": len(todas_las_entradas),
            "entradas_por_seccion": estadisticas
        }
    }

    # Guardar JSON completo
    with open(SALIDA_COMPLETA, 'w', encoding='utf-8') as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=2)
    print(f"✓ Guardado: {SALIDA_COMPLETA}")

    # Guardar solo entradas
    with open(SALIDA_ENTRADAS_COMPLETO, 'w', encoding='utf-8') as f:
        json.dump(todas_las_entradas, f, ensure_ascii=False, indent=2)
    print(f"✓ Guardado: {SALIDA_ENTRADAS_COMPLETO}")

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    print(f"Total de entradas: {len(todas_las_entradas)}")
    print("\nEntradas por sección:")
    for seccion, count in estadisticas.items():
        print(f"  {seccion}: {count}")

    return resultado_final

# ============================================================
# PIPELINE DE EXTRACCIÓN
# ============================================================

def procesar_introduccion_y_capitulo_a() -> dict:
    """
    Procesa introducción y capítulo A como prueba inicial.
    """
    resultado = {
        "introduccion": None,
        "letra_a": None,
        "errores": []
    }

    # Extraer introducción (páginas 1-3)
    print("Extrayendo introducción...")
    try:
        contenido_intro = extraer_seccion_pdf(DICCIONARIO_PATH, 1, 3)
        resultado["introduccion"] = {
            "contenido": contenido_intro,
            "caracteres": len(contenido_intro)
        }
        print(f"  ✓ Introducción: {len(contenido_intro)} caracteres")
    except Exception as e:
        resultado["errores"].append(f"Error introduccion: {e}")
        print(f"  ✗ Error: {e}")

    # Extraer capítulo A (páginas 5-94)
    print("\nExtrayendo capítulo A...")
    try:
        contenido_a = extraer_seccion_pdf(DICCIONARIO_PATH, 5, 94)
        print(f"  ✓ Capítulo A extraído: {len(contenido_a)} caracteres")

        # Estructurar con GPT
        print("\nEstructurando con GPT-4...")
        entradas_a = estructurar_con_gpt(contenido_a, "letra_a")

        resultado["letra_a"] = {
            "contenido_raw": contenido_a,
            "entradas": entradas_a,
            "total_entradas": len(entradas_a)
        }
        print(f"  ✓ {len(entradas_a)} entradas estructuradas")

    except Exception as e:
        resultado["errores"].append(f"Error capítulo A: {e}")
        print(f"  ✗ Error: {e}")

    return resultado


def validar_extraccion(resultado: dict) -> dict:
    """
    Valida la calidad de la extracción.
    """
    reporte = {
        "exitosa": False,
        "problemas": [],
        "metricas": {}
    }

    # Métricas de introducción
    if resultado["introduccion"]:
        if resultado["introduccion"]["caracteres"] > 500:
            reporte["metricas"]["intro_ok"] = True
        else:
            reporte["problemas"].append("Introducción muy corta")
    else:
        reporte["problemas"].append("No se extrajo la introducción")

    # Métricas del capítulo A
    if resultado["letra_a"]:
        num_entradas = resultado["letra_a"]["total_entradas"]
        reporte["metricas"]["entradas_a"] = num_entradas

        # Verificar completitud de entradas
        entradas_completas = sum(
            1 for e in resultado["letra_a"]["entradas"]
            if e.get("termino") and e.get("definicion")
        )
        reporte["metricas"]["entradas_completas"] = entradas_completas

        if num_entradas > 30 and entradas_completas > num_entradas * 0.7:
            reporte["exitosa"] = True
        elif num_entradas > 0:
            reporte["problemas"].append(f"Pocas entradas ({num_entradas}) o baja completitud")
        else:
            reporte["problemas"].append("No se estructuraron entradas")
    else:
        reporte["problemas"].append("No se procesó el capítulo A")

    return reporte


def guardar_resultados(resultado: dict, reporte: dict):
    """
    Guarda los resultados en archivos JSON.
    """
    # Guardar resultado completo
    with open(SALIDA_JSON, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en: {SALIDA_JSON}")

    # Guardar solo las entradas procesadas - CORREGIDO
    entradas_json = []
    if resultado.get("letra_a") and resultado["letra_a"].get("entradas"):
        for entrada in resultado["letra_a"]["entradas"]:
            # La entrada es un dict, no un objeto Pydantic
            entradas_json.append({
                "termino": entrada.get("termino", ""),
                "definicion": entrada.get("definicion", ""),
                "tecnico": entrada.get("tecnico", ""),
                "sentido_biologico": entrada.get("sentido_biologico", ""),
                "conflicto": entrada.get("conflicto", ""),
                "referencias_cruzadas": entrada.get("referencias_cruzadas", [])
            })

    with open(SALIDA_ENTRADAS, 'w', encoding='utf-8') as f:
        json.dump(entradas_json, f, ensure_ascii=False, indent=2)
    print(f"Entradas guardadas en: {SALIDA_ENTRADAS}")

    # Guardar reporte de validación
    with open("reporte_validacion.json", 'w', encoding='utf-8') as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"Reporte de validación guardado en: reporte_validacion.json")

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def main():
    """
    Función principal.
    """
    print("=" * 50)
    print("EXTRACTOR DICCIONARIO BIODESCODIFICACIÓN")
    print("=" * 50)
    print(f"Documento: {DICCIONARIO_PATH}")
    print(f"Tamaño: {os.path.getsize(DICCIONARIO_PATH) / (1024 * 1024):.2f} MB")
    print("=" * 50)

    # Paso 1: Extraer introducción y capítulo A
    print("\n[PASO 1] Extrayendo...")
    resultado = procesar_introduccion_y_capitulo_a()

    # Paso 2: Validar
    print("\n[PASO 2] Validando...")
    reporte = validar_extraccion(resultado)

    print(f"\nExtracción exitosa: {'Sí' if reporte['exitosa'] else 'No'}")
    print(f"Entradas del capítulo A: {reporte['metricas'].get('entradas_a', 0)}")

    if reporte["problemas"]:
        print("\nProblemas:")
        for p in reporte["problemas"]:
            print(f"  - {p}")

    # Paso 3: Guardar
    print("\n[PASO 3] Guardando...")
    guardar_resultados(resultado, reporte)

    print("\nCompletado.")
    return resultado, reporte


# Ejecutar si se corre directamente
# if __name__ == "__main__":
# resultado = procesar_diccionario_completo()

# resultado, reporte = main()
#
# print(f"Resultado: {resultado}")
# print(f"Reporte: {reporte}")

