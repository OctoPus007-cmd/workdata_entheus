# Importar las mismas dependencias que el módulo de felicitaciones
import customtkinter as ctk
from tkcalendar import DateEntry
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import mysql.connector
import threading
from concurrent.futures import ThreadPoolExecutor
from CTkTable import CTkTable
from PIL import Image, ImageTk, ImageSequence
import io
import logging
from datetime import datetime
import traceback
import os
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de tema y colores (igual que en felicitaciones)
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class EstiloApp:
    """Clase para definir los colores y estilos de la aplicación"""
    COLOR_PRINCIPAL = "#E3F2FD"
    COLOR_SECUNDARIO = "#90CAF9"
    COLOR_HOVER = "#64B5F6"
    COLOR_TEXTO = "#000000"
    COLOR_FRAMES = "#BBDEFB"
    COLOR_HEADER = "#FFFFFF"
    
    # Nuevos colores para botones CRUD
    BOTON_INSERTAR = "#4CAF50"
    BOTON_INSERTAR_HOVER = "#45A049"
    BOTON_MODIFICAR = "#2196F3"
    BOTON_MODIFICAR_HOVER = "#1976D2"
    BOTON_ELIMINAR = "#F44336"
    BOTON_ELIMINAR_HOVER = "#D32F2F"
    BOTON_LIMPIAR = "#757575"
    BOTON_LIMPIAR_HOVER = "#616161"

class DatabasePool:
    """Clase para manejar el pool de conexiones a la base de datos"""
    def __init__(self):
        self.config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_DATABASE')
        }
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.connection_pool = []
        self._initialize_pool()

    def _initialize_pool(self, pool_size=3):
        """Inicializar el pool de conexiones"""
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
        def _async_query():
            connection = None
            cursor = None
            try:
                connection = self.get_connection()
                cursor = connection.cursor(buffered=True)
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if query.strip().lower().startswith('select'):
                    result = cursor.fetchall()
                else:
                    connection.commit()
                    result = True

                if callback:
                    callback(result)
                
            except Exception as e:
                if callback:
                    callback(None)
                print(f"Error en consulta: {str(e)}")
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.return_connection(connection)

        self.executor.submit(_async_query)

    def close(self):
        """Cerrar todas las conexiones y el executor"""
        for conn in self.connection_pool:
            try:
                conn.close()
            except:
                pass
        self.executor.shutdown(wait=True)

