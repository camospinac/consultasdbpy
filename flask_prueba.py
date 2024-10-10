#!C:\Users\Camilo Ospinq\AppData\Local\Programs\Python\Python39\python.exe
#TODO: http://127.0.0.1:8888/listas/prueba_python.html
"""
Importar librerias

Para instalar todas estas librerias de manera automatica, recomendamos instalar el archivo
requirements.txt:
    pip install -r requirements.txt

"""
import cgi
import cgitb
import configparser
import requests
import unicodedata
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from datetime import datetime
from PyPDF2 import PdfReader
import time
import psycopg2
import pyodbc
import cx_Oracle
from lxml import etree 
import os
import re

"""
Configuracion CGI y BD's

Para poder hacer uso del proyecto es necesario parametrizar previamente el archivo que está en el mismo
directorio de este script llamado <db_config.ini>, aca va a estar todas las conexiones a la bases de datos
soportadas como así mismo configurar el servido CGI en cualquier entorno de so.

"""
download_dir = os.path.join(os.getcwd(), "downloads")
config = configparser.ConfigParser()
config.read('db_config.ini')
cgitb.enable(display=0, logdir=config['settings']['logdir'])
engine = config['settings']['engine']
conn = None
if engine == 'postgres':
    conn = psycopg2.connect(
        dbname=config['postgres']['dbname'],
        user=config['postgres']['user'],
        password=config['postgres']['password'],
        host=config['postgres']['host'],
        port=config['postgres']['port']
    )
elif engine == 'sqlserver':
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER={config["sqlserver"]["host"]},{config["sqlserver"]["port"]};'
        f'DATABASE={config["sqlserver"]["dbname"]};'
        f'UID={config["sqlserver"]["user"]};'
        f'PWD={config["sqlserver"]["password"]}'
    )
elif engine == 'oracle':
    dsn_tns = cx_Oracle.makedsn(
        config['oracle']['host'],
        config['oracle']['port'],
        service_name=config['oracle']['service_name']
    )
    conn = cx_Oracle.connect(
        user=config['oracle']['user'],
        password=config['oracle']['password'],
        dsn=dsn_tns
    )
else:
    raise ValueError("Motor de base de datos no soportado")

# Funcion para extraer el ultimo consecutivo
def obtener_ultimo_ctvo():
    """
    Extrae el ultimo consecutivo de la tabla plistas y posteriomente le suma uno para poder insertar
    un nuevo registro.

    Args: 
        None
    Returns:
        ultimo_ctvo (numeric):  variable numerica para poder insertar el registro de la persona a consultar
    """
    try:
        cursor = conn.cursor()
        if engine == 'postgres':
            cursor.execute("SELECT MAX(ctvolis) FROM plistas")
        elif engine == 'sqlserver':
            cursor.execute("SELECT MAX(ctvolis) FROM plistas")
        elif engine == 'oracle':
            cursor.execute("SELECT MAX(ctvolis) FROM plistas")
        ultimo_ctvo = cursor.fetchone()[0]
        cursor.close()
        return ultimo_ctvo
    except Exception as e:
        print("Error al obtener el último ctvo de PLISTAS:", e)
        return None
    
# Función para obtener todas las URLs activas desde la tabla CLISTAS
def obtener_urls_activas():
    """
    Función que busca todas las listas parametrizadas y activas en la tabla CLISTAS y las retorna en un array.

    Args:
        None
    
    Returns:
        urls_activas (array): array con las URL activas
    """    
    try:
        cursor = conn.cursor()
        if engine == 'postgres':
            cursor.execute("SELECT codclis, urllis, decrlis FROM clistas WHERE estlis = 'A'")
        elif engine == 'sqlserver':
            cursor.execute("SELECT codclis, urllis, decrlis FROM clistas WHERE estlis = 'A'")
        elif engine == 'oracle':
            cursor.execute("SELECT codclis, urllis, decrlis FROM clistas WHERE estlis = 'A'")
        urls_activas = cursor.fetchall()
        cursor.close()
        return urls_activas
    except Exception as e:
        print("Error al obtener URLs activas:", e)
        return []
    
