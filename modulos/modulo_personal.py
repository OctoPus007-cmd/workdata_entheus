import os
import sys
# Agregar el directorio raíz al path de Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkcalendar import DateEntry
from datetime import datetime
from PIL import Image, ImageTk
import mysql.connector
import customtkinter as ctk
from typing import Optional, Tuple, Callable
from utils.interface_manager import EstiloApp, DialogManager, InterfaceManager
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import logging
import traceback
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from utils.thread_manager import ThreadManager

# Configurar tema claro
ctk.set_appearance_mode("light")  # Forzar modo claro
ctk.set_default_color_theme("blue")

# Cargar variables de entorno
load_dotenv()

# Fix for CustomTkinter scaling issues
def _fix_dpi_scaling():
    try:
        # Desactivar el DPI awareness
        ctk.deactivate_automatic_dpi_awareness()
        
        # Fix for scaling issues in Python 3.12
        from customtkinter.windows.widgets.scaling import ScalingTracker
        def _get_widget_scaling(self, *args, **kwargs):
            return 1.0
        ScalingTracker._get_widget_scaling = _get_widget_scaling
        
        # Fix window transparency issues
        def _block_update_dimensions_event(self): pass
        def _unblock_update_dimensions_event(self): pass
        tk.Tk.block_update_dimensions_event = _block_update_dimensions_event
        tk.Tk.unblock_update_dimensions_event = _unblock_update_dimensions_event
        
    except Exception as e:
        print(f"Warning: Could not apply scaling fixes: {e}")

#_fix_dpi_scaling()

# Directorio temporal para imágenes
TEMP_DIR = os.path.join(tempfile.gettempdir(), "personal_images")
os.makedirs(TEMP_DIR, exist_ok=True)

class DatabaseManager:
    """
    Gestor de base de datos que maneja conexiones asíncronas con MySQL.
    Implementa un sistema de cola para evitar bloqueos en la interfaz de usuario.
    
    Atributos:
        config (dict): Configuración de conexión a MySQL
        queue (Queue): Cola para manejar resultados asíncronos
    """
    def __init__(self):
        """Inicializar el gestor de base de datos"""
        self.config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_DATABASE'),  # Asegurarse de que esta variable existe en .env
            'port': os.getenv('DB_PORT', '3306')  # Puerto opcional
        }
        self.queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.connection_pool = []
        self._initialize_pool()
        self.dialog_manager = DialogManager()

    def _initialize_pool(self, pool_size=3):
        """Inicializar pool de conexiones"""
        try:
            # Verificar que tenemos la información de la base de datos
            if not self.config['database']:
                raise ValueError("No se ha especificado la base de datos en las variables de entorno")

            for _ in range(pool_size):
                connection = mysql.connector.connect(**self.config)
                if not connection.is_connected():
                    raise ConnectionError("No se pudo establecer la conexión con la base de datos")
                self.connection_pool.append(connection)
                
            print(f"Pool de conexiones inicializado con {pool_size} conexiones")
            print(f"Base de datos seleccionada: {self.config['database']}")
            
        except Exception as e:
            print(f"Error inicializando pool: {e}")
            raise

    def get_connection(self):
        """Obtener conexión del pool"""
        if not self.connection_pool:
            connection = mysql.connector.connect(**self.config)
            return connection
        return self.connection_pool.pop()

    def return_connection(self, connection):
        """Devolver conexión al pool"""
        if connection and connection.is_connected():
            self.connection_pool.append(connection)

    def execute_query_async(self, query: str, params: tuple = None, callback=None):
        """Ejecutar consulta de forma asíncrona"""
        def _async_query():
            connection = None
            cursor = None
            try:
                connection = self.get_connection()
                cursor = connection.cursor(buffered=True)  # Usar cursor buffered
                
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
                return result
                
            except Exception as e:
                print(f"Error en consulta: {str(e)}")
                if callback:
                    callback(None)
                return None
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.return_connection(connection)

        return _async_query()  # Ejecutar directamente y retornar el resultado

    def close(self):
        """Cerrar todas las conexiones y el executor"""
        for conn in self.connection_pool:
            try:
                conn.close()
            except:
                pass
        self.executor.shutdown(wait=True)

    def check_queue(self):
        """Verificar la cola de resultados"""
        while not self.queue.empty():
            callback, result = self.queue.get()
            callback(result)

class ImageHandler:
    """Manejador de imágenes para la aplicación"""
    def __init__(self, canvas):
        self.canvas = canvas
        self.current_image = None
        self.photo_preview = None
        self.image_path = None
        self.dialog_manager = DialogManager()

    def load_image(self, path: str) -> bool:
        try:
            # Cargar imagen original
            image = Image.open(path)
            
            # Convertir a RGB/RGBA si es necesario
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGBA')
            
            # Obtener dimensiones del canvas
            canvas_width = self.canvas.winfo_width() or 150
            canvas_height = self.canvas.winfo_height() or 150
            
            # Calcular ratio de aspecto de la imagen y el canvas
            image_ratio = image.width / image.height
            canvas_ratio = canvas_width / canvas_height
            
            # Calcular nuevas dimensiones manteniendo proporción
            if image_ratio > canvas_ratio:
                # Imagen más ancha que el canvas
                new_width = canvas_width
                new_height = int(canvas_width / image_ratio)
            else:
                # Imagen más alta que el canvas
                new_height = canvas_height
                new_width = int(canvas_height * image_ratio)
            
            # Redimensionar la imagen manteniendo la proporción
            self.current_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Si la imagen es más pequeña que el canvas, centrarla
            if new_width < canvas_width or new_height < canvas_height:
                # Crear una imagen en blanco del tamaño del canvas
                background = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
                # Calcular posición para centrar
                x = (canvas_width - new_width) // 2
                y = (canvas_height - new_height) // 2
                # Pegar la imagen redimensionada en el centro
                background.paste(self.current_image, (x, y))
                self.current_image = background
            
            # Actualizar las versiones para mostrar
            self.photo_preview = ImageTk.PhotoImage(self.current_image)
            self.image_path = path
            
            # Actualizar display
            self._display_image()
            return True
            
        except Exception as e:
            print(f"Error loading image: {str(e)}")
            self.dialog_manager.mostrar_mensaje(
                None,  # o self.parent si está disponible
                "Error",
                f"No se pudo cargar la imagen: {e}",
                tipo="error"
            )
            return False

    def rotate_image(self):
        """Rotar imagen y actualizar la vista"""
        if self.current_image:
            self.current_image = self.current_image.rotate(90, expand=True)
            self.current_image.thumbnail((150, 150), Image.LANCZOS)
            self.photo_preview = ImageTk.PhotoImage(self.current_image)
            
            # Guardar la imagen rotada temporalmente
            temp_rotated = os.path.join(TEMP_DIR, "temp_rotated.png")
            self.current_image.save(temp_rotated, "PNG")
            self.image_path = temp_rotated
            
            self._display_image()

    def get_image_data(self) -> bytes:
        """Obtener los datos binarios de la imagen actual"""
        if self.current_image:
            # Guardar la imagen actual en un buffer de bytes
            import io
            img_byte_arr = io.BytesIO()
            self.current_image.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
        return None

    def _display_image(self):
        """Mostrar imagen centrada en el canvas"""
        try:
            self.canvas.delete("all")
            if self.photo_preview:
                # Obtener dimensiones
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                
                # Calcular posición para centrado
                x = canvas_width // 2
                y = canvas_height // 2
                
                self.canvas.create_image(
                    x, y,
                    image=self.photo_preview,
                    anchor=tk.CENTER
                )
        except Exception as e:
            print(f"Error displaying image: {str(e)}")