class AplicacionCertificadosMedicos:
    def __init__(self, parent_frame=None):
        """
        Inicializa la aplicación de certificados médicos.
        Args:
            parent_frame: Si se proporciona, la aplicación se mostrará dentro de este frame.
                         Si es None, se creará una ventana independiente.
        """
        self.is_destroyed = False
        self.mensaje_dialog = None
        self.dialogo_confirmacion = None
        self.certificado_seleccionado_id = None
        self.animation_running = False  # Control de animación
        self.loading_label = None  # Inicializar explícitamente como None
        
        # Configurar el sistema de logging
        self._setup_logging()
        
        self.db_pool = None
        
        if parent_frame is None:
            # Modo standalone: crear ventana independiente
            self.root = ctk.CTk()
            self.root.title("Módulo de Certificados Médicos")
            self.root.geometry("1280x720")
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Iniciar asíncronamente
            self.root.after(100, self._init_async)
        else:
            # Mostrar dentro de un frame existente
            self.show_in_frame(parent_frame)

    def _setup_logging(self):
        """Configurar el sistema de logging"""
        # Crear directorio logs si no existe
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Configurar el logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Verificar si ya tiene handlers para evitar duplicados
        if not self.logger.handlers:
            # Configurar formato
            formatter = logging.Formatter(
                '%(asctime)s - [%(levelname)s] - %(module)s - Línea %(lineno)d: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Configurar handler para archivo
            file_handler = logging.FileHandler(
                os.path.join(log_dir, 'certificados_medicos.log'), 
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def setup_window(self):
        """Configuración inicial de la ventana"""
        self.root.title("Sistema de Gestión de Certificados Médicos")
        # Obtener dimensiones de la pantalla
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Establecer geometría inicial (necesario antes de maximizar)
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Maximizar la ventana
        self.root.state('zoomed')  # Para Windows
        # self.root.attributes('-zoomed', True)  # Para Linux
        
        self.root.configure(fg_color=EstiloApp.COLOR_PRINCIPAL)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

    def create_gui(self):
        """Crear la interfaz gráfica completa"""
        self._create_header_frame()
        
        self.main_frame = ctk.CTkFrame(
            self.root,
            fg_color=EstiloApp.COLOR_PRINCIPAL
        )
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=(140, 150))
        
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_rowconfigure(1, weight=2)
        
        self._create_form()
        self._create_table()

    def _create_form(self):
        """Crear el formulario principal"""
        form_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        form_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 0))
        form_frame.grid_columnconfigure(1, weight=0)

        # Panel izquierdo (formulario)
        left_panel = ctk.CTkFrame(form_frame, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nw", padx=20, pady=20)
        
        # Título
        title_label = ctk.CTkLabel(
            left_panel,
            text="Gestión de Certificados Médicos",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, ))
        
        # Campos del formulario
        self.crear_campos_formulario(left_panel)
  
        # Panel central (foto y datos empleado)
        self._create_employee_info_panel(form_frame)
        
        # Panel derecho (botones CRUD)
        self._create_crud_buttons(form_frame)

    def crear_campos_formulario(self, parent):
        """Crear campos del formulario con nueva disposición en grid"""
        form_container = ctk.CTkFrame(parent, fg_color="transparent")
        form_container.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        
        # Configurar el grid para mejor distribución - 2 columnas principales
        form_container.grid_columnconfigure(1, weight=1)  # Columna para campos cortos
        form_container.grid_columnconfigure(3, weight=1)  # Columna para campos largos

        # Definir campos y sus posiciones con tamaños más pequeños
        fields = [
            # Primera columna (campos cortos)
            ("Legajo:", "entry_legajo", 0, 0, "entry", 120),
            ("Fecha Atención:", "entry_fecha_atencion", 1, 0, "date", 120),
            ("Fecha Recepción:", "entry_fecha_recepcion", 2, 0, "date", 120),
            ("Días:", "entry_cantidad_dias", 3, 0, "entry", 120),
            
            # Segunda columna (campos largos)
            ("Diagnóstico:", "entry_diagnostico", 0, 2, "entry", 300),
            ("Médico/Hospital:", "text_medico_hospital", 1, 2, "entry", 300),  # Cambiado a entry
            ("Datos Adicionales:", "entry_datos_adicionales", 2, 2, "textbox", 300, 2)  # Agregado rowspan=2
        ]

        # Crear campos
        for field in fields:
            # Label
            label = ctk.CTkLabel(
                form_container,
                text=field[0],
                font=('Roboto', 12, 'bold'),
                anchor="e"
            )
            label.grid(row=field[2], column=field[3], padx=(5, 5), pady=3, sticky="e")

            # Widget
            if field[4] == "date":
                # Frame contenedor para DateEntry
                date_frame = ctk.CTkFrame(
                    form_container,
                    fg_color=EstiloApp.COLOR_PRINCIPAL,
                    height=28,
                    width=field[5],
                    border_width=1,
                    border_color=EstiloApp.COLOR_SECUNDARIO,
                    corner_radius=5
                )
                date_frame.grid(row=field[2], column=field[3]+1, sticky="w", padx=5, pady=3)
                date_frame.grid_propagate(False)
                
                widget = DateEntry(
                    date_frame,
                    width=12,
                    background=EstiloApp.COLOR_PRINCIPAL,
                    foreground='black',
                    borderwidth=0,
                    font=('Roboto', 12),
                    date_pattern='dd-mm-yyyy',
                    style='Custom.DateEntry',
                    justify='center',
                    locale='es'
                )
                widget.pack(expand=True, fill='both', padx=3, pady=1)
                
            elif field[4] == "textbox":
                # TextBox para campos de texto largo
                widget = ctk.CTkTextbox(
                    form_container,
                    height=60,  # Altura para 2 filas
                    width=field[5],
                    font=('Roboto', 12),
                    border_width=1,
                    border_color=EstiloApp.COLOR_SECUNDARIO,
                    corner_radius=5
                )
                widget.grid(row=field[2], column=field[3]+1, rowspan=field[6], sticky="w", padx=5, pady=3)
            
            else:  # entry normal
                widget = ctk.CTkEntry(
                    form_container,
                    height=28,
                    width=field[5],
                    font=('Roboto', 12),
                    justify='left' if field[3] == 2 else 'center',
                    border_width=1,
                    border_color=EstiloApp.COLOR_SECUNDARIO,
                    corner_radius=5
                )
                widget.grid(row=field[2], column=field[3]+1, sticky="w", padx=5, pady=3)

            setattr(self, field[1], widget)

            # Vincular eventos al campo legajo
            if field[1] == "entry_legajo":
                widget.bind('<FocusOut>', self.consultar_empleado)
                widget.bind('<Return>', self.consultar_empleado)

    def _create_employee_info_panel(self, parent):
        """Crear panel de información del empleado y estadísticas de certificados"""
        info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="n", padx=20, pady=20)
        
        # Frame para la foto
        photo_frame = ctk.CTkFrame(
            info_frame,
            fg_color=EstiloApp.COLOR_PRINCIPAL,
            corner_radius=10,
            border_width=2,
            border_color=EstiloApp.COLOR_SECUNDARIO,
            width=145,
            height=145
        )
        photo_frame.pack(pady=(0, 0))
        photo_frame.pack_propagate(False)

        # Canvas para la foto
        self.photo_canvas = ctk.CTkCanvas(
            photo_frame,
            width=145,
            height=145,
            bg=EstiloApp.COLOR_PRINCIPAL,
            highlightthickness=0
        )
        self.photo_canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Placeholder inicial para la foto
        self.photo_canvas.create_oval(
            40, 40, 160, 160,
            fill=EstiloApp.COLOR_SECUNDARIO,
            outline=EstiloApp.COLOR_SECUNDARIO
        )
        self.photo_canvas.create_text(
            50, 50,
            text="Sin\nfoto",
            fill=EstiloApp.COLOR_TEXTO,
            font=('Helvetica', 10, 'bold'),
            justify='center'
        )

        # Frame para datos del empleado y estadísticas
        data_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        data_frame.pack(pady=(5, 0))

        # Información del empleado
        self.nombre_completo_label = ctk.CTkLabel(
            data_frame,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
            width=250
        )
        self.nombre_completo_label.pack(pady=(0, 0))

        # Separador visual
        separator = ctk.CTkFrame(
            data_frame,
            height=2,
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            width=230
        )
        separator.pack(pady=(0, 0))

        # Estadísticas de certificados médicos
        self.total_certificados_label = ctk.CTkLabel(
            data_frame,
            text="Total Certificados: 0",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
            width=250
        )
        self.total_certificados_label.pack(pady=(0, 0))

        self.total_dias_label = ctk.CTkLabel(
            data_frame,
            text="Total de días de reposo: 0",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
            width=250
        )
        self.total_dias_label.pack(pady=(0, 0))

        self.ultimo_certificado_label = ctk.CTkLabel(
            data_frame,
            text="Último Certificado: Sin registros",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
            width=250
        )
        self.ultimo_certificado_label.pack(pady=(0, 0))

    def _create_crud_buttons(self, parent):
        """Crear botones CRUD"""
        buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        buttons_frame.grid(row=0, column=2, sticky="ne", padx=2, pady=20)

        buttons = [
            ("Insertar", self.insertar_certificado_medico, EstiloApp.BOTON_INSERTAR, EstiloApp.BOTON_INSERTAR_HOVER),
            ("Modificar", self.modificar_certificado_medico, EstiloApp.BOTON_MODIFICAR, EstiloApp.BOTON_MODIFICAR_HOVER),
            ("Eliminar", self.eliminar_certificado_medico, EstiloApp.BOTON_ELIMINAR, EstiloApp.BOTON_ELIMINAR_HOVER),
            ("Limpiar Todo", self.limpiar_campos, EstiloApp.BOTON_LIMPIAR, EstiloApp.BOTON_LIMPIAR_HOVER)
        ]

        for idx, (text, command, color, hover_color) in enumerate(buttons):
            ctk.CTkButton(
                buttons_frame,
                text=text,
                command=command,
                font=ctk.CTkFont(size=14),
                fg_color=color,
                hover_color=hover_color,
                height=35,
                width=120,
                text_color="white"
            ).grid(row=idx, column=0, pady=5)

    def _create_table(self):
        """Crear tabla de certificados médicos"""
        table_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        table_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 15))
        
        title_label = ctk.CTkLabel(
            table_frame,
            text="Historial de Certificados Médicos",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(15, 10))

        # Frame para la tabla con scrollbars
        tree_container = ctk.CTkFrame(table_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Crear Treeview
        self.tree = ttk.Treeview(
            tree_container,
            columns=("id", "legajo", "fecha_atencion", "fecha_recepcion", 
                    "diagnostico", "dias", "medico", "datos_adicionales"),
            show="headings",
            style="Custom.Treeview"
        )
        
        # Configurar scrollbars
        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Configurar columnas
        columnas = {
            "id": {"texto": "ID", "ancho": 0},
            "legajo": {"texto": "Legajo", "ancho": 100},
            "fecha_atencion": {"texto": "Fecha Atención", "ancho": 100},
            "fecha_recepcion": {"texto": "Fecha Recepción", "ancho": 100},
            "diagnostico": {"texto": "Diagnóstico/Causa", "ancho": 200},
            "dias": {"texto": "Días", "ancho": 50},
            "medico": {"texto": "Médico/Hospital/Clínica", "ancho": 100},
            "datos_adicionales": {"texto": "Datos Adicionales", "ancho": 200}
        }
        
        # Aplicar configuración a las columnas
        for col, config in columnas.items():
            self.tree.heading(col, text=config["texto"], anchor="center")
            self.tree.column(col, width=config["ancho"], anchor="center")
            
            # Ocultar columna ID
            if col == "id":
                self.tree.column(col, width=0, stretch=False)

        # Ubicar componentes
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)
        
        # Agregar el binding para doble clic y clic derecho
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.mostrar_diagnostico_completo)
        
        # Configurar estilo de la tabla
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            background=EstiloApp.COLOR_PRINCIPAL,
            fieldbackground=EstiloApp.COLOR_PRINCIPAL,
            foreground=EstiloApp.COLOR_TEXTO,
            rowheight=25,
            font=('Roboto', 10)
        )
        
        style.configure(
            "Custom.Treeview.Heading",
            background=EstiloApp.COLOR_SECUNDARIO,
            foreground=EstiloApp.COLOR_TEXTO,
            relief="flat",
            font=('Roboto', 10, 'bold')
        )
        
        # Configurar selección
        style.map(
            "Custom.Treeview",
            background=[("selected", EstiloApp.COLOR_HOVER)],
            foreground=[("selected", "white")]
        )

        # Agregar el binding para la selección
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)

    def insertar_certificado_medico(self):
        """Insertar nuevo certificado médico"""
        if not self.validar_campos():
            return

        def _insertar():
            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                cursor = connection.cursor()
                
                # Validar empleado
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM personal 
                    WHERE legajo = %s
                """, (int(self.entry_legajo.get()),))
                
                if cursor.fetchone()[0] == 0:
                    raise ValueError("El legajo no existe en la base de datos")
                
                # Validar que no exista un certificado para la misma fecha
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM certificados_medicos 
                    WHERE legajo = %s AND fecha_atencion_medica = %s
                """, (
                    int(self.entry_legajo.get()),
                    datetime.strptime(self.entry_fecha_atencion.get(), "%d-%m-%Y").strftime("%Y-%m-%d")
                ))
                
                if cursor.fetchone()[0] > 0:
                    raise ValueError("Ya existe un certificado para esta fecha de atención")
                
                # Convertir fechas
                fecha_atencion_sql = datetime.strptime(self.entry_fecha_atencion.get(), "%d-%m-%Y").strftime("%Y-%m-%d")
                fecha_recepcion_sql = datetime.strptime(self.entry_fecha_recepcion.get(), "%d-%m-%Y").strftime("%Y-%m-%d")
                
                sql = """
                INSERT INTO certificados_medicos 
                (legajo, fecha_atencion_medica, fecha_recepcion_certificado, 
                 diagnostico_causa, cantidad_dias, medico_hospital_clinica, datos_adicionales)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                
                datos = (
                    int(self.entry_legajo.get()),
                    fecha_atencion_sql,
                    fecha_recepcion_sql,
                    self.entry_diagnostico.get().strip(),
                    int(self.entry_cantidad_dias.get()),
                    self.text_medico_hospital.get().strip(),
                    self.entry_datos_adicionales.get("1.0", tk.END).strip()
                )
                
                cursor.execute(sql, datos)
                connection.commit()
                
                legajo = self.entry_legajo.get()
                self.logger.info(f"Certificado médico insertado exitosamente para legajo {legajo}")
                
                # Consultar estadísticas actualizadas
                cursor.execute("""
                    SELECT 
                        COUNT(cm.id) as total_certificados,
                        COALESCE(SUM(cm.cantidad_dias), 0) as total_dias,
                        MAX(cm.fecha_atencion_medica) as ultimo_certificado,
                        COALESCE(SUM(CASE 
                            WHEN cm.fecha_atencion_medica >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                            THEN cm.cantidad_dias 
                            ELSE 0 
                        END), 0) as dias_ultimo_anio
                    FROM certificados_medicos cm
                    WHERE cm.legajo = %s
                """, (legajo,))
                
                stats = cursor.fetchone()
                if stats:
                    total_certificados, total_dias, ultimo_certificado, dias_ultimo_anio = stats
                    
                    if not self.is_destroyed:
                        def _actualizar_vista():
                            # Verificar que los widgets existan antes de actualizarlos
                            if hasattr(self, 'total_certificados_label') and self.total_certificados_label.winfo_exists():
                                self.total_certificados_label.configure(
                                    text=f"Total Certificados: {total_certificados}"
                                )
                            if hasattr(self, 'total_dias_label') and self.total_dias_label.winfo_exists():
                                self.total_dias_label.configure(
                                    text=f"Total de días de reposo: {total_dias} (Último año: {dias_ultimo_anio})"
                                )
                            if hasattr(self, 'ultimo_certificado_label') and self.ultimo_certificado_label.winfo_exists():
                                if ultimo_certificado:
                                    fecha_formato = ultimo_certificado.strftime('%d-%m-%Y')
                                    self.ultimo_certificado_label.configure(
                                        text=f"Último Certificado: {fecha_formato}"
                                    )
                            
                            # Mostrar mensaje y actualizar vista
                            self.mostrar_mensaje("Éxito", "Certificado médico registrado correctamente")
                            self.limpiar_campos_parcial()
                            self.consultar_certificados(legajo)
                        
                        self.root.after(0, _actualizar_vista)
                
            except ValueError as ve:
                if connection:
                    connection.rollback()
                if not self.is_destroyed:
                    self.root.after(0, lambda msg=str(ve): self.handle_database_error(msg, "insertar_certificado_medico"))
                
            except Exception as e:
                if connection:
                    connection.rollback()
                self.logger.error(f"Error al insertar certificado: {str(e)}")
                if not self.is_destroyed:
                    error_msg = str(e)  # Capturar el mensaje de error
                    self.root.after(0, lambda msg=error_msg: self.handle_database_error(msg, "insertar_certificado_medico"))
                
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        self.db_pool.executor.submit(_insertar)

    def modificar_certificado_medico(self):
        """Modificar certificado médico seleccionado"""
        if not self.certificado_seleccionado_id:
            self.mostrar_mensaje("Error", "Debe seleccionar un certificado para modificar")
            return

        if not self.validar_campos():
            return

        def _modificar():
            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                cursor = connection.cursor()
                
                # Validar que el certificado aún existe
                cursor.execute("""
                    SELECT legajo 
                    FROM certificados_medicos 
                    WHERE id = %s
                """, (self.certificado_seleccionado_id,))
                
                resultado = cursor.fetchone()
                if not resultado:
                    raise ValueError("El certificado seleccionado ya no existe")
                
                legajo_original = resultado[0]
                
                # Validar empleado
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM personal 
                    WHERE legajo = %s
                """, (int(self.entry_legajo.get()),))
                
                if cursor.fetchone()[0] == 0:
                    raise ValueError("El legajo no existe")
                
                # Validar duplicados en fecha (excluyendo el registro actual)
                fecha_atencion_sql = datetime.strptime(self.entry_fecha_atencion.get(), "%d-%m-%Y").strftime("%Y-%m-%d")
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM certificados_medicos 
                    WHERE legajo = %s 
                    AND fecha_atencion_medica = %s 
                    AND id != %s
                """, (
                    int(self.entry_legajo.get()),
                    fecha_atencion_sql,
                    self.certificado_seleccionado_id
                ))
                
                if cursor.fetchone()[0] > 0:
                    raise ValueError("Ya existe un certificado para esta fecha de atención")
                
                # Convertir fechas
                fecha_recepcion_sql = datetime.strptime(self.entry_fecha_recepcion.get(), "%d-%m-%Y").strftime("%Y-%m-%d")
                
                sql = """
                UPDATE certificados_medicos 
                SET legajo = %s, 
                    fecha_atencion_medica = %s,
                    fecha_recepcion_certificado = %s,
                    diagnostico_causa = %s,
                    cantidad_dias = %s,
                    medico_hospital_clinica = %s,
                    datos_adicionales = %s
                WHERE id = %s
                """
                
                datos = (
                    int(self.entry_legajo.get()),
                    fecha_atencion_sql,
                    fecha_recepcion_sql,
                    self.entry_diagnostico.get().strip(),
                    int(self.entry_cantidad_dias.get()),
                    self.text_medico_hospital.get().strip(),
                    self.entry_datos_adicionales.get("1.0", tk.END).strip(),
                    self.certificado_seleccionado_id
                )
                
                cursor.execute(sql, datos)
                connection.commit()
                
                legajo = self.entry_legajo.get()
                self.logger.info(f"Certificado médico {self.certificado_seleccionado_id} modificado exitosamente")
                
                # Consultar estadísticas actualizadas
                cursor.execute("""
                    SELECT 
                        COUNT(cm.id) as total_certificados,
                        COALESCE(SUM(cm.cantidad_dias), 0) as total_dias,
                        MAX(cm.fecha_atencion_medica) as ultimo_certificado,
                        COALESCE(SUM(CASE 
                            WHEN cm.fecha_atencion_medica >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                            THEN cm.cantidad_dias 
                            ELSE 0 
                        END), 0) as dias_ultimo_anio
                    FROM certificados_medicos cm
                    WHERE cm.legajo = %s
                """, (legajo,))
                
                stats = cursor.fetchone()
                if stats:
                    total_certificados, total_dias, ultimo_certificado, dias_ultimo_anio = stats
                    
                    if not self.is_destroyed:
                        def _actualizar_vista():
                            # Verificar que los widgets existan antes de actualizarlos
                            if hasattr(self, 'total_certificados_label') and self.total_certificados_label.winfo_exists():
                                self.total_certificados_label.configure(
                                    text=f"Total Certificados: {total_certificados}"
                                )
                            if hasattr(self, 'total_dias_label') and self.total_dias_label.winfo_exists():
                                self.total_dias_label.configure(
                                    text=f"Total de días de reposo: {total_dias} (Último año: {dias_ultimo_anio})"
                                )
                            if hasattr(self, 'ultimo_certificado_label') and self.ultimo_certificado_label.winfo_exists():
                                if ultimo_certificado:
                                    fecha_formato = ultimo_certificado.strftime('%d-%m-%Y')
                                    self.ultimo_certificado_label.configure(
                                        text=f"Último Certificado: {fecha_formato}"
                                    )
                            
                            # Mostrar mensaje y actualizar vista
                            self.mostrar_mensaje("Éxito", "Certificado médico modificado correctamente")
                            self.limpiar_campos_parcial()
                            self.consultar_certificados(legajo)
                        
                        self.root.after(0, _actualizar_vista)
                
            except ValueError as ve:
                if connection:
                    connection.rollback()
                if not self.is_destroyed:
                    self.root.after(0, lambda msg=str(ve): self.handle_database_error(msg, "modificar_certificado_medico"))
                
            except Exception as e:
                if connection:
                    connection.rollback()
                self.logger.error(f"Error al modificar certificado: {str(e)}")
                if not self.is_destroyed:
                    error_msg = str(e)
                    self.root.after(0, lambda msg=error_msg: self.handle_database_error(msg, "modificar_certificado_medico"))
                
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        self._mostrar_dialogo_confirmacion(
            "Confirmar modificación",
            "¿Está seguro que desea modificar este certificado médico?",
            lambda: self.db_pool.executor.submit(_modificar)
        )

    def eliminar_certificado_medico(self):
        """Eliminar certificado médico seleccionado"""
        seleccion = self.tree.selection()
        if not seleccion:
            self.mostrar_mensaje("Error", "Debe seleccionar un certificado para eliminar")
            return

        def _eliminar():
            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                cursor = connection.cursor()
                
                item = self.tree.selection()[0]
                valores = self.tree.item(item)['values']
                
                if not valores:
                    raise ValueError("No se pudo obtener la información del certificado seleccionado")
                
                id_certificado = valores[0]
                
                # Validar que el certificado aún existe y obtener información
                cursor.execute("""
                    SELECT cm.id, cm.legajo, p.apellido_nombre 
                    FROM certificados_medicos cm
                    JOIN personal p ON cm.legajo = p.legajo
                    WHERE cm.id = %s
                """, (id_certificado,))
                
                resultado = cursor.fetchone()
                if not resultado:
                    raise ValueError("El certificado seleccionado ya no existe")
                
                # Guardar información para el log
                id_cert, legajo_cert, nombre_empleado = resultado
                
                # Realizar eliminación física
                sql = "DELETE FROM certificados_medicos WHERE id = %s"
                cursor.execute(sql, (id_certificado,))
                connection.commit()
                
                legajo = self.entry_legajo.get()
                self.logger.info(f"Certificado médico {id_cert} eliminado - Empleado: {nombre_empleado} (Legajo: {legajo_cert})")
                
                if not self.is_destroyed:
                    def _actualizar_vista():
                        self.mostrar_mensaje("Éxito", "Certificado médico eliminado correctamente")
                        self.limpiar_campos_parcial()
                        if legajo:
                            self.consultar_certificados(legajo)
                    
                    self.root.after(0, _actualizar_vista)
                
            except ValueError as ve:
                if connection:
                    connection.rollback()
                if not self.is_destroyed:
                    self.root.after(0, lambda msg=str(ve): self.handle_database_error(msg, "eliminar_certificado_medico"))
                
            except Exception as e:
                if connection:
                    connection.rollback()
                self.logger.error(f"Error al eliminar certificado: {str(e)}")
                if not self.is_destroyed:
                    error_msg = str(e)  # Capturar el mensaje de error
                    self.root.after(0, lambda msg=error_msg: self.handle_database_error(msg, "eliminar_certificado_medico"))
                
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        self._mostrar_dialogo_confirmacion(
            "Confirmar eliminación",
            "¿Está seguro que desea eliminar este certificado médico?",
            lambda: self.db_pool.executor.submit(_eliminar)
        )

    def consultar_certificados(self, legajo=None):
        """Consultar certificados médicos por legajo de manera asíncrona"""
        def _consultar():
            connection = None
            cursor = None
            try:
                if not legajo:
                    self.root.after(0, self._clear_treeview)
                    return

                connection = self.db_pool.get_connection()
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT id, legajo, fecha_atencion_medica, fecha_recepcion_certificado, 
                           diagnostico_causa, cantidad_dias, medico_hospital_clinica, datos_adicionales
                    FROM certificados_medicos 
                    WHERE legajo = %s
                    ORDER BY fecha_recepcion_certificado DESC
                """, (legajo,))
                
                registros = cursor.fetchall()
                registros_convertidos = []
                
                for registro in registros:
                    fecha_atencion = registro[2].strftime('%d-%m-%Y')
                    fecha_recepcion = registro[3].strftime('%d-%m-%Y')
                    registro_convertido = list(registro)
                    registro_convertido[2] = fecha_atencion
                    registro_convertido[3] = fecha_recepcion
                    registros_convertidos.append(tuple(registro_convertido))
                
                if not self.is_destroyed:
                    self.root.after(0, lambda: self._update_treeview(registros_convertidos))
                
            except Exception as e:
                if not self.is_destroyed:
                    error_msg = str(e)
                    self.logger.error(f"Error en consultar_certificados: {error_msg}")
                    self.root.after(0, lambda msg=error_msg: 
                        self.handle_database_error(msg, "consultar_certificados"))
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        self.db_pool.executor.submit(_consultar)

    def _check_active(self):
        """Verificar si la aplicación sigue activa y puede actualizar la UI"""
        return not self.is_destroyed and hasattr(self, 'root') and self.root.winfo_exists()

    def safe_after(self, ms, func):
        """Ejecutar `after` de forma segura solo si la aplicación sigue activa."""
        if not self.is_destroyed and hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(ms, func)

    def safe_submit(self, func):
        """Ejecutar una función en el executor de forma segura"""
        if not self.is_destroyed:
            self.db_pool.executor.submit(func)

    def limpiar_campos_parcial(self):
        """Limpiar solo los campos del formulario manteniendo legajo y datos del personal"""
        self.certificado_seleccionado_id = None
        self.entry_fecha_atencion.set_date(datetime.now())
        self.entry_fecha_recepcion.set_date(datetime.now())
        self.entry_diagnostico.delete(0, tk.END)
        self.entry_cantidad_dias.delete(0, tk.END)
        self.text_medico_hospital.delete(0, tk.END)
        self.entry_datos_adicionales.delete("1.0", tk.END)

    def limpiar_campos(self):
        """Limpiar todos los campos y resetear la vista"""
        self.certificado_seleccionado_id = None
        self._ultimo_legajo_consultado = None
        self.entry_legajo.delete(0, tk.END)
        self.entry_fecha_atencion.set_date(datetime.now())
        self.entry_fecha_recepcion.set_date(datetime.now())
        self.entry_diagnostico.delete(0, tk.END)
        self.entry_cantidad_dias.delete(0, tk.END)
        self.text_medico_hospital.delete(0, tk.END)
        self.entry_datos_adicionales.delete("1.0", tk.END)
        
        # Limpiar canvas y datos del empleado
        self.photo_canvas.delete("all")
        self._mostrar_placeholder_foto()
        
        # Resetear labels de información
        self.nombre_completo_label.configure(text="")
        self.total_certificados_label.configure(text="Total Certificados: 0")
        self.total_dias_label.configure(text="Total de días de reposo: 0")
        self.ultimo_certificado_label.configure(text="Último Certificado: Sin registros")
        
        # Limpiar tabla
        self._clear_treeview()

    def _update_treeview(self, registros):
        """Actualizar treeview de forma segura"""
        if not self.is_destroyed and hasattr(self, 'tree'):
            try:
                self._clear_treeview()
                for registro in registros:
                    # Truncar textos largos para mejor visualización
                    valores = list(registro)
                    if len(valores) >= 5:  # Diagnóstico
                        valores[4] = valores[4][:50] + '...' if len(valores[4]) > 50 else valores[4]
                    if len(valores) >= 7:  # Médico/Hospital
                        valores[6] = valores[6][:50] + '...' if len(valores[6]) > 50 else valores[6]
                    if len(valores) >= 8:  # Datos adicionales
                        valores[7] = valores[7][:50] + '...' if len(valores[7]) > 50 else valores[7]
                    self.tree.insert("", tk.END, values=tuple(valores))
            except Exception as e:
                self.logger.error(f"Error actualizando treeview: {str(e)}")

    def _clear_treeview(self):
        """Limpiar todos los registros del treeview de forma segura"""
        if hasattr(self, 'tree') and self.tree.winfo_exists():
            for row in self.tree.get_children():
                self.tree.delete(row)

    def mostrar_calificacion_completa(self, event):
        """Mostrar ventana emergente con la calificación completa"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
            
        valores = self.tree.item(item)['values']
        if not valores:
            return
            
        def _get_calificacion_completa():
            connection = self.db_pool.get_connection()
            try:
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT concepto 
                    FROM conceptos 
                    WHERE id = %s
                """, (valores[0],))
                resultado = cursor.fetchone()
                if resultado and resultado[0]:
                    self.root.after(0, lambda c=resultado[0]: self._crear_ventana_calificacion(c))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)
        
        self.db_pool.executor.submit(_get_calificacion_completa)

    def _crear_ventana_calificacion(self, calificacion):
        """Crear ventana modal con la calificación completa"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Calificación Completa")
        dialog.geometry("500x400")
        dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)
        
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f'+{x}+{y}')
        
        text_widget = ctk.CTkTextbox(
            dialog,
            width=460,
            height=300
        )
        text_widget.pack(fill='both', expand=True)
        text_widget.insert('1.0', calificacion)
        text_widget.configure(state='disabled')
        
        btn_cerrar = ctk.CTkButton(
            dialog,
            text="Cerrar",
            command=dialog.destroy,
            width=100
        )
        btn_cerrar.pack(pady=(0,20))

    def validar_campos(self):
        """Validar todos los campos del formulario"""
        try:
            # Verificar campos obligatorios
            if not all([
                self.entry_legajo.get().strip(),
                self.entry_fecha_atencion.get(),
                self.entry_fecha_recepcion.get(),
                self.entry_diagnostico.get().strip(),
                self.entry_cantidad_dias.get().strip(),
                self.text_medico_hospital.get().strip()
            ]):
                raise ValueError("Todos los campos marcados son obligatorios")

            # Validar legajo
            try:
                legajo = int(self.entry_legajo.get())
                if legajo <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("El legajo debe ser un número positivo válido")

            # Validar cantidad de días
            try:
                dias = int(self.entry_cantidad_dias.get())
                if dias <= 0:
                    raise ValueError()
                if dias > 365:
                    raise ValueError("La cantidad de días no puede superar un año")
            except ValueError as e:
                if str(e):
                    raise ValueError(str(e))
                raise ValueError("La cantidad de días debe ser un número positivo válido")

            # Validar fechas
            try:
                fecha_atencion = datetime.strptime(self.entry_fecha_atencion.get(), "%d-%m-%Y")
                fecha_recepcion = datetime.strptime(self.entry_fecha_recepcion.get(), "%d-%m-%Y")
                fecha_actual = datetime.now()

                if fecha_atencion > fecha_actual:
                    raise ValueError("La fecha de atención no puede ser futura")

                if fecha_recepcion > fecha_actual:
                    raise ValueError("La fecha de recepción no puede ser futura")

                if fecha_recepcion < fecha_atencion:
                    raise ValueError("La fecha de recepción no puede ser anterior a la fecha de atención")

                # Validar que la fecha no sea muy antigua (por ejemplo, más de 2 años)
                dos_anos_atras = fecha_actual - timedelta(days=730)
                if fecha_atencion < dos_anos_atras:
                    raise ValueError("La fecha de atención no puede ser anterior a 2 años")

            except ValueError as e:
                if "does not match format" in str(e):
                    raise ValueError("Formato de fecha inválido. Use DD-MM-YYYY")
                raise e

            # Validar longitud y contenido de campos de texto
            diagnostico = self.entry_diagnostico.get().strip()
            if len(diagnostico) < 5:
                raise ValueError("El diagnóstico debe tener al menos 5 caracteres")

            medico_hospital = self.text_medico_hospital.get().strip()
            if len(medico_hospital) < 3:
                raise ValueError("El campo Médico/Hospital debe tener al menos 3 caracteres")

            return True

        except ValueError as e:
            self.mostrar_mensaje("Error de validación", str(e))
            return False

    def mostrar_mensaje(self, titulo, mensaje, tipo="info"):
        """Mostrar mensaje sin crear múltiples instancias y evitar accesos a widgets destruidos."""
        
        if self.is_destroyed or not hasattr(self, 'root') or not self.root.winfo_exists():
            return

        if hasattr(self, 'mensaje_dialog') and self.mensaje_dialog is not None:
            try:
                self.mensaje_dialog.destroy()
            except:
                pass
            self.mensaje_dialog = None

        self.mensaje_dialog = ctk.CTkToplevel(self.root)
        self.mensaje_dialog.title(titulo)
        self.mensaje_dialog.geometry("300x150")
        self.mensaje_dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)

        if self.is_destroyed or not self.root.winfo_exists():
            self.mensaje_dialog.destroy()
            return

        self.mensaje_dialog.transient(self.root)
        self.mensaje_dialog.grab_set()

        self.mensaje_dialog.update_idletasks()
        x = (self.mensaje_dialog.winfo_screenwidth() // 2) - (150)
        y = (self.mensaje_dialog.winfo_screenheight() // 2) - (75)
        self.mensaje_dialog.geometry(f'+{x}+{y}')

        label = ctk.CTkLabel(self.mensaje_dialog, text=mensaje, font=ctk.CTkFont(size=14), wraplength=250)
        label.pack(pady=20)

        def _cerrar_dialogo():
            if hasattr(self, 'mensaje_dialog') and self.mensaje_dialog is not None:
                try:
                    self.mensaje_dialog.grab_release()
                    self.mensaje_dialog.destroy()
                except:
                    pass
                self.mensaje_dialog = None

        btn_aceptar = ctk.CTkButton(self.mensaje_dialog, text="Aceptar", command=_cerrar_dialogo, width=100)
        btn_aceptar.pack(pady=10)

        self.mensaje_dialog.bind("<Escape>", lambda e: _cerrar_dialogo())
        self.mensaje_dialog.bind("<Return>", lambda e: _cerrar_dialogo())

        btn_aceptar.focus_set()

    def handle_database_error(self, error, operacion):
        """Manejar errores de base de datos"""
        error_msg = str(error)
        self.logger.error(f"Error en {operacion}: {error_msg}")
        self.mostrar_mensaje("Error", f"Error en la operación: {error_msg}")

    def _init_async(self):
        """Inicialización asíncrona de la aplicación"""
        try:
            # Verificar si la aplicación ya fue destruida
            if self.is_destroyed:
                return
                
            # Configurar la ventana si estamos en modo standalone
            if not hasattr(self, 'parent_frame') or self.parent_frame is None:
                self.setup_window()
            
            # Verificar si hay un loading_label para destruir y asegurarse que no es None
            if hasattr(self, 'loading_label') and self.loading_label is not None:
                try:
                    self.loading_label.destroy()
                except Exception as e:
                    self.logger.warning(f"Error al destruir loading_label: {e}")
                finally:
                    self.loading_label = None
            
            # Crear la interfaz gráfica
            self.create_gui()
            
            # Inicializar la base de datos
            self._init_database()
            
        except Exception as e:
            self.logger.error(f"Error en inicialización: {str(e)}")
            messagebox.showerror("Error", f"Error al inicializar la aplicación: {str(e)}")

    def _init_database(self):
        """Inicialización de la base de datos"""
        def _connect():
            try:
                self.db_pool = DatabasePool()
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Éxito", "Conexión establecida correctamente"
                ))
            except Exception as e:
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Error", f"Error al conectar con la base de datos: {str(e)}"
                ))
        
        thread = threading.Thread(target=_connect)
        thread.daemon = True
        thread.start()

    def on_closing(self):
        """Manejar cierre de la aplicación"""
        self.cleanup()
        
        # Solo destruir la ventana en modo standalone
        if hasattr(self, 'root') and self.root and not hasattr(self, 'parent_frame'):
            self.root.destroy()

    def cleanup(self):
        """Limpiar recursos al cerrar la aplicación"""
        try:
            # Detener animaciones
            self.animation_running = False
            
            # Limpiar bindings específicos
            if hasattr(self, 'widgets_with_bindings'):
                for widget in self.widgets_with_bindings:
                    if widget and widget.winfo_exists():
                        try:
                            widget.unbind('<MouseWheel>')
                            widget.unbind('<Shift-MouseWheel>')
                        except:
                            pass
            
            # Cerrar conexiones DB solo en modo standalone
            if hasattr(self, 'db_pool') and self.db_pool and not hasattr(self, 'parent_frame'):
                self.db_pool.close()
            
            self.is_destroyed = True
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error en cleanup: {e}")
            print(f"Error en cleanup: {e}")

    def run(self):
        """Iniciar la aplicación"""
        try:
            self.root.mainloop()
        finally:
            self.cleanup()

    def _create_header_frame(self):
        """Crear frame superior con logo y títulos"""
        header_frame = ctk.CTkFrame(
            self.root,
            fg_color=EstiloApp.COLOR_HEADER,
            corner_radius=10,
            height=80
        )
        
        # Ajustar el padding según si estamos en standalone o en parent_frame
        if hasattr(self, 'parent_frame'):
            header_frame.grid(row=0, column=0, sticky="new", padx=20, pady=(10, 0))  # Sin padding inferior
        else:
            header_frame.grid(row=0, column=0, sticky="new", padx=20, pady=(10, 5))  # Padding original
            
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Frame contenedor para el logo
        logo_container = ctk.CTkFrame(
            header_frame,
            fg_color="transparent",
            width=150,
            height=80
        )
        logo_container.grid(row=0, column=0, rowspan=3, padx=(5, 10), pady=5)
        logo_container.grid_propagate(False)
        
        # Configuración de tamaño del logo - ajustable
        self.logo_width = 190
        self.logo_height = 190  # Ajustado para mantener mejor la proporción
        
        try:
            # Intenta diferentes ubicaciones para el logo
            logo_paths = [
                "logo.gif",
                "imagenes/logo.gif",
                "assets/logo.gif",
                "./logo.gif",
                os.path.join(os.path.dirname(__file__), "logo.gif")
            ]
            
            logo_loaded = False
            for path in logo_paths:
                if os.path.exists(path):
                    self.logo_frames = []
                    self.current_frame = 0
                    pil_image = Image.open(path)
                    
                    # Cargar frames del GIF manteniendo proporción
                    for frame in ImageSequence.Iterator(pil_image):
                        frame = frame.convert('RGBA')
                        
                        # Calcular proporciones para evitar deformación
                        img_width, img_height = frame.size
                        ratio = min(self.logo_width/img_width, self.logo_height/img_height)
                        new_width = int(img_width * ratio)
                        new_height = int(img_height * ratio)
                        
                        # Redimensionar manteniendo proporción
                        frame = frame.resize((new_width, new_height), Image.LANCZOS)
                        
                        ctk_frame = ctk.CTkImage(
                            light_image=frame,
                            dark_image=frame,
                            size=(new_width, new_height)
                        )
                        self.logo_frames.append(ctk_frame)
                    
                    self.logo_label = ctk.CTkLabel(
                        logo_container,
                        text="",
                        image=self.logo_frames[0]
                    )
                    self.logo_label.place(relx=0.5, rely=0.5, anchor="center")
                    self._animate_logo()
                    logo_loaded = True
                    break
            
            if not logo_loaded:
                self._create_logo_placeholder(logo_container)
                
        except Exception as e:
            self.logger.error(f"Error al cargar el logo: {str(e)}")
            self._create_logo_placeholder(logo_container)
        
        # Frame contenedor para los textos
        text_container = ctk.CTkFrame(
            header_frame,
            fg_color="transparent"
        )
        text_container.grid(row=0, column=1, sticky="w", pady=10)
        
        # Título principal
        title_label = ctk.CTkLabel(
            text_container,
            text="Módulo de Certificados Médicos - RRHH",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=EstiloApp.COLOR_TEXTO
        )
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        
        # Subtítulo
        subtitle_label = ctk.CTkLabel(
            text_container,
            text="Entheus Controller",
            font=ctk.CTkFont(size=16),
            text_color=EstiloApp.COLOR_TEXTO
        )
        subtitle_label.grid(row=1, column=0, sticky="w", pady=1)
        
        # Derechos de autor
        copyright_label = ctk.CTkLabel(
            text_container,
            text="© 2025 ENTHEUS CONTROLLER",
            font=ctk.CTkFont(size=12),
            text_color=EstiloApp.COLOR_TEXTO
        )
        copyright_label.grid(row=2, column=0, sticky="w", pady=(1, 0))

    def _create_logo_placeholder(self, parent):
        """Crear placeholder para el logo cuando no se puede cargar"""
        placeholder = ctk.CTkLabel(
            parent,
            text="LOGO",
            font=ctk.CTkFont(size=20, weight="bold"),
            width=120,
            height=60,
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            corner_radius=10
        )
        placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _animate_logo(self, frame_index=0):
        """Anima el logo frame por frame con manejo de errores"""
        try:
            # Verificar si la animación debe continuar
            if not self.animation_running:
                return
                
            # Verificar si el widget todavía existe
            if not hasattr(self, 'logo_label') or not self.logo_label.winfo_exists():
                self.animation_running = False
                return
                
            # Actualizar frame
            self.current_frame = frame_index
            
            # Verificar que tengamos frames y el índice sea válido
            if hasattr(self, 'logo_frames') and self.logo_frames and frame_index < len(self.logo_frames):
                self.logo_label.configure(image=self.logo_frames[frame_index])
                
                # Calcular siguiente frame
                next_frame = (frame_index + 1) % len(self.logo_frames)
                
                # Programar siguiente actualización
                if self.logo_label.winfo_exists() and not self.is_destroyed:
                    self.root.after(100, lambda: self._animate_logo(next_frame))
                else:
                    self.animation_running = False
        except Exception as e:
            # Detener animación en caso de error
            self.animation_running = False
            if hasattr(self, 'logger'):
                self.logger.error(f"Error en animación del logo: {e}")

    def consultar_empleado(self, event=None):
        """Consultar datos del empleado y sus certificados médicos"""
        if not self.db_pool or self.is_destroyed:
            return

        legajo = self.entry_legajo.get().strip()
        if not legajo:
            return

        if hasattr(self, '_ultimo_legajo_consultado') and self._ultimo_legajo_consultado == legajo:
            return
        self._ultimo_legajo_consultado = legajo

        def _consultar():
            if self.is_destroyed:
                return

            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                cursor = connection.cursor()

                # Consulta mejorada para obtener datos del empleado y estadísticas de certificados
                cursor.execute("""
                    SELECT 
                        p.apellido_nombre, 
                        p.foto,
                        COUNT(cm.id) as total_certificados,
                        COALESCE(SUM(cm.cantidad_dias), 0) as total_dias,
                        MAX(cm.fecha_atencion_medica) as ultimo_certificado,
                        COALESCE(SUM(CASE 
                            WHEN cm.fecha_atencion_medica >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                            THEN cm.cantidad_dias 
                            ELSE 0 
                        END), 0) as dias_ultimo_anio
                    FROM personal p
                    LEFT JOIN certificados_medicos cm ON p.legajo = cm.legajo
                    WHERE p.legajo = %s
                    GROUP BY p.legajo, p.apellido_nombre, p.foto
                """, (legajo,))
                
                resultado = cursor.fetchone()

                if resultado:
                    apellido_nombre, foto_blob, total_certificados, total_dias, ultimo_certificado, dias_ultimo_anio = resultado

                    def _actualizar_ui():
                        if self.is_destroyed or not self.root.winfo_exists():
                            return
                        
                        # Actualizar información del empleado
                        self.nombre_completo_label.configure(text=f"{apellido_nombre}")
                        
                        # Actualizar estadísticas de certificados
                        self.total_certificados_label.configure(
                            text=f"Total Certificados: {total_certificados}"
                        )
                        self.total_dias_label.configure(
                            text=f"Total de días de reposo: {total_dias} (Último año: {dias_ultimo_anio})"
                        )
                        if ultimo_certificado:
                            fecha_formato = ultimo_certificado.strftime('%d-%m-%Y')
                            self.ultimo_certificado_label.configure(
                                text=f"Último Certificado: {fecha_formato}"
                            )
                        else:
                            self.ultimo_certificado_label.configure(
                                text="Último Certificado: Sin registros"
                            )
                        
                        # Mostrar foto y actualizar tabla
                        self._mostrar_foto(foto_blob)
                        self.consultar_certificados(legajo)

                    self.root.after(0, _actualizar_ui)
                else:
                    def _mostrar_error():
                        if self.is_destroyed or not self.root.winfo_exists():
                            return
                        self.mostrar_mensaje("Error", f"El legajo {legajo} no existe en la base de datos.")
                        # Limpiar información
                        self.nombre_completo_label.configure(text="")
                        self.total_certificados_label.configure(text="Total Certificados: 0")
                        self.total_dias_label.configure(text="Total de días de reposo: 0")
                        self.ultimo_certificado_label.configure(text="Último Certificado: Sin registros")
                        self._mostrar_placeholder_foto()
                        self._clear_treeview()

                    self.root.after(0, _mostrar_error)

            except Exception as e:
                if not self.is_destroyed:
                    error_msg = str(e)
                    self.logger.error(f"Error en consultar_empleado: {error_msg}")
                    self.root.after(0, lambda msg=error_msg: self.handle_database_error(msg, "consultar_empleado"))
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        self.db_pool.executor.submit(_consultar)

    def _mostrar_foto(self, foto_blob):
        """Mostrar la foto del empleado en el canvas."""
        self.photo_canvas.delete("all")
        
        # Obtener dimensiones del canvas
        canvas_width = self.photo_canvas.winfo_width()
        canvas_height = self.photo_canvas.winfo_height()
        canvas_center_x = canvas_width / 2
        canvas_center_y = canvas_height / 2
        
        if foto_blob and len(foto_blob) > 0:
            try:
                # Convertir blob a imagen
                image = Image.open(io.BytesIO(foto_blob))
                
                # Convertir a RGB si es necesario
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Redimensionar manteniendo proporción
                image.thumbnail((140, 140), Image.Resampling.LANCZOS)  # Tamaño reducido
                
                # Convertir a PhotoImage
                photo = ImageTk.PhotoImage(image)
                
                # Mostrar en canvas centrado
                self.photo_canvas.create_image(
                    canvas_center_x, 
                    canvas_center_y,
                    image=photo,
                    anchor="center"
                )
                self.photo_canvas.image = photo  # Mantener referencia
                
            except Exception as e:
                self.logger.error(f"Error al cargar la imagen: {str(e)}")
                self._mostrar_placeholder_foto()
        else:
            self._mostrar_placeholder_foto()

    def _mostrar_placeholder_foto(self):
        """Mostrar placeholder cuando no hay foto."""
        self.photo_canvas.delete("all")
        
        # Obtener dimensiones del canvas
        canvas_width = self.photo_canvas.winfo_width()
        canvas_height = self.photo_canvas.winfo_height()
        center_x = canvas_width / 2
        center_y = canvas_height / 2
        
        # Dibujar círculo centrado
        radius = 60  # Radio del círculo
        self.photo_canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            fill=EstiloApp.COLOR_SECUNDARIO,
            outline=EstiloApp.COLOR_SECUNDARIO
        )
        
        # Texto centrado
        self.photo_canvas.create_text(
            center_x,
            center_y,
            text="Sin\nfoto",
            fill=EstiloApp.COLOR_TEXTO,
            font=('Helvetica', 12, 'bold'),
            justify='center'
        )

    def on_tree_double_click(self, event=None):
        """Manejar el evento de doble clic en el treeview"""
        seleccion = self.tree.selection()
        if not seleccion:
            return
            
        try:
            item = seleccion[0]
            valores = self.tree.item(item)['values']
            
            if not valores:
                return
            
            # Obtener los datos del certificado médico seleccionado    
            def _get_certificado():
                connection = self.db_pool.get_connection()
                try:
                    cursor = connection.cursor()
                    cursor.execute("""
                        SELECT id, legajo, fecha_atencion_medica, fecha_recepcion_certificado,
                               diagnostico_causa, cantidad_dias, medico_hospital_clinica, 
                               datos_adicionales
                        FROM certificados_medicos 
                        WHERE id = %s
                    """, (valores[0],))
                    resultado = cursor.fetchone()
                    if resultado:
                        self.safe_after(0, lambda: self._cargar_datos_certificado(resultado))
                finally:
                    cursor.close()
                    self.db_pool.return_connection(connection)
            
            self.safe_submit(_get_certificado)
                
        except Exception as e:
            self.mostrar_mensaje("Error", "Error al cargar los datos del certificado")
            self.logger.error(f"Error en double click: {str(e)}")

    def _cargar_datos_certificado(self, datos):
        """Cargar datos del certificado médico en el formulario"""
        try:
            if not datos:
                return
                
            self.certificado_seleccionado_id = datos[0]
            
            # Limpiar campos primero
            self.entry_legajo.delete(0, tk.END)
            self.entry_diagnostico.delete(0, tk.END)
            self.entry_cantidad_dias.delete(0, tk.END)
            self.text_medico_hospital.delete(0, tk.END)
            self.entry_datos_adicionales.delete("1.0", tk.END)
            
            # Cargar datos
            self.entry_legajo.insert(0, str(datos[1]))
            self.entry_fecha_atencion.set_date(datetime.strptime(str(datos[2]), "%Y-%m-%d"))
            self.entry_fecha_recepcion.set_date(datetime.strptime(str(datos[3]), "%Y-%m-%d"))
            self.entry_diagnostico.insert(0, str(datos[4]))
            self.entry_cantidad_dias.insert(0, str(datos[5]))
            self.text_medico_hospital.insert(0, str(datos[6]))
            if datos[7]:  # Datos adicionales es opcional
                self.entry_datos_adicionales.insert("1.0", str(datos[7]))
            
            # Actualizar datos del empleado
            self.consultar_empleado()
            
        except Exception as e:
            self.logger.error(f"Error al cargar datos: {str(e)}, datos={datos}")
            self.mostrar_mensaje("Error", f"Error al cargar los datos: {str(e)}")

    def mostrar_diagnostico_completo(self, event):
        """Mostrar ventana emergente con el diagnóstico completo"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
                
        valores = self.tree.item(item)['values']
        if not valores:
            return
                
        def _get_diagnostico():
            connection = self.db_pool.get_connection()
            try:
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT diagnostico_causa, medico_hospital_clinica, datos_adicionales
                    FROM certificados_medicos 
                    WHERE id = %s
                """, (valores[0],))
                resultado = cursor.fetchone()
                if resultado:
                    diagnostico, medico, datos_adicionales = resultado
                    texto_completo = f"Diagnóstico/Causa:\n{diagnostico}\n\n"
                    texto_completo += f"Médico/Hospital/Clínica:\n{medico}\n\n"
                    if datos_adicionales:
                        texto_completo += f"Datos Adicionales:\n{datos_adicionales}"
                    self.root.after(0, lambda: self._crear_ventana_diagnostico(texto_completo))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)
        
        self.db_pool.executor.submit(_get_diagnostico)

    def _crear_ventana_diagnostico(self, texto):
        """Crear ventana modal con el diagnóstico completo"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Detalles del Certificado Médico")
        dialog.geometry("600x400")
        dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)
        
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f'+{x}+{y}')
        
        text_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        text_frame.pack(fill='both', expand=True, padx=20, pady=(20,10))
        
        text_widget = ctk.CTkTextbox(
            text_frame,
            wrap='word',
            font=ctk.CTkFont(size=12),
            width=560,
            height=300
        )
        text_widget.pack(fill='both', expand=True)
        text_widget.insert('1.0', texto)
        text_widget.configure(state='disabled')
        
        btn_cerrar = ctk.CTkButton(
            dialog,
            text="Cerrar",
            command=dialog.destroy,
            width=100
        )
        btn_cerrar.pack(pady=(0,20))

        # Configurar eventos de teclado
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Return>", lambda e: dialog.destroy())
        
        # Asegurar que el diálogo tenga el foco
        dialog.focus_force()

    def _mostrar_dialogo_confirmacion(self, titulo, mensaje, callback):
        """Mostrar diálogo de confirmación personalizado"""
        if hasattr(self, 'dialogo_confirmacion') and self.dialogo_confirmacion is not None:
            try:
                self.dialogo_confirmacion.destroy()
            except:
                pass
        
        # Crear ventana de diálogo
        self.dialogo_confirmacion = ctk.CTkToplevel(self.root)
        self.dialogo_confirmacion.title(titulo)
        self.dialogo_confirmacion.geometry("400x200")
        self.dialogo_confirmacion.configure(fg_color=EstiloApp.COLOR_FRAMES)
        self.dialogo_confirmacion.transient(self.root)
        self.dialogo_confirmacion.grab_set()
        
        # Centrar la ventana
        self.dialogo_confirmacion.update_idletasks()
        x = (self.dialogo_confirmacion.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialogo_confirmacion.winfo_screenheight() // 2) - (200 // 2)
        self.dialogo_confirmacion.geometry(f'+{x}+{y}')
        
        # Mensaje
        label = ctk.CTkLabel(
            self.dialogo_confirmacion,
            text=mensaje,
            font=ctk.CTkFont(size=14),
            wraplength=350
        )
        label.pack(pady=20)
        
        # Frame para botones
        button_frame = ctk.CTkFrame(
            self.dialogo_confirmacion,
            fg_color="transparent"
        )
        button_frame.pack(pady=20)
        
        # Botón Aceptar
        btn_aceptar = ctk.CTkButton(
            button_frame,
            text="Aceptar",
            font=ctk.CTkFont(size=13),
            width=100,
            fg_color=EstiloApp.BOTON_INSERTAR,
            hover_color=EstiloApp.BOTON_INSERTAR_HOVER,
            command=lambda: self._confirmar_dialogo(callback)
        )
        btn_aceptar.pack(side="left", padx=10)
        
        # Botón Cancelar
        btn_cancelar = ctk.CTkButton(
            button_frame,
            text="Cancelar",
            font=ctk.CTkFont(size=13),
            width=100,
            fg_color=EstiloApp.BOTON_ELIMINAR,
            hover_color=EstiloApp.BOTON_ELIMINAR_HOVER,
            command=lambda: self._cerrar_dialogo()
        )
        btn_cancelar.pack(side="left", padx=10)
        
        # Eventos de teclado
        self.dialogo_confirmacion.bind("<Return>", lambda e: self._confirmar_dialogo(callback))
        self.dialogo_confirmacion.bind("<Escape>", lambda e: self._cerrar_dialogo())
        
        # Dar foco al botón aceptar
        btn_aceptar.focus_set()

    def _confirmar_dialogo(self, callback):
        """Confirmar acción del diálogo y ejecutar callback"""
        if hasattr(self, 'dialogo_confirmacion') and self.dialogo_confirmacion is not None:
            self.dialogo_confirmacion.destroy()
            self.dialogo_confirmacion = None
            if callback:
                callback()

    def _cerrar_dialogo(self):
        """Cerrar diálogo sin ejecutar acción"""
        if hasattr(self, 'dialogo_confirmacion') and self.dialogo_confirmacion is not None:
            self.dialogo_confirmacion.destroy()
            self.dialogo_confirmacion = None

    def on_tree_select(self, event=None):
        """Manejar la selección en el treeview"""
        seleccion = self.tree.selection()
        if seleccion:
            try:
                item = seleccion[0]
                valores = self.tree.item(item)['values']
                if valores:
                    self.certificado_seleccionado_id = valores[0]
            except Exception as e:
                self.logger.error(f"Error al seleccionar item: {str(e)}")
                self.certificado_seleccionado_id = None

    def _actualizar_estadisticas(self, cursor, legajo):
        """Actualizar estadísticas de certificados médicos"""
        cursor.execute("""
            SELECT 
                COUNT(cm.id) as total_certificados,
                COALESCE(SUM(cm.cantidad_dias), 0) as total_dias,
                MAX(cm.fecha_atencion_medica) as ultimo_certificado,
                COALESCE(SUM(CASE 
                    WHEN cm.fecha_atencion_medica >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                    THEN cm.cantidad_dias 
                    ELSE 0 
                END), 0) as dias_ultimo_anio
            FROM certificados_medicos cm
            WHERE cm.legajo = %s
        """, (legajo,))
        
        stats = cursor.fetchone()
        if stats:
            total_certificados, total_dias, ultimo_certificado, dias_ultimo_anio = stats
            
            if not self.is_destroyed:
                def _actualizar_labels():
                    self.total_certificados_label.configure(
                        text=f"Total Certificados: {total_certificados}"
                    )
                    self.total_dias_label.configure(
                        text=f"Total de días de reposo: {total_dias} (Último año: {dias_ultimo_anio})"
                    )
                    if ultimo_certificado:
                        fecha_formato = ultimo_certificado.strftime('%d-%m-%Y')
                        self.ultimo_certificado_label.configure(
                            text=f"Último Certificado: {fecha_formato}"
                        )
                
                self.root.after(0, _actualizar_labels)

    def show_in_frame(self, parent_frame):
        """Mostrar el módulo en un frame específico"""
        try:
            # Detener animaciones existentes
            self.animation_running = False
            
            # Limpiar bindings específicos si existen
            if hasattr(self, 'parent_frame') and self.parent_frame:
                try:
                    widgets_with_bindings = getattr(self, 'widgets_with_bindings', [])
                    for widget in widgets_with_bindings:
                        if widget and widget.winfo_exists():
                            widget.unbind('<MouseWheel>')
                            widget.unbind('<Shift-MouseWheel>')
                except Exception as e:
                    if hasattr(self, 'logger'):
                        self.logger.warning(f"Error al limpiar bindings: {e}")
            
            self.is_destroyed = False
            
            # Marcar que estamos en modo integrado
            self.is_integrated = True
            
            # Limpiar el frame padre
            for widget in parent_frame.winfo_children():
                widget.destroy()
            
            # Actualizar referencias
            self.parent_frame = parent_frame
            self.root = parent_frame
            
            # Configurar el grid del parent_frame
            parent_frame.grid_columnconfigure(0, weight=1)
            parent_frame.grid_rowconfigure(0, weight=1)
            
            # Crear el contenedor principal SIN PADDING Y SIN MARGEN
            self.main_frame = ctk.CTkFrame(
                parent_frame,
                fg_color="transparent",
                corner_radius=0,
                border_width=0
            )
            # Usar grid sin padding
            self.main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
            
            # Configurar el grid del main_frame - importante para eliminar espacios
            self.main_frame.grid_columnconfigure(0, weight=1)
            self.main_frame.grid_rowconfigure(0, weight=0)  # Header: height=min
            self.main_frame.grid_rowconfigure(1, weight=1)  # Content: height=expand
            
            # Lista para seguir widgets con bindings
            self.widgets_with_bindings = []
            
            # Crear la interfaz con ajustes para modo integrado
            self.create_gui()
            
            # Inicializar base de datos
            self._init_database()
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error en show_in_frame: {str(e)}")
            raise

    def _find_root_window(self, widget):
        """Encuentra la ventana principal desde cualquier widget"""
        current = widget
        while current:
            if isinstance(current, (tk.Tk, ctk.CTk)):
                return current
            current = current.master
        return None

    # Para cargar el logo animado, usa este método seguro
    def _load_animated_logo(self, container):
        """Carga el logo animado con manejo de errores mejorado"""
        try:
            # Iniciar control de animación
            self.animation_running = True
            self.current_frame = 0
            self.logo_frames = []
            
            # Cargar GIF
            gif_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                   "resources", "icons_gifs", "logo.gif")
            
            if not os.path.exists(gif_path):
                return False
                
            # Crear label para el logo
            self.logo_label = ctk.CTkLabel(container, text="")
            self.logo_label.pack(pady=10)
            
            # Cargar frames
            gif = Image.open(gif_path)
            for frame in ImageSequence.Iterator(gif):
                frame = frame.convert('RGBA')
                photo = ImageTk.PhotoImage(frame)
                self.logo_frames.append(photo)
            
            # Iniciar animación
            self._animate_logo()
            return True
            
        except Exception as e:
            self.animation_running = False
            if hasattr(self, 'logger'):
                self.logger.error(f"Error cargando logo animado: {e}")
            return False

if __name__ == "__main__":
    try:
        app = AplicacionCertificadosMedicos()
        app.run()
    except Exception as e:
        logging.basicConfig(
            filename="logs/errores_críticos_certificados.log",
            level=logging.CRITICAL,
            format='%(asctime)s - [%(levelname)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.critical(f"Error crítico al iniciar la aplicación: {str(e)}\n{traceback.format_exc()}")
        print(f"Error al iniciar la aplicación: {e}")
