import os
import io
import threading
import tempfile
import webbrowser
from datetime import datetime, timedelta
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from PIL import Image as PILImage, ImageTk, UnidentifiedImageError
import mysql.connector
from dotenv import load_dotenv
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
import glob
import time

# CustomTkinter imports
import customtkinter as ctk
from tkinter import messagebox, ttk
import tkinter as tk

# Corregir la importación de EstiloApp
try:
    # Intenta importar desde utils (ruta relativa)
    from utils.interface_manager import EstiloApp
    
    # Extender EstiloApp con los colores adicionales que necesitamos
    class EstiloExtendido(EstiloApp):
        def __init__(self):
            super().__init__()
            # Colores básicos (si no existen)
            if not hasattr(self, 'COLOR_PRIMARIO'):
                self.COLOR_PRIMARIO = "#1a5276"
            if not hasattr(self, 'COLOR_SECUNDARIO'):
                self.COLOR_SECUNDARIO = "#3498db"
            if not hasattr(self, 'COLOR_TEXTO'):
                self.COLOR_TEXTO = "#2c3e50"
            
            # Colores de fondo (si no existen)
            if not hasattr(self, 'COLOR_FONDO'):
                self.COLOR_FONDO = "#ecf0f1"
            if not hasattr(self, 'COLOR_FONDO_CLARO'):
                self.COLOR_FONDO_CLARO = "#f5f8fa"
            if not hasattr(self, 'COLOR_FONDO_ALTERNO'):
                self.COLOR_FONDO_ALTERNO = "#e6eef2"
            if not hasattr(self, 'COLOR_TEXTO_SECUNDARIO'):
                self.COLOR_TEXTO_SECUNDARIO = "#666666"
                
            # Colores para botones de acción
            if not hasattr(self, 'COLOR_EXITO'):
                self.COLOR_EXITO = "#27ae60"  # Verde
            if not hasattr(self, 'COLOR_EXITO_HOVER'):
                self.COLOR_EXITO_HOVER = "#2ecc71"
            if not hasattr(self, 'COLOR_ERROR'):
                self.COLOR_ERROR = "#e74c3c"  # Rojo
            if not hasattr(self, 'COLOR_ERROR_HOVER'):
                self.COLOR_ERROR_HOVER = "#c0392b"
            if not hasattr(self, 'COLOR_ADVERTENCIA'):
                self.COLOR_ADVERTENCIA = "#f39c12"  # Naranja
            if not hasattr(self, 'COLOR_ADVERTENCIA_HOVER'):
                self.COLOR_ADVERTENCIA_HOVER = "#d35400"
    
    # Usar nuestra versión extendida
    EstiloApp = EstiloExtendido
    
except ImportError:
    try:
        # Intenta importar desde la ruta del proyecto
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from utils.interface_manager import EstiloApp
        
        # Extender EstiloApp con los colores adicionales que necesitamos
        class EstiloExtendido(EstiloApp):
            def __init__(self):
                super().__init__()
                # Colores básicos (si no existen)
                if not hasattr(self, 'COLOR_PRIMARIO'):
                    self.COLOR_PRIMARIO = "#1a5276"
                if not hasattr(self, 'COLOR_SECUNDARIO'):
                    self.COLOR_SECUNDARIO = "#3498db"
                if not hasattr(self, 'COLOR_TEXTO'):
                    self.COLOR_TEXTO = "#2c3e50"
                
                # Colores de fondo (si no existen)
                if not hasattr(self, 'COLOR_FONDO'):
                    self.COLOR_FONDO = "#ecf0f1"
                if not hasattr(self, 'COLOR_FONDO_CLARO'):
                    self.COLOR_FONDO_CLARO = "#f5f8fa"
                if not hasattr(self, 'COLOR_FONDO_ALTERNO'):
                    self.COLOR_FONDO_ALTERNO = "#e6eef2"
                if not hasattr(self, 'COLOR_TEXTO_SECUNDARIO'):
                    self.COLOR_TEXTO_SECUNDARIO = "#666666"
                    
                # Colores para botones de acción
                if not hasattr(self, 'COLOR_EXITO'):
                    self.COLOR_EXITO = "#27ae60"  # Verde
                if not hasattr(self, 'COLOR_EXITO_HOVER'):
                    self.COLOR_EXITO_HOVER = "#2ecc71"
                if not hasattr(self, 'COLOR_ERROR'):
                    self.COLOR_ERROR = "#e74c3c"  # Rojo
                if not hasattr(self, 'COLOR_ERROR_HOVER'):
                    self.COLOR_ERROR_HOVER = "#c0392b"
                if not hasattr(self, 'COLOR_ADVERTENCIA'):
                    self.COLOR_ADVERTENCIA = "#f39c12"  # Naranja
                if not hasattr(self, 'COLOR_ADVERTENCIA_HOVER'):
                    self.COLOR_ADVERTENCIA_HOVER = "#d35400"
        
        # Usar nuestra versión extendida
        EstiloApp = EstiloExtendido
        
    except ImportError:
        # Si todo falla, define una clase EstiloApp básica para que el módulo funcione
        class EstiloApp:
            def __init__(self):
                # Colores predeterminados
                self.COLOR_PRIMARIO = "#1a5276"
                self.COLOR_SECUNDARIO = "#3498db"
                self.COLOR_FONDO = "#ecf0f1"
                self.COLOR_FONDO_CLARO = "#f5f8fa"
                self.COLOR_FONDO_ALTERNO = "#e6eef2"
                self.COLOR_TEXTO = "#2c3e50"
                self.COLOR_TEXTO_SECUNDARIO = "#666666"
                
                # Colores para botones de acción
                self.COLOR_EXITO = "#27ae60"  # Verde
                self.COLOR_EXITO_HOVER = "#2ecc71"
                self.COLOR_ERROR = "#e74c3c"  # Rojo
                self.COLOR_ERROR_HOVER = "#c0392b"
                self.COLOR_ADVERTENCIA = "#f39c12"  # Naranja
                self.COLOR_ADVERTENCIA_HOVER = "#d35400"
                
                print("⚠️ Usando EstiloApp de respaldo - No se pudo importar desde utils")

# Cargar variables de entorno
load_dotenv()