class CustomDateEntry(ctk.CTkFrame):
    """Widget personalizado para calendario moderno"""
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent", height=25)
        self._setup_widgets()
        
    def _setup_widgets(self):
        self.entry_frame = ctk.CTkFrame(
            self, 
            fg_color=EstiloApp.COLOR_PRINCIPAL,
            height=25,
            border_width=1,
            border_color=EstiloApp.COLOR_SECUNDARIO
        )
        self.entry_frame.pack(fill=tk.X, expand=True)
        self.entry_frame.pack_propagate(False)
        
        # Ajustar el tamaño de fuente para que coincida con los demás campos
        custom_font = ('Roboto', 12)  # Reducido de 16 a 12 para coincidir con otros widgets
        
        self.entry = DateEntry(
            master=self.entry_frame,
            width=10,  # Reducido de 15 a 10
            date_pattern='dd-mm-yyyy',
            locale='es',
            font=custom_font,
            background=EstiloApp.COLOR_SECUNDARIO,
            foreground='white',
            selectbackground=EstiloApp.COLOR_PRINCIPAL,
            selectforeground='white',
            borderwidth=0,
            relief="flat"
        )
        self.entry.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Ajustar también el calendario emergente
        self.entry._top_cal.configure(background=EstiloApp.COLOR_SECUNDARIO)
        for w in self.entry._top_cal.winfo_children():
            if isinstance(w, tk.Button):
                w.configure(
                    background=EstiloApp.COLOR_SECUNDARIO,
                    activebackground=EstiloApp.COLOR_PRINCIPAL,
                    foreground=EstiloApp.COLOR_TEXTO,
                    font=('Roboto', 10)  # Reducido tamaño de fuente para el calendario
                )
            elif isinstance(w, tk.Label):  # Ajustar también las etiquetas del calendario
                w.configure(
                    font=('Roboto', 10)
                )

    def get(self):
        return self.entry.get()
        
    def set_date(self, date):
        self.entry.set_date(date)

