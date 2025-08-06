import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# --- CONFIGURACIÓN ---
# Define los 'scopes' (permisos) que necesitará la aplicación.
# En este caso, acceso de solo lectura a las hojas de cálculo y a Google Drive.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

# Ruta al archivo de credenciales JSON que obtendrás de Google Cloud.
# Asegúrate de que este archivo esté en el mismo directorio que tus scripts.
SERVICE_ACCOUNT_FILE = 'credentials.json'

# URL de tu hoja de cálculo de Google.
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1W5G4BTqu6gW5_Rc-vK7LrVHdyfdNcMQqJjC3iFQXZLU/edit?usp=sharing"

def get_client_data(client_nickname: str) -> dict:
    """
    Busca los datos de un cliente en la hoja de cálculo de Google por su nickname.

    Args:
        client_nickname: El apodo del cliente (valor en la primera columna).

    Returns:
        Un diccionario con 'nombre_completo' y 'nit' si se encuentra el cliente,
        o None si no se encuentra.
    """
    try:
        # Autenticación con la cuenta de servicio
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)

        # Abrir la hoja de cálculo por URL y seleccionar la primera hoja
        spreadsheet = client.open_by_url(SPREADSHEET_URL)
        sheet = spreadsheet.sheet1

        # Obtener todos los datos y convertirlos a un DataFrame de pandas
        # get_all_records() usa la primera fila como encabezados
        data = sheet.get_all_records()
        if not data:
            print("No se encontraron datos en la hoja de cálculo.")
            return None
            
        df = pd.DataFrame(data)

        # La primera columna en tu sheet se llama 'ID'. La usamos como índice.
        df.set_index('ID', inplace=True)
        
        # Convertimos el índice a string para asegurar la coincidencia
        df.index = df.index.astype(str)

        if client_nickname in df.index:
            client_info = df.loc[client_nickname]
            # **CORRECCIÓN AQUÍ:** Usamos los nombres exactos de las columnas de tu Sheet.
            return {
                "nombre_completo": client_info['Nombre completo'],
                "nit": str(client_info['NIT']) # Convertimos el NIT a string por si acaso
            }
        else:
            print(f"Nickname '{client_nickname}' no encontrado en el índice del DataFrame.")
            print(f"Índices disponibles: {df.index.tolist()}")
            return None
            
    except FileNotFoundError:
        print(f"Error: El archivo de credenciales '{SERVICE_ACCOUNT_FILE}' no se encontró.")
        return None
    except gspread.exceptions.SpreadsheetNotFound:
        print("Error: No se pudo encontrar la hoja de cálculo. Revisa la URL y los permisos de 'Compartir'.")
        return None
    except KeyError as e:
        print(f"Error de clave: No se pudo encontrar la columna {e}. Revisa que los nombres de las columnas en tu Sheet ('ID', 'Nombre completo', 'NIT') sean correctos.")
        return None
    except Exception as e:
        print(f"Ha ocurrido un error inesperado al conectar con Google Sheets: {e}")
        return None