# ------------------ Configuración de la base de datos ------------------
class DatabaseManager:
    """Gestor de conexiones a base de datos con pool de hilos"""
    def __init__(self):
        self.config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_DATABASE')
        }
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.connection_pool = []
        self.queue = Queue()
        self._initialize_pool()

    def _initialize_pool(self, pool_size=3):
        """Inicializar pool de conexiones"""
        try:
            for _ in range(pool_size):
                connection = mysql.connector.connect(**self.config)
                self.connection_pool.append(connection)
        except Exception as e:
            print(f"Error inicializando pool: {e}")

    def get_connection(self):
        """Obtener una conexión del pool"""
        if not self.connection_pool:
            connection = mysql.connector.connect(**self.config)
            return connection
        return self.connection_pool.pop()

    def return_connection(self, connection):
        """Devolver una conexión al pool"""
        if connection and connection.is_connected():
            self.connection_pool.append(connection)

    def execute_query_async(self, query: str, params: tuple = None, callback=None):
        """Ejecutar consulta de forma asíncrona usando ThreadPoolExecutor"""
        print(f"\n📡 Ejecutando consulta: {query}")
        print(f"🔧 Parámetros: {params}")

        def _async_query():
            connection = None
            cursor = None
            try:
                print("🔌 Obteniendo conexión del pool...")
                connection = self.get_connection()
                print("✅ Conexión obtenida")

                print("🔄 Creando cursor...")
                cursor = connection.cursor()
                print("✅ Cursor creado")

                print("🚀 Ejecutando consulta en la base de datos...")
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                print("✅ Consulta ejecutada")

                if query.strip().lower().startswith('select'):
                    print("📥 Obteniendo resultados...")
                    result = cursor.fetchall()
                    print(f"✨ Resultados obtenidos: {len(result) if result else 0} registros")
                else:
                    print("💾 Haciendo commit de la transacción...")
                    connection.commit()
                    result = True
                    print("✅ Commit realizado")

                if callback:
                    print("🔄 Enviando resultado al callback...")
                    callback(result)
                    print("✅ Callback ejecutado")
                else:
                    print("⚠️ No se definió callback")

            except Exception as e:
                print(f"❌ Error en consulta: {str(e)}")
                if callback:
                    callback(None)
            finally:
                if cursor:
                    cursor.close()
                    print("🔌 Cursor cerrado")
                if connection:
                    self.return_connection(connection)
                    print("🔌 Conexión devuelta al pool")

        self.executor.submit(_async_query)

    def close(self):
        """Cerrar todas las conexiones en el pool"""
        while self.connection_pool:
            connection = self.connection_pool.pop()
            if connection.is_connected():
                connection.close()
        self.executor.shutdown(wait=True)

# Instanciar el administrador de base de datos
db_manager = DatabaseManager()

# ------------------ Formateo de fechas ------------------
def formatear_fecha(fecha):
    """Formatea una fecha como 'dd de nombre_mes de yyyy'"""
    if not fecha:
        return "---"
        
    # Nombres de los meses en español
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio", 
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    
    # Formatear como "dd de nombre_mes de yyyy"
    return f"{fecha.day} de {meses[fecha.month-1]} de {fecha.year}"

# ------------------ Escaneo de informes existentes ------------------
def obtener_informes_generados():
    """Obtiene la lista de informes generados en la carpeta Informes"""
    directorio_informes = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Informes")
    if not os.path.exists(directorio_informes):
        os.makedirs(directorio_informes)
    
    informes = []
    
    for archivo in os.listdir(directorio_informes):
        if archivo.startswith("Informe_") and archivo.endswith(".pdf"):
            ruta_completa = os.path.join(directorio_informes, archivo)
            fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta_completa))
            
            # Extraer información del nombre del archivo
            # Formato: Informe_LEGAJO_APELLIDO_FECHA.pdf
            partes = archivo.replace("Informe_", "").replace(".pdf", "").split("_")
            
            if len(partes) >= 3:
                try:
                    legajo = partes[0]
                    apellido = partes[1]
                    
                    # Fecha y hora del nombre del archivo (si está disponible)
                    if len(partes) >= 4:
                        fecha_str = f"{partes[2]} {partes[3].replace('-', ':')}"
                        fecha_gen = datetime.strptime(fecha_str, "%Y%m%d %H%M%S")
                    else:
                        fecha_gen = fecha_mod
                    
                    # Tamaño del archivo en KB
                    tamanio = os.path.getsize(ruta_completa) / 1024
                    
                    informes.append({
                        "archivo": archivo,
                        "ruta": ruta_completa,
                        "legajo": legajo,
                        "apellido": apellido,
                        "fecha_generacion": fecha_gen,
                        "fecha_modificacion": fecha_mod,
                        "tamanio": tamanio
                    })
                except Exception as e:
                    print(f"Error al procesar archivo {archivo}: {str(e)}")
    
    # Ordenar por fecha de modificación (más reciente primero)
    informes.sort(key=lambda x: x["fecha_modificacion"], reverse=True)
    
    return informes