class PersonalManagementApp:
    """
    Aplicación principal para la gestión de personal.
    Implementa una interfaz gráfica completa con funcionalidades CRUD.
    
    La aplicación se divide en las siguientes secciones principales:
    - Header: Logo y títulos
    - Formulario: Campos para datos del personal
    - Botones: Acciones CRUD y búsqueda
    - Tabla: Visualización de registros
    
    Utiliza operaciones asíncronas para la base de datos para mantener
    la interfaz responsiva durante operaciones largas.
    """

    def __init__(self, parent_frame):
        self.parent = parent_frame
        self.page_size = 50
        self.current_page = 0
        self.db = None
        
        print("🚀 Iniciando módulo de personal...")

        try:
            # Configurar logging
            self._setup_logging()
            
            # Inicializar ThreadManager antes de la base de datos
            self.thread_manager = ThreadManager(max_workers=4)
            
            # Inicializar base de datos
            self.db = DatabaseManager()
            
            # Verificar conexión
            def check_connection(result):
                if result:
                    print("✓ Conexión a base de datos establecida")
                    # Cargar datos iniciales después de confirmar la conexión
                    self._load_data()
                else:
                    print("❌ Error conectando a la base de datos")
                    raise Exception("No se pudo establecer conexión con la base de datos")
            
            # Resto de la inicialización
            self.interface_manager = InterfaceManager(self.parent)
            self._setup_main_frame()
            self._create_interface()
            self._setup_events()
            self._register_callbacks()
            
            # Verificar conexión usando ThreadManager
            self.thread_manager.submit_task(
                "check_connection",
                lambda: self.db.execute_query_async(
                    "SELECT 1", 
                    callback=check_connection
                )
            )
            
        except Exception as e:
            print(f"❌ Error en inicialización: {str(e)}")
            self.logger.error(f"Error en inicialización: {str(e)}")
            messagebox.showerror("Error", f"Error al inicializar el módulo: {str(e)}")

    def _on_record_updated(self, result):
        """Callback para cuando se actualiza un registro"""
        if result:
            self._show_dialog("Éxito", "Registro actualizado correctamente")
            self._clear_form()
            self._load_data()
        else:
            self._show_dialog("Error", "No se pudo actualizar el registro", "error")

    def _on_record_deleted(self, result):
        """Callback para cuando se elimina un registro"""
        if result:
            self._show_dialog("Éxito", "Registro eliminado correctamente")
            self._clear_form()
            self._load_data()
        else:
            self._show_dialog("Error", "No se pudo eliminar el registro", "error")

    def _setup_main_frame(self):
        """Configuración inicial del frame principal"""
        # Frame principal sin padding excesivo
        self.main_frame = ctk.CTkFrame(
            self.parent,
            fg_color=EstiloApp.COLOR_PRINCIPAL,
            width=1366,
            height=768
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.main_frame.pack_propagate(False)

    def _create_interface(self):
        """Crear todos los elementos de la interfaz"""
        self._create_header()
        self._create_form_section(self.main_frame)
        self._create_buttons_section()
        self._create_table(self.main_frame)
        self._load_data()  # Cargar datos iniciales

    def _setup_events(self):
        """Configurar eventos de la aplicación"""
        if self.db:
            self._check_queue_id = self.parent.after(100, self._check_db_queue)

    def _show_window(self):
        """Mostrar la ventana principal maximizada"""
        try:
            self.parent.update_idletasks()  # Asegurar que todo esté actualizado
            
            # Maximizar la ventana
            self.parent.state('zoomed')  # Esto maximiza la ventana en Windows
            
            # En algunas versiones de Linux puede necesitar:
            # self.parent.attributes('-zoomed', True)
            
            # Mostrar la ventana
            self.parent.deiconify()
            print("✨ Ventana mostrada correctamente (maximizada)")
        except Exception as e:
            print(f"❌ Error al mostrar ventana: {str(e)}")

    def _setup_logging(self):
        """Configurar el sistema de logging"""
        # Crear directorio logs si no existe
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Configurar el formato del log
        log_format = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(module)s - Línea %(lineno)d: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Configurar el manejador de archivos con rotación
        file_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, 'errores_personal.log'),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(log_format)
        
        # Configurar el logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        
        # Mensaje inicial
        self.logger.info("🚀 Módulo de Personal iniciado")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Estilo para fondo blanco
        style.configure('White.TFrame', background=EstiloApp.COLOR_PRINCIPAL)
        style.configure('White.TLabel', background=EstiloApp.COLOR_PRINCIPAL)
        style.configure('White.TButton', background=EstiloApp.COLOR_PRINCIPAL)
        style.configure('White.TEntry', background=EstiloApp.COLOR_PRINCIPAL)
        style.configure('White.TLabelframe', background=EstiloApp.COLOR_PRINCIPAL)  # Fondo blanco para LabelFrame
        style.configure('White.TLabelframe.Label', background=EstiloApp.COLOR_PRINCIPAL, font=('Roboto', 12))  # Fondo blanco y tamaño de texto 14 para LabelFrame

        # Agregar estilo para botones de búsqueda
        style.configure(
            'Search.TButton',
            background=EstiloApp.COLOR_SECUNDARIO,
            foreground='white',
            padding=(5, 2),
            font=('Roboto', 12)
        )
        
        # Configuración de estilos personalizados
        style.configure(
        'Modern.TButton',
        background=EstiloApp.COLOR_SECUNDARIO,
        foreground=EstiloApp.COLOR_TEXTO,
        padding=(10, 5),
        font=('Roboto', 12),
        borderwidth=0,
        relief='flat'
        )
        style.map('Modern.TButton',
        background=[('active', EstiloApp.COLOR_PRINCIPAL)],
        foreground=[('active', EstiloApp.COLOR_TEXTO)]
        )
        
        style.configure(
            'Custom.Treeview',
            background=EstiloApp.COLOR_PRINCIPAL,
            foreground=EstiloApp.COLOR_TEXTO,
            rowheight=25,
            fieldbackground=EstiloApp.COLOR_PRINCIPAL
        )
        
        style.configure(
            'Custom.Treeview.Heading',
            background=EstiloApp.COLOR_SECUNDARIO,
            foreground=EstiloApp.COLOR_TEXTO,
            padding=5
        )

    def _create_header(self):
        """Crear header moderno con CTkFrame"""
        header_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=EstiloApp.COLOR_HEADER,
            corner_radius=10
        )
        header_frame.pack(fill=tk.X, pady=(5, 10), padx=10)
        
        # Logo frame
        logo_frame = ctk.CTkFrame(
            header_frame, 
            fg_color='transparent',
            width=150,
            height=150
        )
        logo_frame.pack(side=tk.LEFT, padx=(20, 40), pady=20)  # Añadido pady para centrado vertical
        logo_frame.pack_propagate(False)
        
        # Logo label
        self.logo_label = ctk.CTkLabel(
            logo_frame,
            text="",
            width=150,
            height=150
        )
        self.logo_label.pack(expand=True, fill='both')

        try:
            # Cargar GIF
            logo_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'resources',
                'icons_gifs',
                'logo.gif'
            )
            self.gif_frames = []
            self.current_frame = 0
            
            # Cargar frames del GIF y convertirlos a CTkImage
            self._load_gif_frames()
            
            # Iniciar animación si hay frames
            if self.gif_frames:
                self._animate_gif()
                
        except Exception as e:
            self.logger.error(f"Error cargando logo: {e}")

        # Titles frame con mejor alineación
        titles_frame = ctk.CTkFrame(header_frame, fg_color='transparent')
        titles_frame.pack(side=tk.LEFT, fill=tk.Y, pady=20)  # Añadido pady para alineación vertical

        # Contenedor para los títulos con espaciado consistente
        ctk.CTkLabel(
            titles_frame,
            text="Módulo de Gestión de Personal - RRHH",
            font=('Roboto', 24, 'bold'),
            text_color=EstiloApp.COLOR_TEXTO,
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 5))

        ctk.CTkLabel(
            titles_frame,
            text="Entheus Seguridad",
            font=('Roboto', 16, 'bold'),
            text_color=EstiloApp.COLOR_SECUNDARIO,
            anchor="w"
        ).pack(fill=tk.X, pady=5)

        ctk.CTkLabel(
            titles_frame,
            text="© 2025 Todos los derechos reservados",
            font=('Roboto', 12),
            text_color=EstiloApp.COLOR_TEXTO,
            anchor="w"
        ).pack(fill=tk.X, pady=(5, 0))

    def _load_gif_frames(self):
        """Cargar frames del GIF del logo"""
        try:
            # Construir la ruta al archivo del logo
            logo_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'resources',
                'icons_gifs',
                'logo.gif'
            )
            
            if os.path.exists(logo_path):
                self.gif_frames = []
                self.current_frame = 0
                gif = Image.open(logo_path)
                
                # Calcular el tamaño manteniendo la proporción circular
                size = 300
                padding = 20  # Espacio alrededor del círculo
                circle_size = size - (padding * 2)
                
                for frame_index in range(0, gif.n_frames):
                    gif.seek(frame_index)
                    frame_image = gif.convert('RGBA')
                    
                    # Crear una imagen cuadrada con fondo transparente
                    square_image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                    
                    # Redimensionar el frame manteniendo la proporción
                    aspect_ratio = frame_image.width / frame_image.height
                    if aspect_ratio > 1:
                        new_width = circle_size
                        new_height = int(circle_size / aspect_ratio)
                    else:
                        new_height = circle_size
                        new_width = int(circle_size * aspect_ratio)
                    
                    frame_image = frame_image.resize((new_width, new_height), Image.LANCZOS)
                    
                    # Centrar la imagen en el cuadrado
                    x = (size - new_width) // 2
                    y = (size - new_height) // 2
                    square_image.paste(frame_image, (x, y))
                    
                    ctk_frame = ctk.CTkImage(
                        light_image=square_image,
                        dark_image=square_image,
                        size=(size, size)
                    )
                    self.gif_frames.append(ctk_frame)
                
                if self.gif_frames:
                    self.logo_label.configure(image=self.gif_frames[0])
                    self._animate_gif()
            else:
                self.logger.error(f"Archivo de logo no encontrado en: {logo_path}")
                self._create_placeholder_logo(self.logo_label)
                    
        except Exception as e:
            self.logger.error(f"Error cargando logo: {e}")
            self._create_placeholder_logo(self.logo_label)

    def _animate_gif(self):
        """Animar el GIF frame por frame usando CTkImage"""
        try:
            if (hasattr(self, 'logo_label') and 
                self.logo_label.winfo_exists() and 
                hasattr(self, 'gif_frames') and 
                self.gif_frames and 
                not hasattr(self, 'is_destroyed')):  # Cambiado para módulo personal
                
                # Actualizar el frame actual
                self.logo_label.configure(image=self.gif_frames[self.current_frame])
                self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
                
                # Programar siguiente frame
                if hasattr(self, 'main_frame') and self.main_frame.winfo_exists():
                    self.main_frame.after(100, self._animate_gif)  # Usar main_frame en lugar de main_container
            
        except Exception as e:
            print(f"Error en animación del logo: {e}")

    def _create_main_interface(self):
        # Crear las diferentes secciones
        self._create_form_section()
        self._create_buttons_section()
        self._create_table(self.main_frame)

    def _create_form_section(self, parent):
        """Crear formulario con tres columnas"""
        # Frame principal del formulario con tamaño fijo
        form_frame = ctk.CTkFrame(
            parent,
            fg_color=EstiloApp.COLOR_FRAMES,
            width=1326,
            height=250
        )
        form_frame.pack(fill=tk.X, pady=(0, 5), padx=10)
        form_frame.pack_propagate(False)

        # Configurar grid con 3 columnas
        form_frame.grid_columnconfigure(1, weight=3)  # Campos
        form_frame.grid_columnconfigure(2, weight=1)  # Foto
        form_frame.grid_columnconfigure(10, weight=1)  # Botones

        # Inicializar los widgets antes de usarlos
        self.entry_legajo = None
        self.entry_apellido_nombre = None
        self.entry_fecha_nacimiento = None
        self.entry_fecha_alta = None
        self.cargas_combobox = None
        self.estado_civil_combobox = None
        self.estudios_combobox = None
        
        # 1. Panel izquierdo - Campos de entrada
        self._create_entry_fields(form_frame)
        
        # 2. Panel central - Foto y datos del empleado
        self._create_photo_section(form_frame)
        
        # 3. Panel derecho - Botones CRUD
        self._create_crud_buttons(form_frame)

    def _create_entry_fields(self, parent):
        """Crear campos de entrada en el panel izquierdo"""
        fields_frame = ctk.CTkFrame(parent, fg_color="transparent")
        fields_frame.grid(row=0, column=0, padx=10, pady=2, sticky="nsew")
        
        # Título de la sección
        ctk.CTkLabel(
            fields_frame,
            text="Registre o Modifique datos del Empleado",
            font=('Roboto', 18, 'bold')
        ).pack(pady=(0, 2))

        # Frame contenedor para los campos (evitar expansión)
        fields_container = ctk.CTkFrame(fields_frame, fg_color="transparent")
        fields_container.pack(fill=tk.NONE, anchor="w")

        # Configuración de campos
        fields = [
            ("Legajo:", "entry_legajo", "entry"),
            ("Fecha Alta:", "entry_fecha_alta", "date"),
            ("Apellido y Nombres:", "entry_apellido_nombre", "entry"),
            ("Fecha Nac.:", "entry_fecha_nacimiento", "date"),
            ("Estado Civil:", "estado_civil_combobox", "combo", 
             ["No especifica", "Soltero/a", "Casado/a", "Divorciado/a", "Viudo/a"]),
            ("Estudios:", "estudios_combobox", "combo",
             ["No especifica", "Primaria", "Sec. incompleta", "Sec. completa"]),
            ("Cargas:", "cargas_combobox", "combo",
             ["No especifica", "No", "Sí"])
        ]

        for field in fields:
            frame = ctk.CTkFrame(fields_container, fg_color="transparent")
            frame.pack(anchor="w", pady=2)
            
            # Label con ancho fijo
            label = ctk.CTkLabel(
                frame,
                text=field[0],
                font=('Roboto', 14, 'bold'),
                width=150,
                anchor="e"
            )
            label.pack(side=tk.LEFT, padx=(10, 10))
            
            # Widget
            if field[2] == "entry":
                widget = ctk.CTkEntry(
                    frame,
                    width=200,
                    height=25,
                    font=('Roboto', 12, 'bold'),
                )
            elif field[2] == "date":
                widget = CustomDateEntry(frame)
            else:  # combo
                widget = ctk.CTkOptionMenu(
                    frame,
                    values=field[3],
                    width=150,
                    height=25,
                    font=('Roboto', 14, 'bold'),
                    fg_color=EstiloApp.COLOR_SECUNDARIO,
                    button_color=EstiloApp.COLOR_PRINCIPAL,
                    button_hover_color=EstiloApp.COLOR_SECUNDARIO,
                    text_color='black'
                )
                widget.set(field[3][0])
            
            widget.pack(side=tk.LEFT)
            setattr(self, field[1], widget)

    def _create_photo_section(self, parent):
        """Crear sección central con foto"""
        photo_frame = ctk.CTkFrame(parent, fg_color=EstiloApp.COLOR_FRAMES)
        photo_frame.grid(row=0, column=1, padx=5, pady=2, sticky="nsew")

        # Título de la sección centrado
        ctk.CTkLabel(
            photo_frame,
            text="Fotografía del Empleado",
            font=('Roboto', 18, 'bold'),
            text_color=EstiloApp.COLOR_TEXTO
        ).pack(pady=(2, 2))

        # Marco para la foto
        photo_container = ctk.CTkFrame(
            photo_frame,
            fg_color=EstiloApp.COLOR_PRINCIPAL,
            border_width=15,
            border_color=EstiloApp.COLOR_SECUNDARIO
        )
        photo_container.pack(pady=2)

        # Canvas para la foto
        self.image_canvas = tk.Canvas(
            photo_container,
            width=150,
            height=150,
            bg=EstiloApp.COLOR_PRINCIPAL,
            highlightthickness=5
        )
        self.image_canvas.pack(padx=5, pady=5)

        # Frame para botones centrados
        btn_frame = ctk.CTkFrame(photo_frame, fg_color="transparent", width=200)
        btn_frame.pack(pady=2)

        # Contenedor interno para centrar los botones
        inner_btn_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        inner_btn_frame.pack(expand=True)

        for text, cmd in [
            ("Seleccionar", self._select_photo),
            ("Rotar", lambda: self.image_handler.rotate_image()),
            ("Eliminar", self._delete_photo)
        ]:
            ctk.CTkButton(
                inner_btn_frame,
                text=text,
                command=cmd,
                font=('Roboto', 12, 'bold'),
                fg_color=EstiloApp.COLOR_SECUNDARIO,
                hover_color=EstiloApp.BOTON_HOVER,
                text_color='black',
                width=50, 
                height=42
            ).pack(side=tk.LEFT, padx=3)

        self.image_handler = ImageHandler(self.image_canvas)

    def _create_crud_buttons(self, parent):
        """Crear panel derecho con botones CRUD verticales"""
        buttons_frame = ctk.CTkFrame(parent, fg_color=EstiloApp.COLOR_FRAMES)
        buttons_frame.grid(row=0, column=2, padx=5, pady=2, sticky="nsew")

        # Título de la sección
        ctk.CTkLabel(
            buttons_frame,
            text="Acciones",
            font=('Roboto', 18, 'bold'),
            text_color=EstiloApp.COLOR_TEXTO
        ).pack(pady=(2, 2))

        # Botones CRUD en vertical
        crud_buttons = [
            ("Insertar", self._insert_record, EstiloApp.BOTON_INSERTAR, EstiloApp.BOTON_INSERTAR_HOVER),
            ("Modificar", self._update_record, EstiloApp.BOTON_MODIFICAR, EstiloApp.BOTON_MODIFICAR_HOVER),
            ("Eliminar", self._delete_record, EstiloApp.BOTON_ELIMINAR, EstiloApp.BOTON_ELIMINAR_HOVER),
            ("Limpiar", self._clear_form, EstiloApp.BOTON_LIMPIAR, EstiloApp.BOTON_LIMPIAR_HOVER)
        ]

        # Frame para contener los botones
        btn_container = ctk.CTkFrame(buttons_frame, fg_color="transparent")
        btn_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        for text, command, color, hover_color in crud_buttons:
            ctk.CTkButton(
                btn_container,
                text=text,
                command=command,
                font=('Roboto', 18, 'bold'),
                fg_color=color,
                hover_color=hover_color,
                text_color='black',
                height=45,
                width=1
            ).pack(pady=2, fill=tk.X)

    def _create_form_fields(self, left_parent, right_parent):
        # Crear campos para ambos lados (izquierdo y derecho)
        for parent, fields in [
            (left_parent, [
                ("Legajo:", "entry_legajo", "entry"),
                ("Fecha Alta:", "entry_fecha_alta", "date"),
                ("Apellido:", "entry_apellido_nombre", "entry")
            ]),
            (right_parent, [
                ("Fecha Nac.:", "entry_fecha_nacimiento", "date"),
                ("Estado Civil:", "estado_civil_combobox", "combo", 
                 ["No especifica", "Soltero/a", "Casado/a", "Divorciado/a", "Viudo/a"]),
                ("Cargas:", "cargas_combobox", "combo",
                 ["No especifica", "No", "Sí"]),
                ("Estudios:", "estudios_combobox", "combo",
                 ["No especifica", "Primaria", "Sec. incompleta", "Sec. completa"])
            ])
        ]:
            fields_frame = ctk.CTkFrame(parent, fg_color="transparent")
            fields_frame.pack(fill=tk.X, pady=5)
            
            for field in fields:
                frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
                frame.pack(fill=tk.X, pady=2)
                
                # Label con texto negro
                ctk.CTkLabel(
                    frame,
                    text=field[0],
                    font=('Roboto', 12),
                    width=100,
                    text_color=EstiloApp.COLOR_TEXTO  # Aseguramos texto negro
                ).pack(side=tk.LEFT, padx=(5, 10))
                
                # Widget
                if field[2] == "entry":
                    widget = ctk.CTkEntry(
                        frame,
                        font=('Roboto', 12),
                        height=25,
                        text_color=EstiloApp.COLOR_TEXTO  # Texto negro para entries
                    )
                elif field[2] == "date":
                    widget = CustomDateEntry(frame)
                else:  # combo
                    widget = ctk.CTkOptionMenu(
                        frame,
                        values=field[3],
                        font=('Roboto', 12),
                        height=25,
                        fg_color=EstiloApp.COLOR_SECUNDARIO,
                        button_color=EstiloApp.COLOR_PRINCIPAL,
                        button_hover_color=EstiloApp.COLOR_SECUNDARIO,
                        text_color=EstiloApp.COLOR_TEXTO  # Texto negro para combos
                    )
                    widget.set(field[3][0])
                    
                widget.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
                setattr(self, field[1], widget)

    def _create_image_section(self, parent):
        """Crear sección de imagen con CTkFrame"""
        image_frame = ctk.CTkFrame(
            parent,
            fg_color=EstiloApp.COLOR_FRAMES,
            border_width=1,
            border_color=EstiloApp.COLOR_SECUNDARIO,
            corner_radius=8
        )
        image_frame.grid(row=0, column=6, rowspan=2, padx=10, pady=5, sticky="nse")

        # Canvas para la imagen
        self.image_canvas = tk.Canvas(
            image_frame,
            width=150,
            height=150,
            bg=EstiloApp.COLOR_FRAMES,
            highlightthickness=1,
            highlightbackground=EstiloApp.COLOR_SECUNDARIO
        )
        self.image_canvas.pack(pady=5)

        # Manejador de imágenes
        self.image_handler = ImageHandler(self.image_canvas, self.dialog_manager)

        # Frame para botones
        btn_frame = ctk.CTkFrame(image_frame, fg_color='transparent')
        btn_frame.pack(fill=tk.X, pady=5, padx=10)

        # Botones modernos
        ctk.CTkButton(
            btn_frame,
            text="Seleccionar",
            command=self._select_photo,
            font=('Roboto', 12),
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            hover_color=EstiloApp.BOTON_HOVER,
            width=70
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            btn_frame,
            text="Rotar",
            command=self.image_handler.rotate_image,
            font=('Roboto', 12),
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            hover_color=EstiloApp.BOTON_HOVER,
            width=70
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            btn_frame,
            text="Eliminar",
            command=self._delete_photo,
            font=('Roboto', 12),
            fg_color=EstiloApp.BOTON_ELIMINAR,
            hover_color=EstiloApp.BOTON_ELIMINAR_HOVER,
            width=70
        ).pack(side=tk.LEFT, padx=2)

    def _delete_photo(self):
        """Eliminar la foto actual"""
        self.image_handler.current_image = None
        self.image_handler.photo_preview = None
        self.image_handler.image_path = None
        self.image_handler._display_image()    

    def _create_buttons_section(self):
        """Crear sección de búsqueda y paginación"""
        buttons_frame = ctk.CTkFrame(
            self.main_frame, 
            fg_color="transparent"
        )
        buttons_frame.pack(fill=tk.X, pady=2)

        # Frame para controles de búsqueda
        search_frame = ctk.CTkFrame(
            buttons_frame, 
            fg_color="transparent"
        )
        search_frame.pack(side=tk.RIGHT, fill=tk.X)

        # Actualizar combobox de búsqueda con texto negro y hover personalizado
        self.search_criteria = ctk.CTkOptionMenu(
            search_frame,
            values=["Apellido", "Legajo"],
            width=100,
            font=('Roboto', 12),
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            button_color=EstiloApp.COLOR_PRINCIPAL,
            button_hover_color=EstiloApp.BOTON_HOVER,
            text_color='black',
            dynamic_resizing=False
        )
        self.search_criteria.set("Apellido")
        self.search_criteria.pack(side=tk.LEFT, padx=(0, 5))

        # Entry para búsqueda
        self.search_entry = ctk.CTkEntry(
            search_frame,
            width=150,
            placeholder_text="Buscar...",
            font=('Roboto', 12)
        )
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # Agregar el evento Return al entry
        self.search_entry.bind('<Return>', lambda e: self._search_records())

        # Botón de búsqueda
        ctk.CTkButton(
            search_frame,
            text="Buscar",
            command=self._search_records,
            font=('Roboto', 12, 'bold'),
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            hover_color=EstiloApp.BOTON_HOVER,
            text_color='black',
            width=100
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Frame de paginación
        pagination_frame = ctk.CTkFrame(
            buttons_frame, 
            fg_color="transparent"
        )
        pagination_frame.pack(side=tk.LEFT, fill=tk.X, padx=20)

        # Botones de paginación
        for text, cmd in [("Anterior", self._load_previous_page), 
                         ("Siguiente", self._load_next_page)]:
            ctk.CTkButton(
                pagination_frame,
                text=text,
                command=cmd,
                font=('Roboto', 12),
                fg_color=EstiloApp.COLOR_SECUNDARIO,
                hover_color=EstiloApp.BOTON_HOVER,
                text_color='black',
                width=70
            ).pack(side=tk.LEFT, padx=2)

    def _create_table(self, parent):
        """Crear tabla moderna con estilo personalizado y scrolling suave"""
        # Crear contenedor con dimensiones fijas
        table_container = ctk.CTkFrame(
            parent,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=8,
            border_width=1,
            border_color=EstiloApp.COLOR_SECUNDARIO,
            width=1326,
            height=300
        )
        table_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        table_container.pack_propagate(False)

        # Frame para la tabla y scrollbar
        table_frame = ctk.CTkFrame(table_container, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar personalizado
        scroll_y = ctk.CTkScrollbar(table_frame)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Configurar estilos modernos
        style = ttk.Style()
        style.configure(
            "ModernTable.Treeview",
            background=EstiloApp.COLOR_FRAMES,
            foreground='black',
            fieldbackground=EstiloApp.COLOR_FRAMES,
            rowheight=25,
            font=('Roboto', 11),
            borderwidth=0,
            relief="flat"
        )
        style.configure(
            "ModernTable.Treeview.Heading",
            background=EstiloApp.COLOR_SECUNDARIO,
            foreground='black',
            font=('Roboto', 11, 'bold'),
            relief="flat",
            borderwidth=0
        )
        style.map(
            "ModernTable.Treeview",
            background=[
                ('selected', EstiloApp.COLOR_PRINCIPAL),
                ('!selected', EstiloApp.COLOR_FRAMES),
                ('hover', EstiloApp.COLOR_SECUNDARIO)
            ],
            foreground=[
                ('selected', 'black'),
                ('!selected', 'black'),
                ('hover', 'black')
            ]
        )
        
        # Para los encabezados específicamente
        style.map(
            "ModernTable.Treeview.Heading",
            background=[
                ('active', EstiloApp.COLOR_PRINCIPAL),
                ('!active', EstiloApp.COLOR_SECUNDARIO)
            ],
            foreground=[
                ('active', 'black'),
                ('!active', 'black')
            ]
        )

        # Crear Treeview
        self.tree = ttk.Treeview(
            table_frame,
            style="ModernTable.Treeview",
            columns=("legajo", "fecha_alta", "apellido_nombre", "fecha_nacimiento", 
                    "edad", "estado_civil", "cargas", "estudios"),
            show="headings",
            yscrollcommand=scroll_y.set
        )
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configurar scrollbar
        scroll_y.configure(command=self.tree.yview)

        # Agregar efecto hover
        def on_enter(event):
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.tag_configure('hover', background=EstiloApp.COLOR_SECUNDARIO)
                self.tree.item(item, tags=('hover',))

        def on_leave(event):
            for item in self.tree.get_children():
                self.tree.item(item, tags=())

        self.tree.bind('<Enter>', on_enter)
        self.tree.bind('<Leave>', on_leave)
        self.tree.bind('<Motion>', on_enter)

        # Definir columnas
        columnas = [
            ("legajo", "Legajo", 5),
            ("fecha_alta", "Fecha Alta", 20),
            ("apellido_nombre", "Apellido y Nombre", 250),
            ("fecha_nacimiento", "Fecha Nacimiento", 120),
            ("edad", "Edad", 60),
            ("estado_civil", "Estado Civil", 100),
            ("cargas", "Cargas", 60),
            ("estudios", "Estudios", 100)
        ]

        for col_id, heading, width in columnas:
            self.tree.heading(col_id, text=heading)
            self.tree.column(col_id, width=width, minwidth=width, anchor='center')

        # Empaquetar elementos
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Vincular evento de selección
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)

    def _search_records(self):
        """Buscar registros por criterio seleccionado"""
        self.current_page = 0
        criteria = self.search_criteria.get()
        value = self.search_entry.get().strip()

        if not value:
            self._load_data()
            return

        if (criteria == "Apellido"):
            query = """
            SELECT legajo, fecha_alta, apellido_nombre, fecha_nacimiento,
                   edad, estado_civil, cargas, estudios 
            FROM personal 
            WHERE apellido_nombre LIKE %s
            LIMIT %s OFFSET %s
            """
            params = (f"%{value}%", self.page_size, 0)
        else:
            query = """
            SELECT legajo, fecha_alta, apellido_nombre, fecha_nacimiento,
                   edad, estado_civil, cargas, estudios 
            FROM personal 
            WHERE legajo = %s
            LIMIT %s OFFSET %s
            """
            params = (value, self.page_size, 0)

        self.db.execute_query_async(query, params, callback=self._update_table)

    def _load_data(self):
        """Cargar datos de forma asíncrona usando ThreadManager"""
        try:
            query = """
            SELECT legajo, fecha_alta, apellido_nombre, fecha_nacimiento,
                   edad, estado_civil, cargas, estudios 
            FROM personal
            ORDER BY legajo
            LIMIT %s OFFSET %s
            """
            offset = self.current_page * self.page_size
            
            def on_data_loaded(result):
                if result:
                    self._update_table(result)
                else:
                    self.logger.warning("No se encontraron registros")
            
            self.thread_manager.submit_task(
                "load_data",
                lambda: self.db.execute_query_async(
                    query, 
                    (self.page_size, offset),
                    callback=on_data_loaded
                )
            )
            
        except Exception as e:
            self.logger.error(f"Error cargando datos: {e}")

    def _load_next_page(self):
        """Cargar siguiente página de registros"""
        self.current_page += 1
        self._load_data()

    def _load_previous_page(self):
        """Cargar página anterior de registros"""
        if self.current_page > 0:
            self.current_page -= 1
            self._load_data()

    def _update_table(self, records):
        """Actualizar la tabla con los resultados de manera segura"""
        try:
            # Verificar si el widget existe
            if not self.tree.winfo_exists():
                return

            # Asegurar que la actualización se ejecute en el hilo principal
            if threading.current_thread() != threading.main_thread():
                self.parent.after(0, lambda: self._update_table(records))
                return

            # Limpiar tabla existente
            for item in self.tree.get_children():
                self.tree.delete(item)

            if not records:
                return

            # Insertar nuevos registros
            for record in records:
                try:
                    fecha_alta = record[1].strftime('%d-%m-%Y') if record[1] else ''
                    fecha_nacimiento = record[3].strftime('%d-%m-%Y') if record[3] else ''
                    
                    formatted_record = (
                        record[0],
                        fecha_alta,
                        record[2],
                        fecha_nacimiento,
                        record[4] if record[4] is not None else '',
                        record[5] if record[5] is not None else '',
                        record[6] if record[6] is not None else '',
                        record[7] if record[7] is not None else ''
                    )
                    self.tree.insert("", tk.END, values=formatted_record)
                except Exception as e:
                    self.logger.error(f"Error al formatear registro: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error en actualización de tabla: {e}")

    def _clear_form(self):
        """Limpiar todos los campos del formulario"""
        try:
            if hasattr(self, 'entry_legajo') and self.entry_legajo:
                self.entry_legajo.delete(0, tk.END)
            if hasattr(self, 'entry_apellido_nombre') and self.entry_apellido_nombre:
                self.entry_apellido_nombre.delete(0, tk.END)
            if hasattr(self, 'entry_fecha_nacimiento') and self.entry_fecha_nacimiento:
                self.entry_fecha_nacimiento.set_date(datetime.now())
            if hasattr(self, 'entry_fecha_alta') and self.entry_fecha_alta:
                self.entry_fecha_alta.set_date(datetime.now())
            if hasattr(self, 'cargas_combobox') and self.cargas_combobox:
                self.cargas_combobox.set("")
            if hasattr(self, 'estado_civil_combobox') and self.estado_civil_combobox:
                self.estado_civil_combobox.set("")
            if hasattr(self, 'estudios_combobox') and self.estudios_combobox:
                self.estudios_combobox.set("")
            if hasattr(self, 'image_handler') and self.image_handler:
                self.image_handler.current_image = None
                self.image_handler.photo_preview = None
                self.image_handler.image_path = None
                self.image_handler._display_image()
            if hasattr(self, 'search_entry') and self.search_entry:
                self.search_entry.delete(0, tk.END)
            if hasattr(self, 'search_criteria') and self.search_criteria:
                self.search_criteria.set("Apellido")
        except Exception as e:
            print(f"Error en _clear_form: {str(e)}")
            self.logger.error(f"Error en _clear_form: {str(e)}")

    def _calculate_age(self, birth_date: str) -> int:
        """Calcular edad basada en la fecha de nacimiento"""
        today = datetime.now()
        birth = datetime.strptime(birth_date, "%Y-%m-%d")
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

    def _validate_date_format(self, date_str: str) -> bool:
        """Validar que la fecha esté en el formato dd-mm-yyyy"""
        try:
            datetime.strptime(date_str, '%d-%m-%Y')
            return True
        except ValueError:
            return False

    def _show_dialog(self, title: str, message: str, dialog_type: str = "info") -> bool:
        """Sistema de diálogos modernos"""
        try:
            dialog = ctk.CTkToplevel(self.parent)
            dialog.title(title)
            dialog.geometry("400x200")
            dialog.resizable(False, False)
            
            # Hacer el diálogo modal y centrado
            dialog.transient(self.parent)
            dialog.attributes('-topmost', True)
            
            # Calcular posición centrada
            x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (200)
            y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (100)
            dialog.geometry(f"+{x}+{y}")
            
            # Contenedor principal
            content_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            content_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

            # Mensaje con wraplength para evitar que se salga de la ventana
            message_label = ctk.CTkLabel(
                content_frame,
                text=message,
                font=('Roboto', 14),
                wraplength=350,
                justify='center',
                text_color='black'
            )
            message_label.pack(expand=True, pady=(20, 30))

            result = {"value": False}

            def on_close():
                dialog.grab_release()
                dialog.destroy()
                self.parent.focus_force()

            def on_yes():
                result["value"] = True
                on_close()

            def on_no():
                result["value"] = False
                on_close()

            # Frame para botones
            button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            button_frame.pack(side=tk.BOTTOM, pady=(0, 10))

            if dialog_type == "warning":
                # Botones para diálogo de advertencia
                ctk.CTkButton(
                    button_frame,
                    text="Sí",
                    command=on_yes,
                    width=100,
                    font=('Roboto', 13),
                    fg_color=EstiloApp.COLOR_SECUNDARIO
                ).pack(side=tk.LEFT, padx=5)
                
                ctk.CTkButton(
                    button_frame,
                    text="No",
                    command=on_no,
                    width=100,
                    font=('Roboto', 13),
                    fg_color=EstiloApp.BOTON_ELIMINAR
                ).pack(side=tk.LEFT, padx=5)
            else:
                # Botón único para otros tipos de diálogo
                ctk.CTkButton(
                    button_frame,
                    text="Aceptar",
                    command=on_yes,
                    width=100,
                    font=('Roboto', 13),
                    fg_color=EstiloApp.COLOR_SECUNDARIO
                ).pack(padx=5)

            # Hacer el diálogo modal
            dialog.protocol("WM_DELETE_WINDOW", on_close)
            dialog.grab_set()
            dialog.focus_force()
            
            # Binding de teclas
            dialog.bind("<Return>", lambda e: on_yes())
            dialog.bind("<Escape>", lambda e: on_close())
            
            self.parent.wait_window(dialog)
            return result["value"]
            
        except Exception as e:
            print(f"Error showing dialog: {str(e)}")
            return False

    def _validate_form(self) -> bool:
        try:
            if not self.entry_legajo.get().strip():
                self.logger.warning("Intento de guardar sin legajo")
                self._show_dialog("Error", "El campo Legajo es obligatorio", "error")
                return False
                
            if not self.entry_apellido_nombre.get().strip():
                self.logger.warning("Intento de guardar sin apellido y nombre")
                self._show_dialog("Error", "El campo Apellido y Nombre es obligatorio", "error")
                return False
                
            if not self._validate_date_format(self.entry_fecha_alta.get()):
                self.logger.warning("Formato de fecha inválido ingresado")
                self._show_dialog("Error", "El formato de la Fecha de Alta debe ser dd-mm-yyyy", "error")
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Error en validación de formulario: {str(e)}\n{traceback.format_exc()}")
            return False

    def _get_form_data(self) -> dict:
        """Obtener datos del formulario"""
        fecha_nacimiento = datetime.strptime(self.entry_fecha_nacimiento.get(), '%d-%m-%Y').strftime('%Y-%m-%d')
        fecha_alta = datetime.strptime(self.entry_fecha_alta.get(), '%d-%m-%Y').strftime('%Y-%m-%d')
        return {
            'legajo': int(self.entry_legajo.get()),
            'fecha_alta': fecha_alta,
            'apellido_nombre': self.entry_apellido_nombre.get().strip(),
            'fecha_nacimiento': fecha_nacimiento,
            'edad': self._calculate_age(fecha_nacimiento),
            'estado_civil': self.estado_civil_combobox.get(),
            'cargas': self.cargas_combobox.get(),
            'estudios': self.estudios_combobox.get()
        }

    def _insert_record(self):
        """Insertar nuevo registro usando ThreadManager"""
        if not self._validate_form():
            return

        try:
            data = self._get_form_data()
            photo_blob = self.image_handler.get_image_data() if self.image_handler.current_image else None

            query = """INSERT INTO personal (legajo, fecha_alta, apellido_nombre, 
                      fecha_nacimiento, edad, estado_civil, cargas, estudios, foto)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            
            params = (
                data['legajo'], data['fecha_alta'], data['apellido_nombre'],
                data['fecha_nacimiento'], data['edad'], data['estado_civil'],
                data['cargas'], data['estudios'], photo_blob
            )

            def _execute_insert():
                connection = self.db.get_connection()
                try:
                    cursor = connection.cursor()
                    cursor.execute(query, params)
                    connection.commit()
                    
                    self.parent.after(0, lambda: self._handle_insert_complete(True))
                    
                except Exception as e:
                    connection.rollback()
                    self.parent.after(0, lambda: self._handle_insert_complete(False))
                    self.logger.error(f"Error en inserción: {str(e)}")
                finally:
                    cursor.close()
                    self.db.return_connection(connection)

            self.thread_manager.submit_task("insert_record", _execute_insert)

        except Exception as e:
            self.logger.error(f"Error preparando inserción: {str(e)}")
            self._show_dialog("Error", f"Error al insertar registro: {str(e)}", "error")

    def _handle_insert_complete(self, success: bool):
        """Manejar la finalización de una inserción"""
        if success:
            self._show_dialog("Éxito", "Registro insertado correctamente")
            self._clear_form()
            self.parent.after(100, self._load_data)
        else:
            self._show_dialog("Error", "No se pudo insertar el registro", "error")

    def _update_record(self):
        """Actualizar registro usando ThreadManager"""
        if not self._validate_form():
            return

        selected = self.tree.selection()
        if not selected:
            self._show_dialog("Advertencia", "Por favor, seleccione un registro", "warning")
            return

        try:
            data = self._get_form_data()
            photo_blob = self.image_handler.get_image_data() if self.image_handler.current_image else None
            
            query = """UPDATE personal SET 
                      legajo = %s, fecha_alta = %s, apellido_nombre = %s,
                      fecha_nacimiento = %s, edad = %s, estado_civil = %s,
                      cargas = %s, estudios = %s, foto = %s
                      WHERE legajo = %s"""
            
            params = (
                data['legajo'], data['fecha_alta'], data['apellido_nombre'],
                data['fecha_nacimiento'], data['edad'], data['estado_civil'],
                data['cargas'], data['estudios'], photo_blob, data['legajo']
            )

            def _execute_update():
                connection = self.db.get_connection()
                try:
                    cursor = connection.cursor()
                    cursor.execute(query, params)
                    connection.commit()
                    
                    self.parent.after(0, lambda: self._handle_update_complete(True))
                    
                except Exception as e:
                    connection.rollback()
                    self.parent.after(0, lambda: self._handle_update_complete(False))
                    self.logger.error(f"Error en actualización: {str(e)}")
                finally:
                    cursor.close()
                    self.db.return_connection(connection)

            self.thread_manager.submit_task("update_record", _execute_update)

        except Exception as e:
            self.logger.error(f"Error preparando actualización: {str(e)}")
            self._show_dialog("Error", f"Error al actualizar registro: {str(e)}", "error")

    def _handle_update_complete(self, success: bool):
        """Manejar la finalización de una actualización"""
        if success:
            self._show_dialog("Éxito", "Registro actualizado correctamente")
            self._clear_form()
            self.parent.after(100, self._load_data)
        else:
            self._show_dialog("Error", "No se pudo actualizar el registro", "error")

    def _delete_record(self):
        """Eliminar registro usando ThreadManager"""
        selected = self.tree.selection()
        if not selected:
            self._show_dialog("Advertencia", "Por favor, seleccione un registro", "warning")
            return

        if self._show_dialog("Confirmar", "¿Está seguro de eliminar este registro?", "warning"):
            try:
                legajo = self.tree.item(selected[0])['values'][0]
                query = "DELETE FROM personal WHERE legajo = %s"

                def _execute_delete():
                    connection = self.db.get_connection()
                    try:
                        cursor = connection.cursor()
                        cursor.execute(query, (legajo,))
                        connection.commit()
                        
                        self.parent.after(0, lambda: self._handle_delete_complete(True))
                        
                    except Exception as e:
                        connection.rollback()
                        self.parent.after(0, lambda: self._handle_delete_complete(False))
                        self.logger.error(f"Error en eliminación: {str(e)}")
                    finally:
                        cursor.close()
                        self.db.return_connection(connection)

                self.thread_manager.submit_task("delete_record", _execute_delete)

            except Exception as e:
                self.logger.error(f"Error preparando eliminación: {str(e)}")
                self._show_dialog("Error", f"Error al eliminar registro: {str(e)}", "error")

    def _handle_delete_complete(self, success: bool):
        """Manejar la finalización de una eliminación"""
        if success:
            self._show_dialog("Éxito", "Registro eliminado correctamente")
            self._clear_form()
            self.parent.after(100, self._load_data)
        else:
            self._show_dialog("Error", "No se pudo eliminar el registro", "error")

    def _on_tree_select(self, event=None):
        """Manejar selección en la tabla"""
        selected = self.tree.selection()
        if not selected:
            return

        values = self.tree.item(selected[0])['values']
        
        try:
            # Limpiar formulario actual
            self._clear_form()
            
            # Llenar formulario con datos básicos de manera inmediata
            self.entry_legajo.insert(0, values[0] if values[0] else '')
            self.entry_apellido_nombre.insert(0, values[2] if values[2] else '')
            
            # Configurar fechas de manera segura
            def set_dates():
                if values[1]:  # fecha_alta
                    try:
                        self.entry_fecha_alta.set_date(datetime.strptime(values[1], '%d-%m-%Y'))
                    except:
                        self.entry_fecha_alta.set_date(datetime.now())
                        
                if values[3]:  # fecha_nacimiento
                    try:
                        self.entry_fecha_nacimiento.set_date(datetime.strptime(values[3], '%d-%m-%Y'))
                    except:
                        self.entry_fecha_nacimiento.set_date(datetime.now())
            
            # Aplicar fechas con un pequeño retardo
            self.parent.after(20, set_dates)
            
            # Establecer valores de los combobox con un pequeño retardo
            def set_combos():
                self.estado_civil_combobox.set(values[5] if values[5] else "No especifica")
                self.cargas_combobox.set(values[6] if values[6] else "No especifica")
                self.estudios_combobox.set(values[7] if values[7] else "No especifica")
                
            self.parent.after(30, set_combos)

            # Guardar los valores originales
            self.original_values = {
                'legajo': values[0],
                'fecha_alta': values[1],
                'apellido_nombre': values[2],
                'fecha_nacimiento': values[3],
                'estado_civil': values[5],
                'cargas': values[6],
                'estudios': values[7]
            }

            # Cargar foto con retardo controlado
            temp_image_path = os.path.join(TEMP_DIR, f"temp_{values[0]}.png")
            query = "SELECT foto FROM personal WHERE legajo = %s"
            
            def on_photo_load(result):
                if result and result[0][0]:  # Verificar que hay resultado y foto
                    try:
                        with open(temp_image_path, 'wb') as file:
                            file.write(result[0][0])
                        # Usar retardo para evitar problemas de escalado
                        self.parent.after(50, lambda: self.image_handler.load_image(temp_image_path))
                    except Exception as e:
                        print(f"Error al cargar imagen: {e}")

            self.db.execute_query_async(query, (values[0],), callback=on_photo_load)

        except Exception as e:
            print(f"Error al cargar datos en formulario: {str(e)}")
            self._show_dialog("Error", "Error al cargar los datos del registro", "error")

    def _select_photo(self):
        """Seleccionar foto de perfil"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if file_path:
            self.image_handler.load_image(file_path)

    def _check_db_queue(self):
        """Verificar la cola de la base de datos periódicamente"""
        try:
            if self.db and not self.parent.winfo_exists():
                return
                
            if self.db:
                self.db.check_queue()
                self._check_queue_id = self.parent.after(100, self._check_db_queue)
                
        except Exception as e:
            print(f"Error checking queue: {e}")

    def _on_close(self):
        """Manejar el cierre de la aplicación"""
        try:
            if hasattr(self, 'gif_frames'):
                self.gif_frames = []
            
            if hasattr(self, '_check_queue_id'):
                self.parent.after_cancel(self._check_queue_id)
            
            if hasattr(self, 'thread_manager'):
                self.thread_manager.shutdown()
            
            if self.db:
                self.db.close()
                
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def _register_callbacks(self):
        """Registrar callbacks para los eventos de la aplicación"""
        try:
            # Registrar callback para actualización de datos
            self.interface_manager.register_callback("data_loaded", self._update_table)
            
            # Callbacks para operaciones CRUD
            self.interface_manager.register_callback("record_inserted", self._on_record_inserted)
            self.interface_manager.register_callback("record_updated", self._on_record_updated)
            self.interface_manager.register_callback("record_deleted", self._on_record_deleted)
            
            print("✓ Callbacks registrados correctamente")
        except Exception as e:
            print(f"❌ Error registrando callbacks: {e}")
            self.logger.error(f"Error en registro de callbacks: {e}")

    def _on_record_inserted(self, result: bool):
        """Callback para cuando se inserta un registro"""
        if result:
            self._show_dialog("Éxito", "Registro insertado correctamente")
            self._clear_form()
            self._load_data()
        else:
            self._show_dialog("Error", "No se pudo insertar el registro", "error")

    def __del__(self):
        """Destructor para limpiar recursos"""
        if hasattr(self, 'thread_manager'):
            self.thread_manager.shutdown()

class ModuloPersonal:
    def __init__(self, parent):
        self.parent = parent
        self.dialog_manager = DialogManager()
        self.interface_manager = InterfaceManager(parent)
        
        # Frame principal usando los colores de EstiloApp
        self.frame = ctk.CTkFrame(
            parent,
            fg_color=EstiloApp.COLOR_FRAMES
        )
        
        # Ejemplo de botón con estilos consistentes
        self.btn_agregar = ctk.CTkButton(
            self.frame,
            text="Agregar Personal",
            font=("Roboto", 13),
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            hover_color=EstiloApp.COLOR_HOVER,
            command=self.agregar_personal
        )
        
        # Ejemplo de tabla o lista
        self.tabla_personal = ctk.CTkFrame(
            self.frame,
            fg_color=EstiloApp.COLOR_PRINCIPAL
        )
        
    def mostrar_error(self, mensaje: str):
        """Utiliza DialogManager para mostrar errores"""
        self.dialog_manager.mostrar_mensaje(
            self.parent,
            "Error",
            mensaje,
            tipo="error"
        )
    
    def confirmar_eliminacion(self, id_personal: int):
        """Utiliza DialogManager para confirmaciones"""
        self.dialog_manager.mostrar_confirmacion(
            self.parent,
            "Confirmar Eliminación",
            "¿Está seguro que desea eliminar este registro?",
            lambda: self.eliminar_personal(id_personal)
        )
    
    def mostrar_carga(self, mensaje: str = "Procesando..."):
        """Utiliza InterfaceManager para mostrar overlay de carga"""
        overlay = self.interface_manager.show_loading(mensaje)
        return overlay

# Agregar después de las importaciones existentes y antes de la clase PersonalManagementApp

# Modificar la sección de ejecución directa
if __name__ == "__main__":
    try:
        print("\n🔵 Iniciando módulo personal en modo standalone...")
        root = ctk.CTk()
        app = PersonalManagementApp(root)
        print("🔵 Iniciando mainloop...")
        root.mainloop()
    except Exception as e:
        print(f"❌ Error crítico: {str(e)}")
        logging.basicConfig(
            filename="logs/errores_críticos_personal.log",
            level=logging.CRITICAL,
            format='%(asctime)s - [%(levelname)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.critical(f"Error crítico al iniciar módulo de personal: {str(e)}\n{traceback.format_exc()}")
        print(f"Error al iniciar la aplicación: {e}")

# ...rewritten code...