# Función para iniciar el WebDriver con Selenium
def iniciar_driver():
    """
    
    Función para inicializar el driver en todas las funciones de consulta

    Args:
        None

    Returns:
        driver (object): Objeto con las propiedades cargadas
    """    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920x1080")
    os.makedirs(download_dir, exist_ok=True)
    prefs = {
        "download.default_directory": download_dir,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    service = Service(executable_path="chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

#Funcion para leer respuesta de la procuraduría
def normalizar_texto(texto):
    """
    
    Función para normalizar el texto de las respuestas proporcionadas en el txt (solo se usa para la procuraduria) 

    Args:
        texto (string): Archivo de texto con las respuestas precargadas para el captcha

    Returns:
        texto_normalizado (string): texto totalmente normalizado
    """    
    texto_normalizado = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto_normalizado.lower().strip()

def cargar_preguntas_respuestas(archivo):
    """
    Función para cargar el archivo txt con las preguntas para previamente devolverla en diccionario

    Args:
        archivo (blob): Archivo txt con las preguntas y respuestas del captcha

    Returns:
        diccionario_preguntas (array): devuelve un dict o array de preguntas sin normalizar
    """    
    diccionario_preguntas = {}
    with open(archivo, 'r', encoding='utf-8') as f:
        for linea in f:
            pregunta, respuesta = linea.strip().split(':')
            pregunta_normalizada = normalizar_texto(pregunta)
            diccionario_preguntas[pregunta_normalizada] = respuesta.strip()
    return diccionario_preguntas

# Funciones de consulta para cada tipo de URL
def consultar_policia(driver, url, fecha_expedicion, numero_cedula):  #PONAL
    """
    Función para consultar el portal web de la Policia Nacional de Colombia

    Args:
        driver (object): Para arrastrar las propiedades del driver y el navegador
        url (string): Url para consultar
        fecha_expedicion (date): Fecha de expedicion del documento de la persona a consultar
        numero_cedula (string): Numero de identificacion de la persona

    Returns:
        elemento_h3.text (string): Descripción o resultado de la consulta
    """    
    driver.get(url)
    selector_combobox = Select(driver.find_element(By.ID, 'ctl00_ContentPlaceHolder3_ddlTipoDoc'))
    selector_combobox.select_by_value('55')
    campo_fecha = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'txtFechaexp')))
    campo_fecha.send_keys(fecha_expedicion)
    campo_texto = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder3_txtExpediente')))
    campo_texto.send_keys(numero_cedula, Keys.ENTER)
    boton_consultar = driver.find_element(By.ID, 'ctl00_ContentPlaceHolder3_btnConsultar2')
    boton_consultar.click()
    elemento_h3 = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//div[@class="row"]/h3')))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'captura_policia_{numero_cedula}_{timestamp}.png'
    driver.save_screenshot(filename)
    return elemento_h3.text

def consultar_dian(driver, url, fecha_expedicion, numero_cedula): #DIAN
    """
    
    Función para consultar al portal de la DIAN

    Args:
        driver (object): Para arrastrar las propiedades del driver y el navegador
        url (string): Url para consultar
        fecha_expedicion (date): Fecha de expedicion del documento de la persona a consultar - No se usa en esta función
        numero_cedula (string): Numero de identificacion de la persona

    Returns:
        driver.find_element(By.ID, 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:estado').text (string): Descripción o resultado de la consulta
    """    
    driver.get(url)
    campo_texto = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:numNit')))
    campo_texto.send_keys(numero_cedula, Keys.ENTER)
    boton_consultar = driver.find_element(By.ID,'vistaConsultaEstadoRUT:formConsultaEstadoRUT:btnBuscar')
    boton_consultar.click()
    time.sleep(1)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'captura_dian_{numero_cedula}_{timestamp}.png'
    driver.save_screenshot(filename)
    return driver.find_element(By.ID, 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:estado').text

def consultar_rues(driver, url, fecha_expedicion, numero_cedula): #RUES
    """
    Función para consultar al RUES

    Args:
        driver (object): Para arrastrar las propiedades del driver y el navegador
        url (string): Url para consultar
        fecha_expedicion (date): Fecha de expedicion del documento de la persona a consultar - No se usa en esta función
        numero_cedula (string): Numero de identificacion de la persona
    Returns:
        estadoF (string): Descripción o resultado de la consulta
    """    
    driver.get(url)
    campo_texto = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'search')))
    campo_texto.send_keys(numero_cedula)
    campo_texto.send_keys(Keys.ENTER) 
    estado_elemento = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.XPATH, '//div[@class="registroapi"]//p[text()="Estado"]/following-sibling::span'))
    )
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'captura_rues_{numero_cedula}_{timestamp}.png'
    driver.save_screenshot(filename)
    estadoF = 'REGISTRO '+estado_elemento.text.upper()
    return estadoF

