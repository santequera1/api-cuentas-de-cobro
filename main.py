import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from generador import generar_cuenta_de_cobro

app = FastAPI(
    title="API de Cuentas de Cobro",
    description="Una API para generar cuentas de cobro en formato PDF.",
    version="1.0.0"
)

class DatosCliente(BaseModel):
    nombre: str = Field(..., example="Pepito Perez")
    identificacion: str = Field(..., example="123456789")
    valor: float = Field(..., gt=0, example=150000.50)
    concepto: str = Field(..., max_length=200, example="Desarrollo de landing page")

@app.post("/crear-cuenta/", summary="Crear una nueva cuenta de cobro")
async def crear_cuenta(cliente: DatosCliente):
    """
    Recibe los datos de un cliente en formato JSON, genera una cuenta de cobro en formato PDF y la devuelve para su descarga.
    """
    try:
        ruta_archivo_generado = generar_cuenta_de_cobro(
            nombre_cliente=cliente.nombre,
            identificacion=cliente.identificacion,
            valor=cliente.valor,
            concepto=cliente.concepto
        )

        if not os.path.exists(ruta_archivo_generado):
            raise HTTPException(status_code=500, detail="Error interno del servidor: el archivo no pudo ser creado.")

        return FileResponse(
            path=ruta_archivo_generado, 
            media_type='application/pdf',
            filename=os.path.basename(ruta_archivo_generado)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocurrió un error inesperado: {e}")
