import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime
import os
import gc
import sys
import fcntl
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2 import service_account
import requests
import json

load_dotenv()

# Lock file para prevenir múltiples instancias
LOCK_FILE = "/tmp/email_monitor.lock"

# Caché global para categorías (evita llamadas repetidas a Google Sheets)
_categorias_cache = {
    "entradas": [],
    "salidas": [],
    "last_update": None
}
CACHE_DURATION_SECONDS = 300  # Refrescar caché cada 5 minutos

# Configuración de email
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")  # contabilidad@dtgrowthpartners.com
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER")  # ej: mail.dtgrowthpartners.com
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

# Configuración de Slack
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")  # Para notificaciones
CANAL_CUENTAS = "C099YJRMA9E"

# Configuración de WhatsApp (cola JSON para María)
WHATSAPP_QUEUE_FILE = os.getenv("WHATSAPP_QUEUE_FILE", "transacciones_pendientes.json")

# Configuración de Google Sheets
SPREADSHEET_ID = "1SKHZBmxEsZgKjoEx_p5QtyOy21Z0o9twIsWWlICmuzE"
SERVICE_ACCOUNT_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Inicializar Google Sheets
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
sheets_service = build("sheets", "v4", credentials=creds)


def obtener_categorias_sheets(tipo="salidas", force_refresh=False):
    """
    Obtiene las categorías desde Google Sheets con caché.
    """
    global _categorias_cache

    try:
        # Verificar si el caché es válido
        now = datetime.now()
        if not force_refresh and _categorias_cache["last_update"]:
            elapsed = (now - _categorias_cache["last_update"]).total_seconds()
            if elapsed < CACHE_DURATION_SECONDS and _categorias_cache[tipo]:
                return _categorias_cache[tipo]

        sheet_name = "Entradas" if tipo == "entradas" else "Salidas"

        # Obtener metadata con validación de datos
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID,
            ranges=[f"{sheet_name}!D:D"],
            includeGridData=True
        ).execute()

        categorias = []

        for sheet in spreadsheet.get("sheets", []):
            if sheet.get("properties", {}).get("title") == sheet_name:
                grid_data = sheet.get("data", [])
                for data in grid_data:
                    row_data = data.get("rowData", [])
                    for row in row_data:
                        cells = row.get("values", [])
                        for cell in cells:
                            data_validation = cell.get("dataValidation")
                            if data_validation:
                                condition = data_validation.get("condition", {})
                                if condition.get("type") == "ONE_OF_LIST":
                                    values = condition.get("values", [])
                                    for val in values:
                                        user_entered = val.get("userEnteredValue", "")
                                        if user_entered and user_entered not in categorias:
                                            categorias.append(user_entered)
                                    if categorias:
                                        # Guardar en caché
                                        _categorias_cache[tipo] = categorias
                                        _categorias_cache["last_update"] = now
                                        return categorias

        # Si no hay validación, leer valores únicos
        if not categorias:
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!D:D"
            ).execute()

            values = result.get("values", [])
            for row in values[1:]:
                if row and row[0] and row[0] not in categorias:
                    categorias.append(row[0])

        # Guardar en caché
        _categorias_cache[tipo] = categorias
        _categorias_cache["last_update"] = now
        return categorias

    except Exception as e:
        print(f"Error obteniendo categorías: {e}")
        # Retornar caché existente si hay error
        if _categorias_cache[tipo]:
            return _categorias_cache[tipo]
        return []


