# Primero configuramos el path antes de cualquier importación personalizada
import os
import sys
from pathlib import Path

# Obtener ruta absoluta al directorio raíz del proyecto y configurar path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
sys.path.append(str(PROJECT_ROOT))  # Convertir Path a string

# Ahora las importaciones estándar
import customtkinter as ctk
from tkcalendar import DateEntry
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import mysql.connector
import threading
from concurrent.futures import ThreadPoolExecutor
from CTkTable import CTkTable
from PIL import Image, ImageTk, ImageSequence, ImageDraw
import io
import logging
from datetime import datetime, date
import traceback
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Configurar .env
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')
print(f"Ruta absoluta al .env: {ENV_PATH}")
load_dotenv(ENV_PATH)

# Ahora podemos importar nuestros módulos personalizados
from utils.interface_manager import EstiloApp, InterfaceManager

# Verificación de variables de entorno
print(f"Buscando .env en: {ENV_PATH}")
if os.path.exists(ENV_PATH):
    print(".env encontrado")
    print("Variables de entorno cargadas:")
    print(f"DB_HOST: {os.getenv('DB_HOST')}")
    print(f"DB_USER: {os.getenv('DB_USER')}")
    print(f"DB_DATABASE: {os.getenv('DB_DATABASE')}")
else:
    print(f"❌ ERROR: Archivo .env no encontrado en {ENV_PATH}")

# Configuración de tema y colores
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class DatabasePool:
    """Clase para manejar el pool de conexiones a la base de datos"""
    def __init__(self):
        self.config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_DATABASE')
        }
        # Agregar print para debug
        print("Configuración DB:", {k: v for k, v in self.config.items() if k != 'password'})
        
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