# ------------------ Generación de informes ------------------
def generar_primer_nivel(legajo):
    """Genera un PDF con el informe de antecedentes del legajo especificado"""
    try:
        print(f"\n🔍 Generando informe para legajo: {legajo}")
        
        # Obtener conexión de la base de datos
        connection = db_manager.get_connection()
        cursor = connection.cursor()
        
        # Consulta principal - Datos personales
        cursor.execute("""
            SELECT p.legajo, p.apellido_nombre, p.fecha_nacimiento, 
                   p.fecha_alta, p.foto, p.edad,
                   p.estado_civil, p.cargas, p.estudios
            FROM personal p
            WHERE p.legajo = %s
        """, (legajo,))
        
        personal = cursor.fetchone()
        
        if personal:
            # Datos del personal encontrados
            legajo = personal[0]
            apellido_nombre = personal[1]
            fecha_nacimiento = personal[2]
            fecha_alta = personal[3]
            foto_bytes = personal[4]
            edad = personal[5]
            estado_civil = personal[6]
            cargas = personal[7]
            estudios = personal[8]
            
            # Separar el apellido y nombre si es necesario para el PDF
            partes_nombre = apellido_nombre.split(",") if apellido_nombre else ["", ""]
            apellido = partes_nombre[0].strip() if len(partes_nombre) > 0 else ""
            nombre = partes_nombre[1].strip() if len(partes_nombre) > 1 else ""
            
            # Ruta del archivo del informe
            directorio_informes = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Informes")
            if not os.path.exists(directorio_informes):
                os.makedirs(directorio_informes)
                
            nombre_archivo = f"Informe_{legajo}_{apellido}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = os.path.join(directorio_informes, nombre_archivo)
            
            # Mostrar información básica
            print(f"📄 Generando informe para: {nombre} {apellido}")
            print(f"📂 Ruta del informe: {pdf_path}")
            
            # Preparar directorio temporal para la foto
            temp_dir = tempfile.mkdtemp()
            temp_foto = os.path.join(temp_dir, "temp_foto.jpg")
            
            # Guardar la foto en un archivo temporal si existe
            foto_path = None
            if foto_bytes:
                try:
                    image_stream = io.BytesIO(foto_bytes)
                    img = PILImage.open(image_stream)
                    
                    # Aumentar el tamaño de la imagen si es muy pequeña
                    if img.size[0] < 80:  # Si el ancho es menor a 800px
                        ratio = img.size[1] / img.size[0]
                        new_width = 80
                        new_height = int(new_width * ratio)
                        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

                    if img.mode == 'RGBA':
                        img = img.convert('RGB')

                    # Guardar con mayor calidad
                    img.save(temp_foto, 'JPEG', quality=95, dpi=(300, 300))
                    
                    # Verificar que el archivo existe
                    if os.path.exists(temp_foto):
                        foto_path = f"file:///{temp_foto.replace(os.sep, '/').lstrip('/')}"
                        print(f"✅ Foto guardada en alta calidad: {foto_path}")
                    else:
                        print("❌ Error: No se pudo guardar la foto temporal")
                        foto_path = None

                except UnidentifiedImageError:
                    print(f"❌ Error: No se pudo identificar el archivo de imagen para el legajo {legajo}")
                except Exception as e:
                    print(f"❌ Error procesando imagen: {str(e)}")
                    foto_path = None
            
            # Obtener fecha actual
            fecha_actual = datetime.now()
            
            # Convertir fecha de alta para mostrarse formateada
            fecha_alta_formateada = formatear_fecha(fecha_alta) if fecha_alta else "---"
            
            # Obtener datos de felicitaciones
            cursor.execute("""
                SELECT fecha, objetivo, motivo
                FROM felicitaciones 
                WHERE legajo = %s
                ORDER BY fecha DESC
            """, (legajo,))
            felicitaciones = cursor.fetchall()
            
            # Obtener datos de sanciones actuales
            cursor.execute("""
                SELECT fecha, cantidad_dias, motivo, solicita, tipo_sancion
                FROM sanciones 
                WHERE legajo = %s AND fecha >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR)
                ORDER BY fecha DESC
            """, (legajo,))
            sanciones = cursor.fetchall()
            
            # Calcular días totales de suspensión
            total_dias_sanciones = sum([s[1] if s[1] and s[4] == 'Suspensión' else 0 for s in sanciones])
            
            # Obtener datos de sanciones históricas (más de 3 años)
            cursor.execute("""
                SELECT fecha, cantidad_dias, motivo, solicita, tipo_sancion
                FROM sanciones 
                WHERE legajo = %s AND fecha < DATE_SUB(CURDATE(), INTERVAL 3 YEAR)
                ORDER BY fecha DESC
            """, (legajo,))
            sanciones_historicas = cursor.fetchall()
            
            # Obtener datos de préstamos con su estado de pago
            cursor.execute("""
                SELECT p.fecha_inicio, p.monto_total, p.cuotas, p.motivo, 
                       CASE 
                           WHEN COUNT(pa.id) = 0 THEN 'Sin pagos registrados'
                           WHEN SUM(CASE WHEN pa.estado = 'Pendiente' THEN 1 ELSE 0 END) = 0 THEN 'Pagado'
                           ELSE 'Pendiente'
                       END AS estado_pago
                FROM prestamos p
                LEFT JOIN pagos pa ON p.id_prestamos = pa.id_prestamos
                WHERE p.legajo = %s
                GROUP BY p.id_prestamos
                ORDER BY p.fecha_inicio DESC
            """, (legajo,))
            prestamos = cursor.fetchall()

            # Obtener datos de certificados médicos
            cursor.execute("""
                SELECT fecha_atencion_medica, fecha_recepcion_certificado, 
                       diagnostico_causa, cantidad_dias, medico_hospital_clinica, datos_adicionales
                FROM certificados_medicos 
                WHERE legajo = %s
                ORDER BY fecha_atencion_medica DESC
            """, (legajo,))
            certificados_medicos = cursor.fetchall()
            
            # Obtener datos de accidentes de trabajo (ART)
            cursor.execute("""
                SELECT 
                    fecha_acc, 
                    fecha_alta, 
                    dx, 
                    ambito, 
                    objetivo, 
                    n_siniestro, 
                    descripcion
                FROM accidentes 
                WHERE legajo = %s
                ORDER BY fecha_acc DESC
            """, (legajo,))
            accidentes = cursor.fetchall()
            
            # Obtener datos de licencias sin goce
            cursor.execute("""
                SELECT 
                    cantidad_dias,
                    desde_fecha,
                    hasta_fecha,
                    solicita,
                    motivo
                FROM licencias_sin_goce 
                WHERE legajo = %s
                ORDER BY desde_fecha DESC
            """, (legajo,))
            licencias_sin_goce = cursor.fetchall()
            
            # -----------------------Conceptos-----------------------
            # Definir rango de fechas para conceptos (6 meses anteriores, sin incluir el mes actual)
            fecha_actual = datetime.now()
            
            # Primer día del mes actual
            primer_dia_mes_actual = fecha_actual.replace(day=1)
            
            # Último día del mes anterior (fecha_fin)
            fecha_fin = primer_dia_mes_actual - timedelta(days=1)
            
            # Para asegurar exactamente 6 meses, calculamos mes por mes
            meses = []
            mes_actual = fecha_fin.replace(day=1)  # Primer día del mes anterior
            
            # Añadir los 6 meses anteriores (comenzando con el mes anterior al actual)
            for i in range(6):
                meses.insert(0, mes_actual)  # Insertar al inicio para orden cronológico
                # Retroceder un mes
                if mes_actual.month == 1:
                    mes_actual = datetime(mes_actual.year - 1, 12, 1)
                else:
                    mes_actual = datetime(mes_actual.year, mes_actual.month - 1, 1)
            
            # El primer mes de nuestra lista es el inicio del rango
            fecha_inicio = meses[0]
            
            print(f"DEBUG - Meses para conceptos: {[m.strftime('%B %Y') for m in meses]}")
            print(f"DEBUG - Rango de fechas: {fecha_inicio} a {fecha_fin}")
            
            # Obtener conceptos
            cursor.execute("""
                SELECT fecha, concepto 
                FROM conceptos 
                WHERE legajo = %s 
                AND fecha BETWEEN %s AND %s
                ORDER BY fecha ASC
            """, (legajo, fecha_inicio, fecha_fin))
            
            conceptos_raw = cursor.fetchall()
            print(f"DEBUG - Conceptos encontrados: {len(conceptos_raw)}")
            
            # Convertir conceptos a diccionario para fácil acceso
            conceptos_dict = {
                concepto[0].strftime('%Y-%m'): concepto[1] 
                for concepto in conceptos_raw
            }
            
            # Preparar datos para la plantilla
            nombres_meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", 
                            "julio", "agosto", "sept", "octubre", "noviembre", "diciembre"]
            
            encabezados_conceptos = []
            calificaciones = []
            
            for mes in meses:
                mes_str = mes.strftime('%Y-%m')
                nombre_mes = f"{nombres_meses[mes.month-1]}-{mes.year}"
                encabezados_conceptos.append(nombre_mes)
                calificaciones.append(conceptos_dict.get(mes_str, "N/A"))
            
            print(f"DEBUG - Número de encabezados: {len(encabezados_conceptos)}")
            print(f"DEBUG - Encabezados: {encabezados_conceptos}")
            
            # Preparar entorno Jinja2 para el template
            templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
            env = Environment(loader=FileSystemLoader(templates_dir))
            template = env.get_template("informe.html")
            
            # Obtener la ruta del logo para el informe (usar PNG en lugar de GIF)
            logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "icons", "logo.png"))
            
            # Verificar que el archivo existe
            if not os.path.exists(logo_path):
                # Intentar con rutas alternativas si no se encuentra
                alternativas = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "logo.png")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "icons_gifs", "logo.png"))
                ]
                
                for alt_path in alternativas:
                    if os.path.exists(alt_path):
                        logo_path = alt_path
                        break
            
            # Convertir a formato URL para WeasyPrint con manejo adecuado para transparencia
            logo_path = f"file:///{logo_path.replace(os.sep, '/').lstrip('/')}"
            print(f"✅ Ruta del logo para el informe: {logo_path}")
            
            # Renderizar la plantilla con los datos
            html_content = template.render(
                legajo=legajo,
                nombre=nombre,
                apellido=apellido,
                apellido_nombre=apellido_nombre,
                documento="",
                fecha_nacimiento=formatear_fecha(fecha_nacimiento),
                fecha_alta=fecha_alta_formateada,
                fecha_informe=formatear_fecha(fecha_actual),
                edad=edad,
                estado_civil=estado_civil,
                cargas=cargas,
                estudios=estudios,
                foto_path=foto_path,
                logo_path=logo_path,
                felicitaciones=[{
                    'fecha': formatear_fecha(f[0]),
                    'objetivo': f[1],
                    'motivo': f[2]
                } for f in felicitaciones],
                sanciones=[{
                    'fecha': formatear_fecha(f[0]),
                    'dias': f[1] if f[4] == 'Suspensión' else 'No aplicable',
                    'motivo': f[2],
                    'solicita': f[3],
                    'tipo_sancion': f[4]
                } for f in sanciones],
                sanciones_historicas=[{
                    'fecha': formatear_fecha(f[0]),
                    'dias': f[1] if f[4] == 'Suspensión' else 'No aplicable',
                    'motivo': f[2],
                    'solicita': f[3],
                    'tipo_sancion': f[4]
                } for f in sanciones_historicas],
                total_dias_sanciones=total_dias_sanciones,
                prestamos=[{
                    'fecha': formatear_fecha(f[0]),
                    'monto': f[1],
                    'cuotas': f[2],
                    'motivo': f[3],
                    'estado': f[4]
                } for f in prestamos],
                certificados_medicos=[{
                    'fecha_atencion': formatear_fecha(f[0]) if f[0] else "No registrada",
                    'fecha_recepcion': formatear_fecha(f[1]) if f[1] else "No registrada",
                    'diagnostico': f[2] if f[2] else "",
                    'dias': f[3] if f[3] else 0,
                    'centro_medico': f[4] if f[4] else "",
                    'datos_adicionales': f[5] if f[5] else ""
                } for f in certificados_medicos],
                accidentes=[{
                    'fecha_acc': formatear_fecha(f[0]) if f[0] else "No registrada",
                    'fecha_alta': formatear_fecha(f[1]) if f[1] else "No registrada",
                    'dx': f[2] if f[2] else "",
                    'ambito': f[3] if f[3] else "",
                    'objetivo': f[4] if f[4] else "",
                    'n_siniestro': f[5] if f[5] else "",
                    'descripcion': f[6] if f[6] else ""
                } for f in accidentes],
                encabezados_conceptos=encabezados_conceptos,
                calificaciones=calificaciones,
                licencias_sin_goce=[{
                    'cantidad_dias': f[0] if f[0] else 0,
                    'desde_fecha': formatear_fecha(f[1]) if f[1] else "No registrada",
                    'hasta_fecha': formatear_fecha(f[2]) if f[2] else "No registrada",
                    'solicita': f[3] if f[3] else "",
                    'motivo': f[4] if f[4] else ""
                } for f in licencias_sin_goce]
            )

            # Generar PDF con WeasyPrint
            HTML(string=html_content).write_pdf(pdf_path)
            print(f"✅ PDF generado exitosamente en: {pdf_path}")

            # Cerrar conexiones de BD
            cursor.close()
            db_manager.return_connection(connection)

            # Ya no abrimos el PDF aquí, solo retornamos la ruta para abrirlo después
            return pdf_path  # Retornar la ruta del PDF en lugar de True

        else:
            messagebox.showerror("Error", f"No se encontró el legajo {legajo}")
            cursor.close()
            db_manager.return_connection(connection)
            return False

    except Exception as e:
        messagebox.showerror("Error", f"Error al generar el PDF: {str(e)}")
        print(f"❌ Error completo: {str(e)}")
        return False

