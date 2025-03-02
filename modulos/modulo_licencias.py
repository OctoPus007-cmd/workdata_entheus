import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from tkcalendar import DateEntry
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import mysql.connector
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk, ImageSequence, ImageDraw
import io
import logging
from datetime import datetime, date
import traceback
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from io import BytesIO

# Importaciones de utils
from utils.thread_manager import ThreadManager, DatabasePool
from utils.interface_manager import EstiloApp

# Cargar variables de entorno
load_dotenv()

# Configuración de tema y colores
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class EstiloApp:
    """Clase para definir los colores y estilos de la aplicación"""
    COLOR_PRINCIPAL = "#E3F2FD"
    COLOR_SECUNDARIO = "#90CAF9"
    COLOR_TEXTO = "#000000"
    COLOR_FRAMES = "#BBDEFB"
    COLOR_HEADER = "#FFFFFF"

    # Nuevos colores para botones CRUD
    BOTON_INSERTAR = "#4CAF50"  # Verde - representa creación/nuevo
    BOTON_INSERTAR_HOVER = "#45A049"  # Verde más oscuro
    
    BOTON_MODIFICAR = "#2196F3"  # Azul - representa actualización
    BOTON_MODIFICAR_HOVER = "#1976D2"  # Azul más oscuro
    
    BOTON_ELIMINAR = "#F44336"  # Rojo - representa eliminación/peligro
    BOTON_ELIMINAR_HOVER = "#D32F2F"  # Rojo más oscuro
    
    BOTON_LIMPIAR = "#757575"  # Gris - representa acción neutral
    BOTON_LIMPIAR_HOVER = "#616161"  # Gris más oscuro

