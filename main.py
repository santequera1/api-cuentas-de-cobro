import os
from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from generador import generar_cuenta_de_cobro
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
import json
import logging
import traceback

logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Cuentas de Cobro",
    description="Una API para generar cuentas de cobro en formato PDF y registrar transacciones.",
    version="4.0.0"
)

# --- Configuración de Google Sheets ---
SPREADSHEET_ID = "1SKHZBmxEsZgKjoEx_p5QtyOy21Z0o9twIsWWlICmuzE"
SERVICE_ACCOUNT_FILE = "credentials.json"
SCOPES_SHEETS = ["https://www.googleapis.com/auth/spreadsheets"]
TRANSACCIONES_PENDIENTES_FILE = "transacciones_pendientes.json"

try:
    creds_sheets = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES_SHEETS
    )
    sheets_service = build("sheets", "v4", credentials=creds_sheets)
    logger.info("Google Sheets conectado para API")
except Exception as e:
    logger.warning(f"Google Sheets no disponible: {e}")
    sheets_service = None


def insertar_en_fila_2(sheet_name: str, valores: list) -> bool:
    """Inserta una nueva fila en la posicion 2 (despues del encabezado)."""
    try:
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID
        ).execute()

        target_sheet = None
        for sheet in spreadsheet.get("sheets", []):
            if sheet.get("properties", {}).get("title") == sheet_name:
                target_sheet = sheet
                break

        if not target_sheet:
            logger.error(f"No se encontro la hoja '{sheet_name}'")
            return False

        sheet_id = target_sheet["properties"]["sheetId"]

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

        sheets_service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A2:G2",
            valueInputOption="USER_ENTERED",
            body={"values": [valores]}
        ).execute()

        logger.info(f"Registro insertado en fila 2 de '{sheet_name}'")
        return True

    except Exception as e:
        logger.error(f"Error insertando en fila 2: {e}")
        logger.error(traceback.format_exc())
        return False


def agregar_transaccion_pendiente(transaccion: dict):
    """Agrega una transaccion al archivo de pendientes para notificacion WhatsApp."""
    try:
        pendientes = []
        if os.path.exists(TRANSACCIONES_PENDIENTES_FILE):
            with open(TRANSACCIONES_PENDIENTES_FILE, "r", encoding="utf-8") as f:
                pendientes = json.load(f)

        pendientes.append({
            **transaccion,
            "notificado": False
        })

        with open(TRANSACCIONES_PENDIENTES_FILE, "w", encoding="utf-8") as f:
            json.dump(pendientes, f, indent=2, ensure_ascii=False)

        logger.info("Transaccion pendiente agregada para notificacion")
    except Exception as e:
        logger.error(f"Error guardando transaccion pendiente: {e}")

class Servicio(BaseModel):
    descripcion: str = Field(..., example="Desarrollo de landing page")
    cantidad: int = Field(..., example=1)
    precio_unitario: float = Field(..., example=500000)

class SolicitudCuenta(BaseModel):
    nickname_cliente: str = Field(..., example="experiencia_cartagena")
    valor: float = Field(..., example=2000000)
    servicios: List[Servicio]
    concepto: str = Field(..., example="Facturación de servicios de marketing")
    observaciones: str = Field("", example="Pago correspondiente al mes de Noviembre.")
    fecha: str = Field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y"))
    servicio_proyecto: str = Field("", example="Desarrollo Web, Marketing Digital")

def get_client_data_local(nickname: str):
    try:
        with open("clientes.json", "r", encoding="utf-8") as f:
            clientes = json.load(f)
        return clientes.get(nickname)
    except FileNotFoundError:
        return None

