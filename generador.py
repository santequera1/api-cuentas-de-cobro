import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from datetime import datetime

def generar_cuenta_de_cobro(nombre_cliente: str, identificacion: str, valor: float, concepto: str) -> str:
    """
    Genera una cuenta de cobro en formato PDF.

    Args:
        nombre_cliente: El nombre del cliente.
        identificacion: La identificación del cliente.
        valor: El valor a cobrar.
        concepto: El concepto de la cuenta de cobro.

    Returns:
        La ruta del archivo PDF generado.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # --- DATOS DEL EMISOR ---
    emisor_nombre = "Dairo Traslaviña"
    emisor_cedula = "1143397563"
    emisor_telefono = "3007189383"
    emisor_email = "Dairo@dtgrowthpartners.com"
    emisor_ciudad = "Cartagena, Colombia"
    cuenta_bancolombia = "78841707710"
    nequi = "3007189383"

    # --- REGISTRAR FUENTES ---
    fuentes_dir = os.path.join(script_dir, 'fuentes')
    if os.path.isdir(fuentes_dir):
        mapa_fuentes = {'HN-Normal': 'HelveticaNeueLight.ttf', 'HN-Bold': 'HelveticaNeueBold.ttf', 'HN-Italic': 'HelveticaNeueItalic.ttf'}
        for nombre, archivo in mapa_fuentes.items():
            ruta_fuente = os.path.join(fuentes_dir, archivo)
            if os.path.exists(ruta_fuente):
                pdfmetrics.registerFont(TTFont(nombre, ruta_fuente))
        pdfmetrics.registerFontFamily('HelveticaNeue', normal='HN-Normal', bold='HN-Bold', italic='HN-Italic')

    # --- RUTA IMAGEN BASE ---
    archivo_base = None
    for nombre in ["base.jpg", "base.png"]:
        path_completo = os.path.join(script_dir, nombre)
        if os.path.exists(path_completo):
            archivo_base = path_completo
            break

    # --- GENERACIÓN DEL PDF ---
    numero_cuenta = datetime.now().strftime("%Y%m%d%H%M%S")
    nombre_archivo = f"cuenta_cobro_{nombre_cliente.replace(' ', '_')}_{numero_cuenta}.pdf"
    ruta_salida = os.path.join(script_dir, nombre_archivo)

    c = canvas.Canvas(ruta_salida, pagesize=letter)
    width, height = letter

    if archivo_base:
        c.drawImage(archivo_base, 0, 0, width=width, height=height, preserveAspectRatio=False)

    margen_izquierdo = 40
    c.setFont("HN-Normal", 22)
    c.setFillColor(colors.HexColor("#304a7c"))
    c.drawCentredString(width / 2.0, height - 120, f"CUENTA DE COBRO N.° {numero_cuenta}")

    y = height - 160
    c.setFont("HN-Normal", 9)
    c.setFillColor(colors.HexColor("#0070c0"))
    c.drawString(margen_izquierdo, y, emisor_telefono)
    y -= 12
    c.drawString(margen_izquierdo, y, emisor_email)
    y -= 12
    c.drawString(margen_izquierdo, y, emisor_ciudad)

    y -= 24
    c.setFont("HN-Bold", 9)
    c.setFillColor(colors.black)
    c.drawString(margen_izquierdo, y, "Cliente:")
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo + 43, y, nombre_cliente)
    y -= 12
    c.setFont("HN-Bold", 9)
    c.drawString(margen_izquierdo, y, "Identificación:")
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo + 70, y, identificacion)
    y -= 12
    c.setFont("HN-Bold", 9)
    c.drawString(margen_izquierdo, y, "Fecha:")
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo + 36, y, datetime.now().strftime("%d/%m/%Y"))

    y -= 24
    c.setFont("HN-Bold", 9)
    c.drawString(margen_izquierdo, y, "Concepto:")
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo + 63, y, concepto)

    # --- TABLA DE SERVICIOS ---
    servicios = [{'descripcion': concepto, 'cantidad': 1, 'precio_unitario': valor}]
    col_widths = [280, 60, 100, 100]
    row_height = 20
    table_y_start = height - 330
    header_color = colors.Color(red=47/255, green=84/255, blue=150/255)

    c.setFillColor(header_color)
    c.rect(margen_izquierdo, table_y_start, sum(col_widths), row_height, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("HN-Bold", 9)
    headers = ["Descripción", "Cantidad", "Precio unitario", "Importe"]
    for i, header in enumerate(headers):
        c.drawCentredString(margen_izquierdo + sum(col_widths[:i]) + col_widths[i]/2, table_y_start + 6, header)
    
    current_y, total = table_y_start, 0
    c.setFont("HN-Normal", 9)
    c.setFillColor(colors.black)
    for servicio in servicios:
        current_y -= row_height
        importe = servicio['cantidad'] * servicio['precio_unitario']
        total += importe
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.grid([margen_izquierdo, margen_izquierdo + col_widths[0], margen_izquierdo + sum(col_widths[:2]), margen_izquierdo + sum(col_widths[:3]), margen_izquierdo + sum(col_widths)], [current_y, current_y + row_height])
        c.drawString(margen_izquierdo + 5, current_y + 6, servicio['descripcion'][:50])
        c.drawCentredString(margen_izquierdo + col_widths[0] + col_widths[1]/2, current_y + 6, str(servicio['cantidad']))
        c.drawRightString(margen_izquierdo + sum(col_widths[:3]) - 10, current_y + 6, f"$ {servicio['precio_unitario']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c.drawRightString(margen_izquierdo + sum(col_widths) - 10, current_y + 6, f"$ {importe:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    current_y -= row_height
    c.grid([margen_izquierdo, margen_izquierdo + sum(col_widths)], [current_y, current_y + row_height])
    c.drawString(margen_izquierdo + 5, current_y + 6, "No responsable de IVA")
    c.setFont("HN-Bold", 10)
    c.drawString(margen_izquierdo + col_widths[0] + col_widths[1] + 10, current_y + 6, "Total")
    c.drawString(margen_izquierdo + sum(col_widths[:3]) + 10, current_y + 6, f"$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    y = current_y - 20

    # --- INFORMACIÓN DE PAGO ---
    c.setFont("HN-Bold", 9)
    c.drawString(margen_izquierdo, y, "Páguese a:")
    y -= 12
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo, y, f"Nombre: {emisor_nombre}")
    y -= 12
    c.drawString(margen_izquierdo, y, f"Cédula: {emisor_cedula}")
    y -= 12
    c.drawString(margen_izquierdo, y, f"Cuenta de ahorros Bancolombia: {cuenta_bancolombia}")
    y -= 12
    c.drawString(margen_izquierdo, y, f"Nequi: {nequi}")
    
    y -= 36
    c.drawString(margen_izquierdo, y, "Atentamente,")
    y -= 48
    c.drawString(margen_izquierdo, y, emisor_nombre)

    c.save()
    return ruta_salida
