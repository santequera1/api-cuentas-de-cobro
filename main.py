import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List
from generador import generar_cuenta_de_cobro

app = FastAPI(
    title="API de Cuentas de Cobro",
    description="Una API para generar cuentas de cobro en formato PDF con múltiples ítems.",
    version="2.0.0"
)

class Servicio(BaseModel):
    descripcion: str = Field(..., example="Servicio de diseño web")
    cantidad: int = Field(..., gt=0, example=1)
    precio_unitario: float = Field(..., gt=0, example=1200000.0)

class DatosFactura(BaseModel):
    nombre: str = Field(..., example="Pepito Perez")
    identificacion: str = Field(..., example="123456789")
    servicios: List[Servicio]

@app.post("/crear-cuenta/", summary="Crear una nueva cuenta de cobro con múltiples ítems")
async def crear_cuenta(factura: DatosFactura):
    """
    Recibe los datos de una factura en formato JSON, incluyendo una lista de servicios,
    genera una cuenta de cobro en PDF y la devuelve para su descarga.
    """
    try:
        # Convertir la lista de objetos Pydantic a una lista de diccionarios
        servicios_dict = [servicio.dict() for servicio in factura.servicios]

        ruta_archivo_generado = generar_cuenta_de_cobro(
            nombre_cliente=factura.nombre,
            identificacion=factura.identificacion,
            servicios=servicios_dict
        )

        if not os.path.exists(ruta_archivo_generado):
            raise HTTPException(status_code=500, detail="Error interno del servidor: el archivo no pudo ser creado.")

        return FileResponse(
            path=ruta_archivo_generado, 
            media_type='application/pdf',
            filename=os.path.basename(ruta_archivo_generado)
        )
    except Exception as e:
        # Log del error para depuración
        print(f"Error inesperado: {e}")
        raise HTTPException(status_code=500, detail=f"Ocurrió un error inesperado: {e}")