def consulta_funpub(driver, url, fecha_expedicion, numero_cedula):
    """
    Función para consultar en el portal de Funcionarios Publicos
    Args:
        driver (object): Para arrastrar las propiedades del driver y el navegador
        url (string): Url para consultar
        fecha_expedicion (date): Fecha de expedicion del documento de la persona a consultar - No se usa en esta función
        numero_cedula (string): Numero de identificacion de la persona
    Returns:
        datos_concatenados.strip() (array): Descripción o resultado de la consulta
    """     
    driver.get(url)
    campo_texto = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'numeroDocumento')))
    campo_texto.send_keys(numero_cedula, Keys.ENTER)
    boton_consultar = driver.find_element(By.ID, 'find')
    boton_consultar.click()
    tabla = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "table")))
    try:
        mensaje_error_element = tabla.find_element(By.XPATH, ".//tbody/tr/td[@colspan='10']")
        if mensaje_error_element:
            mensaje_error = mensaje_error_element.text
            return f"No se encontraron registros: {mensaje_error}"
    except:
        pass
    encabezados = [header.text for header in tabla.find_elements(By.XPATH, ".//thead/tr/th")]
    filas = tabla.find_elements(By.XPATH, ".//tbody/tr")
    datos_concatenados = ""
    for fila in filas:
        celdas = fila.find_elements(By.XPATH, "./td[position() > 2]")
        for indice, celda in enumerate(celdas, start=2):
            datos_concatenados += f" {encabezados[indice]}: {celda.text}\n"
    return datos_concatenados.strip()


def consulta_onu(driver, url, fecha_expedicion, numero_cedula): #ONU
    """
    Función para consultar la base XML de la ONU

    Args:
        driver (object): Para arrastrar las propiedades del driver y el navegador - No se usa en esta función
        url (string): Url para consultar
        fecha_expedicion (date): Fecha de expedicion del documento de la persona a consultar - No se usa en esta función
        numero_cedula (string): Numero de identificacion de la persona
    Returns:
        comentariom (string): Descripción o resultado de la consulta
    """    
    response = requests.get(url)
    xml_content = response.content
    tree = etree.fromstring(xml_content)
    individual = tree.xpath(f"//INDIVIDUAL[DATAID='{numero_cedula}']")
    if individual:
        comentario = individual[0].find('COMMENTS1').text
        return comentario
    else:
        comentariom = 'NO SE ENCUENTRA EN LA LISTA DE LA ONU'
        return comentariom

def consulta_procu(driver, url, fecha_expedicion, numero_cedula):
    """
    Función para consultar la pagina web de la procuraduría

    Args:
        driver (object): Para arrastrar las propiedades del driver y el navegador
        url (string): Url para consultar
        fecha_expedicion (date): Fecha de expedicion del documento de la persona a consultar - No se usa en esta función
        numero_cedula (string): Numero de identificacion de la persona
    Returns:
        respuesta_texto (string): Descripción o resultado de la consulta
    """    
    archivo_preguntas_respuestas = 'respuestas.txt'
    diccionario_preguntas = cargar_preguntas_respuestas(archivo_preguntas_respuestas)
    driver.get(url)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, 'lblPregunta')))
    pregunta = driver.find_element(By.ID, 'lblPregunta').text
    pregunta_normalizada = normalizar_texto(pregunta)
    select_combobox = Select(driver.find_element(By.ID, 'ddlTipoID'))
    select_combobox.select_by_value('1')
    campo_texto = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'txtNumID')))
    campo_texto.send_keys(numero_cedula)
    respuesta = diccionario_preguntas.get(pregunta_normalizada, '')
    campo_resp = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'txtRespuestaPregunta')))
    campo_resp.send_keys(respuesta)
    boton_consultar = driver.find_element(By.ID, 'btnConsultar')
    time.sleep(2)
    boton_consultar.click()
    time.sleep(4)
    h2_element = driver.find_element(By.XPATH, '//div[@id="divSec"]/h2[2]')
    respuesta_texto = h2_element.text
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'captura_procuraduria_{numero_cedula}_{timestamp}.png'
    driver.save_screenshot(filename)
    return respuesta_texto