def extract_transaction_data(email_body):
    """
    Extrae información de la transacción del correo de Bancolombia
    """
    try:
        # Limpiar el texto
        text = email_body.replace('\n', ' ').replace('\r', '')

        # Patrones de regex para extraer información
        # Ejemplo: "Compraste $28.250,00 en RAPPI con tu T.Deb *5993, el 29/12/2025 a las 06:34"

        # Tipo de transacción
        tipo = None
        if re.search(r'Compraste|Pagaste|Compra', text, re.IGNORECASE):
            tipo = "saliente"
            tipo_desc = "Compra"
        elif re.search(r'Transferiste|Transferencia enviada', text, re.IGNORECASE):
            tipo = "saliente"
            tipo_desc = "Transferencia"
        elif re.search(r'Recibiste|Transferencia recibida', text, re.IGNORECASE):
            tipo = "entrante"
            tipo_desc = "Transferencia recibida"
        else:
            # Por defecto, si no se identifica, asumimos que es salida
            tipo = "saliente"
            tipo_desc = "Transacción"

        # Monto - buscar patrones de Bancolombia
        # Formatos posibles:
        # - $79,607.00 (coma como separador de miles, punto decimal) - Formato americano
        # - $700,000 (coma como separador de miles, sin decimales)
        # - $28.250,00 (punto para miles, coma para decimales) - Formato europeo
        # - $1.800.000 (punto para miles, sin decimales)
        # Regex simple: captura todo lo que sea dígitos, puntos y comas después del $
        monto_match = re.search(r'\$\s?([\d.,]+)', text)
        if not monto_match:
            return None

        monto_str = monto_match.group(1)
        # Limpiar trailing puntos o comas si quedaron
        monto_str = monto_str.rstrip('.,')
        print(f"DEBUG - Monto extraído del correo: '{monto_str}'")

        # Detectar el formato del monto
        # Contar puntos y comas para determinar el formato
        num_puntos = monto_str.count('.')
        num_comas = monto_str.count(',')

        # Determinar la posición del último separador para identificar decimales
        last_punto = monto_str.rfind('.')
        last_coma = monto_str.rfind(',')

        if num_comas >= 1 and num_puntos == 1:
            # Puede ser formato americano: $300,000.00 (coma miles, punto decimal)
            # O formato europeo: $28.250,00 (punto miles, coma decimal)
            # Verificar cuál separador está al final (ese es el decimal)
            if last_punto > last_coma:
                # Formato americano: $300,000.00 - punto es decimal, coma es miles
                monto_str = monto_str.replace(',', '')
            else:
                # Formato europeo: $28.250,00 - coma es decimal, punto es miles
                monto_str = monto_str.replace('.', '').replace(',', '.')
        elif num_comas == 1 and num_puntos == 0:
            # Formato: $700,000 (coma como separador de miles, sin decimales)
            monto_str = monto_str.replace(',', '')
        elif num_comas > 1:
            # Formato: $1,000,000 (comas como separadores de miles)
            monto_str = monto_str.replace(',', '')
        elif num_puntos > 1:
            # Formato: $1.800.000 (puntos como separadores de miles)
            monto_str = monto_str.replace('.', '')
        elif num_puntos == 1 and num_comas == 0:
            # Formato: $300.00 o $300000.00 - punto es decimal
            # No hacer nada, float() lo maneja
            pass
        else:
            # Sin separadores, número limpio
            pass

        monto = float(monto_str)
        print(f"DEBUG - Monto convertido: {monto}")

        # Descripción - extraer el comercio o destinatario
        descripcion = ""

        # Patrón mejorado: captura comercio con caracteres especiales (NAME-CHEAP.COM*, etc)
        comercio_match = re.search(r'(?:en|a)\s+([A-Z0-9\s\-\.\_\*]+?)(?:\s+con|\s+el|\s*,)', text, re.IGNORECASE)
        if comercio_match:
            comercio = comercio_match.group(1).strip().rstrip('*')
            descripcion = f"{tipo_desc} en {comercio}"
        else:
            descripcion = tipo_desc

        # Fecha - buscar patrón DD/MM/YYYY a las HH:MM
        fecha_match = re.search(r'el\s+(\d{2}/\d{2}/\d{4})\s+a\s+las\s+(\d{2}:\d{2})', text)
        if fecha_match:
            fecha = f"{fecha_match.group(1)} {fecha_match.group(2)}:00"
        else:
            # Si no encuentra fecha, usar la actual
            fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # Cuenta - usar solo el nombre del banco preestablecido
        cuenta = "Bancolombia"

        return {
            "tipo": tipo,
            "monto": monto,
            "descripcion": descripcion,
            "fecha": fecha,
            "cuenta": cuenta,
            "categoria": clasificar_categoria(descripcion, tipo),
            "entidad": "DT Growth Partners"
        }

    except Exception as e:
        print(f"Error extrayendo datos: {e}")
        return None

