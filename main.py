import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from generador import generar_cuenta_de_cobro
from google_sheets_client import get_client_data

app = FastAPI(
    title="API de Cuentas de Cobro con Google Sheets",
    description="Una API para generar cuentas de cobro en formato PDF utilizando una hoja de cálculo de Google como base de datos de clientes.",
    version="2.0.0"
)

class SolicitudCuenta(BaseModel):
    # El 'nickname' debe corresponder a un valor de la primera columna de tu Google Sheet
    nickname_cliente: str = Field(..., example="acbfit", description="El apodo único del cliente (de la columna A en Google Sheets).")
    valor: float = Field(..., gt=0, example=150000.50)
    concepto: str = Field(..., max_length=200, example="Desarrollo de landing page")

@app.post("/crear-cuenta/", summary="Crear una nueva cuenta de cobro desde Google Sheets")
async def crear_cuenta(solicitud: SolicitudCuenta):
    """
    Genera una cuenta de cobro para un cliente específico almacenado en Google Sheets.

    - **nickname_cliente**: El identificador único del cliente (de la primera columna de la hoja).
    - **valor**: El monto a cobrar.
    - **concepto**: La descripción del servicio.
    """
    try:
        # 1. Obtener los datos del cliente desde Google Sheets
        cliente_data = get_client_data(solicitud.nickname_cliente)
        
        if not cliente_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Cliente con nickname '{solicitud.nickname_cliente}' no encontrado en Google Sheets."
            )

        # 2. Generar el PDF con los datos obtenidos
        ruta_archivo_generado = generar_cuenta_de_cobro(
            nombre_cliente=cliente_data['nombre_completo'],
            identificacion=cliente_data['nit'],
            valor=solicitud.valor,
            concepto=solicitud.concepto
        )

        if not os.path.exists(ruta_archivo_generado):
            raise HTTPException(status_code=500, detail="Error interno del servidor: el archivo PDF no pudo ser creado.")

        # 3. Devolver el archivo PDF
        return FileResponse(
            path=ruta_archivo_generado, 
            media_type='application/pdf',
            filename=os.path.basename(ruta_archivo_generado)
        )
    except HTTPException as http_exc:
        # Re-lanzar las excepciones HTTP para que FastAPI las maneje
        raise http_exc
    except Exception as e:
        # Capturar cualquier otro error inesperado
        raise HTTPException(status_code=500, detail=f"Ocurrió un error inesperado: {e}")

@app.get("/")
def read_root():
    return {"mensaje": "Bienvenido a la API de Cuentas de Cobro. Dirígete a /docs para ver la documentación."}