def consulta_contra(driver, url, fecha_expedicion, numero_cedula):
    """
    Función para consultar en la pagina web de la Contraloria

    Args:
        driver (object): Para arrastrar las propiedades del driver y el navegador
        url (string): Url para consultar
        fecha_expedicion (date): Fecha de expedicion del documento de la persona a consultar - No se usa en esta función
        numero_cedula (string): Numero de identificacion de la persona
    Returns:
        result (string): Descripción o resultado de la consulta
    """    
    try:
        driver.get(url)
        campo_texto = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'txtNumeroDocumento')))
        campo_texto.send_keys(numero_cedula)
        select_combobox = Select(driver.find_element(By.ID, 'ddlTipoDocumento'))
        select_combobox.select_by_value('CC')
        time.sleep(1)
        boton_consultar = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'btnBuscar')))
        boton_consultar.click()
        time.sleep(1)
        
        pdf_files = [f for f in os.listdir(download_dir) if f.endswith('.pdf')]
        if pdf_files:
            pdf_path = os.path.join(download_dir, pdf_files[0])
            with open(pdf_path, 'rb') as pdf_file:
                reader = PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
            if re.search(r"no\s*se\s*encuentra\s*reportado", text.lower()):
                result = "La persona no está reportada"
            else:
                result = "La persona sí está reportada"
        else:
            result = "No se pudo encontrar el archivo PDF descargado"
        return result
    except (NoSuchElementException, TimeoutException) as e:
        print(f"Error encontrado: {e}. Refrescando la página y reintentando...")
        driver.refresh()
        time.sleep(2)
        return consulta_contra(driver, url, fecha_expedicion, numero_cedula)

# Mapeo de funciones de consulta según el código de lista

funciones_consulta = {
    
    """
    funciones_consulta:
    En este diccionario, se mapean todas las consultas nuevas o existen que vayan llegando para poder parametrizarlas
    """    
    'PONAL': consultar_policia,
    'DIAN': consultar_dian,
    'RUES': consultar_rues,
    'FPUB': consulta_funpub,
    'ONU' : consulta_onu,
    'PROC': consulta_procu,
    'CONT': consulta_contra,
}

# Función para insertar resultados en la base de datos
def insertar_resultado(resultados, numero_cedula, fecha_expedicion, tip_id, primer_nombre, seg_nombre, primer_ape, seg_apelli, tip_id_h, empresa, usu_reg):
    """
    
    Función para insertar los resultados de la busqueda de los portales en la base de datos
    Logica: Primero inserta la cabecera PLISTAS y luego inserta la consultas en la tabla heredada PLISTAS1, tiene un try catch en caso
    de que ocurra algún error y pueda hacer un rollback sin afectar la integridad de los datos.

    Args:
        resultados (string): El resultado devuelto por la pagina web a consultar
        numero_cedula (string): Número de identificación de la persona consultada
        fecha_expedicion (date): Fecha de expedición del documento de la persona consultada
        tip_id (string): Tipo de identificación de la persona consultada
        primer_nombre (string): Primer nombre de la persona consultada
        seg_nombre (string): Segundo nombre de la persona consultada
        primer_ape (string): Primer apellido de la persona consultada
        seg_apelli (string): Segundo apellido de la persona consultada
        tip_id_h (string): Tipo de documento estandarizado para la consulta de la PONAL
        empresa (string): Empresa de logeo
        usu_reg (string): Usuario de registro
        
    Returns:
        None
    """    
    
    try:
        ultimo_ctvo = obtener_ultimo_ctvo()
        ctvo_padre = (ultimo_ctvo + 1) if ultimo_ctvo else 1
        timestamp_actual = datetime.now()
        cursor = conn.cursor()
        #PLISTAS CABECERA
        if engine == 'postgres':
            cursor.execute("""
                INSERT INTO plistas(ctvolis, tipidlis, numidlis, prnomlis, sgnomlis, sgaplis, praplis, fchexlis, empcod, usurelisp, usumolisp, fchrelisp, fchmolisp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (ctvo_padre, tip_id, numero_cedula, primer_nombre, seg_nombre, seg_apelli, primer_ape, fecha_expedicion, empresa, usu_reg, '', timestamp_actual, '00010101'))
        elif engine == 'sqlserver':
            cursor.execute("""
                INSERT INTO plistas(ctvolis, tipidlis, numidlis, prnomlis, sgnomlis, sgaplis, praplis, fchexlis, empcod, usurelisp, usumolisp, fchrelisp, fchmolisp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ctvo_padre, tip_id, numero_cedula, primer_nombre, seg_nombre, seg_apelli, primer_ape, fecha_expedicion, empresa, usu_reg, '', timestamp_actual, '00010101'))
        elif engine == 'oracle':
            cursor.execute("""
                INSERT INTO plistas(ctvolis, tipidlis, numidlis, prnomlis, sgnomlis, sgaplis, praplis, fchexlis, empcod, usurelisp, usumolisp, fchrelisp, fchmolisp)
                VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13)
            """, (ctvo_padre, tip_id, numero_cedula, primer_nombre, seg_nombre, seg_apelli, primer_ape, fecha_expedicion, empresa, usu_reg, '', timestamp_actual, '00010101'))
        #PLISTAS DETALLE
        for descripcion, valor, codigo in resultados:
            if engine == 'postgres':
                cursor.execute("""
                    INSERT INTO plistas2(ctvolis, empcod, codclis, decrlist, rtalis, tipdohlis)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (ctvo_padre, empresa, codigo, descripcion, valor, tip_id_h))
            elif engine == 'sqlserver':
                cursor.execute("""
                    INSERT INTO plistas2(ctvolis, empcod, codclis, decrlist, rtalis, tipdohlis)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ctvo_padre, empresa, codigo, descripcion, valor, tip_id_h))
            elif engine == 'oracle':
                cursor.execute("""
                    INSERT INTO plistas2(ctvolis, empcod, codclis, decrlist, rtalis, tipdohlis)
                    VALUES (:1, :2, :3, :4, :5, :6)
                """, (ctvo_padre, empresa, codigo, descripcion, valor, tip_id_h))
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"Error al insertar en la base de datos: {e}")
        conn.rollback()

