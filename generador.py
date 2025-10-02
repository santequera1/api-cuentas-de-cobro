import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generar_propuesta(contenido: str) -> str:
    """
    Genera una propuesta en formato PDF.

    Args:
        contenido: El contenido de la propuesta.

    Returns:
        La ruta del archivo PDF generado.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # --- DATOS DEL EMISOR ---
    emisor_nombre = "Dairo Traslaviña"
    emisor_telefono = "+57 3007189383"
    emisor_email = "Dairo@dtgrowthpartners.com"
    emisor_ciudad = "Cartagena, Colombia"

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
    nombre_archivo = "propuesta_CartagenaExperience.pdf"
    ruta_salida = os.path.join(script_dir, nombre_archivo)

    doc = SimpleDocTemplate(ruta_salida, pagesize=letter)
    width, height = letter

    def on_first_page(canvas, doc):
        if archivo_base:
            canvas.drawImage(archivo_base, 0, 0, width=width, height=height, preserveAspectRatio=False)
        canvas.saveState()
        # Footer
        canvas.setFont('HN-Normal', 9)
        canvas.drawString(letter[0]/2, 40, f"{emisor_nombre} | {emisor_email} | {emisor_telefono}")
        canvas.restoreState()

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=4)) # 4 = Justify
    styles.add(ParagraphStyle(name='Bold', fontName='HN-Bold'))

    styles.add(ParagraphStyle(name='MyTitle', fontName='HN-Bold', fontSize=18, alignment=1, spaceAfter=20, leading=22))

    story = []
    
    # Add a spacer to move the content down
    story.append(Spacer(1, 100))

    contenido_split = contenido.split('\n')
    titulo = contenido_split[0]
    cuerpo = '\n'.join(contenido_split[1:])

    story.append(Paragraph(titulo, styles['MyTitle']))

    reducir_interlineado = False
    for line in cuerpo.split('\n'):
        if "2. Propuesta de Servicios" in line:
            reducir_interlineado = True
        if line.startswith('**') and line.endswith('**'):
            line = f"<b>{line.strip('**')}</b>"
        story.append(Paragraph(line, styles['Justify']))
        if reducir_interlineado:
            story.append(Spacer(1, 6))
        else:
            story.append(Spacer(1, 12))

    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_first_page)
    return ruta_salida

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
    emisor_telefono = "+57 3007189383"
    emisor_email = "Dairo@dtgrowthpartners.com"
    emisor_ciudad = "Cartagena, Colombia"
    cuenta_bancolombia = "78841707710"
    nequi = "+57 3007189383"

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
    c.setFillColor(colors.HexColor("#005F99"))
    c.drawCentredString(width / 2.0, height - 120, f"CUENTA DE COBRO N.° {numero_cuenta}")

    y = height - 160
    c.setFont("HN-Normal", 9)
    c.setFillColor(colors.HexColor("#005F99"))
    c.drawString(margen_izquierdo, y, emisor_telefono)
    y -= 12
    c.drawString(margen_izquierdo, y, emisor_email)
    y -= 12
    dark_gray = colors.HexColor("#005F99")
    c.setFillColor(dark_gray)
    c.drawString(margen_izquierdo, y, emisor_ciudad)

    y -= 30  # Aumenté el espacio antes de los datos del cliente
    c.setFont("HN-Bold", 9)
    c.setFillColor(colors.black)
    
    # CORREGIDO: Espaciado reducido para los datos del cliente
    label_cliente = "Cliente:"
    c.drawString(margen_izquierdo, y, label_cliente)
    label_width = c.stringWidth(label_cliente, "HN-Bold", 9)
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo + label_width + 2, y, nombre_cliente)  # Reducido de 5 a 2
    
    y -= 15  # Aumenté el espaciado entre líneas de 12 a 15
    c.setFont("HN-Bold", 9)
    label_id = "Identificación:"
    c.drawString(margen_izquierdo, y, label_id)
    label_width = c.stringWidth(label_id, "HN-Bold", 9)
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo + label_width + 2, y, identificacion)  # Reducido de 5 a 2
    
    y -= 15  # Aumenté el espaciado entre líneas de 12 a 15
    c.setFont("HN-Bold", 9)
    label_fecha = "Fecha:"
    c.drawString(margen_izquierdo, y, label_fecha)
    label_width = c.stringWidth(label_fecha, "HN-Bold", 9)
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo + label_width + 2, y, datetime.now().strftime("%d/%m/%Y"))  # Reducido de 5 a 2

    y -= 30  # Aumenté el espaciado antes del concepto de 24 a 30
    c.setFont("HN-Bold", 9)
    label_concepto = "Servicio / Proyecto:"
    c.drawString(margen_izquierdo, y, label_concepto)
    label_width = c.stringWidth(label_concepto, "HN-Bold", 9)
    c.setFont("HN-Normal", 9)
    c.drawString(margen_izquierdo + label_width + 2, y, concepto)  # Reducido de 5 a 2

    # --- TABLA DE SERVICIOS ---
    servicios = [{'descripcion': concepto, 'cantidad': 1, 'precio_unitario': valor}]
    col_widths = [280, 60, 100, 100]
    row_height = 20
    table_y_start = height - 330
    header_color = colors.Color(red=0/255, green=95/255, blue=153/255)


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
    
    styles = getSampleStyleSheet()
    descripcion_style = ParagraphStyle(
        'descripcion',
        parent=styles['Normal'],
        fontName='HN-Normal',
        fontSize=9,
        leading=11
    )

    for servicio in servicios:
        descripcion_p = Paragraph(servicio['descripcion'], descripcion_style)
        
        desc_width = col_widths[0] - 10
        w, h = descripcion_p.wrap(desc_width, table_y_start)
        
        dynamic_row_height = max(row_height, h + 10)

        current_y -= dynamic_row_height
        importe = servicio['cantidad'] * servicio['precio_unitario']
        total += importe
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.grid([margen_izquierdo, margen_izquierdo + col_widths[0], margen_izquierdo + sum(col_widths[:2]), margen_izquierdo + sum(col_widths[:3]), margen_izquierdo + sum(col_widths)], [current_y, current_y + dynamic_row_height])
        
        descripcion_p.drawOn(c, margen_izquierdo + 5, current_y + (dynamic_row_height - h) / 2)

        text_y = current_y + (dynamic_row_height / 2) - 3
        c.drawCentredString(margen_izquierdo + col_widths[0] + col_widths[1]/2, text_y, str(servicio['cantidad']))
        c.drawRightString(margen_izquierdo + sum(col_widths[:3]) - 10, text_y, f"$ {servicio['precio_unitario']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c.drawRightString(margen_izquierdo + sum(col_widths) - 10, text_y, f"$ {importe:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

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
    c.drawString(margen_izquierdo, y, f"Nequi / Daviplata: {nequi}")
    
    y -= 36
    # CORREGIDO: "Atentamente" en línea separada
    c.setFont("HN-Bold", 9)
    c.drawString(margen_izquierdo, y, "Notas adicionales:")
    c.setFont("HN-Normal", 9)
    label_width = c.stringWidth("Notas adicionales: ", "HN-Bold", 9)
    c.drawString(margen_izquierdo + label_width, y, "Se solicita que el pago sea realizado a la mayor brevedad posible.")
    y -= 80  # Aumentado de 12 a 18 para bajar más "Atentamente,"
    c.drawString(margen_izquierdo, y, "Atentamente,")
    y -= 16  # Reducido el espacio antes de la firma de 48 a 36
    c.drawString(margen_izquierdo, y, emisor_nombre)

    # --- FOOTER CENTRADO ---
    footer_y = 40
    c.setFont("HN-Normal", 9)
    dark_gray = colors.HexColor("#36454F")

    # Textos y links
    text_dt = "dtgrowthpartners.com"
    link_dt = "http://www.dtgrowthpartners.com"
    text_whatsapp = "+57 300 718 9383"
    link_whatsapp = "https://api.whatsapp.com/send/?phone=573007189383&text=Hola%20Dairo&type=phone_number&app_absent=0"
    text_dairo = "dairotraslavina.com"
    link_dairo = "http://www.dairotraslavina.com"

    # Crear el texto completo centrado
    footer_text = f"{text_dt} | {text_whatsapp} | {text_dairo}"
    
    # Calcular ancho total del texto
    total_width = c.stringWidth(footer_text, "HN-Normal", 9)
    
    # Posición x centrada
    center_x = width / 2
    start_x = center_x - (total_width / 2)
    
    # Calcular posiciones para cada enlace
    width_dt = c.stringWidth(text_dt, "HN-Normal", 9)
    width_separator1 = c.stringWidth(" | ", "HN-Normal", 9)
    width_whatsapp = c.stringWidth(text_whatsapp, "HN-Normal", 9)
    width_separator2 = c.stringWidth(" | ", "HN-Normal", 9)
    width_dairo = c.stringWidth(text_dairo, "HN-Normal", 9)
    
    # Dibujar el texto completo
    c.setFillColor(dark_gray)
    c.drawString(start_x, footer_y, footer_text)
    
    # Crear enlaces individuales
    # Enlace 1: dtgrowthpartners.com
    c.linkURL(link_dt, (start_x, footer_y, start_x + width_dt, footer_y + 10), relative=1)
    
    # Enlace 2: whatsapp (saltamos el primer separador)
    whatsapp_start_x = start_x + width_dt + width_separator1
    c.linkURL(link_whatsapp, (whatsapp_start_x, footer_y, whatsapp_start_x + width_whatsapp, footer_y + 10), relative=1)
    
    # Enlace 3: dairotraslavina.com 
    dairo_start_x = whatsapp_start_x + width_whatsapp + width_separator2
    c.linkURL(link_dairo, (dairo_start_x, footer_y, dairo_start_x + width_dairo, footer_y + 10), relative=1)

    c.save()
    return ruta_salida

if __name__ == "__main__":
    with open(r"C:\Users\sante\Desktop\gemini-cli\stiven_files\PDFS\api-cuentas-de-cobro\propuesta.txt", "r", encoding="utf-8") as f:
        contenido_propuesta = f.read()
    generar_propuesta(contenido_propuesta)

    # --- CÓDIGO PARA GENERAR CUENTA DE COBRO A TRAVÉS DE LA API ---
    import requests

    url = "https://api-cuentas-de-cobro.onrender.com/crear-cuenta/"
    datos_cuenta = {
        "nickname_cliente": "acbfit",
        "valor": 150000.50,
        "concepto": "Desarrollo de landing page"
    }

    respuesta = requests.post(url, json=datos_cuenta)

    if respuesta.status_code == 200:
        with open("cuenta_de_cobro.pdf", "wb") as f:
            f.write(respuesta.content)
        print("Cuenta de cobro generada y guardada como 'cuenta_de_cobro.pdf'")
    else:
        print(f"Error al generar la cuenta de cobro: {respuesta.text}")