class AplicacionLicencias:
    def __init__(self, parent_frame=None):
        self.is_destroyed = False
        self.is_standalone = parent_frame is None
        self.licencia_seleccionada_id = None
        self._ultimo_legajo_consultado = None
        
        print("=== INICIANDO APLICACIÓN LICENCIAS ===")
        
        # Configurar logging
        self._setup_logging()
        
        # Configuración de base de datos
        print(f"Variables de entorno: HOST={os.getenv('DB_HOST')}, USER={os.getenv('DB_USER')}, DB={os.getenv('DB_DATABASE')}")
        
        self.db_config = {
            'host': os.getenv('DB_HOST') or 'localhost',
            'user': os.getenv('DB_USER') or 'root',
            'password': os.getenv('DB_PASSWORD') or '',
            'database': os.getenv('DB_DATABASE') or 'antecedentes_laborales'
        }
        
        print(f"Configuración DB: {self.db_config}")
        
        # Inicializar pool de base de datos
        try:
            print("Intentando inicializar pool de base de datos...")
            self.db_pool = DatabasePool()
            print("Pool de base de datos inicializado correctamente")
        except Exception as e:
            print(f"ERROR al inicializar pool de base de datos: {str(e)}")
        
        if parent_frame is None:
            self.root = ctk.CTk()
            self.root.title("Módulo de Licencias Sin Goce")
            self.root.geometry("1280x720")
            self.root.protocol("WM_DELETE_WINDOW", self.cleanup)
            self.parent = None
            # Crear GUI en modo standalone
            self.create_gui()
        else:
            self.show_in_frame(parent_frame)

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
            filename=os.path.join(log_dir, 'errores_licencias.log'),
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
        self.logger.info("🚀 Aplicación iniciada")

    def _init_async(self):
        """Inicialización asíncrona de la aplicación"""
        try:
            # Configurar ventana
            self.setup_window()
            
            # Eliminar mensaje de carga
            if hasattr(self, 'loading_label'):
                self.loading_label.destroy()
            
            # Crear interfaz
            self.create_gui()
            
            # Inicializar base de datos en segundo plano
            self.root.after(100, self._init_database)
            
        except Exception as e:
            self.mostrar_mensaje("Error", f"Error al iniciar la aplicación: {str(e)}")

    def _init_database(self):
        """Inicializar conexión a base de datos de forma asíncrona"""
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
        
        # Crear thread para conexión
        thread = threading.Thread(target=_connect)
        thread.daemon = True
        thread.start()

    def on_closing(self):
        """Manejar el evento de cierre"""
        if self.is_destroyed:
            return
        
        self.is_destroyed = True
        
        # Cerrar conexiones de la base de datos
        if self.db_pool:
            self.db_pool.close()
        
        # Cancelar eventos programados
        try:
            if hasattr(self, '_init_async') and callable(self._init_async):
                self.root.after_cancel(self._init_async)
        except Exception:
            pass
        
        # Destruir la ventana solo en modo standalone
        if self.is_standalone and self.root.winfo_exists():
            self.root.quit()
            self.root.destroy()

    def cleanup(self):
        """Limpiar recursos al cerrar"""
        if hasattr(self, 'is_destroyed') and self.is_destroyed:
            return
        
        try:
            self.is_destroyed = True
            
            # Limpiar pool de base de datos si existe
            if hasattr(self, 'db_pool'):
                try:
                    self.db_pool.executor.shutdown(wait=False)
                except Exception:
                    pass
            
            # Cerrar ventana solo si estamos en modo standalone
            if self.is_standalone:
                try:
                    # Verificar si la ventana aún existe y es válida
                    if (hasattr(self, 'root') and 
                        isinstance(self.root, (ctk.CTk, tk.Tk)) and 
                        self.root.winfo_exists()):
                        self.root.quit()
                        self.root.destroy()
                except (tk.TclError, RuntimeError, Exception):
                    pass  # Ignorar errores si la ventana ya fue destruida
                    
        except Exception as e:
            # Solo registrar el error, no hacer nada más
            if hasattr(self, 'logger'):
                self.logger.error(f"Error en cleanup: {str(e)}")

    def iniciar_aplicacion(self):
        """Iniciar la aplicación principal optimizando la carga"""
        try:
            if not self.root:
                self.root = ctk.CTk()
                self.setup_window()
                self.create_gui()
                
                # Configure cleanup on window close
                self.root.protocol("WM_DELETE_WINDOW", self.cleanup)
                
                # Initialize database after UI is shown
                self.root.after(100, self.initialize_database)
            
            self.root.mainloop()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al iniciar la aplicación: {str(e)}")
            self.cleanup()

    def run(self):
        """Iniciar aplicación en modo standalone"""
        if not self.parent:  # Solo si no está en modo integrado
            self.root.mainloop()

    def handle_database_error(self, error, operacion):
        """Manejar errores de base de datos de forma centralizada"""
        error_msg = str(error)
        error_type = type(error).__name__
        stack_trace = traceback.format_exc()
        
        # Registrar el error con nivel apropiado
        if isinstance(error, mysql.connector.Error):
            if error.errno in [1045, 2003]:  # Errores críticos de conexión
                self.logger.critical(f"""
                ERROR CRÍTICO DE BASE DE DATOS
                Operación: {operacion}
                Tipo: {error_type}
                Mensaje: {error_msg}
                Traza: {stack_trace}
                """)
            else:
                self.logger.error(f"""
                ERROR DE BASE DE DATOS
                Operación: {operacion}
                Tipo: {error_type}
                Mensaje: {error_msg}
                Traza: {stack_trace}
                """)
        elif isinstance(error, ValueError):
            self.logger.warning(f"""
            ERROR DE VALIDACIÓN
            Operación: {operacion}
            Mensaje: {error_msg}
            """)
        else:
            self.logger.error(f"""
            ERROR INESPERADO
            Operación: {operacion}
            Tipo: {error_type}
            Mensaje: {error_msg}
            Traza: {stack_trace}
            """)

        # Mostrar mensaje al usuario
        mensaje = self._get_error_message(error)
        self.mostrar_mensaje("Error", mensaje, tipo="error")

    def _get_error_message(self, error):
        """Obtener mensaje de error apropiado según el tipo"""
        if isinstance(error, mysql.connector.Error):
            if error.errno == 1045:
                return "Error de acceso a la base de datos: Credenciales incorrectas"
            elif error.errno == 1049:
                return "Error: Base de datos no existe"
            elif error.errno == 1062:
                return "Error: Registro duplicado"
            elif error.errno == 1146:
                return "Error: La tabla no existe"
            elif error.errno == 2003:
                return "Error: No se puede conectar al servidor de base de datos"
            else:
                return f"Error de base de datos ({error.errno}): {error.msg}"
        elif isinstance(error, ValueError):
            return str(error)
        else:
            return f"Error inesperado: {str(error)}"

    def setup_window(self):
        """Configurar la ventana principal con escalado dinámico"""
        if self.is_standalone:
            # Obtener dimensiones de la pantalla
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # Calcular dimensiones relativas
            window_width = int(screen_width * 0.8)  # 80% del ancho de pantalla
            window_height = int(screen_height * 0.8)  # 80% del alto de pantalla
            
            # Calcular posición centrada
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # Configurar geometría
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Establecer tamaños mínimos
            self.root.minsize(1024, 768)
        
        # Configurar grid weights para expansión proporcional
        self.root.grid_columnconfigure(0, weight=1)
        # Estas configuraciones aplican en ambos modos
        if isinstance(self.root, ctk.CTk):
            self.root.grid_columnconfigure(0, weight=1)
            self.root.grid_rowconfigure(0, weight=0)  # Header
            self.root.grid_rowconfigure(1, weight=1)  # Main container
        
        # Configurar el grid del contenedor principal
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)  # Form
        self.main_container.grid_rowconfigure(1, weight=2)  # Table
        self.main_container.grid_rowconfigure(2, weight=1)  # Buttons

    def create_gui(self):
        """Crear interfaz gráfica"""
        # Frame principal
        self.main_container = ctk.CTkFrame(
            self.root,
            fg_color=EstiloApp.COLOR_PRINCIPAL
        )
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        
        # Configurar grid weights
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(2, weight=1)

        # Crear header con logo
        self._create_header_frame()

        # Crear formulario con nueva estructura
        self._create_form()

        # Frame contenedor para el treeview con el mismo estilo que el contenedor principal
        tree_container = ctk.CTkFrame(
            self.main_container,
            fg_color=EstiloApp.COLOR_FRAMES
        )
        tree_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        # Configurar grid weights del contenedor del treeview
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        # Crear Treeview dentro del nuevo contenedor
        self._create_treeview(tree_container)

        # Configurar grid del root
        if isinstance(self.root, ctk.CTk):
            self.root.grid_columnconfigure(0, weight=1)
            self.root.grid_rowconfigure(0, weight=1)
            
        # Llamar al método original
        resultado = super().create_gui() if hasattr(super(), 'create_gui') else None
        
        # Añadir bindings para calcular días automáticamente
        if hasattr(self, 'entry_desde_fecha') and hasattr(self, 'entry_hasta_fecha'):
            self.entry_desde_fecha.bind("<FocusOut>", self._calcular_dias_licencia)
            self.entry_hasta_fecha.bind("<FocusOut>", self._calcular_dias_licencia)
        
        return resultado

    def _create_table(self):
        """Crear la tabla de registros de licencias"""
        # Frame contenedor para la tabla
        table_container = ctk.CTkFrame(
            self.main_container,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        table_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=0)  # Para el título
        table_container.grid_rowconfigure(1, weight=1)  # Para el treeview

    def _create_form_fields(self, parent):
        """Crear los campos del formulario para el registro de licencias"""
        # Configuración de fuentes
        label_font = ctk.CTkFont(size=14)
        entry_font = ctk.CTkFont(size=14)
        
        # Configuración de campos con posiciones específicas
        field_configs = {
            # Columna izquierda
            "legajo": {"row": 1, "column": 0, "width": 200, "height": 35},
            "desde_fecha": {"row": 2, "column": 0, "width": 200, "height": 35, "date": True},
            "hasta_fecha": {"row": 3, "column": 0, "width": 200, "height": 35, "date": True},
            "cantidad_dias": {"row": 4, "column": 0, "width": 200, "height": 35},
            "solicita": {"row": 5, "column": 0, "width": 200, "height": 35},
            # Columna derecha (motivo)
            "motivo": {"row": 1, "column": 1, "width": 400, "height": 200, "rowspan": 5, "textbox": True},
        }

        # Crear los campos según la configuración
        for field_name, config in field_configs.items():
            # Crear label
            label_text = field_name.replace("_", " ").capitalize()
            label = ctk.CTkLabel(
                parent, 
                text=f"{label_text}:",
                font=label_font
            )
            label.grid(row=config["row"], column=config["column"]*2, 
                      sticky='e', padx=5, pady=5)

            if field_name == "motivo":
                # TextBox para motivo que abarca múltiples filas
                widget = ctk.CTkTextbox(
                    parent,
                    height=config["height"],
                    width=config["width"],
                    border_color=EstiloApp.COLOR_SECUNDARIO,
                    fg_color="white",
                    font=entry_font,
                    border_width=2
                )
                widget.grid(row=config["row"], column=config["column"]*2+1,
                          rowspan=config["rowspan"], padx=20, pady=5, sticky="nsew")
                setattr(self, "text_motivo", widget)
                
            elif "date" in config and config["date"]:
                # Frame contenedor para el DateEntry
                date_frame = ctk.CTkFrame(
                    parent,
                    fg_color="transparent",
                    width=config["width"],
                    height=config["height"]
                )
                date_frame.grid(row=config["row"], column=config["column"]*2+1,
                              padx=20, pady=5, sticky="w")
                date_frame.grid_propagate(False)
                
                widget = DateEntry(
                    date_frame,
                    width=12,
                    background=EstiloApp.COLOR_SECUNDARIO,
                    foreground='black',
                    borderwidth=2,
                    font=('Roboto', 12),
                    date_pattern='dd-mm-yyyy',
                    locale='es',
                    justify='center'
                )
                widget.place(relx=0, rely=0, relwidth=1, relheight=1)
                field_attr = field_name.replace("_fecha", "")
                setattr(self, f"entry_{field_attr}", widget)
                
            else:
                # Entry normal para otros campos
                widget = ctk.CTkEntry(
                    parent,
                    height=config["height"],
                    width=config["width"],
                    border_color=EstiloApp.COLOR_SECUNDARIO,
                    fg_color="white",
                    font=entry_font
                )
                widget.grid(row=config["row"], column=config["column"]*2+1,
                          padx=20, pady=5, sticky="w")
                setattr(self, f"entry_{field_name}", widget)

        # Configurar el grid para que se expanda correctamente
        parent.grid_columnconfigure(3, weight=1)  # Columna después de motivo se expande

    def _create_stats_labels(self, parent):
        """Crear etiquetas de estadísticas"""
        self.total_licencias_label = ctk.CTkLabel(
            parent,
            text="📋 Historial: Sin licencias registradas",
            font=ctk.CTkFont(size=12)
        )
        self.total_licencias_label.grid(row=0, column=0, pady=2, padx=5, sticky="w")

        self.ultima_licencia_label = ctk.CTkLabel(
            parent,
            text="⏱️ Última licencia: No registrada",
            font=ctk.CTkFont(size=12)
        )
        self.ultima_licencia_label.grid(row=1, column=0, pady=2, padx=5, sticky="w")

        self.dias_totales_label = ctk.CTkLabel(
            parent,
            text="📊 Total días de licencia: 0 días",
            font=ctk.CTkFont(size=12)
        )
        self.dias_totales_label.grid(row=2, column=0, pady=2, padx=5, sticky="w")

    def _create_treeview(self, tree_frame):
        """Crear el treeview para mostrar las licencias"""
        # Estilos personalizados
        style = ttk.Style()
        style.configure("Treeview", 
                        background=EstiloApp.COLOR_PRINCIPAL,
                        fieldbackground=EstiloApp.COLOR_PRINCIPAL,
                        rowheight=25)
        style.configure("Treeview.Heading", 
                        background=EstiloApp.COLOR_SECUNDARIO,
                        foreground=EstiloApp.COLOR_TEXTO,
                        font=('Helvetica', 10, 'bold'))
        style.map('Treeview', background=[('selected', EstiloApp.COLOR_SECUNDARIO)])
        
        # Frame contenedor para el título
        title_frame = ctk.CTkFrame(tree_frame, fg_color=EstiloApp.COLOR_FRAMES)
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        
        # Título para la tabla
        title_label = ctk.CTkLabel(
            title_frame,
            text="REGISTRO DE LICENCIAS",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.pack(pady=10)
        
        # Frame contenedor para el Treeview
        tree_container = ctk.CTkFrame(tree_frame, fg_color=EstiloApp.COLOR_FRAMES)
        tree_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)
        
        # Crear Treeview
        self.tree = ttk.Treeview(
            tree_container,
            columns=("id", "legajo", "fecha_inicio", "fecha_fin", "dias", "solicita","motivo"),
            show="headings",
            height=15
        )
        
        # Definir encabezados de columnas
        self.tree.heading('id', text='ID')
        self.tree.heading('legajo', text='Legajo')
        self.tree.heading('fecha_inicio', text='Desde')
        self.tree.heading('fecha_fin', text='Hasta')
        self.tree.heading('dias', text='Días')
        self.tree.heading('solicita', text='Solicita')
        self.tree.heading('motivo', text='Motivo')
        
        # Definir anchos de columnas
        self.tree.column('id', width=50, anchor='center')
        self.tree.column('legajo', width=70, anchor='center')
        self.tree.column('fecha_inicio', width=100, anchor='center')
        self.tree.column('fecha_fin', width=100, anchor='center')
        self.tree.column('dias', width=70, anchor='center')
        self.tree.column('solicita', width=300, anchor='center')
        self.tree.column('motivo', width=150, anchor='center')

        # Scrollbars
        scrollbar_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        # Binding para selección y menú contextual
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind('<Button-3>', self.mostrar_menu_contextual)
        self.tree.bind('<Double-1>', self.on_tree_double_click)
        
        # Crear menú contextual
        self.menu_contextual = tk.Menu(self.root, tearoff=0)
        self.menu_contextual.add_command(
            label="Ver motivo completo", 
            command=self.mostrar_ventana_motivo
        )

    def _create_header_frame(self):
        """Crear el frame del encabezado con logo animado"""
        header_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=EstiloApp.COLOR_HEADER,
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
            target_height = 200
            for frame in ImageSequence.Iterator(gif):
                frame = frame.convert('RGBA')
                width, height = frame.size
                aspect_ratio = width / height
                target_width = int(target_height * aspect_ratio)
                
                # Redimensionar manteniendo proporción
                frame = frame.resize((target_width, target_height), Image.LANCZOS)
                frames.append(frame)
            
            # Crear el label dentro del contenedor del logo
            logo_label = tk.Label(
                logo_container,
                bg=EstiloApp.COLOR_HEADER
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
            self._create_logo_placeholder(header_frame)

        # Título principal
        title_label = ctk.CTkLabel(
            header_frame,
            text="Módulo de Licencias Sin Goce - RRHH",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=EstiloApp.COLOR_TEXTO
        )
        title_label.grid(row=0, column=1, sticky="w", pady=(2, 2))
        
        # Subtítulo
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Entheus Seguridad",
            font=ctk.CTkFont(size=16),
            text_color=EstiloApp.COLOR_TEXTO
        )
        subtitle_label.grid(row=1, column=1, sticky="w", pady=1)
        
        # Derechos de autor
        copyright_label = ctk.CTkLabel(
            header_frame,
            text="© 2025 Todos los derechos reservados",
            font=ctk.CTkFont(size=12),
            text_color=EstiloApp.COLOR_TEXTO
        )
        copyright_label.grid(row=2, column=1, sticky="w", pady=(1, 5))

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
        """Animar el logo GIF frame por frame usando CTkImage"""
        try:
            if (hasattr(self, 'logo_frames') and 
                self.logo_frames and 
                hasattr(self, 'logo_label') and 
                self.logo_label.winfo_exists() and 
                not self.is_destroyed):
                
                self.logo_label.configure(image=self.logo_frames[self.current_frame])
                self.current_frame = (self.current_frame + 1) % len(self.logo_frames)
                # Guardar referencia al after_id para poder cancelarlo
                self.animation_after_id = self.root.after(100, self._animate_logo)
        except Exception as e:
            self.logger.error(f"Error en animación del logo: {str(e)}")

    def consultar_empleado(self, event=None):
        """Consultar información del empleado por legajo"""
        print(f"=== INICIANDO CONSULTA EMPLEADO (Evento: {event}) ===")
        
        # Prevenir consultas múltiples
        if hasattr(self, '_consulta_en_proceso') and self._consulta_en_proceso:
            print(">>> CONSULTA YA EN PROCESO, IGNORANDO LLAMADA ADICIONAL")
            return
            
        self._consulta_en_proceso = True
        
        legajo = self.entry_legajo.get().strip()
        print(f"Legajo a consultar: '{legajo}'")
        
        if not legajo:
            print("Legajo vacío, cancelando consulta")
            self._consulta_en_proceso = False
            self.mostrar_mensaje("Error", "Debe ingresar un legajo")
            return
        
        # Si es el mismo legajo recientemente consultado, no volver a consultar
        if hasattr(self, '_ultimo_legajo_consultado') and legajo == self._ultimo_legajo_consultado:
            print(f"Legajo {legajo} ya consultado recientemente, ignorando consulta")
            self._consulta_en_proceso = False
            return
            
        print("Mostrando ventana de carga...")
        self.mostrar_carga("Consultando empleado...")
        
        def _consultar():
            print("Iniciando consulta en segundo plano...")
            try:
                print("Obteniendo conexión del pool...")
                connection = self.db_pool.get_connection()
                cursor = connection.cursor(dictionary=True)
                print("Conexión obtenida correctamente")
                
                try:
                    # Primero intentemos una consulta más simple
                    query = """
                        SELECT legajo, apellido_nombre, foto
                        FROM personal
                        WHERE legajo = %s
                    """
                    print(f"Ejecutando query: {query.strip()} con legajo {legajo}")
                    cursor.execute(query, (legajo,))
                    resultado = cursor.fetchone()
                    
                    if resultado:
                        print(f"Resultado encontrado: {resultado}")
                        apellido_nombre = resultado['apellido_nombre']
                        foto_blob = resultado['foto']
                        
                        # Ahora hacemos una segunda consulta para las estadísticas
                        query_stats = """
                            SELECT 
                                COALESCE(COUNT(id), 0) as total_licencias,
                                MAX(desde_fecha) as ultima_licencia,
                                COALESCE(SUM(cantidad_dias), 0) as total_dias
                            FROM licencias_sin_goce
                            WHERE legajo = %s
                        """
                        cursor.execute(query_stats, (legajo,))
                        stats = cursor.fetchone()
                        
                        total_licencias = stats['total_licencias'] if stats else 0
                        ultima_fecha = stats['ultima_licencia'] if stats else None
                        total_dias = stats['total_dias'] if stats else 0
                        
                        def _actualizar_ui():
                            print("Actualizando UI con datos del empleado")
                            # Actualizar nombre del empleado
                            self.nombre_completo_label.configure(text=f"👤 Empleado: {apellido_nombre}")
                            
                            # Actualizar estadísticas
                            self.total_licencias_label.configure(text=f"📋 Historial: {total_licencias} licencias registradas")
                            
                            # Actualizar última licencia
                            if ultima_fecha:
                                fecha_formateada = ultima_fecha.strftime('%d-%m-%Y')
                                self.ultima_licencia_label.configure(text=f"⏱️ Última licencia: {fecha_formateada}")
                            else:
                                self.ultima_licencia_label.configure(text="⏱️ Última licencia: No registrada")
                            
                            # Actualizar total de días
                            self.dias_totales_label.configure(text=f"📊 Total días de licencia: {total_dias} días")
                            
                            # Actualizar foto
                            self.actualizar_foto(foto_blob)
                            
                            # Guardar último legajo consultado
                            self._ultimo_legajo_consultado = legajo
                            
                            # Ocultar ventana de carga
                            self.ocultar_carga()
                            
                            # Permitir nuevas consultas
                            self._consulta_en_proceso = False
                            print("UI actualizada correctamente")
                        
                        if not self.is_destroyed and hasattr(self, 'root') and self.root.winfo_exists():
                            print("Enviando actualización de UI al hilo principal")
                            self.root.after(0, _actualizar_ui)
                        else:
                            print("La ventana ya no existe, cancelando actualización")
                            self._consulta_en_proceso = False
                        
                        # Consultar licencias para el treeview
                        print("Consultando licencias para el treeview")
                        self.consultar_licencias(legajo)
                        
                    else:
                        print(f"No se encontró empleado con legajo {legajo}")
                        def _mostrar_error():
                            self.mostrar_mensaje("Error", f"No se encontró empleado con legajo {legajo}")
                            self.ocultar_carga()
                            self._consulta_en_proceso = False
                        
                        if not self.is_destroyed and hasattr(self, 'root') and self.root.winfo_exists():
                            self.root.after(0, _mostrar_error)
                        else:
                            print("La ventana ya no existe, cancelando mensaje de error")
                            self._consulta_en_proceso = False
                except Exception as error:
                    print(f"ERROR en consulta: {str(error)}")
                    def _mostrar_error_exception():
                        self.mostrar_mensaje("Error", f"Error al consultar datos: {str(error)}")
                        self.ocultar_carga()
                        self._consulta_en_proceso = False
                    
                    if not self.is_destroyed and hasattr(self, 'root') and self.root.winfo_exists():
                        self.root.after(0, _mostrar_error_exception)
                    else:
                        self._consulta_en_proceso = False
                finally:
                    print("Cerrando cursor y devolviendo conexión")
                    cursor.close()
                    self.db_pool.return_connection(connection)
            except Exception as e:
                print(f"ERROR CRÍTICO al consultar empleado: {str(e)}")
                self._consulta_en_proceso = False
                if not self.is_destroyed and hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda: self.mostrar_mensaje("Error", f"Error crítico: {str(e)}"))
                    self.root.after(0, self.ocultar_carga)

        print("Enviando consulta a thread en segundo plano")
        threading.Thread(target=_consultar, daemon=True).start()

    def actualizar_foto(self, foto_blob):
        """Actualiza la foto del empleado en el canvas"""
        try:
            # Limpiar canvas primero (eliminar óvalo y cualquier imagen previa)
            self.photo_canvas.delete("all")
            
            if foto_blob:
                # Si hay una foto, procesarla
                try:
                    # Procesar la imagen
                    image_bytes = BytesIO(foto_blob)
                    img = Image.open(image_bytes)
                    img = img.resize((180, 180), Image.LANCZOS)
                    
                    # Convertir a formato compatible con tkinter
                    self.current_photo = ImageTk.PhotoImage(img)
                    
                    # Mostrar la imagen en el canvas
                    self.photo_canvas.create_image(90, 90, image=self.current_photo, anchor="center")
                    
                except Exception as e:
                    self.logger.error(f"Error procesando imagen: {e}")
                    # Si hay error, mostrar el emoji de usuario
                    self._draw_user_emoji()
            else:
                # Si no hay foto, mostrar el emoji de usuario
                self._draw_user_emoji()
        
        except Exception as e:
            self.logger.error(f"Error en actualizar_foto: {e}")
            # Si hay error, al menos mostrar el emoji de usuario
            self._draw_user_emoji()

    def _draw_user_emoji(self):
        """Dibuja un óvalo y un emoji de usuario como placeholder"""
        # Limpiar el canvas primero para asegurarnos de que no haya elementos previos
        self.photo_canvas.delete("all")
        
        # Intentar con un símbolo de usuario más compatible y más grande
        self.photo_canvas.create_text(90, 90, text="👤", font=("Segoe UI Emoji", 90), fill="#64B5F6", tags="user_emoji")

    def _create_form(self):
        """Crear el formulario de registro de licencias"""
        form_frame = ctk.CTkFrame(
            self.main_container, 
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10,
            height=350  # Establecer una altura mínima para asegurar suficiente espacio
        )
        form_frame.grid(row=1, column=0, sticky="new", padx=10, pady=(5, 20))  # Aumentar el pady inferior
        form_frame.grid_columnconfigure(0, weight=1)  # Panel izquierdo
        form_frame.grid_columnconfigure(1, weight=1)  # Panel central
        form_frame.grid_columnconfigure(2, weight=1)  # Panel derecho
        form_frame.grid_propagate(False)  # Evitar que el frame se redimensione según su contenido

        # Panel izquierdo (formulario)
        left_panel = ctk.CTkFrame(form_frame, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="e", padx=(50, 20), pady=10)  # Ajustado padding y sticky
        
        # Título del formulario
        title_label = ctk.CTkLabel(
            left_panel,
            text="Registre o Modifique una Licencia",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Crear campos del formulario
        self._create_form_fields(left_panel)

        # Panel central (foto y datos empleado)
        center_panel = ctk.CTkFrame(form_frame, fg_color="transparent")
        center_panel.grid(row=0, column=1, sticky="n", padx=20, pady=10)  # Ajustado padding

        # Frame para foto y datos en horizontal
        info_container = ctk.CTkFrame(center_panel, fg_color="transparent")
        info_container.pack(expand=True)

        # Frame para la foto
        photo_frame = ctk.CTkFrame(
            info_container,
            fg_color=EstiloApp.COLOR_PRINCIPAL,
            corner_radius=10,
            border_width=2,
            border_color=EstiloApp.COLOR_SECUNDARIO,
            width=190,
            height=190
        )
        photo_frame.grid(row=0, column=0, padx=(0, 20), pady=(45, 0))
        photo_frame.grid_propagate(False)  # Mantener tamaño fijo del frame

        # Canvas para la foto
        self.photo_canvas = ctk.CTkCanvas(
            photo_frame,
            width=180,
            height=180,
            bg=EstiloApp.COLOR_PRINCIPAL,
            highlightthickness=0
        )
        self.photo_canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Placeholder inicial con óvalo
        self.photo_canvas.create_text(90, 90, text="👤", font=("Segoe UI Emoji", 90), fill="#64B5F6", tags="user_emoji")
        
        # Guardar referencia al item de la foto para actualizarlo después
        self.photo_item = self.photo_canvas.create_image(90, 90, image=None)
        
        # Frame para datos del empleado
        data_frame = ctk.CTkFrame(info_container, fg_color="transparent")
        data_frame.grid(row=0, column=1, sticky="nw", padx=(20, 0), pady=(45, 0))  # Agregado pady top igual que la foto

        # Labels de información
        self.nombre_completo_label = ctk.CTkLabel(
            data_frame,
            text="👤 Empleado: No seleccionado",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
            width=300
        )
        self.nombre_completo_label.pack(anchor="w", pady=(0, 15))  # Ajustado padding vertical inicial

        self.total_licencias_label = ctk.CTkLabel(
            data_frame,
            text="📋 Historial: Sin licencias registradas",
            font=ctk.CTkFont(size=14),
            anchor="w",
            width=300
        )
        self.total_licencias_label.pack(anchor="w", pady=15)  # Ajustado padding vertical

        self.ultima_licencia_label = ctk.CTkLabel(
            data_frame,
            text="⏱️ Última licencia: No registrada",
            font=ctk.CTkFont(size=14),
            anchor="w",
            width=300
        )
        self.ultima_licencia_label.pack(anchor="w", pady=15)  # Ajustado padding vertical

        self.dias_totales_label = ctk.CTkLabel(
            data_frame,
            text="📊 Total días de licencia: 0 días",
            font=ctk.CTkFont(size=14),
            anchor="w",
            width=300
        )
        self.dias_totales_label.pack(anchor="w", pady=15)
        
        # Vincular evento de entrada al campo legajo para consultar automáticamente
        self.entry_legajo.bind('<FocusOut>', self.consultar_empleado)
        self.entry_legajo.bind('<Return>', self.consultar_empleado)
        
        # Agregar un frame espaciador para aumentar el espacio vertical
        spacer_frame = ctk.CTkFrame(form_frame, fg_color="transparent", height=60)
        spacer_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        
        # Crear botones CRUD en la parte inferior del formulario
        buttons_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        # Usar solo place para posicionar el frame en el centro
        # Ajustamos la posición vertical para que quede dentro del contenedor
        buttons_frame.place(relx=0.5, rely=0.90, anchor="center")
        
        # Configuración para botones de tamaño fijo
        buttons_frame.grid_columnconfigure(0, weight=0)
        buttons_frame.grid_columnconfigure(1, weight=0)
        buttons_frame.grid_columnconfigure(2, weight=0)
        buttons_frame.grid_columnconfigure(3, weight=0)
        
        # Botón Guardar (Insertar) - con ancho fijo
        self.btn_guardar = ctk.CTkButton(
            buttons_frame,
            text="Guardar Licencia",
            command=self.guardar_licencia,
            fg_color=EstiloApp.BOTON_INSERTAR,
            hover_color=EstiloApp.BOTON_INSERTAR_HOVER,
            width=150
        )
        self.btn_guardar.grid(row=0, column=0, padx=10, pady=10)
        
        # Botón Modificar
        self.btn_modificar_action = ctk.CTkButton(
            buttons_frame,
            text="Modificar Licencia",
            command=self.modificar_licencia,
            fg_color=EstiloApp.BOTON_MODIFICAR,
            hover_color=EstiloApp.BOTON_MODIFICAR_HOVER,
            width=150
        )
        self.btn_modificar_action.grid(row=0, column=1, padx=10, pady=10)
        
        # Botón Eliminar
        btn_eliminar = ctk.CTkButton(
            buttons_frame,
            text="Eliminar Licencia",
            command=self.eliminar_licencia,
            fg_color=EstiloApp.BOTON_ELIMINAR,
            hover_color=EstiloApp.BOTON_ELIMINAR_HOVER,
            width=150
        )
        btn_eliminar.grid(row=0, column=2, padx=10, pady=10)
        
        # Botón Limpiar
        self.btn_limpiar_action = ctk.CTkButton(
            buttons_frame,
            text="Limpiar Campos",
            command=self.limpiar_campos,
            fg_color=EstiloApp.BOTON_LIMPIAR,
            hover_color=EstiloApp.BOTON_LIMPIAR_HOVER,
            width=150
        )
        self.btn_limpiar_action.grid(row=0, column=3, padx=10, pady=10)
        
        return form_frame

    def _create_table(self, tree_frame):
        """Crear la tabla de registros de licencias"""
        # Frame contenedor para la tabla
        table_container = ctk.CTkFrame(
            tree_frame,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        table_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=0)  # Para el título
        table_container.grid_rowconfigure(1, weight=1)  # Para el treeview

        # Título de la tabla
        title_label = ctk.CTkLabel(
            table_container,
            text="Registros de Licencias",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=5)

        # Frame para el treeview y scrollbars
        tree_frame = ctk.CTkFrame(table_container, fg_color="transparent")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        # Crear estilo personalizado para el Treeview
        style = ttk.Style()
        style.configure(
            "Custom.Treeview.Heading",
            font=('Helvetica', 10, 'bold'),  # Encabezados en negrita
            foreground='black'
        )
        style.configure(
            "Custom.Treeview",
            font=('Helvetica', 10),  # Fuente normal para el contenido
            foreground='black',
            background='white',
            fieldbackground='white'
        )

        # Crear Treeview con el estilo personalizado
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("id", "legajo", "fecha_inicio", "fecha_fin", "dias", "solicita", "motivo"),
            show="headings",
            height=20,
            style="Custom.Treeview"
        )

        # Configurar las columnas
        columnas = {
            "id": ("ID", 50),
            "legajo": ("Legajo", 80),
            "fecha_inicio": ("Desde", 100),
            "fecha_fin": ("Hasta", 100),
            "dias": ("Días", 60),
            "silicita": ("Solicita", 200),
            "motivo": ("MotivoS", 120),
        }

        for col, (heading, width) in columnas.items():
            self.tree.heading(col, text=heading, anchor="center")  # Centrar encabezados
            self.tree.column(col, width=width, minwidth=width, anchor="center")  # Centrar contenido

        # Configurar scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Vincular eventos
        self.tree.bind("<Button-3>", self.mostrar_motivo_completo)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

    def on_tree_double_click(self, event):
        """Manejar doble clic en el treeview"""
        item = self.tree.selection()
        if not item:
            return
        
        valores = self.tree.item(item[0])['values']
        if not valores:
            return

        # Guardar ID de la licencia seleccionada
        self.licencia_seleccionada_id = valores[0]
        
        # Cargar datos en los campos
        self.entry_legajo.delete(0, tk.END)
        self.entry_legajo.insert(0, str(valores[1]))
        
        try:
            # Columnas: id, legajo, fecha_inicio, fecha_fin, dias, motivo, solicita
            self.entry_desde.set_date(datetime.strptime(valores[2], '%d-%m-%Y'))
            self.entry_hasta.set_date(datetime.strptime(valores[3], '%d-%m-%Y'))
            
            self.entry_cantidad_dias.delete(0, tk.END)
            self.entry_cantidad_dias.insert(0, str(valores[4]))
            
            self.text_motivo.delete("1.0", tk.END)
            self.text_motivo.insert("1.0", valores[5])
            
            self.entry_solicita.delete(0, tk.END)
            self.entry_solicita.insert(0, valores[6] if len(valores) > 6 else "")
        except Exception as e:
            # Mostrar mensaje de error
            self.mostrar_mensaje("Error", f"Error al cargar datos: {str(e)}", "error")
            print(f"Error en on_tree_double_click: {e}")
            print(f"Valores: {valores}")

    def eliminar_sancion(self):
        """Este método ya no es necesario, pero se mantiene para compatibilidad temporal.
        Redirige a la función eliminar_licencia"""
        return self.eliminar_licencia()

    def eliminar_licencia(self):
        """Eliminar una licencia"""
        if not self.licencia_seleccionada_id:
            self.mostrar_mensaje("Error", "No hay licencia seleccionada para eliminar")
            return
        
        # Mostrar confirmación
        self._mostrar_dialogo_confirmacion(
            "Confirmar eliminación",
            "¿Está seguro de que desea eliminar esta licencia? Esta acción no se puede deshacer.",
            self._eliminar_licencia_confirmado
        )

    def _eliminar_licencia_confirmado(self):
        """Eliminar licencia después de confirmación"""
        def _eliminar():
            connection = self.db_pool.get_connection()
            if not connection:
                return

            try:
                cursor = connection.cursor()
                
                # Eliminar licencia
                cursor.execute("""
                    DELETE FROM licencias_sin_goce 
                    WHERE id = %s
                """, (self.licencia_seleccionada_id,))
                
                connection.commit()
                
                def _actualizar_ui():
                    # Guardar el legajo actual antes de limpiar campos
                    legajo_actual = self.entry_legajo.get()
                    
                    # Limpiar treeview
                    self._clear_treeview()
                    # Limpiar formulario
                    self.limpiar_campos()
                    # Consultar licencias actualizadas con el legajo guardado
                    self.consultar_licencias(legajo_actual)
                    # Mostrar mensaje de éxito
                    self.mostrar_mensaje("Éxito", "Licencia eliminada correctamente")
                
                self.root.after(0, _actualizar_ui)
                
            except mysql.connector.Error as err:
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Error", f"No se pudo eliminar: {err}", tipo="error"
                ))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)

        self.db_pool.executor.submit(_eliminar)

    def modificar_sancion(self):
        """Este método ya no es necesario, pero se mantiene para compatibilidad temporal.
        Redirige a la función modificar_licencia"""
        return self.modificar_licencia()

    def insertar_sancion(self):
        """Este método ya no es necesario, pero se mantiene para compatibilidad temporal.
        Redirige a la función guardar_licencia"""
        return self.guardar_licencia()

    def mostrar_motivo_completo(self, event):
        """Mostrar ventana con el motivo completo al hacer clic derecho"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
            
        valores = self.tree.item(item)['values']
        if not valores:
            return
            
        def _get_motivo_completo():
            connection = self.db_pool.get_connection()
            try:
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT motivo 
                    FROM sanciones 
                    WHERE id = %s
                """, (valores[0],))
                resultado = cursor.fetchone()
                if resultado and resultado[0]:
                    self.root.after(0, lambda m=resultado[0]: self._crear_ventana_motivo(m))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)
        
        self.db_pool.executor.submit(_get_motivo_completo)

    def _crear_ventana_motivo(self, motivo):
        """Crear ventana modal con el motivo completo"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Motivo Completo")
        dialog.geometry("500x400")
        dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)
        
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar la ventana
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f'+{x}+{y}')
        
        # Frame para el texto
        text_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        text_frame.pack(fill='both', expand=True, padx=20, pady=(20,10))
        
        # Widget de texto
        text_widget = ctk.CTkTextbox(
            text_frame,
            wrap='word',
            font=ctk.CTkFont(size=12),
            width=460,
            height=300
        )
        text_widget.pack(fill='both', expand=True)
        
        # Insertar el motivo en el widget de texto
        text_widget.insert("1.0", motivo)
        text_widget.configure(state="disabled")  # Hacer el texto de solo lectura
        
        # Botón cerrar
        btn_cerrar = ctk.CTkButton(
            dialog,
            text="Cerrar",
            command=dialog.destroy,
            width=100,
            fg_color=EstiloApp.BOTON_LIMPIAR,
            hover_color=EstiloApp.BOTON_LIMPIAR_HOVER
        )
        btn_cerrar.pack(pady=(0,20))
        
        # Vincular tecla Escape para cerrar
        dialog.bind("<Escape>", lambda e: dialog.destroy())


    def limpiar_campos_parcial(self):
        """Limpiar solo los campos del formulario manteniendo legajo y datos del personal"""
        try:
            # Reset variable importante
            self.sancion_seleccionada_id = None
            
            # Limpiar solo campos específicos manteniendo legajo y datos del vigilador
            self.entry_fecha.set_date(datetime.now())
            self.entry_objetivo.delete(0, tk.END)
            self.text_motivo.delete("1.0", tk.END)
            self.entry_cantidad_dias.delete(0, tk.END)
            self.entry_solicita.delete(0, tk.END)
            self.combo_tipo.set("Suspensión")  # Resetear al valor por defecto
            
            # Desactivar checkbox de suspensión si está activo
            if self.suspension_var.get():
                self.suspension_var.set(False)
                self.entry_cantidad_dias.configure(state="disabled")
            
            # Mover el foco al campo objetivo para agilizar la carga
            self.entry_objetivo.focus_set()
            
        except Exception as e:
            self.logger.error(f"Error en limpiar_campos_parcial: {e}")

    def modificar_licencia(self):
        """Modificar licencia existente"""
        if not self.licencia_seleccionada_id or not self.validar_campos():
            return

        def _modificar():
            connection = self.db_pool.get_connection()
            if not connection:
                return

            try:
                cursor = connection.cursor()
                
                # Convertir fechas al formato MySQL
                desde_fecha = datetime.strptime(self.entry_desde.get(), '%d-%m-%Y').strftime('%Y-%m-%d')
                hasta_fecha = datetime.strptime(self.entry_hasta.get(), '%d-%m-%Y').strftime('%Y-%m-%d')
                
                # Actualizar licencia
                cursor.execute("""
                    UPDATE licencias_sin_goce 
                    SET legajo = %s,
                        cantidad_dias = %s,
                        desde_fecha = %s,
                        hasta_fecha = %s,
                        solicita = %s,
                        motivo = %s
                    WHERE id = %s
                """, (
                    self.entry_legajo.get(),
                    self.entry_cantidad_dias.get(),
                    desde_fecha,
                    hasta_fecha,
                    self.entry_solicita.get(),
                    self.text_motivo.get("1.0", tk.END).strip(),
                    self.licencia_seleccionada_id
                ))
                
                connection.commit()
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Éxito", "Licencia modificada correctamente"
                ))
                
                # Actualizar vista
                self.consultar_licencias(self.entry_legajo.get())
                
            except mysql.connector.Error as err:
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Error", f"No se pudo modificar: {err}", tipo="error"
                ))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)

        self.db_pool.executor.submit(_modificar)

    def consultar_licencias(self, legajo=None):
        """Consultar licencias según filtros"""
        print("Iniciando consulta de licencias...")
        # Mostrar ventana de carga
        self.mostrar_carga("Consultando licencias...")
        
        def _consultar():
            conexion = None
            cursor = None
            try:
                # Crear conexión a la base de datos
                conexion = mysql.connector.connect(**self.db_config)
                cursor = conexion.cursor()
                
                # Modificamos la consulta para incluir el nombre del empleado
                if legajo:
                    sql = """
                    SELECT l.id, l.legajo,
                           DATE_FORMAT(l.desde_fecha, '%d-%m-%Y') as desde_fecha,
                           DATE_FORMAT(l.hasta_fecha, '%d-%m-%Y') as hasta_fecha,
                           l.cantidad_dias, l.motivo, l.solicita
                    FROM licencias_sin_goce l
                    WHERE l.legajo = %s
                    ORDER BY l.desde_fecha DESC
                    """
                    cursor.execute(sql, (legajo,))
                else:
                    sql = """
                    SELECT l.id, l.legajo,
                           DATE_FORMAT(l.desde_fecha, '%d-%m-%Y') as desde_fecha,
                           DATE_FORMAT(l.hasta_fecha, '%d-%m-%Y') as hasta_fecha,
                           l.cantidad_dias, l.motivo, l.solicita
                    FROM licencias_sin_goce l
                    ORDER BY l.desde_fecha DESC
                    """
                    cursor.execute(sql)
                
                # Obtener resultados
                resultados = cursor.fetchall()
                
                # Actualizar UI en el hilo principal
                def _actualizar_ui():
                    self._update_treeview(resultados)
                    # No pasar el cursor aquí, será cerrado después
                    if legajo:
                        self._actualizar_estadisticas_seguro(legajo)
                    self.ocultar_carga()
                
                self.root.after(0, _actualizar_ui)
                
            except Exception as error:
                # Capturar el error para usarlo en una función local
                error_msg = str(error)  # Guardar el mensaje de error en una variable local
                self.logger.error(f"Error en consultar_licencias: {error_msg}")
                
                # Definir una función para mostrar el error
                def _mostrar_error_ui():
                    messagebox.showerror("Error", f"Error al consultar licencias: {error_msg}")
                    self.ocultar_carga()
                
                # Programar la ejecución de la función en el hilo principal
                self.root.after(0, _mostrar_error_ui)
                
            finally:
                # Cerrar recursos
                if cursor:
                    cursor.close()
                if conexion and conexion.is_connected():
                    conexion.close()
        
        # Ejecutar en hilo separado
        threading.Thread(target=_consultar, daemon=True).start()

    def validar_campos(self):
        """Validar todos los campos del formulario"""
        try:
            # Validar campos obligatorios
            if not self.entry_legajo.get():
                raise ValueError("El campo Legajo es obligatorio")
            if not self.entry_desde.get():
                raise ValueError("El campo Fecha Desde es obligatorio")
            if not self.entry_hasta.get():
                raise ValueError("El campo Fecha Hasta es obligatorio")
            if not self.entry_cantidad_dias.get():
                raise ValueError("El campo Cantidad de días es obligatorio")
            if not self.text_motivo.get("1.0", tk.END).strip():
                raise ValueError("El campo Motivo es obligatorio")
            if not self.entry_solicita.get():
                raise ValueError("El campo Solicita es obligatorio")

            # Validar legajo
            try:
                legajo = int(self.entry_legajo.get())
                if legajo <= 0:
                    raise ValueError("El legajo debe ser un número positivo")
            except ValueError:
                raise ValueError("El legajo debe ser un número válido")

            # Validar días
            try:
                dias = int(self.entry_cantidad_dias.get())
                if dias <= 0:
                    raise ValueError("Los días deben ser un número positivo")
            except ValueError:
                raise ValueError("La cantidad de días debe ser un número válido")

            # Validar fechas
            desde = datetime.strptime(self.entry_desde.get(), '%d-%m-%Y')
            hasta = datetime.strptime(self.entry_hasta.get(), '%d-%m-%Y')
            if hasta < desde:
                raise ValueError("La fecha Hasta no puede ser anterior a la fecha Desde")

            return True

        except ValueError as e:
            self.mostrar_mensaje("Error de validación", str(e))
            return False

    def buscar_empleado(self):
        """Buscar empleado por legajo"""
        if not self.db_pool:
            messagebox.showerror("Error", "No hay conexión a la base de datos")
            return

        legajo = self.entry_legajo.get().strip()
        if not legajo:
            messagebox.showerror("Error", "Ingrese un número de legajo")
            return

        def _consultar():
            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                cursor = connection.cursor()
                
                # Consultar datos del empleado
                cursor.execute("""
                    SELECT apellido_nombre, foto 
                    FROM personal 
                    WHERE legajo = %s
                """, (legajo,))
                
                resultado = cursor.fetchone()
                
                if resultado:
                    apellido_nombre, foto_blob = resultado
                    
                    # Consultar estadísticas de licencias
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_licencias,
                            MAX(desde_fecha) as ultima_fecha,
                            SUM(cantidad_dias) as total_dias
                        FROM licencias_sin_goce 
                        WHERE legajo = %s
                    """, (legajo,))
                    
                    stats = cursor.fetchone()
                    total_licencias = stats[0] if stats[0] else 0
                    ultima_fecha = stats[1]
                    total_dias = stats[2] if stats[2] else 0

                    # Consultar licencias para el treeview
                    cursor.execute("""
                        SELECT 
                            id,
                            legajo,
                            DATE_FORMAT(desde_fecha, '%d-%m-%Y') as desde,
                            DATE_FORMAT(hasta_fecha, '%d-%m-%Y') as hasta,
                            cantidad_dias,
                            motivo,
                            solicita
                        FROM licencias_sin_goce 
                        WHERE legajo = %s
                        ORDER BY desde_fecha DESC
                    """, (legajo,))
                    
                    licencias = cursor.fetchall()
                    
                    # Actualizar UI en el thread principal
                    if not self.is_destroyed:
                        self.root.after(0, lambda: self._actualizar_datos_empleado(
                            apellido_nombre, 
                            total_licencias, 
                            ultima_fecha, 
                            total_dias, 
                            foto_blob,
                            licencias
                        ))
                else:
                    if not self.is_destroyed:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Error", 
                            "No se encontró el empleado"
                        ))
                    
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Error en búsqueda de empleado: {error_msg}")
                if not self.is_destroyed:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error",
                        f"Error al buscar empleado: {error_msg}"
                    ))
                
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except:
                        pass
                if connection:
                    try:
                        self.db_pool.return_connection(connection)
                    except:
                        pass

        # Ejecutar consulta en thread separado
        self.db_pool.executor.submit(_consultar)

    def _actualizar_datos_empleado(self, nombre, licencias, fecha, dias, foto, datos_treeview):
        """Actualizar la interfaz con los datos del empleado"""
        try:
            if self.is_destroyed:
                return
                
            self.nombre_completo_label.configure(
                text=f"👤 Empleado: {nombre}"
            )
            self.total_licencias_label.configure(
                text=f"📋 Historial: {licencias} licencias"
            )
            
            if fecha:
                fecha_formateada = fecha.strftime('%d-%m-%Y')
                self.ultima_licencia_label.configure(
                    text=f"⏱️ Última: {fecha_formateada}"
                )
            else:
                self.ultima_licencia_label.configure(
                    text="⏱️ Última: No registrada"
                )
            
            self.dias_totales_label.configure(
                text=f"📊 Total días: {dias}"
            )
            
            self.actualizar_foto(foto)
            
            # Actualizar treeview
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            for licencia in datos_treeview:
                self.tree.insert('', 'end', values=licencia)
            
        except Exception as e:
            self.logger.error(f"Error al actualizar datos del empleado: {str(e)}")

    def on_tree_select(self, event):
        """Manejar selección en el treeview"""
        try:
            # Verificar que hay algún ítem seleccionado
            selected_items = self.tree.selection()
            if not selected_items:
                return
                
            # Activar botones de acción si hay selección
            if hasattr(self, 'btn_modificar'):
                self.btn_modificar.configure(state="normal")
                
            # Obtener datos del item seleccionado
            item = self.tree.item(selected_items[0])
            valores = item['values']
            if not valores:
                return

            # Guardar ID de la licencia seleccionada
            self.licencia_seleccionada_id = valores[0]

            # Actualizar campos del formulario
            self.entry_legajo.delete(0, tk.END)
            self.entry_legajo.insert(0, valores[1])

            # Actualizar fechas
            self.entry_desde.set_date(datetime.strptime(valores[2], '%d-%m-%Y'))
            self.entry_hasta.set_date(datetime.strptime(valores[3], '%d-%m-%Y'))

            # Actualizar días
            self.entry_cantidad_dias.delete(0, tk.END)
            self.entry_cantidad_dias.insert(0, valores[4])

            # Actualizar motivo
            self.text_motivo.delete("1.0", tk.END)
            self.text_motivo.insert("1.0", valores[5])

            # Actualizar solicita
            self.entry_solicita.delete(0, tk.END)
            self.entry_solicita.insert(0, valores[6])

        except Exception as e:
            print(f"Error en selección: {e}")
            self.mostrar_mensaje("Error", "Error al cargar los datos seleccionados")

    def mostrar_menu_contextual(self, event):
        """Mostrar menú contextual al hacer click derecho"""
        # Seleccionar el item bajo el cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu_contextual.post(event.x_root, event.y_root)

    def mostrar_ventana_motivo(self):
        """Mostrar ventana con el motivo completo"""
        # Obtener el item seleccionado
        seleccion = self.tree.selection()
        if not seleccion:
            return
        
        # Obtener el motivo del item seleccionado
        item = self.tree.item(seleccion[0])
        valores = item['values']
        if not valores:
            return
        
        # El motivo está en la posición 5 (índice basado en 0)
        motivo = valores[5]
        
        # Crear ventana
        ventana_motivo = tk.Toplevel(self.root)
        ventana_motivo.title("Motivo Completo")
        
        # Configurar geometría
        ventana_motivo.geometry("250x250")
        ventana_motivo.resizable(False, False)
        
        # Configurar estilo
        ventana_motivo.configure(bg=EstiloApp.COLOR_FRAMES)
        
        # Crear widget de texto
        texto = tk.Text(
            ventana_motivo,
            wrap=tk.WORD,
            font=('Helvetica', 11),
            bg=EstiloApp.COLOR_FRAMES,
            fg=EstiloApp.COLOR_TEXTO,
            padx=10,
            pady=10
        )
        texto.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Insertar motivo
        texto.insert('1.0', motivo)
        texto.configure(state='disabled')  # Hacer el texto de solo lectura
        
        # Centrar la ventana respecto a la ventana principal
        ventana_motivo.transient(self.root)
        ventana_motivo.grab_set()
        
        x = self.root.winfo_x() + (self.root.winfo_width() - 250) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 250) // 2
        ventana_motivo.geometry(f"+{x}+{y}")

    # Método para crear el canvas de la foto (similar al de módulo_sanciones)
    def _create_photo_canvas(self, parent):
        """Crear canvas para mostrar la foto del empleado"""
        # Frame contenedor para la foto
        self.photo_frame = ctk.CTkFrame(parent, fg_color=EstiloApp.COLOR_FRAMES)
        self.photo_frame.grid(row=0, column=1, rowspan=3, padx=10, pady=10, sticky="ne")
        
        # Canvas para la foto
        self.photo_canvas = tk.Canvas(
            self.photo_frame,
            width=120,
            height=150,
            bg=EstiloApp.COLOR_FRAMES,
            highlightthickness=0
        )
        self.photo_canvas.pack(padx=5, pady=5)
        
        # Imagen por defecto
        self.default_photo = Image.new('RGB', (120, 150), color='lightgray')
        draw = ImageDraw.Draw(self.default_photo)
        draw.text((40, 70), "Sin\nFoto", fill='gray')
        
        self.photo_image = ImageTk.PhotoImage(self.default_photo)
        self.photo_item = self.photo_canvas.create_image(60, 75, image=self.photo_image)
        
        return self.photo_frame

    # Restauramos el método para que maneje el canvas de la foto y los labels estadísticos
    def _create_action_buttons(self, parent):
        """
        Método mejorado para mostrar la foto y stats (similar a módulo_sanciones)
        """
        # No creamos botones duplicados aquí, solo inicializamos atributos para compatibilidad
        self.btn_guardar = None
        self.btn_modificar_action = None
        self.btn_limpiar_action = None
        
        # Crear un frame para estadísticas y foto (lado derecho)
        stats_photo_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_photo_frame.grid(row=0, column=1, sticky="ne", padx=10, pady=10)
        
        # Crear frame para estadísticas (lado izquierdo)
        stats_frame = ctk.CTkFrame(stats_photo_frame, fg_color=EstiloApp.COLOR_FRAMES)
        stats_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
        
        # Crear etiquetas de estadísticas
        self._create_stats_labels(stats_frame)
        
        # Crear canvas para la foto
        self._create_photo_canvas(stats_photo_frame)
        
        # Ajuste para darle más espacio al treeview
        if hasattr(parent, 'grid_rowconfigure'):
            parent.grid_rowconfigure(3, weight=1)  # Dar más peso a la fila del treeview
        
        return stats_photo_frame

    def guardar_licencia(self):
        """Guardar nueva licencia en la base de datos"""
        if not self.validar_campos():
            return

        def _guardar():
            connection = self.db_pool.get_connection()
            if not connection:
                return

            try:
                cursor = connection.cursor()
                
                # Convertir fechas al formato MySQL
                desde_fecha = datetime.strptime(self.entry_desde.get(), '%d-%m-%Y').strftime('%Y-%m-%d')
                hasta_fecha = datetime.strptime(self.entry_hasta.get(), '%d-%m-%Y').strftime('%Y-%m-%d')
                
                # Insertar nueva licencia
                cursor.execute("""
                    INSERT INTO licencias_sin_goce (
                        legajo, 
                        cantidad_dias, 
                        desde_fecha,
                        hasta_fecha,
                        solicita,
                        motivo
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    self.entry_legajo.get(),
                    self.entry_cantidad_dias.get(),
                    desde_fecha,
                    hasta_fecha,
                    self.entry_solicita.get(),
                    self.text_motivo.get("1.0", tk.END).strip()
                ))
                
                connection.commit()
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Éxito", "Licencia registrada correctamente"
                ))
                
                # Actualizar vista
                self.consultar_licencias(self.entry_legajo.get())
                
            except mysql.connector.Error as err:
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Error", f"No se pudo guardar: {err}", tipo="error"
                ))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)

        self.db_pool.executor.submit(_guardar)

    def _mostrar_dialogo_confirmacion(self, titulo, mensaje, accion_confirmacion):
        """Mostrar diálogo de confirmación genérico"""
        if self.root.winfo_exists():
            dialog = ctk.CTkToplevel(self.root)
            dialog.title(titulo)
            dialog.geometry("300x150")
            dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centrar la ventana
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (150)
            y = (dialog.winfo_screenheight() // 2) - (75)
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
            btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_frame.pack(pady=10)
            
            # Botones
            btn_si = ctk.CTkButton(
                btn_frame,
                text="Sí",
                font=ctk.CTkFont(size=13),
                width=80,
                fg_color=EstiloApp.BOTON_MODIFICAR,
                hover_color=EstiloApp.BOTON_MODIFICAR_HOVER,
                command=lambda: [dialog.destroy(), self.db_pool.executor.submit(accion_confirmacion)]
            )
            btn_si.grid(row=0, column=0, padx=10)
            
            btn_no = ctk.CTkButton(
                btn_frame,
                text="No",
                font=ctk.CTkFont(size=13),
                width=80,
                fg_color=EstiloApp.BOTON_LIMPIAR,
                hover_color=EstiloApp.BOTON_LIMPIAR_HOVER,
                command=dialog.destroy
            )
            btn_no.grid(row=0, column=1, padx=10)

    def _clear_treeview(self):
        """Limpiar todos los registros del treeview"""
        for row in self.tree.get_children():
            self.tree.delete(row)

    def _update_treeview(self, registros):
        """Actualizar el treeview con registros de licencias"""
        self._clear_treeview()
        for registro in registros:
            try:
                # Extraer los valores del registro
                id_licencia = registro[0]
                legajo = registro[1]
                
                # Obtener el nombre del empleado de la consulta SQL
                nombre_empleado = registro[2] if len(registro) > 2 and registro[2] else ""
                
                # Extraer el resto de los valores
                fecha_desde = registro[3]
                fecha_hasta = registro[4]
                dias = registro[5]
                motivo = registro[6]
                solicita = registro[7] if len(registro) > 7 else ""
                
                # Truncar motivo si es muy largo
                if motivo and len(motivo) > 50:
                    motivo_display = motivo[:47] + "..."
                else:
                    motivo_display = motivo
                
                # Crear lista de valores para insertar en el treeview
                valores = [
                    id_licencia,
                    legajo,
                    nombre_empleado,
                    fecha_desde,
                    fecha_hasta,
                    dias,
                    motivo_display,
                    solicita
                ]
                
                # Convertir todos los valores a string
                valores = [str(valor) if valor is not None else "" for valor in valores]
                
                # Insertar en el treeview
                self.tree.insert("", "end", values=valores)
            except Exception as e:
                self.logger.error(f"Error al actualizar treeview: {str(e)}")
                print(f"Error en _update_treeview: {e}")
                print(f"Registro: {registro}")

    def limpiar_campos(self):
        """Limpiar todos los campos del formulario"""
        # Reset variables importantes
        self._ultimo_legajo_consultado = None
        
        # Limpiar campos de entrada
        self.entry_legajo.delete(0, tk.END)
        self.text_motivo.delete("1.0", tk.END)
        self.entry_cantidad_dias.delete(0, tk.END)
        self.entry_solicita.delete(0, tk.END)
        self.entry_desde.set_date(datetime.now())
        self.entry_hasta.set_date(datetime.now())

        # Limpiar canvas y datos del empleado
        if hasattr(self, 'photo_canvas') and self.photo_canvas:
            self.photo_canvas.delete("all")
            # Recrear el óvalo placeholder
            self.photo_canvas.create_text(90, 90, text="👤", font=("Segoe UI Emoji", 90), fill="#64B5F6", tags="user_emoji")

        
        # Resetear labels de información
        self.nombre_completo_label.configure(text="👤 Empleado: No seleccionado")
        self.total_licencias_label.configure(text="📋 Historial: Sin licencias registradas")
        self.ultima_licencia_label.configure(text="⏱️ Última licencia: No registrada")
        self.dias_totales_label.configure(text="📊 Total días de licencia: 0 días")
        
        # Limpiar tabla
        self._clear_treeview()

    def mostrar_mensaje(self, titulo, mensaje, tipo="info"):
        """Mostrar mensaje en ventana emergente"""
        try:
            if not hasattr(self, 'root') or not self.root or not self.root.winfo_exists():
                print(f"Mensaje omitido (ventana cerrada): {titulo} - {mensaje}")
                return  # Evita abrir el mensaje si la aplicación ya está cerrada
            
            # Verificar si ya hay un diálogo abierto con el mismo título y mensaje
            for widget in self.root.winfo_children():
                if isinstance(widget, ctk.CTkToplevel) and widget.title() == titulo:
                    # Ya existe un diálogo similar, evitamos duplicar
                    return
            
            dialog = ctk.CTkToplevel(self.root)
            dialog.title(titulo)
            dialog.geometry("300x150")
            dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)
            
            # Hacer la ventana modal
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centrar la ventana
            dialog.update_idletasks()
            width = dialog.winfo_width()
            height = dialog.winfo_height()
            x = (dialog.winfo_screenwidth() // 2) - (width // 2)
            y = (dialog.winfo_screenheight() // 2) - (height // 2)
            dialog.geometry(f"+{x}+{y}")
            
            # Determinar color según tipo de mensaje
            bg_color = EstiloApp.COLOR_FRAMES
            if tipo == "error":
                bg_color = "#FFCCCC"  # Rojo claro para errores
            elif tipo == "warning":
                bg_color = "#FFFFCC"  # Amarillo claro para advertencias
            elif tipo == "success":
                bg_color = "#CCFFCC"  # Verde claro para éxito
            
            dialog.configure(fg_color=bg_color)
            
            # Frame principal
            frame = ctk.CTkFrame(dialog, fg_color=bg_color)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Mensaje
            lbl_mensaje = ctk.CTkLabel(
                frame, 
                text=mensaje,
                wraplength=250,
                justify="center"
            )
            lbl_mensaje.pack(pady=(10, 20))
            
            # Botón para cerrar
            btn_close = ctk.CTkButton(
                frame,
                text="Cerrar",
                command=dialog.destroy
            )
            btn_close.pack(pady=10)
            
            # Asegurarse de que se cierre después de un tiempo para evitar ventanas atascadas
            dialog.after(15000, dialog.destroy)
            
        except Exception as e:
            # Evitamos recursión al manejar errores en el propio método
            print(f"Error al mostrar mensaje: {e}")
            logging.error(f"Error en mostrar_mensaje: {str(e)}")

    def mostrar_carga(self, mensaje="Cargando..."):
        """Mostrar indicador de carga"""
        print(f"=== INICIANDO MOSTRAR_CARGA: {mensaje} ===")
        
        # Evitar múltiples ventanas de carga
        if hasattr(self, 'is_loading') and self.is_loading:
            print("Ya hay una ventana de carga activa, ignorando")
            return
            
        try:
            self.is_loading = True  # Marcar que hay una carga en proceso
            
            if not hasattr(self, 'root') or not self.root or not self.root.winfo_exists():
                print("La ventana principal no existe, cancelando mostrar_carga")
                self.is_loading = False
                return
                
            # Verificar si ya existe una ventana de carga
            if hasattr(self, 'loading_dialog') and self.loading_dialog and self.loading_dialog.winfo_exists():
                print("Ventana de carga ya existe, actualizando mensaje")
                # Actualizar mensaje en ventana existente
                for widget in self.loading_dialog.winfo_children():
                    if isinstance(widget, ctk.CTkLabel):
                        widget.configure(text=mensaje)
                        return
                return

            print("Creando nueva ventana de carga")
            self.loading_dialog = ctk.CTkToplevel(self.root)
            self.loading_dialog.title("Cargando")
            self.loading_dialog.geometry("200x100")
            self.loading_dialog.transient(self.root)
            self.loading_dialog.grab_set()

            # Centrar ventana
            self.loading_dialog.update_idletasks()
            x = (self.loading_dialog.winfo_screenwidth() // 2) - (200 // 2)
            y = (self.loading_dialog.winfo_screenheight() // 2) - (100 // 2)
            self.loading_dialog.geometry(f'+{x}+{y}')

            label = ctk.CTkLabel(self.loading_dialog, text=mensaje, font=ctk.CTkFont(size=14))
            label.pack(expand=True)
            
            # Asegurar que la ventana no se quede abierta indefinidamente
            self.root.after(15000, self.ocultar_carga)  # 15 segundos máximo
            print("Ventana de carga creada correctamente")
            
        except Exception as e:
            print(f"ERROR al mostrar ventana de carga: {str(e)}")
            self.is_loading = False

    def ocultar_carga(self):
        """Ocultar indicador de carga"""
        print("=== INICIANDO OCULTAR_CARGA ===")
        try:
            # Limpiar flag de carga
            self.is_loading = False
            
            if hasattr(self, 'loading_dialog'):
                if self.loading_dialog and self.loading_dialog.winfo_exists():
                    print("Destruyendo ventana de carga")
                    self.loading_dialog.grab_release()  # Liberar antes de destruir
                    self.loading_dialog.destroy()
                # Eliminar referencia
                del self.loading_dialog
                print("Ventana de carga eliminada")
            else:
                print("No hay ventana de carga para ocultar")
        except Exception as e:
            print(f"ERROR al ocultar ventana de carga: {str(e)}")
            # Intentar limpiar referencias en caso de error
            if hasattr(self, 'loading_dialog'):
                del self.loading_dialog

    def __del__(self):
        """Destructor de clase"""
        try:
            self.cleanup()
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def _actualizar_estadisticas_seguro(self, legajo):
        """Actualiza estadísticas creando una nueva conexión y cursor"""
        if not legajo:
            return
        
        conexion = None
        cursor = None
        try:
            # Crear una nueva conexión para estadísticas
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor()
            
            # Ahora podemos actualizar estadísticas con un cursor nuevo
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_licencias,
                    SUM(cantidad_dias) as total_dias,
                    MAX(desde_fecha) as ultima_fecha
                FROM licencias_sin_goce 
                WHERE legajo = %s
            """, (legajo,))
            
            resultado = cursor.fetchone()
            if resultado:
                total_licencias, total_dias, ultima_fecha = resultado
                
                # Actualizar UI en el hilo principal
                def _actualizar_labels():
                    # Comprobar si los labels existen antes de actualizar
                    if hasattr(self, 'total_licencias_label'):
                        self.total_licencias_label.configure(text=f"📋 Historial: {total_licencias or 0} licencias registradas")
                    
                    # Convertir fecha con manejo de errores
                    fecha_formateada = "No disponible"
                    if ultima_fecha:
                        try:
                            fecha_formateada = ultima_fecha.strftime('%d-%m-%Y')
                        except Exception as e:
                            self.logger.error(f"Error al formatear fecha: {str(e)}")
                    
                    if hasattr(self, 'ultima_licencia_label'):
                        self.ultima_licencia_label.configure(text=f"⏱️ Última licencia: {fecha_formateada}")
                    
                    if hasattr(self, 'dias_totales_label'):
                        self.dias_totales_label.configure(text=f"📊 Total días de licencia: {total_dias or 0} días")
                
                self.root.after(0, _actualizar_labels)
        
        except Exception as e:
            self.logger.error(f"Error al actualizar estadísticas: {str(e)}")
        
        finally:
            # Cerrar recursos
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    def show_in_frame(self, parent_frame):
        """Mostrar el módulo en un frame específico"""
        try:
            # Limpiar solo los bindings específicos que agregamos
            if hasattr(self, 'parent_frame'):
                try:
                    self.parent_frame.unbind('<MouseWheel>')  # Unbind específico en lugar de unbind_all
                    self.parent_frame.unbind('<Shift-MouseWheel>')
                except Exception as e:
                    self.logger.warning(f"Error al limpiar bindings: {e}")
            
            self.is_destroyed = False
            
            # Limpiar el frame padre
            for widget in parent_frame.winfo_children():
                widget.destroy()
            
            # Actualizar referencias
            self.parent = parent_frame
            self.root = parent_frame
            
            # Crear el contenedor principal
            self.main_container = ctk.CTkFrame(
                parent_frame,
                fg_color="transparent"
            )
            self.main_container.grid(row=0, column=0, sticky="nsew")
            
            # Configurar el grid del contenedor principal
            self.main_container.grid_columnconfigure(0, weight=1)
            self.main_container.grid_rowconfigure(0, weight=0)  # Header
            self.main_container.grid_rowconfigure(1, weight=1)  # Content
            
            # Crear la interfaz
            self.create_gui()
        
        except Exception as e:
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

    def _on_mousewheel(self, event, canvas):
        """Manejar el evento de la rueda del mouse con verificaciones de seguridad"""
        try:
            # Verificar si el canvas aún existe y es válido
            if not canvas.winfo_exists():
                print("Canvas no existe, removiendo binding")
                if hasattr(self, 'parent_frame'):
                    self.parent_frame.unbind_all('<MouseWheel>')
                    self.parent_frame.unbind_all('<Shift-MouseWheel>')
                return

            # Verificar si el canvas tiene scroll activo
            try:
                scroll_region = canvas.cget('scrollregion')
                if not scroll_region:
                    return
            except tk.TclError:
                print("Error accediendo al canvas, removiendo binding")
                return

            # Obtener la posición actual del scroll de forma segura
            try:
                current_view = canvas.yview()
                if not current_view:
                    return
            except tk.TclError:
                print("Error obteniendo yview, removiendo binding")
                return

            # Aplicar el scroll con verificaciones
            try:
                if event.state & 4:  # Shift presionado
                    canvas.xview_scroll(int(-1*(event.delta/120)), "units")
                else:
                    # Verificar límites antes de hacer scroll
                    if (event.delta > 0 and current_view[0] > 0) or \
                       (event.delta < 0 and current_view[1] < 1):
                        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError as e:
                print(f"Error durante scroll: {e}")
                return

        except Exception as e:
            print(f"Error general en _on_mousewheel: {e}")
            # Intentar limpiar bindings
            if hasattr(self, 'parent_frame'):
                try:
                    self.parent_frame.unbind_all('<MouseWheel>')
                    self.parent_frame.unbind_all('<Shift-MouseWheel>')
                except:
                    pass

    def create_scrollable_frame(self, parent):
        """Crear frame scrollable con manejo mejorado"""
        # Frame contenedor
        container = ctk.CTkFrame(parent)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Canvas con manejo de errores mejorado
        canvas = tk.Canvas(container, bg=parent.cget('fg_color'))
        canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbar
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Frame interior
        inner_frame = ctk.CTkFrame(canvas)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Configurar el canvas
        canvas_frame = canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        def _configure_canvas(event):
            if canvas.winfo_exists():
                try:
                    canvas.configure(scrollregion=canvas.bbox("all"))
                    canvas.itemconfig(canvas_frame, width=canvas.winfo_width())
                except tk.TclError:
                    print("Error configurando canvas")

        def _bind_mousewheel(event=None):
            if canvas.winfo_exists():
                try:
                    container.bind_all("<MouseWheel>", lambda e: self._on_mousewheel(e, canvas))
                    container.bind_all("<Shift-MouseWheel>", lambda e: self._on_mousewheel(e, canvas))
                except Exception as e:
                    print(f"Error en binding mousewheel: {e}")

        def _unbind_mousewheel(event=None):
            try:
                container.unbind_all("<MouseWheel>")
                container.unbind_all("<Shift-MouseWheel>")
            except Exception as e:
                print(f"Error unbinding mousewheel: {e}")

        # Configurar bindings con manejo de errores
        try:
            inner_frame.bind("<Configure>", _configure_canvas)
            container.bind("<Enter>", _bind_mousewheel)
            container.bind("<Leave>", _unbind_mousewheel)
        except Exception as e:
            print(f"Error configurando bindings: {e}")

    def limpiar_formulario(self):
        """Limpia todos los campos del formulario"""
        # Reiniciar el ID seleccionado
        self.licencia_seleccionada_id = None
        
        # Limpiar entrada de legajo y nombre
        self.entry_legajo.delete(0, tk.END)
        self.label_nombre_valor.config(text="")
        
        # Restaurar fechas al día actual
        fecha_actual = datetime.now()
        self.entry_desde.set_date(fecha_actual)
        self.entry_hasta.set_date(fecha_actual)
        
        # Limpiar resto de campos
        self.entry_cantidad_dias.delete(0, tk.END)
        self.text_motivo.delete("1.0", tk.END)
        self.entry_solicita.delete(0, tk.END)
        
        # Habilitar el campo de legajo
        self.entry_legajo.config(state="normal")

    def eliminar_registro(self):
        """Eliminar el registro seleccionado"""
        conexion = None
        try:
            if not self.licencia_seleccionada_id:
                messagebox.showwarning("Advertencia", "Debe seleccionar una licencia para eliminar")
                return
                
            confirmacion = messagebox.askyesno("Confirmar eliminación", 
                                              "¿Está seguro de eliminar esta licencia?")
            if not confirmacion:
                return
                
            # Verificar que tengamos la configuración de la base de datos
            if not hasattr(self, 'db_config') or not self.db_config:
                messagebox.showerror("Error", "No se ha configurado la conexión a la base de datos")
                return
                
            # Crear conexión
            try:
                conexion = mysql.connector.connect(**self.db_config)
                cursor = conexion.cursor()
            except mysql.connector.Error as e:
                self.logger.error(f"Error al conectar con la base de datos: {str(e)}")
                messagebox.showerror("Error de conexión", f"No se pudo conectar a la base de datos: {str(e)}")
                return
            
            # Eliminar registro
            sql = "DELETE FROM licencias_sin_goce WHERE id = %s"
            cursor.execute(sql, (self.licencia_seleccionada_id,))
            
            conexion.commit()
            cursor.close()
            conexion.close()
            
            messagebox.showinfo("Éxito", "Licencia eliminada correctamente")
            self.limpiar_formulario()
            self.consultar_licencias()
            
        except Exception as e:
            self.logger.error(f"Error en eliminar_registro: {str(e)}")
            messagebox.showerror("Error", f"Error al eliminar registro: {str(e)}")
            if conexion is not None and conexion.is_connected():
                conexion.close()

    def guardar_registro(self):
        """Guardar un nuevo registro de licencia o actualizar uno existente"""
        conexion = None
        try:
            # Validar campos obligatorios
            legajo = self.entry_legajo.get().strip()
            desde_fecha = self.entry_desde.get_date()
            hasta_fecha = self.entry_hasta.get_date()
            
            cantidad_dias = self.entry_cantidad_dias.get().strip()
            motivo = self.text_motivo.get("1.0", "end-1c").strip()
            solicita = self.entry_solicita.get().strip()
            
            # Validar campos requeridos
            if not legajo or not desde_fecha or not hasta_fecha or not motivo or not solicita:
                messagebox.showerror("Error", "Todos los campos son obligatorios")
                return
                
            # Validar fechas
            if desde_fecha > hasta_fecha:
                messagebox.showerror("Error", "La fecha de inicio no puede ser posterior a la fecha de fin")
                return
                
            # Validar que cantidad_dias sea un número
            try:
                if cantidad_dias:
                    int(cantidad_dias)
            except ValueError:
                messagebox.showerror("Error", "La cantidad de días debe ser un número entero")
                return
                
            # Convertir fechas a formato adecuado para la base de datos
            desde_fecha_db = desde_fecha.strftime('%Y-%m-%d')
            hasta_fecha_db = hasta_fecha.strftime('%Y-%m-%d')
            
            # Verificar que tengamos la configuración de la base de datos
            if not hasattr(self, 'db_config') or not self.db_config:
                messagebox.showerror("Error", "No se ha configurado la conexión a la base de datos")
                return
                
            # Crear conexión
            try:
                conexion = mysql.connector.connect(**self.db_config)
                cursor = conexion.cursor()
            except mysql.connector.Error as e:
                self.logger.error(f"Error al conectar con la base de datos: {str(e)}")
                messagebox.showerror("Error de conexión", f"No se pudo conectar a la base de datos: {str(e)}")
                return
            
            # Verificar que el legajo exista
            cursor.execute("SELECT COUNT(*) FROM personal WHERE legajo = %s", (legajo,))
            if cursor.fetchone()[0] == 0:
                messagebox.showerror("Error", f"No existe un empleado con el legajo {legajo}")
                cursor.close()
                conexion.close()
                return
            
            if self.licencia_seleccionada_id:
                # Actualizar registro existente
                sql = """
                UPDATE licencias_sin_goce 
                SET legajo = %s, desde_fecha = %s, hasta_fecha = %s, cantidad_dias = %s, 
                    motivo = %s, solicita = %s
                WHERE id = %s
                """
                values = (legajo, desde_fecha_db, hasta_fecha_db, cantidad_dias, 
                         motivo, solicita, self.licencia_seleccionada_id)
                
                cursor.execute(sql, values)
                mensaje = "Licencia actualizada correctamente"
            else:
                # Crear nuevo registro
                sql = """
                INSERT INTO licencias_sin_goce 
                (legajo, desde_fecha, hasta_fecha, cantidad_dias, motivo, solicita)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                values = (legajo, desde_fecha_db, hasta_fecha_db, cantidad_dias, 
                         motivo, solicita)
                
                cursor.execute(sql, values)
                mensaje = "Licencia registrada correctamente"
                
            conexion.commit()
            cursor.close()
            conexion.close()
            
            messagebox.showinfo("Éxito", mensaje)
            self.limpiar_formulario()
            self.consultar_licencias()
            
        except Exception as e:
            self.logger.error(f"Error en guardar_registro: {str(e)}")
            messagebox.showerror("Error", f"Error al guardar registro: {str(e)}")
            if conexion is not None and conexion.is_connected():
                conexion.close()

    def _setup_buttons(self, parent_frame):
        """Configurar los botones de acción del formulario"""
        # Crear un frame para contener los botones
        buttons_frame = ctk.CTkFrame(parent_frame)
        buttons_frame.grid(row=7, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        # Configurar el frame para que los botones se expandan
        for i in range(4):
            buttons_frame.columnconfigure(i, weight=1)
        
        # Crear botones
        btn_guardar = ctk.CTkButton(
            buttons_frame, 
            text="Guardar", 
            command=self.guardar_registro,
            fg_color="#28a745",
            hover_color="#218838"
        )
        btn_guardar.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        btn_limpiar = ctk.CTkButton(
            buttons_frame, 
            text="Limpiar", 
            command=self.limpiar_formulario,
            fg_color="#ffc107",
            hover_color="#e0a800",
            text_color="#000000"
        )
        btn_limpiar.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        btn_eliminar = ctk.CTkButton(
            buttons_frame, 
            text="Eliminar", 
            command=self.eliminar_registro,
            fg_color="#dc3545",
            hover_color="#c82333"
        )
        btn_eliminar.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        btn_exportar = ctk.CTkButton(
            buttons_frame, 
            text="Exportar", 
            command=self.exportar_a_excel,
            fg_color="#17a2b8",
            hover_color="#138496"
        )
        btn_exportar.grid(row=0, column=3, padx=5, pady=5, sticky="ew")


    def _calcular_dias_licencia(self, event=None):
        """Calcula automáticamente la cantidad de días entre fecha_desde y fecha_hasta"""
        try:
            # Verificar que los campos existan
            if not hasattr(self, 'entry_fecha_desde') or not hasattr(self, 'entry_fecha_hasta') or not hasattr(self, 'entry_dias'):
                print("Faltan campos necesarios para calcular días")
                return
                
            fecha_desde_str = self.entry_fecha_desde.get()
            fecha_hasta_str = self.entry_fecha_hasta.get()
            
            # Verificar que ambas fechas estén ingresadas
            if not fecha_desde_str or not fecha_hasta_str:
                return
                
            # Convertir strings a objetos datetime
            fecha_desde = datetime.strptime(fecha_desde_str, '%d/%m/%Y')
            fecha_hasta = datetime.strptime(fecha_hasta_str, '%d/%m/%Y')
            
            # Calcular la diferencia en días
            diferencia = (fecha_hasta - fecha_desde).days + 1  # +1 para incluir el día final
            
            # Verificar que la diferencia sea positiva
            if diferencia <= 0:
                return
                
            # Actualizar el campo de días
            self.entry_dias.delete(0, tk.END)
            self.entry_dias.insert(0, str(diferencia))
            
            print(f"Días calculados: {diferencia} días entre {fecha_desde_str} y {fecha_hasta_str}")
            
        except ValueError as e:
            print(f"Error al calcular días: {e}")
        except Exception as e:
            print(f"Error inesperado: {e}")

if __name__ == "__main__":
    app = None
    try:
        app = AplicacionLicencias()
        app.run()
    except Exception as e:
        # Configurar logging básico en caso de error antes de inicialización
        logging.basicConfig(
            filename="logs/errores_críticos_licencias.log",
            level=logging.CRITICAL,
            format='%(asctime)s - [%(levelname)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.critical(f"Error crítico al iniciar la aplicación: {str(e)}\n{traceback.format_exc()}")
        print(f"Error al iniciar la aplicación: {e}")
        app and hasattr(app, 'cleanup') and app.cleanup()