# Procesamiento CGI
print("Content-Type: text/html\n")
form = cgi.FieldStorage()
fecha_expedicion = form.getvalue('fecha_expedicion')
numero_cedula = form.getvalue('numero_cedula')
primer_nombre = form.getvalue('primer_nombre')
seg_nombre = form.getvalue('seg_nombre')
primer_ape = form.getvalue('primer_ape')
seg_apelli = form.getvalue('seg_apelli')
tip_id_cu = form.getvalue('tipid')
empresa = form.getvalue('empresa')
usu_reg = form.getvalue('usureg')

# Obtener las URLs activas y realizar las consultas
resultados = []
urls_activas = obtener_urls_activas()
with iniciar_driver() as driver:
    for codigo, url, descripcion in urls_activas:
        if codigo in funciones_consulta:
            resultado = funciones_consulta[codigo](driver, url, fecha_expedicion, numero_cedula)
            resultados.append((descripcion, resultado, codigo))

# Insertar los resultados en la base de datos
if resultados:
    tip_id = 55
    insertar_resultado(resultados, numero_cedula, fecha_expedicion, tip_id_cu, primer_nombre, seg_nombre, primer_ape, seg_apelli, tip_id, empresa, usu_reg)

# Generar respuesta HTML

print("<html>")
print("<head>")
print("<title>Resultado de la consulta - L2K</title>")
print('<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">')
print("<script type='text/javascript'>")
print("setTimeout(function() { window.close(); }, 5000);")
print("</script>")
print("</head>")
print("<body class='bg-light'>")
print("<div class='container mt-5'>")
print("<div class='card'>")
print("<div class='card-body text-center'>")
print("<h2 class='card-title'>CONSULTA REALIZADA CON EXITO</h2>")
print("<h3 class='card-text'>Está ventana se cerrará automáticamente en 5 segundos...</h3>")
print("<p class='card-text'>Powered By: </p>")
print("<img src='https://l2k.com.co/wp-content/uploads/2020/03/logo-l2k-horizontal.png' alt='Logo' class='img-fluid my-3' style='max-width: 150px;'>")
print("</div>")
print("</div>")
print("</div>")
print("</body>")
print("</html>")



# print("<html>")
# print("<head>")
# print("<title>Resultado de la consulta - L2K</title>")
# print("<script type='text/javascript'>")
# print("setTimeout(function() { window.close(); }, 5000);")
# print("</script>")
# print("</head>")
# print("<body>")
# print("<h2>CONSULTA REALIZADA CON EXITO</h2>")
# print("<h3>Está ventana se cerrará automaticamente en 5 segundos...</h3>")
# # print("<h4>Cedula:</h4>")
# # print("<p>{}</p>".format(numero_cedula))
# # print("<h4>Fecha expedicion:</h4>")
# # print("<p>{}</p>".format(fecha_expedicion))
# # print("<h4>Resultados:</h4>")
# # for descripcion, valor, codigo in resultados:
# #     print("<p>{}: {}</p>".format(descripcion, valor, codigo))
# print("</body>")
# print("</html>")


# Cerrar la conexión a la base de datos
conn.close()