class AplicacionConceptos:
    def __init__(self, parent_frame=None):
        # Flags de control
        self.is_destroyed = False
        self.is_closing = False
        self._showing_message = False
        self.mensaje_dialog = None
        self.pending_operations = []
        
        # Determinar si es standalone o integrado
        self.is_standalone = parent_frame is None
        
        print(f"Inicializando módulo conceptos. Standalone: {self.is_standalone}")
        print(f"Parent frame recibido: {parent_frame}")
        
        if self.is_standalone:
            self.root = ctk.CTk()
            self.main_container = self.root
            self.root.title("Sistema de Gestión de Conceptos")
            self.root.state('zoomed')
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Mostrar mensaje de carga solo en modo standalone
            self.loading_label = ctk.CTkLabel(
                self.root,
                text="Iniciando aplicación...",
                font=ctk.CTkFont(size=16)
            )
            self.loading_label.grid(row=0, column=0)
            self.root.after(100, self._init_async)
        else:
            self.root = parent_frame
            self.main_container = ctk.CTkFrame(self.root, fg_color=EstiloApp.COLOR_PRINCIPAL)
            self.main_container.grid(row=0, column=0, sticky="nsew")
            self.root.grid_columnconfigure(0, weight=1)
            self.root.grid_rowconfigure(0, weight=1)
            self._init_async()
        
        self.db_pool = None
        self.concepto_seleccionado_id = None
        
        # Configurar el sistema de logging
        self._setup_logging()

    def _setup_logging(self):
        """Configurar el sistema de logging"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_format = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(module)s - Línea %(lineno)d: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, 'errores_conceptos.log'),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(log_format)
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        
        self.logger.info("🚀 Módulo de Conceptos iniciado")

    def _init_async(self):
        """Inicialización asíncrona de la aplicación"""
        try:
            # Configurar ventana
            self.setup_window()
            
            # Crear interfaz
            self.create_gui()
            
            # Inicializar base de datos en segundo plano
            self.root.after(100, self._init_database)
            
        except Exception as e:
            self.mostrar_mensaje("Error", f"Error al iniciar la aplicación: {str(e)}")

    def setup_window(self):
        """Configurar la ventana principal"""
        if self.is_standalone:
            # Configurar solo si es una ventana standalone
            self.root.configure(fg_color=EstiloApp.COLOR_PRINCIPAL)
            self.root.grid_columnconfigure(0, weight=1)
            self.root.grid_rowconfigure(0, weight=1)
        
        # Configurar el grid del contenedor principal
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=0)  # Header
        self.main_container.grid_rowconfigure(1, weight=1)  # Content frame

    def create_gui(self):
        """Crear la interfaz gráfica usando grid consistentemente"""
        # Header frame (row 0)
        header_frame = self._create_header_frame()
        header_frame.grid(row=0, column=0, sticky="new", padx=20, pady=(10, 5))
        
        # Content frame (row 1)
        content_container = ctk.CTkFrame(
            self.main_container,
            fg_color=EstiloApp.COLOR_PRINCIPAL
        )
        content_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        # Configurar grid del content_container
        content_container.grid_columnconfigure(0, weight=1)
        content_container.grid_rowconfigure(0, weight=0)  # Form
        content_container.grid_rowconfigure(1, weight=1)  # Table
        
        # Form frame
        form_frame = self._create_form(content_container)
        form_frame.grid(row=0, column=0, sticky="new", padx=10, pady=5)
        
        # Table frame
        table_frame = self._create_table(content_container)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

    def _create_form(self, parent):
        """Crear el formulario principal"""
        form_frame = ctk.CTkFrame(
            parent,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        form_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        form_frame.grid_columnconfigure(1, weight=1)

        # Panel izquierdo (formulario)
        left_panel = ctk.CTkFrame(form_frame, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nw", padx=20, pady=20)
        
        # Título
        title_label = ctk.CTkLabel(
            left_panel,
            text="Gestión de Conceptos",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Campos del formulario
        self.crear_campos_formulario(left_panel)
        
        # Panel central (foto y datos empleado)
        self._create_employee_info_panel(form_frame)
        
        # Panel derecho (botones CRUD)
        self._create_crud_buttons(form_frame)

        return form_frame

    def crear_campos_formulario(self, parent):
        """Crear campos del formulario"""
        campos = [
            ("Legajo:", "entry_legajo"),
            ("Fecha:", "entry_fecha", "date"),
            ("Concepto:", "entry_calificacion")
        ]
        
        for idx, campo in enumerate(campos):
            label = ctk.CTkLabel(
                parent,
                text=campo[0],
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=idx+1, column=0, sticky="e", padx=5, pady=5)
            
            if len(campo) > 2 and campo[2] == "date":
                # Frame contenedor para el DateEntry con borde
                date_frame = ctk.CTkFrame(
                    parent,
                    fg_color=EstiloApp.COLOR_PRINCIPAL,
                    height=35,
                    width=200,
                    border_width=1,  # Agregar borde
                    border_color=EstiloApp.COLOR_SECUNDARIO  # Color del borde
                )
                date_frame.grid(row=idx+1, column=1, sticky="w", padx=20, pady=5)
                date_frame.grid_propagate(False)
                
                widget = DateEntry(
                    date_frame,
                    width=12,
                    background=EstiloApp.COLOR_SECUNDARIO,
                    foreground='black',
                    borderwidth=0,
                    font=('Helvetica', 12),
                    date_pattern='dd-mm-yyyy',
                    locale='es',
                    justify='center'
                )
                widget.place(relx=0.5, rely=0.5, anchor="center")
            else:
                # Entry normal con texto centrado
                widget = ctk.CTkEntry(
                    parent,
                    height=35,
                    width=200,
                    font=ctk.CTkFont(size=14),
                    justify='center'  # Centrar el texto
                )
                widget.grid(row=idx+1, column=1, sticky="w", padx=20, pady=5)
            
            setattr(self, campo[1], widget)
        
        # Vincular eventos al campo legajo
        self.entry_legajo.bind('<FocusOut>', self.consultar_empleado)
        self.entry_legajo.bind('<Return>', self.consultar_empleado)

    def _create_employee_info_panel(self, parent):
        """Crear panel de información del empleado"""
        # Panel central (foto y datos empleado)
        info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        # Frame para la foto - Dimensiones ajustadas
        photo_frame = ctk.CTkFrame(
            info_frame,
            fg_color=EstiloApp.COLOR_PRINCIPAL,
            width=160,
            height=160,
            corner_radius=10,
            border_width=1,
            border_color=EstiloApp.COLOR_SECUNDARIO
        )
        photo_frame.grid(row=0, column=0, padx=10, pady=5)
        photo_frame.grid_propagate(False)
        
        # Canvas para la foto - Mismo tamaño que el frame, pero con un pequeño margen interior
        self.photo_canvas = tk.Canvas(
            photo_frame,
            width=150,
            height=150,
            bg=EstiloApp.COLOR_PRINCIPAL,
            highlightthickness=0
        )
        self.photo_canvas.place(relx=0.5, rely=0.5, anchor="center")
        
        # Mostrar placeholder inicial
        self._mostrar_placeholder_foto()
        
        # Frame para información del empleado
        info_labels_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_labels_frame.grid(row=0, column=1, sticky="nw", padx=10)
        
        # Labels informativos con emoji
        self.nombre_completo_label = ctk.CTkLabel(
            info_labels_frame,
            text="👤 Apellido y Nombre: -",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.nombre_completo_label.grid(row=0, column=0, sticky="w", pady=2)
        
        # Frame para estadísticas
        stats_frame = ctk.CTkFrame(info_labels_frame, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="w", pady=(10, 0))
        
        # Labels estadísticos con emojis
        labels_info = [
            ("calificacion_alta_label", "⭐ Concepto más alto: -"),
            ("calificacion_baja_label", "📉 Concepto más bajo: -"),
            ("calificacion_promedio_label", "📊 Concepto Promedio: -")
        ]
        
        for idx, (attr_name, text) in enumerate(labels_info):
            label = ctk.CTkLabel(
                stats_frame,
                text=text,
                font=ctk.CTkFont(size=13),
                anchor="w",
                justify="left"
            )
            label.grid(row=idx, column=0, sticky="w", pady=2)
            setattr(self, attr_name, label)
        
        return info_frame

    def _create_crud_buttons(self, parent):
        """Crear botones CRUD"""
        buttons_frame = ctk.CTkFrame(
            parent,
            fg_color="transparent"
        )
        buttons_frame.grid(row=0, column=2, sticky="ne", padx=20, pady=20)

        buttons = [
            ("Insertar", self.insertar_calificacion, EstiloApp.BOTON_INSERTAR, EstiloApp.BOTON_INSERTAR_HOVER),
            ("Modificar", self.modificar_calificacion, EstiloApp.BOTON_MODIFICAR, EstiloApp.BOTON_MODIFICAR_HOVER),
            ("Eliminar", self.eliminar_calificacion, EstiloApp.BOTON_ELIMINAR, EstiloApp.BOTON_ELIMINAR_HOVER),
            ("Limpiar", self.limpiar_campos, EstiloApp.BOTON_LIMPIAR, EstiloApp.BOTON_LIMPIAR_HOVER)
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

        return buttons_frame

    def _create_table(self, parent):
        """Crear tabla de calificaciones"""
        table_frame = ctk.CTkFrame(
            parent,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        table_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 10))
        
        title_label = ctk.CTkLabel(
            table_frame,
            text="Historias de Conceptos",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(10, 10))

        tree_container = ctk.CTkFrame(table_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        # Crear Treeview con las columnas para calificaciones
        self.tree = ttk.Treeview(
            tree_container,
            columns=("id", "legajo", "fecha", "concepto"),
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
            "fecha": {"texto": "Fecha", "ancho": 100},
            "concepto": {"texto": "Concepto", "ancho": 400}
        }
        
        for col, config in columnas.items():
            self.tree.heading(col, text=config["texto"], anchor="center")
            self.tree.column(col, width=config["ancho"], anchor="center")

        # Ubicar componentes
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)
        
        # Vincular eventos
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.mostrar_calificacion_completa)

        return table_frame

    def insertar_calificacion(self):
        """Insertar nueva calificación manteniendo datos del legajo"""
        if not self.validar_campos():
            return

        def _insertar():
            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                if not connection:
                    raise ConnectionError("No se pudo obtener conexión")

                cursor = connection.cursor()
                
                # Validar empleado
                cursor.execute("SELECT 1 FROM personal WHERE legajo = %s", 
                             (int(self.entry_legajo.get()),))
                if not cursor.fetchone():
                    raise ValueError("El legajo no existe en la base de datos")
                
                # Convertir fecha de forma segura
                try:
                    fecha_sql = datetime.strptime(self.entry_fecha.get(), "%d-%m-%Y").strftime("%Y-%m-%d")
                except ValueError:
                    raise ValueError("Formato de fecha inválido")
                
                sql = """
                INSERT INTO conceptos (legajo, fecha, concepto)
                VALUES (%s, %s, %s)
                """
                datos = (
                    int(self.entry_legajo.get()),
                    fecha_sql,
                    self.entry_calificacion.get().strip()
                )
                
                cursor.execute(sql, datos)
                connection.commit()
                
                # Guardar el legajo antes de cualquier actualización
                legajo = self.entry_legajo.get()
                
                def _actualizar_ui():
                    if not self.is_destroyed:
                        try:
                            # Primero actualizar los datos del empleado (esto actualizará las estadísticas)
                            self.consultar_empleado()
                            
                            # Luego limpiar solo los campos necesarios
                            self.entry_calificacion.delete(0, tk.END)
                            self.entry_fecha.set_date(datetime.now())
                            self.concepto_seleccionado_id = None
                            
                            # Finalmente mostrar el mensaje de éxito
                            self.mostrar_mensaje("Éxito", "Calificación registrada correctamente")
                            
                        except Exception as e:
                            self.handle_database_error(e, "actualizar_ui_insercion")
                
                if not self.is_destroyed:
                    self.root.after(0, _actualizar_ui)
                
            except Exception as e:
                if connection:
                    connection.rollback()
                if not self.is_destroyed:
                    self.root.after(0, lambda: self.handle_database_error(e, "insertar_calificacion"))
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        # Ejecutar la inserción en un thread separado
        self.db_pool.executor.submit(_insertar)

    def _mostrar_dialogo_confirmacion(self, titulo, mensaje, accion_confirmacion):
        """Mostrar diálogo de confirmación genérico"""
        try:
            # Encontrar la ventana principal
            ventana_principal = self._find_root_window(self.root)
            
            # Crear diálogo
            dialog = ctk.CTkToplevel(ventana_principal)
            dialog.title(titulo)
            dialog.geometry("300x150")
            dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)
            
            # Hacer modal
            dialog.transient(ventana_principal)
            dialog.grab_set()
            
            # Centrar en la pantalla
            x = ventana_principal.winfo_x() + (ventana_principal.winfo_width() - 300) // 2
            y = ventana_principal.winfo_y() + (ventana_principal.winfo_height() - 150) // 2
            dialog.geometry(f'+{x}+{y}')
            
            # Mensaje
            label = ctk.CTkLabel(
                dialog,
                text=mensaje,
                font=ctk.CTkFont(size=14),
                wraplength=250
            )
            label.pack(pady=20)
            
            # Frame para botones
            button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            button_frame.pack(pady=10)
            
            def confirmar():
                dialog.destroy()
                accion_confirmacion()
            
            def cancelar():
                dialog.destroy()
            
            # Botones
            ctk.CTkButton(
                button_frame,
                text="Confirmar",
                command=confirmar,
                fg_color=EstiloApp.BOTON_INSERTAR,
                hover_color=EstiloApp.BOTON_INSERTAR_HOVER
            ).pack(side="left", padx=10)
            
            ctk.CTkButton(
                button_frame,
                text="Cancelar",
                command=cancelar,
                fg_color=EstiloApp.BOTON_ELIMINAR,
                hover_color=EstiloApp.BOTON_ELIMINAR_HOVER
            ).pack(side="left", padx=10)
            
        except Exception as e:
            self.logger.error(f"Error mostrando diálogo de confirmación: {str(e)}")
            self.mostrar_mensaje("Error", "No se pudo mostrar el diálogo de confirmación")

    def _find_root_window(self, widget):
        """Encuentra la ventana principal desde cualquier widget"""
        current = widget
        while current:
            if isinstance(current, (tk.Tk, ctk.CTk)):
                return current
            current = current.master
        return None

    def modificar_calificacion(self):
        """Modificar calificación seleccionada manteniendo datos del legajo"""
        if not self.concepto_seleccionado_id:
            self.mostrar_mensaje("Error", "Debe seleccionar una calificación para modificar")
            return

        if not self.validar_campos():
            return

        def _modificar():
            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                cursor = connection.cursor(buffered=True)
                
                fecha_sql = datetime.strptime(self.entry_fecha.get(), "%d-%m-%Y").strftime("%Y-%m-%d")
                
                sql = """
                UPDATE conceptos 
                SET legajo = %s, fecha = %s, concepto = %s
                WHERE id = %s
                """
                
                legajo = int(self.entry_legajo.get())
                datos = (
                    legajo,
                    fecha_sql,
                    self.entry_calificacion.get().strip(),
                    self.concepto_seleccionado_id
                )
                
                cursor.execute(sql, datos)
                connection.commit()
                
                def _actualizar_ui():
                    if not self.is_destroyed:
                        try:
                            # Primero actualizar los datos del empleado (esto actualizará las estadísticas)
                            self.consultar_empleado()
                            
                            # Luego limpiar solo los campos necesarios
                            self.entry_calificacion.delete(0, tk.END)
                            self.entry_fecha.set_date(datetime.now())
                            self.concepto_seleccionado_id = None
                            
                            # Finalmente mostrar el mensaje de éxito
                            self.mostrar_mensaje("Éxito", "Calificación modificada correctamente")
                            
                        except Exception as e:
                            self.handle_database_error(e, "actualizar_ui_modificacion")
                
                if not self.is_destroyed:
                    self.root.after(0, _actualizar_ui)
                
            except Exception as e:
                if connection:
                    connection.rollback()
                if not self.is_destroyed:
                    self.root.after(0, lambda: self.handle_database_error(e, "modificar_calificacion"))
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        self._mostrar_dialogo_confirmacion(
            "Confirmar modificación",
            "¿Está seguro que desea modificar esta calificación?",
            _modificar
        )

    def eliminar_calificacion(self):
        """Eliminar calificación seleccionada manteniendo datos del legajo"""
        seleccion = self.tree.selection()
        if not seleccion:
            self.mostrar_mensaje("Error", "Debe seleccionar una calificación para eliminar")
            return

        def _eliminar():
            connection = self.db_pool.get_connection()
            try:
                cursor = connection.cursor()
                item = self.tree.selection()[0]
                valores = self.tree.item(item)['values']
                
                sql = "DELETE FROM conceptos WHERE id = %s"
                datos = (valores[0],)
                
                cursor.execute(sql, datos)
                connection.commit()
                
                # Obtener el legajo antes de limpiar los campos
                legajo = self.entry_legajo.get()
                
                def _actualizar_vista():
                    self.mostrar_mensaje("Éxito", "Calificación eliminada correctamente")
                    self.limpiar_campos(mantener_legajo=True)  # Mantener legajo
                    if legajo:
                        self.consultar_calificaciones(legajo)
                        self.consultar_empleado()  # Actualizar estadísticas
                
                self.root.after(0, _actualizar_vista)
                
            except Exception as e:
                connection.rollback()
                self.root.after(0, lambda: self.handle_database_error(e, "eliminar_calificacion"))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)

        self._mostrar_dialogo_confirmacion(
            "Confirmar eliminación",
            "¿Está seguro que desea eliminar esta calificación?",
            _eliminar
        )

    def consultar_calificaciones(self, legajo=None):
        """Consultar calificaciones filtradas por legajo"""
        if self.is_destroyed or self.is_closing:  # Agregar verificación aquí
            return

        def _consultar():
            if self.is_destroyed or self.is_closing:  # Y aquí
                return

            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                if not connection:
                    return  # Salir silenciosamente si no hay conexión

                cursor = connection.cursor()
                cursor.execute("""
                    SELECT id, legajo, fecha, concepto
                    FROM conceptos 
                    WHERE legajo = %s
                    ORDER BY fecha DESC
                """, (legajo,))

                registros = cursor.fetchall()
                registros_convertidos = []

                for registro in registros:
                    if self.is_destroyed or self.is_closing:  # Verificar durante el procesamiento
                        return
                    try:
                        fecha_mysql = registro[2]
                        fecha_ui = datetime.strptime(str(fecha_mysql), '%Y-%m-%d').strftime('%d-%m-%Y')
                        registro_convertido = list(registro)
                        registro_convertido[2] = fecha_ui
                        registros_convertidos.append(tuple(registro_convertido))
                    except Exception as e:
                        print(f"Error convirtiendo registro: {str(e)}")
                        continue

                def _update_ui():
                    if self.is_destroyed or self.is_closing:  # Verificar antes de actualizar UI
                        return
                    self._clear_treeview()
                    for registro in registros_convertidos:
                        if self.is_destroyed or self.is_closing:
                            return
                        self.tree.insert("", tk.END, values=registro)

                if not self.is_destroyed and not self.is_closing and hasattr(self, 'root') and self.root.winfo_exists():
                    self.safe_after(0, _update_ui)

            except Exception as e:
                if not (self.is_destroyed or self.is_closing):
                    error_msg = str(e)
                    self.safe_after(0, lambda: self.handle_database_error(error_msg, "consultar_calificaciones"))
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        if not self.is_destroyed and not self.is_closing and self.db_pool:
            self.safe_submit(_consultar)

    def _check_active(self):
        """Verificar si la aplicación sigue activa y puede actualizar la UI"""
        return not self.is_destroyed and hasattr(self, 'root') and self.root.winfo_exists()

    def safe_after(self, delay, callback):
        """Ejecutar callback solo si la aplicación sigue activa"""
        if self.is_destroyed or self.is_closing:
            return None
            
        if hasattr(self, 'root') and self.root.winfo_exists():
            after_id = self.root.after(delay, callback)
            self.pending_operations.append(after_id)
            return after_id
        return None

    def safe_submit(self, func):
        """Ejecutar función en thread pool solo si la aplicación está activa"""
        if not self.is_destroyed and self.db_pool:
            self.db_pool.executor.submit(func)

    def limpiar_campos(self, event=None):
        """Limpiar todos los campos del formulario"""
        self.concepto_seleccionado_id = None
        self._ultimo_legajo_consultado = None
        
        # Limpiar campo de legajo
        if hasattr(self, 'entry_legajo'):
            self.entry_legajo.delete(0, tk.END)
        
        # Limpiar otros campos
        if hasattr(self, 'entry_calificacion'):
            self.entry_calificacion.delete(0, tk.END)
        
        if hasattr(self, 'entry_fecha'):
            self.entry_fecha.set_date(datetime.now())
        
        # Resetear labels de información
        if hasattr(self, 'nombre_completo_label'):
            self.nombre_completo_label.configure(text="👤 Apellido y Nombre: -")
        if hasattr(self, 'calificacion_alta_label'):
            self.calificacion_alta_label.configure(text="⭐ Concepto más alto: -")
        if hasattr(self, 'calificacion_baja_label'):
            self.calificacion_baja_label.configure(text="📉 Concepto más bajo: -")
        if hasattr(self, 'calificacion_promedio_label'):
            self.calificacion_promedio_label.configure(text="📊 Concepto Promedio: -")
        
        # Restaurar el placeholder de la foto
        if hasattr(self, 'photo_canvas'):
            self._mostrar_placeholder_foto()
        
        # Limpiar tabla
        self._clear_treeview()

    def _update_treeview(self, registros):
        """Actualizar treeview de forma segura"""
        if not self.is_destroyed and hasattr(self, 'tree'):
            try:
                self._clear_treeview()
                for registro in registros:
                    self.tree.insert("", tk.END, values=registro)
            except Exception as e:
                print(f"Error actualizando treeview: {str(e)}")

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
        
        text_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        text_frame.pack(fill='both', expand=True, padx=20, pady=(20,10))
        
        text_widget = ctk.CTkTextbox(
            text_frame,
            wrap='word',
            font=ctk.CTkFont(size=12),
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
        """Validar campos del formulario"""
        try:
            if not all([
                self.entry_legajo.get().strip(),
                self.entry_fecha.get().strip(),
                self.entry_calificacion.get().strip()
            ]):
                raise ValueError("Todos los campos son obligatorios")

            try:
                legajo = int(self.entry_legajo.get())
                if legajo <= 0:
                    raise ValueError("El legajo debe ser un número positivo")
            except ValueError:
                raise ValueError("El legajo debe ser un número válido")

            return True
        except ValueError as e:
            self.mostrar_mensaje("Error de validación", str(e))
            return False

    def mostrar_mensaje(self, titulo, mensaje, tipo="info"):
        """Mostrar mensaje de forma segura"""
        if self.is_destroyed or self.is_closing:
            return
            
        if self._showing_message:
            return
            
        self._showing_message = True
        
        try:
            if hasattr(self, 'mensaje_dialog') and self.mensaje_dialog:
                try:
                    self.mensaje_dialog.destroy()
                except:
                    pass
                    
            if not hasattr(self, 'root') or not self.root.winfo_exists():
                return
                
            self.mensaje_dialog = ctk.CTkToplevel(self.root)
            self.mensaje_dialog.title(titulo)
            self.mensaje_dialog.geometry("300x150")
            self.mensaje_dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)
            
            # Hacer el diálogo modal
            self.mensaje_dialog.transient(self.root)
            self.mensaje_dialog.grab_set()
            
            # Centrar el diálogo
            self.mensaje_dialog.update_idletasks()
            x = (self.mensaje_dialog.winfo_screenwidth() // 2) - (150)
            y = (self.mensaje_dialog.winfo_screenheight() // 2) - (75)
            self.mensaje_dialog.geometry(f'+{x}+{y}')

            # Contenido del diálogo
            label = ctk.CTkLabel(
                self.mensaje_dialog, 
                text=mensaje, 
                font=ctk.CTkFont(size=14), 
                wraplength=250
            )
            label.pack(pady=20)

            def _cerrar_dialogo(event=None):
                self._showing_message = False
                if hasattr(self, 'mensaje_dialog') and self.mensaje_dialog is not None:
                    try:
                        self.mensaje_dialog.grab_release()
                        self.mensaje_dialog.destroy()
                    except:
                        pass
                    self.mensaje_dialog = None

            # Botón de cerrar
            btn_aceptar = ctk.CTkButton(
                self.mensaje_dialog, 
                text="Aceptar", 
                command=_cerrar_dialogo, 
                width=100
            )
            btn_aceptar.pack(pady=10)

            # Vincular teclas
            self.mensaje_dialog.bind("<Escape>", _cerrar_dialogo)
            self.mensaje_dialog.bind("<Return>", _cerrar_dialogo)
            
            # Asegurar que el diálogo se cierre si la ventana principal se cierra
            self.mensaje_dialog.protocol("WM_DELETE_WINDOW", _cerrar_dialogo)

            btn_aceptar.focus_set()

        except Exception as e:
            print(f"Error mostrando mensaje: {e}")
        finally:
            self._showing_message = False

    def handle_database_error(self, error_msg, operacion):
        """Manejar errores de base de datos de forma segura"""
        if self.is_destroyed or self.is_closing:
            return
            
        self.logger.error(f"Error en {operacion}: {error_msg}")
        self.safe_after(0, lambda: self.mostrar_mensaje("Error", f"Error en la operación: {error_msg}"))

    def _init_async(self):
        """Inicialización asíncrona"""
        try:
            self.setup_window()
            self.create_gui()
            self.root.after(100, self._init_database)
        except Exception as e:
            self.mostrar_mensaje("Error", f"Error al iniciar la aplicación: {str(e)}")

    def _init_database(self):
        """Inicialización de la base de datos"""
        if self.is_destroyed or self.is_closing:
            return

        def _connect():
            if self.is_destroyed or self.is_closing:
                return
            try:
                self.db_pool = DatabasePool()
                def _show_success():
                    if not (self.is_destroyed or self.is_closing):
                        self.mostrar_mensaje("Éxito", "Conexión establecida correctamente")
                self.safe_after(0, _show_success)
            except Exception as e:
                if not (self.is_destroyed or self.is_closing):
                    error_msg = str(e)
                    self.safe_after(0, lambda: self.mostrar_mensaje(
                        "Error", f"Error al conectar con la base de datos: {error_msg}"
                    ))

        thread = threading.Thread(target=_connect)
        thread.daemon = True
        thread.start()

    def on_closing(self):
        """Manejar cierre de la aplicación"""
        if self.is_closing:
            return
        
        self.is_closing = True
        self.is_destroyed = True
        
        # Aumentar el delay a 500ms para dar más tiempo a las operaciones pendientes
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(500, self.cleanup)  # Aumentado de 100 a 500

    def cleanup(self):
        """Limpiar recursos antes de destruir el módulo"""
        try:
            if self.db_pool:
                self.db_pool.close()
            if self.is_standalone and hasattr(self, 'root'):
                self.root.destroy()
        except Exception as e:
            # Silenciar el error de winfo
            if "winfo" not in str(e):
                print(f"Error durante el cierre: {e}")

    def run(self):
        """Iniciar la aplicación"""
        try:
            self.root.mainloop()
        finally:
            self.cleanup()

    def _create_header_frame(self):
        """Crear el frame del encabezado con logo animado más grande"""
        header_frame = ctk.CTkFrame(
            self.main_container,
            fg_color="white",  # Fondo blanco puro
            corner_radius=10,
            height=160
        )
        header_frame.grid(row=0, column=0, sticky="new", padx=35, pady=(5, 2))
        header_frame.grid_propagate(False)
        header_frame.grid_columnconfigure(1, weight=1)

        # Frame específico para el logo
        logo_container = ctk.CTkFrame(
            header_frame,
            fg_color="transparent",
            width=150,
            height=120
        )
        logo_container.grid(row=0, column=0, rowspan=3, padx=(20, 10), pady=5, sticky="nsew")
        logo_container.grid_propagate(False)

        try:
            # Cargar el GIF animado
            gif_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                   "resources", "icons_gifs", "logo.gif")
            
            gif = Image.open(gif_path)
            frames = []
            
            # Calcular el tamaño manteniendo la proporción
            target_height = 200  # Mismo tamaño que en módulo_prestamos
            for frame in ImageSequence.Iterator(gif):
                frame = frame.convert('RGBA')
                # Obtener dimensiones originales
                width, height = frame.size
                # Calcular nueva anchura manteniendo proporción
                aspect_ratio = width / height
                target_width = int(target_height * aspect_ratio)
                
                # Redimensionar manteniendo proporción
                frame = frame.resize((target_width, target_height), Image.LANCZOS)
                frames.append(frame)
            
            # Crear el label dentro del contenedor del logo
            logo_label = tk.Label(
                logo_container,
                bg="white"
            )
            logo_label.place(relx=0.5, rely=0.5, anchor="center")
            
            def update_gif(frame_index=0):
                if hasattr(self, 'is_destroyed') and self.is_destroyed:
                    return
                frame = frames[frame_index]
                photo = ImageTk.PhotoImage(frame)
                logo_label.configure(image=photo)
                logo_label.image = photo
                
                next_frame = (frame_index + 1) % len(frames)
                logo_label.after(100, lambda: update_gif(next_frame))
            
            update_gif()

        except Exception as e:
            print(f"Error al cargar el logo: {e}")

        # Títulos
        title_label = ctk.CTkLabel(
            header_frame,
            text="Módulo de Conceptos - RRHH",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="black"
        )
        title_label.grid(row=0, column=1, sticky="sw", padx=(0, 10), pady=(10, 0))
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Gestión de Conceptos y Calificaciones",
            font=ctk.CTkFont(size=16),
            text_color="black"
        )
        subtitle_label.grid(row=1, column=1, sticky="nw", padx=(0, 10), pady=(2, 2))
        
        copyright_label = ctk.CTkLabel(
            header_frame,
            text="© 2025 Todos los derechos reservados",
            font=ctk.CTkFont(size=12),
            text_color="black"
        )
        copyright_label.grid(row=2, column=1, sticky="nw", padx=(0, 10), pady=(0, 5))

        return header_frame

    def _create_logo_placeholder(self, header_frame):
        """Crear placeholder para el logo cuando no se puede cargar"""
        placeholder = ctk.CTkLabel(
            header_frame,
            text="LOGO",
            font=ctk.CTkFont(size=20, weight="bold"),
            width=50,
            height=50,
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            corner_radius=10
        )
        placeholder.grid(row=0, column=0, rowspan=3, padx=(10, 20), pady=5)

    def _animate_logo(self):
        """Animar el logo con control de ejecución"""
        if not hasattr(self, 'animation_running'):
            self.animation_running = True
        
        if self.animation_running and hasattr(self, 'logo_label') and self.logo_label.winfo_exists():
            try:
                self.logo_label.configure(image=self.logo_frames[self.current_frame])
                self.current_frame = (self.current_frame + 1) % len(self.logo_frames)
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(100, self._animate_logo)
            except Exception as e:
                print(f"Error en animación del logo: {e}")

    def consultar_empleado(self, event=None):
        """Consultar datos del empleado cuando se ingresa el legajo."""
        if not self.db_pool or self.is_destroyed:
            return

        legajo = self.entry_legajo.get().strip()
        if not legajo:
            return

        self._ultimo_legajo_consultado = legajo

        def _consultar():
            if self.is_destroyed:
                return

            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                if not connection:
                    raise ConnectionError("No se pudo obtener conexión")

                cursor = connection.cursor(buffered=True)

                # Consulta modificada para ignorar conceptos con valor 0
                cursor.execute("""
                    SELECT 
                        p.apellido_nombre, 
                        p.foto,
                        (SELECT concepto
                         FROM conceptos 
                         WHERE legajo = p.legajo AND concepto > 0
                         ORDER BY concepto DESC, fecha DESC 
                         LIMIT 1) as max_concepto,
                        (SELECT DATE_FORMAT(fecha, '%m-%Y')
                         FROM conceptos 
                         WHERE legajo = p.legajo AND concepto > 0
                         ORDER BY concepto DESC, fecha DESC 
                         LIMIT 1) as max_fecha,
                        (SELECT concepto
                         FROM conceptos 
                         WHERE legajo = p.legajo AND concepto > 0
                         ORDER BY concepto ASC, fecha DESC 
                         LIMIT 1) as min_concepto,
                        (SELECT DATE_FORMAT(fecha, '%m-%Y')
                         FROM conceptos 
                         WHERE legajo = p.legajo AND concepto > 0
                         ORDER BY concepto ASC, fecha DESC 
                         LIMIT 1) as min_fecha,
                        COALESCE(AVG(CASE WHEN c.concepto > 0 THEN c.concepto END), 0) as promedio,
                        COUNT(CASE WHEN c.concepto > 0 THEN 1 END) as total_conceptos_validos
                    FROM personal p
                    LEFT JOIN conceptos c ON p.legajo = c.legajo
                    WHERE p.legajo = %s
                    GROUP BY p.legajo, p.apellido_nombre, p.foto
                """, (legajo,))
                
                resultado = cursor.fetchone()

                if resultado:
                    (apellido_nombre, foto_blob, max_concepto, max_fecha, 
                     min_concepto, min_fecha, promedio, total_conceptos) = resultado

                    def _actualizar_ui():
                        if self.is_destroyed or not self.root.winfo_exists():
                            return

                        # Actualizar nombre y estadísticas
                        self.nombre_completo_label.configure(
                            text=f"👤 Apellido y Nombre: {apellido_nombre}"
                        )

                        # Actualizar conceptos máximo y mínimo
                        max_text = f"Sin conceptos válidos"
                        min_text = f"Sin conceptos válidos"
                        if max_concepto and max_fecha:
                            max_text = f"{max_concepto} ({max_fecha})"
                        if min_concepto and min_fecha:
                            min_text = f"{min_concepto} ({min_fecha})"

                        self.calificacion_alta_label.configure(
                            text=f"⭐ Concepto más alto: {max_text}"
                        )
                        self.calificacion_baja_label.configure(
                            text=f"📉 Concepto más bajo: {min_text}"
                        )

                        # Actualizar promedio solo si hay conceptos válidos
                        if total_conceptos > 0 and promedio > 0:
                            promedio_texto = self._calcular_concepto_promedio(promedio)
                            self.calificacion_promedio_label.configure(
                                text=f"📊 Concepto Promedio: {promedio_texto} ({promedio:.2f})"
                            )
                        else:
                            self.calificacion_promedio_label.configure(
                                text="📊 Concepto Promedio: Sin conceptos válidos"
                            )

                        # Actualizar foto
                        self._mostrar_foto(foto_blob)

                        # Consultar y mostrar calificaciones en el treeview
                        self.consultar_calificaciones(legajo)

                    self.root.after(0, _actualizar_ui)
                else:
                    def _mostrar_error():
                        if not self.is_destroyed:
                            self.mostrar_mensaje("Error", f"El legajo {legajo} no existe en la base de datos.")
                            self.limpiar_campos()
                    self.root.after(0, _mostrar_error)

            except Exception as e:
                error_msg = str(e)  # Capturar el mensaje de error
                if not self.is_destroyed:
                    def _show_error():
                        self.handle_database_error(error_msg, "consultar_empleado")
                    self.root.after(0, _show_error)
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        self.db_pool.executor.submit(_consultar)

    def _calcular_concepto_promedio(self, promedio):
        """Calcular la clasificación del concepto según el promedio"""
        if promedio >= 8:
            return "Muy Bueno"
        elif promedio >= 6:
            return "Bueno"
        elif promedio >= 4:
            return "Regular"
        elif promedio >= 2:
            return "Malo"
        else:
            return "Muy Malo"

    def _mostrar_foto(self, foto_blob):
        """Mostrar la foto del empleado en el canvas."""
        self.photo_canvas.delete("all")
        
        if foto_blob and len(foto_blob) > 0:
            try:
                # Convertir blob a imagen
                image = Image.open(io.BytesIO(foto_blob))
                
                # Convertir a RGB si es necesario
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Redimensionar manteniendo proporciones para que quepa en 150x150
                image.thumbnail((150, 150), Image.Resampling.LANCZOS)
                
                # Convertir a PhotoImage
                photo = ImageTk.PhotoImage(image)
                
                # Calcular posición para centrar en el canvas
                x_center = 75
                y_center = 75
                
                # Mostrar en canvas centrado
                self.photo_canvas.create_image(x_center, y_center, image=photo, anchor="center")
                self.photo_canvas.image = photo  # Mantener referencia
                
            except Exception as e:
                self.logger.error(f"Error al cargar la imagen: {str(e)}")
                self._mostrar_placeholder_foto()
        else:
            self._mostrar_placeholder_foto()

    def _mostrar_placeholder_foto(self):
        """Mostrar placeholder cuando no hay foto disponible"""
        self.photo_canvas.delete("all")
        
        # Dibujar un círculo como fondo para el ícono
        self.photo_canvas.create_oval(
            25, 25, 125, 125,
            fill="#E0E0E0",
            outline=""
        )
        
        # Agregar ícono de usuario
        self.photo_canvas.create_text(
            75, 75,
            text="👤",
            font=("Arial", 40),
            fill="#909090"
        )
        
        # Texto abajo del ícono
        self.photo_canvas.create_text(
            75, 135,
            text="Sin foto",
            font=("Arial", 10),
            fill="#606060"
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
            
            # Obtener los datos de la calificación seleccionada    
            def _get_calificacion():
                connection = self.db_pool.get_connection()
                try:
                    cursor = connection.cursor()
                    cursor.execute("""
                        SELECT id, legajo, fecha, concepto
                        FROM conceptos 
                        WHERE id = %s
                    """, (valores[0],))
                    
                    resultado = cursor.fetchone()
                    if resultado:
                        self.safe_after(0, lambda: self._cargar_datos_calificacion(resultado))
                finally:
                    cursor.close()
                    self.db_pool.return_connection(connection)
            
            self.safe_submit(_get_calificacion)
                
        except Exception as e:
            self.mostrar_mensaje("Error", "Error al cargar los datos de la calificación")
            self.logger.error(f"Error en double click: {str(e)}")

    def _cargar_datos_calificacion(self, datos):
        """Cargar datos de calificación en el formulario"""
        try:
            if not datos:
                return
                
            self.concepto_seleccionado_id = datos[0]
            
            # Limpiar campos primero
            self.entry_legajo.delete(0, tk.END)
            self.entry_calificacion.delete(0, tk.END)
            
            # Cargar datos
            self.entry_legajo.insert(0, str(datos[1]))
            self.entry_fecha.set_date(datetime.strptime(str(datos[2]), "%Y-%m-%d"))
            self.entry_calificacion.insert(0, str(datos[3]))
            
            # Actualizar datos del empleado
            self.consultar_empleado()
            
        except Exception as e:
            self.logger.error(f"Error al cargar datos: {str(e)}, datos={datos}")
            self.mostrar_mensaje("Error", f"Error al cargar los datos: {str(e)}")

    def show_in_frame(self, parent_frame):
        """Mostrar el módulo en un frame específico"""
        try:
            # Limpiar estado anterior
            self.cleanup()
            
            # Reiniciar flags
            self.is_destroyed = False
            self.is_closing = False
            self._showing_message = False
            self.mensaje_dialog = None
            self.pending_operations = []
            
            # Limpiar el frame padre
            for widget in parent_frame.winfo_children():
                widget.destroy()
            
            # Configurar el frame padre
            parent_frame.grid_columnconfigure(0, weight=1)
            parent_frame.grid_rowconfigure(0, weight=1)
            
            # Actualizar referencias
            self.root = parent_frame
            
            # Crear el contenedor principal que ocupará todo el espacio
            self.main_container = ctk.CTkFrame(
                self.root,
                fg_color=EstiloApp.COLOR_PRINCIPAL
            )
            self.main_container.grid(row=0, column=0, sticky="nsew")
            
            # Configurar el grid del contenedor principal
            self.main_container.grid_columnconfigure(0, weight=1)
            self.main_container.grid_rowconfigure(0, weight=0)  # Header
            self.main_container.grid_rowconfigure(1, weight=1)  # Content
            
            # Crear header
            header_frame = self._create_header_frame()
            header_frame.grid(row=0, column=0, sticky="new", padx=10, pady=5)
            
            # Crear contenedor para el contenido principal
            content_frame = ctk.CTkFrame(
                self.main_container,
                fg_color=EstiloApp.COLOR_FRAMES,
                corner_radius=10
            )
            content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
            
            # Configurar el grid del content_frame
            content_frame.grid_columnconfigure(0, weight=1)
            content_frame.grid_rowconfigure(0, weight=0)  # Form
            content_frame.grid_rowconfigure(1, weight=1)  # Table
            
            # Crear formulario
            form_frame = self._create_form(content_frame)
            form_frame.grid(row=0, column=0, sticky="new", padx=10, pady=5)
            
            # Crear tabla
            table_frame = self._create_table(content_frame)
            table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
            
            # Forzar actualización de geometría
            self.main_container.update_idletasks()
            
            # Inicializar base de datos
            self._init_database()
            
        except Exception as e:
            self.logger.error(f"Error en show_in_frame: {str(e)}")
            raise

if __name__ == "__main__":
    try:
        print("\n🚀 Iniciando módulo de conceptos...")
        app = AplicacionConceptos()
        app.run()
    except Exception as e:
        print(f"❌ Error crítico: {str(e)}")
        logging.basicConfig(
            filename="logs/errores_críticos_conceptos.log",
            level=logging.CRITICAL,
            format='%(asctime)s - [%(levelname)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.critical(f"Error crítico: {str(e)}")