def clasificar_categoria(descripcion, tipo="saliente"):
    """
    Clasifica automáticamente la categoría según la descripción,
    usando las categorías válidas de Google Sheets.
    """
    desc_lower = descripcion.lower()

    # Obtener categorías válidas desde Google Sheets
    if tipo == "entrante":
        categorias_validas = obtener_categorias_sheets("entradas")
    else:
        categorias_validas = obtener_categorias_sheets("salidas")

    # Convertir a minúsculas para comparación
    categorias_lower = {cat.lower(): cat for cat in categorias_validas}

    # Intentar mapear según palabras clave
    mapeo_keywords = {
        'rappi': ['almuerzos', 'meriendas'],
        'uber eats': ['almuerzos', 'meriendas'],
        'domicilio': ['almuerzos', 'meriendas'],
        'restaurante': ['almuerzos'],
        'comida': ['almuerzos'],
        'almuerzo': ['almuerzos'],
        'merienda': ['meriendas'],
        'uber': ['transportes - gasolina', 'transportes'],
        'taxi': ['transportes - gasolina', 'transportes'],
        'transporte': ['transportes - gasolina', 'transportes'],
        'gasolina': ['transportes - gasolina'],
        'publicidad': ['publicidad'],
        'meta': ['publicidad'],
        'facebook': ['publicidad'],
        'google ads': ['publicidad'],
        'marketing': ['publicidad'],
        'nequi': ['traslado de nequi'],
        'daviplata': ['traslado de daviplata'],
        'bancolombia': ['traslado de bancolombia'],
        'rappicuenta': ['traslado de rappicuenta'],
        'transferencia': ['traslado de bancolombia', 'traslado de nequi'],
        'servidor': ['servidores/hosting/dominios'],
        'hosting': ['servidores/hosting/dominios'],
        'dominio': ['servidores/hosting/dominios'],
        'namecheap': ['servidores/hosting/dominios'],
        'name-cheap': ['servidores/hosting/dominios'],
        'godaddy': ['servidores/hosting/dominios'],
        'cloudflare': ['servidores/hosting/dominios'],
        'digitalocean': ['servidores/hosting/dominios'],
        'aws': ['servidores/hosting/dominios'],
        'amazon web': ['servidores/hosting/dominios'],
        'azure': ['servidores/hosting/dominios'],
        'siteground': ['servidores/hosting/dominios'],
        'hostinger': ['servidores/hosting/dominios'],
        'vercel': ['servidores/hosting/dominios'],
        'netlify': ['servidores/hosting/dominios'],
        'render': ['servidores/hosting/dominios'],
        'claude': ['herramientas (claude, gpt, lovable, twilio, etc)'],
        'gpt': ['herramientas (claude, gpt, lovable, twilio, etc)'],
        'openai': ['herramientas (claude, gpt, lovable, twilio, etc)'],
        'lovable': ['herramientas (claude, gpt, lovable, twilio, etc)'],
        'twilio': ['herramientas (claude, gpt, lovable, twilio, etc)'],
        'freelancer': ['freelancers'],
        'contador': ['honorarios contador'],
        'arriendo': ['arriendo'],
        'nomina': ['nómina (stiven)', 'nómina (dairo)', 'nómina (edgardo)'],
        'pago cliente': ['pago de cliente'],
        'cliente': ['pago de cliente'],
    }

    # Buscar coincidencia de keywords
    for keyword, posibles_categorias in mapeo_keywords.items():
        if keyword in desc_lower:
            for posible in posibles_categorias:
                if posible in categorias_lower:
                    return categorias_lower[posible]

    # Si no hay coincidencia, buscar categorías que contengan palabras de la descripción
    for cat_lower, cat_original in categorias_lower.items():
        for palabra in desc_lower.split():
            if len(palabra) > 3 and palabra in cat_lower:
                return cat_original

    # Si es transferencia bancaria, usar categoría de traslado según el banco
    if 'nequi' in desc_lower and 'traslado de nequi' in categorias_lower:
        return categorias_lower['traslado de nequi']
    if 'daviplata' in desc_lower and 'traslado de daviplata' in categorias_lower:
        return categorias_lower['traslado de daviplata']
    if 'bancolombia' in desc_lower and 'traslado de bancolombia' in categorias_lower:
        return categorias_lower['traslado de bancolombia']

    # Retornar la primera categoría disponible o un valor por defecto
    if categorias_validas:
        # Buscar una categoría genérica como "Otros" o "Ajuste saldo"
        for cat in categorias_validas:
            if 'ajuste' in cat.lower() or 'otro' in cat.lower():
                return cat
        return categorias_validas[0]

    return "Sin categoría"