# ------------------ Interfaz gráfica con CustomTkinter ------------------
import os
class ModuloAntecedentes(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Obtener estilos de la aplicación
        self.estilos = EstiloApp()
        
        # Configurar el estilo del frame principal
        self.configure(fg_color=self.estilos.COLOR_FONDO)
        
        # Crear componentes de la interfaz
        self.crear_widgets()
        
    def crear_widgets(self):
        """Crear todos los widgets de la interfaz"""
        # Header frame con logo - Nuevo
        self.header_frame = ctk.CTkFrame(self, fg_color=self.estilos.COLOR_PRIMARIO, height=200)
        self.header_frame.pack(fill="x", padx=0, pady=0)
        self.header_frame.pack_propagate(False)  # Mantener altura fija
        
        # Cargar logo
        try:
            # Corregir la ruta para apuntar a la subcarpeta icons_gifs
            logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons_gifs", "logo.gif")
            
            # Cargar el GIF animado
            self.logo_img = tk.PhotoImage(file=logo_path)
            
            # Label para el logo - Importante usar tk.Label para soportar animación GIF
            self.logo_label = tk.Label(self.header_frame, image=self.logo_img, bg=self.estilos.COLOR_PRIMARIO)
            self.logo_label.pack(side="left", padx=0)
            
            # Variables para controlar la animación
            self.frame_index = 0
            self.frames = []
            
            # Función para cargar todos los frames del GIF
            def load_gif_frames():
                try:
                    # Intentar cargar los frames del GIF
                    temp_img = tk.PhotoImage(file=logo_path)
                    
                    # Intentar determinar cuántos frames tiene el GIF
                    frame_count = 0
                    frames = []
                    
                    # Intentar cargar hasta 30 frames (número arbitrario, ajustar según sea necesario)
                    for i in range(37):
                        try:
                            # format='gif -index {i}' es la sintaxis para obtener un frame específico
                            frame = tk.PhotoImage(file=logo_path, format=f'gif -index {i}')
                            frames.append(frame)
                            frame_count += 1
                        except tk.TclError:
                            # Cuando no hay más frames, se lanza TclError
                            break
                    
                    print(f"✅ GIF cargado con {frame_count} frames")
                    return frames
                except Exception as e:
                    print(f"❌ Error cargando frames del GIF: {e}")
                    return []
            
            # Cargar los frames
            self.frames = load_gif_frames()
            
            # Función para actualizar la animación
            def update_animation():
                if self.frames:
                    # Actualizar al siguiente frame
                    self.frame_index = (self.frame_index + 1) % len(self.frames)
                    self.logo_label.configure(image=self.frames[self.frame_index])
                    # Programar la próxima actualización (100ms = 0.1s)
                    self.after(125, update_animation)
            
            # Iniciar la animación solo si hay frames
            if self.frames:
                self.after(100, update_animation)
            else:
                print("⚠️ No se pudieron cargar frames para animar el GIF")
            
        except Exception as e:
            print(f"❌ Error al cargar el logo: {e}")
        
        # Título del módulo en el header
        self.header_title = ctk.CTkLabel(
            self.header_frame,
            text="SISTEMA DE ANTECEDENTES LABORALES - RRHH",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white"
        )
        self.header_title.pack(side="left", padx=20)
        
        # Frame para título (ahora debajo del header)
        self.frame_titulo = ctk.CTkFrame(self, fg_color=self.estilos.COLOR_FONDO)
        self.frame_titulo.pack(fill="x", padx=20, pady=(10, 5))
        
        # Título
        self.lbl_titulo = ctk.CTkLabel(
            self.frame_titulo, 
            text="Generación y administración de informes de antecedentes laborales",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.estilos.COLOR_PRIMARIO
        )
        self.lbl_titulo.pack(pady=5)
        
        # Separador
        #self.separador = ctk.CTkFrame(self, height=2, fg_color=self.estilos.COLOR_SECUNDARIO)
        #self.separador.pack(fill="x", padx=20, pady=5)
        
        # Frame para formulario
        self.frame_form = ctk.CTkFrame(self, fg_color=self.estilos.COLOR_FONDO)
        self.frame_form.pack(fill="x", padx=20, pady=10)
        
        # Frame centrado para el legajo (nuevo)
        self.frame_legajo_container = ctk.CTkFrame(self.frame_form, fg_color=self.estilos.COLOR_FONDO)
        self.frame_legajo_container.pack(pady=15, padx=20, fill="x")
        
        # Etiqueta para legajo con estilo destacado
        self.lbl_legajo = ctk.CTkLabel(
            self.frame_legajo_container, 
            text="INGRESE NÚMERO DE LEGAJO:",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.estilos.COLOR_PRIMARIO
        )
        self.lbl_legajo.pack(pady=(0, 10))
        
        # Subtítulo explicativo
        self.lbl_legajo_subtitulo = ctk.CTkLabel(
            self.frame_legajo_container, 
            text="Ingrese el número de legajo para generar el informe completo de antecedentes",
            font=ctk.CTkFont(size=12),
            text_color=self.estilos.COLOR_TEXTO_SECUNDARIO
        )
        self.lbl_legajo_subtitulo.pack(pady=(0, 15))
        
        # Frame para el campo de entrada y botón
        self.frame_input = ctk.CTkFrame(self.frame_legajo_container, fg_color=self.estilos.COLOR_FONDO)
        self.frame_input.pack(fill="x")
        
        # Crear un frame contenedor para centrar los elementos
        self.frame_input_center = ctk.CTkFrame(self.frame_input, fg_color=self.estilos.COLOR_FONDO)
        self.frame_input_center.pack(pady=10, padx=20, anchor="center", expand=True)
        
        # Campo de entrada para legajo - Más grande y destacado, ahora centrado
        self.entry_legajo = ctk.CTkEntry(
            self.frame_input_center,
            width=100,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.estilos.COLOR_PRIMARIO,
            justify="center"  # Centrar el texto dentro del campo
        )
        self.entry_legajo.pack(pady=(0, 35))  # Añadir espacio debajo del campo
        
        # Vincular la tecla Enter al campo de legajo para generar el informe
        self.entry_legajo.bind("<Return>", lambda event: self.generar_informe())
        
        # Frame para botones
        self.frame_botones = ctk.CTkFrame(self.frame_input_center, fg_color=self.estilos.COLOR_FONDO)
        self.frame_botones.pack()
        
        # Botón para generar informe - Más grande para coincidir con el campo
        self.btn_generar = ctk.CTkButton(
            self.frame_botones,
            text="Generar Antecedentes",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.estilos.COLOR_PRIMARIO,
            hover_color=self.estilos.COLOR_SECUNDARIO,
            height=45,
            corner_radius=8,
            command=self.generar_informe
        )
        self.btn_generar.pack(side="left", padx=(0, 15))
        
        # Botón para abrir carpeta de informes
        self.btn_abrir_carpeta = ctk.CTkButton(
            self.frame_botones,
            text="Abrir Carpeta de Informes",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.estilos.COLOR_PRIMARIO,
            hover_color=self.estilos.COLOR_SECUNDARIO,
            height=45,
            corner_radius=8,
            command=self.abrir_carpeta_informes
        )
        self.btn_abrir_carpeta.pack(side="left")
        
        # Barra de progreso para mostrar el avance de la generación
        self.frame_progress = ctk.CTkFrame(self.frame_legajo_container, fg_color=self.estilos.COLOR_FONDO)
        self.frame_progress.pack(fill="x", pady=(15, 5))
        
        self.progress_bar = ctk.CTkProgressBar(
            self.frame_progress,
            width=400,
            height=15,
            corner_radius=5,
            mode="determinate",
            progress_color=self.estilos.COLOR_EXITO
        )
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)  # Inicialmente en 0
        
        # Etiqueta para mostrar el estado del progreso
        self.lbl_progress = ctk.CTkLabel(
            self.frame_progress,
            text="Listo para generar informe",
            font=ctk.CTkFont(size=12),
            text_color=self.estilos.COLOR_TEXTO_SECUNDARIO
        )
        self.lbl_progress.pack(pady=(0, 5))
        
        # Ocultar inicialmente la barra de progreso y su etiqueta
        self.frame_progress.pack_forget()
        
        # Frame para historial de informes
        self.frame_historial = ctk.CTkFrame(self, fg_color=self.estilos.COLOR_FONDO)
        self.frame_historial.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Frame para título y búsqueda
        self.frame_titulo_busqueda = ctk.CTkFrame(self.frame_historial, fg_color=self.estilos.COLOR_FONDO)
        self.frame_titulo_busqueda.pack(fill="x", pady=5, padx=10)
        
        # Etiqueta para historial
        self.lbl_historial = ctk.CTkLabel(
            self.frame_titulo_busqueda, 
            text="Historial de Informes Generados",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.estilos.COLOR_PRIMARIO
        )
        self.lbl_historial.pack(side="left", pady=5)
        
        # Frame para búsqueda
        self.frame_busqueda = ctk.CTkFrame(self.frame_titulo_busqueda, fg_color=self.estilos.COLOR_FONDO)
        self.frame_busqueda.pack(side="right", pady=5)
        
        # Etiqueta para búsqueda
        self.lbl_busqueda = ctk.CTkLabel(
            self.frame_busqueda, 
            text="Buscar:",
            font=ctk.CTkFont(size=12),
            text_color=self.estilos.COLOR_TEXTO
        )
        self.lbl_busqueda.pack(side="left", padx=(0, 5))
        
        # Campo de entrada para búsqueda
        self.entry_busqueda = ctk.CTkEntry(
            self.frame_busqueda,
            width=150,
            font=ctk.CTkFont(size=12),
            border_width=1
        )
        self.entry_busqueda.pack(side="left", padx=5)
        
        # Vincular evento de tecla para buscar mientras se escribe
        self.entry_busqueda.bind("<KeyRelease>", self.filtrar_treeview)
        
        # Botón para limpiar búsqueda
        self.btn_limpiar_busqueda = ctk.CTkButton(
            self.frame_busqueda,
            text="Limpiar",
            font=ctk.CTkFont(size=12),
            fg_color=self.estilos.COLOR_ERROR,
            hover_color=self.estilos.COLOR_ERROR_HOVER,
            width=70,
            command=self.limpiar_busqueda
        )
        self.btn_limpiar_busqueda.pack(side="left", padx=5)
        
        # Crear un frame para contener el Treeview
        self.frame_treeview = tk.Frame(self.frame_historial, bg=self.estilos.COLOR_FONDO_CLARO)
        self.frame_treeview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Estilo para el Treeview
        self.estilo = ttk.Style()
        self.estilo.theme_use('default')  # Usar tema default como base
        
        # Configurar colores y estilos del Treeview
        self.estilo.configure(
            "Treeview", 
            background=self.estilos.COLOR_FONDO_CLARO,
            foreground=self.estilos.COLOR_TEXTO,
            rowheight=25,
            fieldbackground=self.estilos.COLOR_FONDO_CLARO,
            font=('Helvetica', 12)
        )
        self.estilo.configure(
            "Treeview.Heading", 
            background=self.estilos.COLOR_PRIMARIO,
            foreground="white",
            font=('Helvetica', 14, 'bold')
        )
        # Color de selección
        self.estilo.map(
            'Treeview', 
            background=[('selected', self.estilos.COLOR_SECUNDARIO)],
            foreground=[('selected', 'white')]
        )
        
        # Configurar estilo moderno para el scrollbar
        self.estilo.configure(
            "Vertical.TScrollbar",
            background=self.estilos.COLOR_FONDO_CLARO,
            troughcolor=self.estilos.COLOR_FONDO,
            arrowcolor=self.estilos.COLOR_PRIMARIO,
            bordercolor=self.estilos.COLOR_FONDO,
            lightcolor=self.estilos.COLOR_SECUNDARIO,
            darkcolor=self.estilos.COLOR_PRIMARIO
        )
        
        # Crear scrollbar con el nuevo estilo
        scrollbar = ttk.Scrollbar(self.frame_treeview, style="Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Crear el Treeview
        self.treeview = ttk.Treeview(
            self.frame_treeview,
            columns=("legajo", "apellido", "fecha", "tamaño"),
            show="headings",
            yscrollcommand=scrollbar.set,
            style="Treeview"
        )
        
        # Configurar scrollbar
        scrollbar.config(command=self.treeview.yview)
        
        # Definir las columnas
        self.treeview.heading("legajo", text="Legajo")
        self.treeview.heading("apellido", text="Apellido")
        self.treeview.heading("fecha", text="Fecha/Hora")
        self.treeview.heading("tamaño", text="Tamaño (KB)")
        
        # Configurar anchos de columnas
        self.treeview.column("legajo", width=80, anchor="center")
        self.treeview.column("apellido", width=150, anchor="center")
        self.treeview.column("fecha", width=150, anchor="center")
        self.treeview.column("tamaño", width=100, anchor="center")
        
        # Empaquetar el Treeview
        self.treeview.pack(fill="both", expand=True)
        
        # Vincular evento de doble clic
        self.treeview.bind("<Double-1>", self.abrir_informe_seleccionado)
        
        # Botones de acción para informes - Aseguramos que use COLOR_FONDO
        self.frame_acciones = ctk.CTkFrame(self.frame_historial, fg_color=self.estilos.COLOR_FONDO)
        self.frame_acciones.pack(fill="x", padx=10, pady=(0, 10))
        
        # Botón para abrir informe seleccionado
        self.btn_abrir_informe = ctk.CTkButton(
            self.frame_acciones,
            text="Abrir Informe",
            font=ctk.CTkFont(size=12),
            fg_color=self.estilos.COLOR_PRIMARIO,
            hover_color=self.estilos.COLOR_SECUNDARIO,
            command=self.abrir_informe_seleccionado
        )
        self.btn_abrir_informe.pack(side="left", padx=5, pady=5)
        
        # Botón para regenerar informe
        self.btn_regenerar = ctk.CTkButton(
            self.frame_acciones,
            text="Regenerar Informe",
            font=ctk.CTkFont(size=12),
            fg_color=self.estilos.COLOR_EXITO,  # Color de éxito para regenerar
            hover_color=self.estilos.COLOR_EXITO_HOVER,
            command=self.regenerar_informe
        )
        self.btn_regenerar.pack(side="left", padx=5, pady=5)
        
        # Botón para eliminar informe
        self.btn_eliminar = ctk.CTkButton(
            self.frame_acciones,
            text="Eliminar Informe",
            font=ctk.CTkFont(size=12),
            fg_color=self.estilos.COLOR_ERROR,  # Color de error para eliminar
            hover_color=self.estilos.COLOR_ERROR_HOVER,
            command=self.eliminar_informe
        )
        self.btn_eliminar.pack(side="left", padx=5, pady=5)
        
        # Botón para actualizar lista
        self.btn_actualizar = ctk.CTkButton(
            self.frame_acciones,
            text="Actualizar Lista",
            font=ctk.CTkFont(size=12),
            fg_color=self.estilos.COLOR_ADVERTENCIA,  # Color de advertencia para actualizar
            hover_color=self.estilos.COLOR_ADVERTENCIA_HOVER,
            command=self.actualizar_lista_informes
        )
        self.btn_actualizar.pack(side="right", padx=5, pady=5)
        
        # Frame para status - Cambiamos de transparent a COLOR_FONDO
        self.frame_status = ctk.CTkFrame(self, height=30, fg_color=self.estilos.COLOR_FONDO)
        self.frame_status.pack(fill="x", padx=20, pady=(0, 10), side="bottom")
        
        # Etiqueta de estado
        self.lbl_status = ctk.CTkLabel(
            self.frame_status, 
            text="Listo para generar informes",
            font=ctk.CTkFont(size=12),
            text_color=self.estilos.COLOR_TEXTO
        )
        self.lbl_status.pack(side="left", padx=10)
        
        # Frame para footer con copyright - Aseguramos que use COLOR_FONDO_CLARO
        self.frame_footer = ctk.CTkFrame(self, height=25, fg_color=self.estilos.COLOR_FONDO_CLARO)
        self.frame_footer.pack(fill="x", side="bottom")
        
        # Etiqueta de copyright
        self.lbl_copyright = ctk.CTkLabel(
            self.frame_footer, 
            text=f"© {datetime.now().year} Todos los derechos reservados.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.estilos.COLOR_TEXTO_SECUNDARIO
        )
        self.lbl_copyright.pack(pady=5)
        
        # Cargar informes existentes
        self.actualizar_lista_informes()
    
    def actualizar_lista_informes(self):
        """Actualizar la lista de informes en el Treeview"""
        # Limpiar Treeview
        for item in self.treeview.get_children():
            self.treeview.delete(item)
        
        # Cargar informes
        informes = obtener_informes_generados()
        
        # Poblar Treeview
        for i, informe in enumerate(informes):
            # Alternar colores de fila
            tags = ('evenrow',) if i % 2 == 0 else ('oddrow',)
            
            self.treeview.insert(
                "", "end", 
                values=(
                    informe["legajo"],
                    informe["apellido"],
                    informe["fecha_modificacion"].strftime("%d/%m/%Y %H:%M"),
                    f"{informe['tamanio']:.1f}"
                ),
                tags=tags,
                iid=informe["ruta"]  # Usar la ruta completa como iid para facilitar el acceso
            )
        
        # Configurar colores alternos para filas
        self.estilo.map('Treeview', background=[
            ('selected', self.estilos.COLOR_SECUNDARIO),
        ])
        self.treeview.tag_configure('evenrow', background=self.estilos.COLOR_FONDO_CLARO)
        self.treeview.tag_configure('oddrow', background=self.estilos.COLOR_FONDO_ALTERNO)
        
        # Actualizar estado
        self.lbl_status.configure(text=f"Se encontraron {len(informes)} informes generados")
    
    def abrir_informe_seleccionado(self, event=None):
        """Abrir el informe seleccionado en el Treeview"""
        seleccion = self.treeview.selection()
        if seleccion:
            ruta_informe = seleccion[0]  # La ruta completa se usó como iid
            
            try:
                # Abrir el informe con el visor predeterminado
                webbrowser.open(ruta_informe)
                self.lbl_status.configure(text=f"Informe abierto: {os.path.basename(ruta_informe)}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el informe: {str(e)}")
                self.lbl_status.configure(text=f"Error al abrir el informe")
        else:
            messagebox.showwarning("Advertencia", "Selecciona un informe primero")
        
    def regenerar_informe(self):
        """Regenerar el informe seleccionado"""
        seleccion = self.treeview.selection()
        if seleccion:
            ruta_informe = seleccion[0]
            archivo = os.path.basename(ruta_informe)
            
            try:
                # Extraer legajo del nombre del archivo
                legajo = archivo.replace("Informe_", "").split("_")[0]
                
                # Convertir a entero
                legajo = int(legajo)
                
                # Generar nuevo informe
                self.entry_legajo.delete(0, 'end')
                self.entry_legajo.insert(0, str(legajo))
                self.generar_informe()
                
            except ValueError:
                messagebox.showerror("Error", "No se pudo extraer el legajo del nombre del archivo")
            except Exception as e:
                messagebox.showerror("Error", f"Error al regenerar informe: {str(e)}")
        else:
            messagebox.showwarning("Advertencia", "Selecciona un informe primero")
    
    def eliminar_informe(self):
        """Eliminar el informe seleccionado"""
        seleccion = self.treeview.selection()
        if seleccion:
            ruta_informe = seleccion[0]
            archivo = os.path.basename(ruta_informe)
            
            if messagebox.askyesno("Confirmar", f"¿Estás seguro de eliminar el informe:\n{archivo}?"):
                try:
                    os.remove(ruta_informe)
                    self.actualizar_lista_informes()
                    self.lbl_status.configure(text=f"Informe eliminado: {archivo}")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo eliminar el informe: {str(e)}")
        else:
            messagebox.showwarning("Advertencia", "Selecciona un informe primero")
        
    def generar_informe(self):
        """Generar informe para el legajo especificado"""
        try:
            legajo = self.entry_legajo.get().strip()
            if not legajo:
                messagebox.showwarning("Advertencia", "Por favor ingresa un número de legajo")
                return
                
            legajo = int(legajo)
            
            # Limpiar el campo de legajo inmediatamente después de obtener su valor
            self.entry_legajo.delete(0, 'end')
            
            # Verificar límite de informes diarios
            directorio_informes = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Informes")
            
            # Verificar si el directorio existe
            if not os.path.exists(directorio_informes):
                os.makedirs(directorio_informes)
            
            # Obtener la fecha actual en formato string YYYYMMDD
            fecha_hoy = datetime.now().strftime("%Y%m%d")
            
            # Buscar archivos con el patrón "Informe_{legajo}_*_{fecha_hoy}*.pdf"
            patron = f"Informe_{legajo}_*_{fecha_hoy}*.pdf"
            
            # Usar glob para encontrar archivos que coincidan con el patrón
            ruta_patron = os.path.join(directorio_informes, patron)
            archivos_hoy = glob.glob(ruta_patron)
            
            # Si ya hay 2 o más informes, mostrar advertencia
            if len(archivos_hoy) >= 2:
                print(f"DEBUG: Se encontraron {len(archivos_hoy)} informes para legajo {legajo} hoy")
                print(f"DEBUG: Archivos: {archivos_hoy}")
                
                resultado = messagebox.askyesno(
                    "Límite de informes diarios",
                    f"Ya se han generado {len(archivos_hoy)} informes para el legajo {legajo} hoy.\n\n"
                    f"Se recomienda no generar más de 2 informes por día para el mismo legajo.\n\n"
                    f"¿Desea generar otro informe de todos modos?"
                )
                if not resultado:
                    self.lbl_status.configure(text=f"Generación cancelada: límite diario alcanzado para legajo {legajo}")
                    return
            
            # Mostrar la barra de progreso
            self.frame_progress.pack(fill="x", pady=(15, 10))
            self.progress_bar.set(0)
            self.lbl_progress.configure(text="Iniciando generación del informe...")
            self.update_idletasks()
            
            # Actualizar estado
            self.lbl_status.configure(text=f"Generando informe para legajo {legajo}...")
            
            # Simular progreso durante la generación
            def update_progress_bar():
                progress_steps = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
                progress_messages = [
                    "Conectando a la base de datos...",
                    "Obteniendo datos personales...",
                    "Procesando historial de felicitaciones...",
                    "Procesando historial de sanciones...",
                    "Procesando préstamos...",
                    "Procesando certificados médicos...",
                    "Procesando conceptos...",
                    "Generando documento PDF...",
                    "Finalizando informe..."
                ]
                
                for i, (step, message) in enumerate(zip(progress_steps, progress_messages)):
                    self.progress_bar.set(step)
                    self.lbl_progress.configure(text=message)
                    self.update_idletasks()
                    time.sleep(0.5)  # Pequeña pausa para visualizar el progreso
            
            # Ejecutar en un hilo separado para no bloquear la interfaz
            def ejecutar_generacion():
                try:
                    # Actualizar la barra de progreso en el hilo principal
                    self.after(0, update_progress_bar)
                    
                    # Generar el informe
                    resultado = generar_primer_nivel(legajo)
                    
                    # Actualizar la interfaz desde el hilo principal
                    self.after(0, lambda: self.actualizar_estado_generacion(resultado, legajo))
                except Exception as e:
                    self.after(0, lambda: self.mostrar_error_generacion(str(e)))
            
            threading.Thread(target=ejecutar_generacion, daemon=True).start()
            
        except ValueError:
            messagebox.showerror("Error", "El legajo debe ser un número entero")
            self.lbl_status.configure(text="Error: El legajo debe ser un número entero")
            # Ocultar barra de progreso en caso de error
            if hasattr(self, 'frame_progress') and self.frame_progress.winfo_ismapped():
                self.frame_progress.pack_forget()
        except Exception as e:
            messagebox.showerror("Error", f"Error al generar informe: {str(e)}")
            self.lbl_status.configure(text="Error al generar informe")
            print(f"ERROR COMPLETO: {str(e)}")
            # Ocultar barra de progreso en caso de error
            if hasattr(self, 'frame_progress') and self.frame_progress.winfo_ismapped():
                self.frame_progress.pack_forget()
        
    def actualizar_estado_generacion(self, resultado, legajo):
        """Actualizar el estado después de generar un informe"""
        if resultado:  # resultado ahora contiene la ruta del PDF
            # Completar la barra de progreso
            self.progress_bar.set(1.0)
            self.lbl_progress.configure(text="¡Informe generado exitosamente!")
            self.lbl_status.configure(text=f"Informe generado exitosamente para legajo {legajo}")
            
            # Actualizar la lista de informes
            self.actualizar_lista_informes()
            
            # Guardar la ruta del PDF para abrirlo después
            self.ultimo_pdf_generado = resultado
            
            # Programar la apertura del PDF después de un breve retraso
            self.after(1500, self.abrir_ultimo_pdf)
            
            # Ocultar la barra de progreso después de 3 segundos
            self.after(3000, self.frame_progress.pack_forget)
        else:
            self.lbl_status.configure(text=f"Error al generar informe para legajo {legajo}")
            self.frame_progress.pack_forget()

    def mostrar_error_generacion(self, mensaje_error):
        """Mostrar error durante la generación"""
        self.progress_bar.set(0)
        self.lbl_progress.configure(text=f"Error: {mensaje_error}")
        self.lbl_status.configure(text="Error al generar informe")
        
        # Ocultar la barra de progreso después de 3 segundos
        self.after(3000, self.frame_progress.pack_forget)
    
    def abrir_carpeta_informes(self):
        """Abrir la carpeta donde se guardan los informes"""
        directorio_informes = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Informes")
        if not os.path.exists(directorio_informes):
            os.makedirs(directorio_informes)
        
        # Abrir carpeta según el sistema operativo
        if os.name == 'nt':  # Windows
            os.startfile(directorio_informes)
        else:  # Mac, Linux
            try:
                import subprocess
                subprocess.Popen(['xdg-open', directorio_informes])
            except:
                try:
                    subprocess.Popen(['open', directorio_informes])
                except:
                    messagebox.showerror("Error", "No se pudo abrir la carpeta de informes.")
                    return

        self.lbl_status.configure(text=f"Carpeta de informes abierta: {directorio_informes}")

    def filtrar_treeview(self, event=None):
        """Filtra los elementos del TreeView según el texto de búsqueda"""
        texto_busqueda = self.entry_busqueda.get().lower()
        
        # Si no hay texto de búsqueda, mostrar todos los elementos
        if not texto_busqueda:
            self.actualizar_lista_informes()
            return
        
        # Limpiar TreeView
        for item in self.treeview.get_children():
            self.treeview.delete(item)
        
        # Cargar informes
        informes = obtener_informes_generados()
        
        # Filtrar y mostrar solo los que coinciden con la búsqueda
        informes_filtrados = []
        for informe in informes:
            # Buscar solo en legajo y apellido
            if (texto_busqueda in str(informe["legajo"]).lower() or 
                texto_busqueda in informe["apellido"].lower()):
                informes_filtrados.append(informe)
        
        # Poblar TreeView con resultados filtrados
        for i, informe in enumerate(informes_filtrados):
            # Alternar colores de fila
            tags = ('evenrow',) if i % 2 == 0 else ('oddrow',)
            
            self.treeview.insert(
                "", "end", 
                values=(
                    informe["legajo"],
                    informe["apellido"],
                    informe["fecha_modificacion"].strftime("%d/%m/%Y %H:%M"),
                    f"{informe['tamanio']:.1f}"
                ),
                tags=tags,
                iid=informe["ruta"]  # Usar la ruta completa como iid para facilitar el acceso
            )
        
        # Actualizar estado
        self.lbl_status.configure(text=f"Se encontraron {len(informes_filtrados)} informes que coinciden con '{texto_busqueda}' (por legajo o apellido)")
    
    def limpiar_busqueda(self):
        """Limpia el campo de búsqueda y muestra todos los elementos"""
        self.entry_busqueda.delete(0, 'end')
        self.actualizar_lista_informes()
        self.lbl_status.configure(text="Búsqueda limpiada, mostrando todos los informes")

    def abrir_ultimo_pdf(self):
        """Abrir el último PDF generado"""
        if hasattr(self, 'ultimo_pdf_generado') and self.ultimo_pdf_generado:
            try:
                # Abrir el PDF con el visor predeterminado
                webbrowser.open(self.ultimo_pdf_generado)
                print(f"✅ PDF abierto: {self.ultimo_pdf_generado}")
            except Exception as e:
                print(f"❌ Error al abrir el PDF: {str(e)}")
                messagebox.showerror("Error", f"No se pudo abrir el informe: {str(e)}")

# Función principal para crear y mostrar el módulo
def crear_modulo(parent_frame):
    """
    Crea y devuelve una instancia del módulo de antecedentes
    
    Args:
        parent_frame: El frame padre donde se integrará el módulo
        
    Returns:
        ModuloAntecedentes: Instancia del módulo
    """
    modulo = ModuloAntecedentes(parent_frame)
    modulo.pack(fill="both", expand=True)
    return modulo

# Función para ejecutar el módulo de forma independiente (para pruebas)
def ejecutar_independiente():
    """Ejecuta el módulo en modo standalone para pruebas"""
    root = ctk.CTk()
    root.title("Módulo de Antecedentes Laborales")
    root.geometry("1200x800")  # Tamaño más grande para mejor visualización
    
    # Configurar tema
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    
    # Crear módulo
    modulo = ModuloAntecedentes(root)
    modulo.pack(fill="both", expand=True)
    
    # Función para manejar el cierre
    def on_closing():
        db_manager.close()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

# Ejecutar módulo si se corre directamente
if __name__ == "__main__":
    ejecutar_independiente() 