@app.post("/crear-cuenta/", summary="Crear una nueva cuenta de cobro")
async def crear_cuenta(solicitud: SolicitudCuenta):
    """
    Genera una cuenta de cobro para un cliente específico.
    """
    try:
        cliente_data = get_client_data_local(solicitud.nickname_cliente)
        
        if not cliente_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Cliente con nickname '{solicitud.nickname_cliente}' no encontrado."
            )

        servicios_dict = [s.dict() for s in solicitud.servicios]

        ruta_archivo_generado = generar_cuenta_de_cobro(
            nombre_cliente=cliente_data['nombre_completo'],
            identificacion=cliente_data['nit'],
            servicios=servicios_dict,
            observaciones=solicitud.observaciones,
            concepto=solicitud.concepto,
            fecha=solicitud.fecha,
            servicio_proyecto=solicitud.servicio_proyecto if solicitud.servicio_proyecto else None
        )

        if not os.path.exists(ruta_archivo_generado):
            raise HTTPException(status_code=500, detail="Error: el archivo PDF no pudo ser creado.")

        return FileResponse(
            path=ruta_archivo_generado, 
            media_type='application/pdf',
            filename=os.path.basename(ruta_archivo_generado)
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocurrió un error inesperado: {e}")

@app.get("/")
def read_root():
    return {"mensaje": "Bienvenido a la API de Cuentas de Cobro. Dirígete a /docs para ver la documentación."}


# ============== TRANSACCIONES ==============

class Transaccion(BaseModel):
    tipo: Literal["entrante", "saliente"] = Field(..., example="saliente")
    importe: float = Field(..., example=150000)
    descripcion: str = Field(..., example="Pago proveedor diseño")
    categoria: str = Field("", example="Freelancers")
    cuenta: str = Field("Bancolombia", example="Bancolombia")
    entidad: Literal["DT Growth Partners", "Dairo T"] = Field("DT Growth Partners", example="DT Growth Partners")
    tercero: str = Field("tercero", example="Juan Perez")
    fecha: Optional[str] = Field(None, example="18/03/2026 10:30:00")


@app.post("/api/webhook/bot/sheets/gastos", summary="Registrar una transaccion (entrada o salida)")
async def registrar_transaccion(data: Transaccion):
    """
    Registra una transaccion en Google Sheets (hoja Entradas o Salidas)
    y la agrega al archivo de transacciones pendientes para notificacion WhatsApp.
    """
    if not sheets_service:
        raise HTTPException(status_code=503, detail="Google Sheets no esta configurado")

    fecha = data.fecha or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    sheet_name = "Entradas" if data.tipo == "entrante" else "Salidas"

    valores = [
        fecha,
        int(data.importe),
        data.descripcion,
        data.categoria,
        data.cuenta,
        data.entidad,
        data.tercero
    ]

    if not insertar_en_fila_2(sheet_name, valores):
        raise HTTPException(status_code=500, detail="Error al insertar en Google Sheets")

    # Agregar a transacciones pendientes para WhatsApp
    agregar_transaccion_pendiente({
        "tipo": data.tipo,
        "fecha": fecha,
        "importe": data.importe,
        "descripcion": data.descripcion,
        "categoria": data.categoria,
        "cuenta": data.cuenta,
        "entidad": data.entidad,
        "tercero": data.tercero
    })

    return {
        "status": "ok",
        "hoja": sheet_name,
        "mensaje": f"Transaccion registrada en {sheet_name}",
        "datos": {
            "fecha": fecha,
            "importe": int(data.importe),
            "descripcion": data.descripcion,
            "categoria": data.categoria,
            "cuenta": data.cuenta,
            "entidad": data.entidad,
            "tercero": data.tercero
        }
    }


class EditarTransaccion(BaseModel):
    # Campos de búsqueda (requeridos)
    fecha: str = Field(..., example="19/03/2026", description="Fecha de la transaccion (DD/MM/YYYY o YYYY-MM-DD)")
    importe: float = Field(..., example=59800, description="Monto exacto para identificar la fila")
    descripcion: str = Field("", example="Compra en RAPPI COLOMBIA*DL", description="Descripcion exacta (para desambiguar si hay varias coincidencias)")

    # Campos editables (al menos uno requerido)
    categoria: Optional[str] = Field(None, example="Nomina (Dairo)")
    entidad: Optional[str] = Field(None, example="Dairo Alberto Traslaviña Torres")
    descripcion_nueva: Optional[str] = Field(None, example="Pago nomina Dairo marzo")
    cuenta: Optional[str] = Field(None, example="Bancolombia")
    tipo: Optional[Literal["entrante", "saliente"]] = Field(None, example="saliente", description="Cambiar entre entrada/salida")
    tercero: Optional[str] = Field(None, example="Juan Perez")


def _normalizar_fecha(fecha_str: str) -> str:
    """Normaliza fecha a DD/MM/YYYY para comparación."""
    fecha_str = fecha_str.strip()
    # Si viene como YYYY-MM-DD
    if len(fecha_str) >= 10 and fecha_str[4] == "-":
        try:
            dt = datetime.strptime(fecha_str[:10], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            pass
    # Si ya viene como DD/MM/YYYY (con o sin hora)
    return fecha_str[:10]


def _buscar_fila(sheet_name: str, fecha: str, importe: float, descripcion: str) -> list:
    """Busca filas en una hoja que coincidan con fecha + importe (+ descripcion).
    Retorna lista de tuplas (row_index, row_data)."""
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A:G"
        ).execute()
        rows = result.get("values", [])
    except Exception as e:
        logger.error(f"Error leyendo hoja {sheet_name}: {e}")
        return []

    fecha_normalizada = _normalizar_fecha(fecha)
    coincidencias = []

    # Fila 0 = encabezado, datos desde fila 1 (row_index 2 en Sheets)
    for i, row in enumerate(rows[1:], start=2):
        if len(row) < 3:
            continue
        # Columna A = fecha, B = importe, C = descripcion
        row_fecha = _normalizar_fecha(str(row[0]))
        try:
            row_importe = float(str(row[1]).replace(",", "").replace("$", "").strip())
        except (ValueError, IndexError):
            continue

        if row_fecha == fecha_normalizada and row_importe == importe:
            coincidencias.append((i, row))

    # Si hay descripcion y múltiples coincidencias, filtrar por descripcion
    if descripcion and len(coincidencias) > 1:
        filtradas = [(i, r) for i, r in coincidencias if len(r) > 2 and r[2].strip().lower() == descripcion.strip().lower()]
        if filtradas:
            coincidencias = filtradas

    return coincidencias


@app.patch("/sheets/transacciones", summary="Editar una transaccion existente buscando por fecha+importe")
async def editar_transaccion_por_busqueda(data: EditarTransaccion):
    """
    Busca una transaccion por fecha + importe (+ descripcion si hay ambigüedad)
    y actualiza solo los campos enviados.
    """
    if not sheets_service:
        raise HTTPException(status_code=503, detail="Google Sheets no esta configurado")

    # Validar que al menos un campo editable fue enviado
    campos_editables = {
        "categoria": data.categoria,
        "entidad": data.entidad,
        "descripcion_nueva": data.descripcion_nueva,
        "cuenta": data.cuenta,
        "tipo": data.tipo,
        "tercero": data.tercero,
    }
    campos_a_editar = {k: v for k, v in campos_editables.items() if v is not None}
    if not campos_a_editar:
        raise HTTPException(status_code=400, detail="Debes enviar al menos un campo a editar (categoria, entidad, descripcion_nueva, cuenta, tipo, tercero)")

    # Buscar en ambas hojas
    coincidencias_entradas = [(i, r, "Entradas") for i, r in _buscar_fila("Entradas", data.fecha, data.importe, data.descripcion)]
    coincidencias_salidas = [(i, r, "Salidas") for i, r in _buscar_fila("Salidas", data.fecha, data.importe, data.descripcion)]
    todas = coincidencias_entradas + coincidencias_salidas

    if not todas:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontro ninguna transaccion con fecha={data.fecha}, importe={data.importe}" +
                   (f", descripcion='{data.descripcion}'" if data.descripcion else "") +
                   ". Verifica los datos e intenta de nuevo."
        )

    if len(todas) > 1:
        opciones = []
        for row_idx, row, hoja in todas:
            opciones.append({
                "hoja": hoja,
                "fila": row_idx,
                "fecha": row[0] if len(row) > 0 else "",
                "importe": row[1] if len(row) > 1 else "",
                "descripcion": row[2] if len(row) > 2 else "",
                "categoria": row[3] if len(row) > 3 else "",
                "cuenta": row[4] if len(row) > 4 else "",
                "entidad": row[5] if len(row) > 5 else "",
                "tercero": row[6] if len(row) > 6 else "",
            })
        raise HTTPException(
            status_code=409,
            detail={
                "mensaje": f"Se encontraron {len(todas)} transacciones que coinciden. Envia la descripcion exacta para desambiguar.",
                "opciones": opciones
            }
        )

    # Exactamente una coincidencia
    row_idx, row_actual, hoja_actual = todas[0]

    # Completar la fila con valores vacíos si tiene menos de 7 columnas
    while len(row_actual) < 7:
        row_actual.append("")

    # Determinar si hay cambio de hoja (tipo)
    hoja_destino = hoja_actual
    if data.tipo:
        nueva_hoja = "Entradas" if data.tipo == "entrante" else "Salidas"
        if nueva_hoja != hoja_actual:
            hoja_destino = nueva_hoja

    # Construir fila actualizada: A=fecha, B=importe, C=descripcion, D=categoria, E=cuenta, F=entidad, G=tercero
    fila_actualizada = [
        row_actual[0],  # fecha (no cambia)
        row_actual[1],  # importe (no cambia)
        data.descripcion_nueva if data.descripcion_nueva is not None else row_actual[2],
        data.categoria if data.categoria is not None else row_actual[3],
        data.cuenta if data.cuenta is not None else row_actual[4],
        data.entidad if data.entidad is not None else row_actual[5],
        data.tercero if data.tercero is not None else row_actual[6],
    ]

    try:
        if hoja_destino != hoja_actual:
            # Mover: borrar de hoja origen e insertar en hoja destino
            # Borrar fila en hoja origen
            spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
            sheet_id_origen = None
            for sheet in spreadsheet.get("sheets", []):
                if sheet["properties"]["title"] == hoja_actual:
                    sheet_id_origen = sheet["properties"]["sheetId"]
                    break

            if sheet_id_origen is not None:
                sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": [{"deleteDimension": {"range": {
                        "sheetId": sheet_id_origen,
                        "dimension": "ROWS",
                        "startIndex": row_idx - 1,
                        "endIndex": row_idx
                    }}}]}
                ).execute()

            # Insertar en hoja destino
            if not insertar_en_fila_2(hoja_destino, fila_actualizada):
                raise HTTPException(status_code=500, detail="Error al mover la transaccion a la nueva hoja")
        else:
            # Actualizar en la misma hoja
            sheets_service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{hoja_actual}!A{row_idx}:G{row_idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [fila_actualizada]}
            ).execute()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editando transaccion: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error al actualizar en Google Sheets: {e}")

    return {
        "success": True,
        "updated": {
            "fecha": fila_actualizada[0],
            "importe": fila_actualizada[1],
            "descripcion": fila_actualizada[2],
            "categoria": fila_actualizada[3],
            "cuenta": fila_actualizada[4],
            "entidad": fila_actualizada[5],
            "tercero": fila_actualizada[6],
            "hoja": hoja_destino
        }
    }