def insertar_en_fila_2(sheet_name, valores):
    """
    Inserta una nueva fila en la posición 2 (después del encabezado)
    empujando las filas existentes hacia abajo.
    """
    try:
        # Paso 1: Obtener el sheetId numérico
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID
        ).execute()

        target_sheet = None
        for sheet in spreadsheet.get("sheets", []):
            if sheet.get("properties", {}).get("title") == sheet_name:
                target_sheet = sheet
                break

        if not target_sheet:
            print(f"❌ No se encontró la hoja '{sheet_name}'")
            return False

        sheet_id = target_sheet["properties"]["sheetId"]

        # Paso 2: Insertar fila vacía en posición 2 (índice 1)
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "insertDimension": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "ROWS",
                                "startIndex": 1,
                                "endIndex": 2
                            },
                            "inheritFromBefore": False
                        }
                    }
                ]
            }
        ).execute()

        # Paso 3: Escribir los datos en la fila 2
        sheets_service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A2:G2",
            valueInputOption="USER_ENTERED",
            body={"values": [valores]}
        ).execute()

        print(f"✅ Registro insertado en fila 2 de '{sheet_name}'")
        return True

    except Exception as e:
        print(f"❌ Error insertando en fila 2: {e}")
        return False


def registrar_en_sheets(data):
    """
    Registra la transacción en Google Sheets (insertando en fila 2)
    """
    try:
        sheet_name = "Entradas" if data["tipo"] == "entrante" else "Salidas"

        # Tercero por defecto para transacciones de email
        tercero = data.get("tercero", "tercero")

        valores = [
            data["fecha"],
            int(data['monto']),  # Número entero sin signo peso
            data["descripcion"],
            data["categoria"],
            data["cuenta"],
            data["entidad"],
            tercero  # Columna G - Tercero
        ]

        if insertar_en_fila_2(sheet_name, valores):
            print(f"✅ Registrado en Sheets: {data['descripcion']} - ${data['monto']}")
            return True
        return False

    except Exception as e:
        print(f"❌ Error registrando en Sheets: {e}")
        return False

def notificar_slack(data):
    """
    Notifica en Slack solo las salidas
    """
    if data["tipo"] != "saliente":
        return

    try:
        mensaje = f"💸 *Nueva salida detectada*\n\n"
        mensaje += f"*Importe:* ${data['monto']:,.0f} COP\n".replace(",", ".")
        mensaje += f"*Descripción:* {data['descripcion']}\n"
        mensaje += f"*Categoría:* {data['categoria']}\n"
        mensaje += f"*Cuenta:* {data['cuenta']}\n"
        mensaje += f"*Fecha:* {data['fecha']}\n"
        mensaje += f"*Entidad:* {data['entidad']}"

        if SLACK_WEBHOOK_URL:
            response = requests.post(
                SLACK_WEBHOOK_URL,
                json={"text": mensaje},
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                print(f"✅ Notificado en Slack: {data['descripcion']}")
            else:
                print(f"❌ Error notificando en Slack: {response.status_code}")

    except Exception as e:
        print(f"❌ Error en notificación Slack: {e}")

def notificar_whatsapp(data):
    """
    Escribe la transacción en una cola JSON para que María (WhatsApp) la notifique.
    Solo escribe salidas (gastos).
    """
    if data["tipo"] != "saliente":
        return

    try:
        transaccion = {
            "tipo": data["tipo"],
            "monto": data["monto"],
            "descripcion": data["descripcion"],
            "categoria": data["categoria"],
            "cuenta": data["cuenta"],
            "fecha": data["fecha"],
            "entidad": data["entidad"],
            "timestamp": datetime.now().isoformat(),
            "notificado": False
        }

        # Leer cola existente o crear lista vacía
        cola = []
        if os.path.exists(WHATSAPP_QUEUE_FILE):
            try:
                with open(WHATSAPP_QUEUE_FILE, "r", encoding="utf-8") as f:
                    cola = json.load(f)
            except (json.JSONDecodeError, ValueError):
                cola = []

        cola.append(transaccion)

        with open(WHATSAPP_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(cola, f, ensure_ascii=False, indent=2)

        print(f"✅ Cola WhatsApp: {data['descripcion']} - ${data['monto']:,.0f}".replace(",", "."))

    except Exception as e:
        print(f"❌ Error escribiendo cola WhatsApp: {e}")

def procesar_correos():
    """
    Conecta al servidor IMAP y procesa correos no leídos de Bancolombia
    """
    try:
        # Conectar al servidor IMAP
        print(f"Conectando a {IMAP_SERVER}:{IMAP_PORT}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        print("✅ Conectado al servidor de correo")

        # Seleccionar bandeja de entrada
        mail.select("INBOX")

        # Buscar correos no leídos con asunto "Alertas y Notificaciones" (incluye reenviados)
        status, messages = mail.search(None, '(UNSEEN SUBJECT "Alertas y Notificaciones")')

        if status != "OK":
            print("❌ Error buscando correos")
            return

        email_ids = messages[0].split()

        if not email_ids:
            print("📭 No hay correos nuevos de Bancolombia")
            return

        print(f"📧 Procesando {len(email_ids)} correos nuevos...")

        for email_id in email_ids:
            try:
                # Obtener el correo
                status, msg_data = mail.fetch(email_id, "(RFC822)")

                if status != "OK":
                    continue

                # Parsear el correo
                msg = email.message_from_bytes(msg_data[0][1])

                # Extraer el cuerpo del correo
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                        elif part.get_content_type() == "text/html":
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                # Extraer datos de la transacción
                data = extract_transaction_data(body)

                if data:
                    # Registrar en Google Sheets
                    if registrar_en_sheets(data):
                        # Notificar en Slack solo si es salida
                        notificar_slack(data)
                        # Escribir en cola WhatsApp para María
                        notificar_whatsapp(data)
                else:
                    print(f"⚠️ No se pudo extraer datos del correo {email_id}")

            except Exception as e:
                print(f"❌ Error procesando correo {email_id}: {e}")
                continue

        # Cerrar conexión
        mail.close()
        mail.logout()
        print("✅ Proceso completado")

    except Exception as e:
        print(f"❌ Error en proceso de correos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import time
    import logging

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('email_monitor.log'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    # ========== LOCK FILE PARA PREVENIR MÚLTIPLES INSTANCIAS ==========
    lock_file = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
    except IOError:
        logger.error("❌ Ya hay una instancia de email_monitor.py corriendo. Saliendo...")
        sys.exit(1)

    logger.info(f"🔒 Lock adquirido (PID: {os.getpid()})")
    # ==================================================================

    # Intervalo de verificación en segundos (cada 2 minutos)
    CHECK_INTERVAL = 120

    # Contador para garbage collection periódico
    gc_counter = 0

    logger.info("🚀 Iniciando monitor de correos en modo continuo...")

    try:
        while True:
            try:
                logger.info(f"🔄 Verificando correos - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                procesar_correos()
            except Exception as e:
                logger.error(f"❌ Error en ciclo principal: {e}")

            # Ejecutar garbage collection cada 10 ciclos para liberar memoria
            gc_counter += 1
            if gc_counter >= 10:
                gc.collect()
                gc_counter = 0
                logger.info("🧹 Garbage collection ejecutado")

            logger.info(f"💤 Esperando {CHECK_INTERVAL} segundos para próxima verificación...")
            time.sleep(CHECK_INTERVAL)
    finally:
        # Liberar lock al terminar
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        logger.info("🔓 Lock liberado")
