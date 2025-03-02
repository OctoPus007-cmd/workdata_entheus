import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from tkcalendar import DateEntry
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import mysql.connector
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk, ImageSequence
import io
import logging
from datetime import datetime, date
import traceback
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

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

class AplicacionSanciones:
    def __init__(self, parent_frame=None):
        """
        Inicializar la aplicación
        :param parent_frame: Frame padre donde se mostrará el módulo
        """
        # Inicializar is_destroyed primero
        self.is_destroyed = False
        
        # Determinar si es standalone o integrado
        self.is_standalone = parent_frame is None
        
        if self.is_standalone:
            # Modo standalone: crear ventana principal
            self.root = ctk.CTk()
            self.main_container = self.root
            # Configurar atributos de ventana solo en modo standalone
            self.root.title("Sistema de Gestión de Sanciones")
            self.root.state('zoomed')
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        else:
            # Modo integrado: usar frame proporcionado
            self.root = parent_frame
            self.main_container = ctk.CTkFrame(self.root, fg_color=EstiloApp.COLOR_PRINCIPAL)
            self.main_container.grid(row=0, column=0, sticky="nsew")
        
        self.db_pool = None
        self.sancion_seleccionada_id = None
        
        # Configurar el sistema de logging
        self._setup_logging()
        
        # Mostrar mensaje de carga solo en modo standalone
        if self.is_standalone:
            self.loading_label = ctk.CTkLabel(
                self.root,
                text="Iniciando aplicación...",
                font=ctk.CTkFont(size=16)
            )
            self.loading_label.grid(row=0, column=0)
            self.root.after(100, self._init_async)
        else:
            self._init_async()

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
            filename=os.path.join(log_dir, 'errores_sanciones.log'),
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
        """Limpiar recursos y bindings"""
        try:
            # Limpiar bindings de mousewheel
            if hasattr(self, 'parent_frame'):
                self.parent_frame.unbind_all('<MouseWheel>')
                self.parent_frame.unbind_all('<Shift-MouseWheel>')
            
            # Detener animación del logo si existe
            if hasattr(self, 'animation_running'):
                self.animation_running = False
            
            # Solo cerrar la conexión si estamos en modo standalone
            if self.is_standalone and hasattr(self, 'db_pool'):
                self.db_pool.close()
            
            self.is_destroyed = True
            
        except Exception as e:
            print(f"Error en cleanup: {e}")

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
        """Iniciar la aplicación"""
        try:
            self.root.mainloop()
        finally:
            self.cleanup()

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
        """Crear la interfaz gráfica de usuario"""
        # Frame superior
        self._create_header_frame()  # row=0
        
        # Crear frame para botones CRUD
        self._create_buttons()  # row=1
        
        # Crear main_container pegado a los botones
        self.main_container = ctk.CTkFrame(
            self.root,
            fg_color=EstiloApp.COLOR_PRINCIPAL,
        )
        self.main_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))
        
        # Configurar el grid del root con pesos específicos
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0)  # Header - sin expansión
        self.root.grid_rowconfigure(1, weight=0)  # Buttons - sin expansión
        self.root.grid_rowconfigure(2, weight=2)  # Main container - expansible
        
        # Configurar el grid del contenedor principal
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=0)  # Form
        self.main_container.grid_rowconfigure(1, weight=3)  # Table

        # Crear componentes
        self._create_form()
        self._create_table()

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

        # Título principal
        title_label = ctk.CTkLabel(
            header_frame,
            text="Módulo de Sanciones - RRHH",
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
        """Consultar datos del empleado cuando se ingresa el legajo"""
        if not self.db_pool:
            self.mostrar_mensaje("Error", "Esperando conexión a la base de datos...")
            return

        legajo = self.entry_legajo.get().strip()
        
        def _consultar():
            connection = self.db_pool.get_connection()
            try:
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
                    
                    # Consultar estadísticas
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_sanciones,
                            COALESCE(
                                SUM(CASE 
                                    WHEN LOWER(REPLACE(tipo_sancion, 'ó', 'o')) IN ('suspension', 'suspensión', 'suspencion')
                                    AND fecha >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
                                    THEN cantidad_dias 
                                    ELSE 0 
                                END
                            ), 0) as dias_suspension_recientes,
                            MAX(fecha) as ultima_fecha
                        FROM sanciones 
                        WHERE legajo = %s
                    """, (legajo,))
                    
                    stats = cursor.fetchone()
                    total_sanciones = stats[0]
                    dias_suspension_recientes = stats[1]
                    ultima_fecha = stats[2]
                    
                    def _actualizar_ui():
                        self.nombre_completo_label.configure(text=f"👤 Empleado: {apellido_nombre}")
                        self.total_sanciones_label.configure(text=f"📋 Historial: {total_sanciones} sanciones registradas")
                        
                        # Actualizar última sanción
                        if ultima_fecha:
                            fecha_formateada = ultima_fecha.strftime('%d-%m-%Y')
                            self.ultima_sancion_label.configure(text=f"⏱️ Última sanción: {fecha_formateada}")
                        else:
                            self.ultima_sancion_label.configure(text="⏱️ Última sanción: No registrada")
                        
                        # Actualizar suspensiones recientes
                        self.suspensiones_recientes_label.configure(
                            text=f"⚠️ Suspensiones (365 días): {dias_suspension_recientes} días"
                        )
                        
                        # Actualizar foto
                        self.actualizar_foto(foto_blob)
                    
                    if not self.is_destroyed:
                        self.root.after(0, _actualizar_ui)
                        
                    # Consultar sanciones para el treeview
                    self.consultar_sanciones(legajo)
                    
                else:
                    if not self.is_destroyed:
                        self.root.after(0, lambda: self.mostrar_mensaje(
                            "Error", "No se encontró el empleado"
                        ))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)

        self.db_pool.executor.submit(_consultar)

    def actualizar_foto(self, foto_blob):
        """Actualizar la foto del empleado"""
        try:
            if foto_blob and len(foto_blob) > 0:
                image = Image.open(io.BytesIO(foto_blob))
                
                # Calcular el tamaño manteniendo la proporción
                target_size = 210  # Tamaño objetivo
                width, height = image.size
                aspect_ratio = width / height
                
                if aspect_ratio > 1:
                    new_width = target_size
                    new_height = int(target_size / aspect_ratio)
                else:
                    new_height = target_size
                    new_width = int(target_size * aspect_ratio)
                
                # Convertir y redimensionar la imagen
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Crear una imagen cuadrada con fondo blanco
                square_image = Image.new('RGB', (target_size, target_size), 'white')
                
                # Calcular posición para centrar
                x = (target_size - new_width) // 2
                y = (target_size - new_height) // 2
                
                # Pegar la imagen redimensionada en el centro
                square_image.paste(image, (x, y))
                
                # Crear PhotoImage
                photo = ImageTk.PhotoImage(square_image)
                
                # Actualizar canvas
                self.photo_canvas.delete("all")
                self.photo_canvas.create_image(
                    target_size//2,  # Centro x
                    target_size//2,  # Centro y
                    image=photo,
                    anchor="center"
                )
                # Mantener referencia
                self.photo_canvas.image = photo
                
            else:
                raise ValueError("No hay foto disponible")
        except Exception as e:
            self.logger.error(f"Error al cargar la imagen: {str(e)}")
            self.photo_canvas.delete("all")
            self.photo_canvas.create_oval(
                10, 10,
                200, 200,
                fill=EstiloApp.COLOR_SECUNDARIO,
                outline=EstiloApp.COLOR_SECUNDARIO
            )
            self.photo_canvas.create_text(
                105, 105,
                text="Sin\nfoto",
                fill=EstiloApp.COLOR_TEXTO,
                font=('Helvetica', 16, 'bold'),
                justify='center'
            )

    def _create_form(self):
        """Crear el formulario de registro de sanciones"""
        form_frame = ctk.CTkFrame(
            self.main_container, 
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        form_frame.grid(row=0, column=0, sticky="new", padx=10, pady=5)
        form_frame.grid_columnconfigure(0, weight=1)  # Panel izquierdo
        form_frame.grid_columnconfigure(1, weight=1)  # Panel central
        form_frame.grid_columnconfigure(2, weight=1)  # Panel derecho

        # Panel izquierdo (formulario)
        left_panel = ctk.CTkFrame(form_frame, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="e", padx=(50, 20), pady=10)  # Ajustado padding y sticky
        
        # Título del formulario
        title_label = ctk.CTkLabel(
            left_panel,
            text="Registre o Modifique una Sanción",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Crear campos del formulario
        self.crear_campos_formulario(left_panel)

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
            width=220,
            height=220
        )
        photo_frame.grid(row=0, column=0, padx=(0, 20), pady=(45, 0))
        photo_frame.grid_propagate(False)  # Mantener tamaño fijo del frame

        # Canvas para la foto - aumentado el tamaño
        self.photo_canvas = ctk.CTkCanvas(
            photo_frame,
            width=210,  # Aumentado de 200 a 210
            height=210,  # Aumentado de 200 a 210
            bg=EstiloApp.COLOR_PRINCIPAL,
            highlightthickness=0
        )
        self.photo_canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Placeholder inicial con óvalo más grande
        self.photo_canvas.create_oval(
            10, 10,  # Reducido el margen de 40 a 10
            200, 200,  # Aumentado el tamaño del óvalo
            fill=EstiloApp.COLOR_SECUNDARIO,
            outline=EstiloApp.COLOR_SECUNDARIO
        )
        self.photo_canvas.create_text(
            105, 105,  # Centrado en el nuevo óvalo
            text="Sin\nfoto",
            fill=EstiloApp.COLOR_TEXTO,
            font=('Helvetica', 16, 'bold'),  # Aumentado tamaño de fuente
            justify='center'
        )

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

        self.total_sanciones_label = ctk.CTkLabel(
            data_frame,
            text="📋 Historial: Sin sanciones registradas",
            font=ctk.CTkFont(size=14),
            anchor="w",
            width=300
        )
        self.total_sanciones_label.pack(anchor="w", pady=15)  # Ajustado padding vertical

        self.ultima_sancion_label = ctk.CTkLabel(
            data_frame,
            text="⏱️ Última sanción: No registrada",
            font=ctk.CTkFont(size=14),
            anchor="w",
            width=300
        )
        self.ultima_sancion_label.pack(anchor="w", pady=15)  # Ajustado padding vertical

        # Nuevo label para suspensiones del último año
        self.suspensiones_recientes_label = ctk.CTkLabel(
            data_frame,
            text="⚠️ Suspensiones (365 días): 0 días",
            font=ctk.CTkFont(size=14),
            anchor="w",
            width=300
        )
        self.suspensiones_recientes_label.pack(anchor="w", pady=15)

        # Nuevo label para total histórico de suspensiones
        self.suspensiones_historicas_label = ctk.CTkLabel(
            data_frame,
            text="📊 Total histórico suspensiones: 0 días",
            font=ctk.CTkFont(size=14),
            anchor="w",
            width=300
        )
        self.suspensiones_historicas_label.pack(anchor="w", pady=15)

        # Vincular evento de entrada al campo legajo
        self.entry_legajo.bind('<FocusOut>', self.consultar_empleado)
        self.entry_legajo.bind('<Return>', self.consultar_empleado)

    def _create_table(self):
        """Crear la tabla de registros de sanciones"""
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

        # Título de la tabla
        title_label = ctk.CTkLabel(
            table_container,
            text="Registros de Sanciones",
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
            columns=("id", "legajo", "fecha", "objetivo", "motivo", "tipo_sancion", "cantidad_dias", "solicita"),
            show="headings",
            height=20,
            style="Custom.Treeview"
        )

        # Configurar las columnas
        columnas = {
            "id": ("ID", 50),
            "legajo": ("Legajo", 80),
            "fecha": ("Fecha", 100),
            "objetivo": ("Objetivo", 150),
            "motivo": ("Motivo", 200),
            "tipo_sancion": ("Tipo Sanción", 120),
            "cantidad_dias": ("Días", 60),
            "solicita": ("Solicita", 150)
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

        # Guardar ID de la sanción seleccionada
        self.sancion_seleccionada_id = valores[0]
        
        # Cargar datos en los campos
        self.entry_legajo.delete(0, tk.END)
        self.entry_legajo.insert(0, str(valores[1]))
        
        self.entry_fecha.set_date(datetime.strptime(valores[2], '%d-%m-%Y'))
        
        self.entry_objetivo.delete(0, tk.END)
        self.entry_objetivo.insert(0, valores[3])
        
        self.text_motivo.delete("1.0", tk.END)
        self.text_motivo.insert("1.0", valores[4])
        
        self.combo_tipo.set(valores[5])
        
        self.entry_cantidad_dias.delete(0, tk.END)
        self.entry_cantidad_dias.insert(0, str(valores[6]))
        
        self.entry_solicita.delete(0, tk.END)
        self.entry_solicita.insert(0, valores[7])

    def _create_buttons(self):
        """Crear barra de botones"""
        button_frame = ctk.CTkFrame(
            self.root,
            fg_color="transparent"
        )
        button_frame.grid(row=1, column=0, padx=20, pady=(5, 5), sticky="ew")  # Ajustar pady

        buttons = [
            ("Insertar", self.insertar_sancion, EstiloApp.BOTON_INSERTAR, EstiloApp.BOTON_INSERTAR_HOVER),
            ("Modificar", self.modificar_sancion, EstiloApp.BOTON_MODIFICAR, EstiloApp.BOTON_MODIFICAR_HOVER),
            ("Eliminar", self.eliminar_sancion, EstiloApp.BOTON_ELIMINAR, EstiloApp.BOTON_ELIMINAR_HOVER),
            ("Limpiar", self.limpiar_campos, EstiloApp.BOTON_LIMPIAR, EstiloApp.BOTON_LIMPIAR_HOVER)
        ]

        for idx, (text, command, color, hover_color) in enumerate(buttons):
            ctk.CTkButton(
                button_frame,
                text=text,
                font=ctk.CTkFont(size=14),
                width=120,
                height=35,
                fg_color=color,
                text_color="white",
                hover_color=hover_color,
                command=command
            ).grid(row=0, column=idx, padx=10)

    def eliminar_sancion(self):
        """Eliminar sanción seleccionada"""
        seleccion = self.tree.selection()
        if not seleccion:
            self.mostrar_mensaje("Error", "Debe seleccionar una sanción para eliminar")
            return

        def _eliminar():
            connection = self.db_pool.get_connection()
            if not connection:
                return

            try:
                cursor = connection.cursor()
                item = self.tree.selection()[0]
                valores = self.tree.item(item)['values']
                legajo = valores[1]  # Guardar el legajo para actualizar la vista
                
                # Eliminar la sanción
                cursor.execute("DELETE FROM sanciones WHERE id = %s", (valores[0],))
                connection.commit()
                
                # Consultar sanciones actualizadas
                cursor.execute("""
                    SELECT id, legajo, fecha, objetivo, motivo, tipo_sancion, cantidad_dias, solicita
                    FROM sanciones 
                    WHERE legajo = %s
                    ORDER BY fecha DESC
                """, (legajo,))
                
                registros = cursor.fetchall()
                
                # Obtener estadísticas actualizadas
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_sanciones,
                        COALESCE(SUM(CASE 
                            WHEN tipo_sancion = 'Suspensión' 
                            AND fecha >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
                            THEN cantidad_dias 
                            ELSE 0 
                        END), 0) as dias_suspension_recientes,
                        MAX(fecha) as ultima_fecha
                    FROM sanciones 
                    WHERE legajo = %s
                """, (legajo,))
                
                stats = cursor.fetchone()
                
                def _actualizar_ui():
                    # Limpiar treeview
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    
                    # Insertar registros actualizados
                    for registro in registros:
                        fecha = datetime.strptime(str(registro[2]), '%Y-%m-%d').strftime('%d-%m-%Y')
                        valores = list(registro)
                        valores[2] = fecha
                        self.tree.insert("", "end", values=valores)
                    
                    # Actualizar contadores existentes
                    self.total_sanciones_label.configure(text=f"📋 Historial: {stats[0] or 0} sanciones registradas")
                    self.suspensiones_recientes_label.configure(text=f"⚠️ Suspensiones (365 días): {stats[1] or 0} días")
                    
                    # Actualizar última sanción si existe
                    if stats[2]:
                        fecha_formateada = datetime.strptime(str(stats[2]), '%Y-%m-%d').strftime('%d-%m-%Y')
                        self.ultima_sancion_label.configure(text=f"⏱️ Última sanción: {fecha_formateada}")
                    else:
                        self.ultima_sancion_label.configure(text="⏱️ Última sanción: No registrada")
                    
                    # Mostrar mensaje de éxito
                    self.mostrar_mensaje("Éxito", "Sanción eliminada correctamente")
                
                # Actualizar UI en el hilo principal
                if not self.is_destroyed:
                    self.root.after(0, _actualizar_ui)
                
            except Exception as e:
                if connection:
                    connection.rollback()
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Error", f"No se pudo eliminar la sanción: {str(e)}"
                ))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)

        # Mostrar diálogo de confirmación
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Confirmar eliminación")
        dialog.geometry("300x150")
        dialog.configure(fg_color=EstiloApp.COLOR_FRAMES)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar la ventana
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (150)
        y = (dialog.winfo_screenheight() // 2) - (75)
        dialog.geometry(f'+{x}+{y}')
        
        # Mensaje de confirmación
        label = ctk.CTkLabel(
            dialog,
            text="¿Está seguro que desea eliminar la sanción seleccionada?",
            font=ctk.CTkFont(size=14),
            wraplength=250
        )
        label.pack(pady=20)
        
        # Frame para botones
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        # Botones Sí y No
        btn_si = ctk.CTkButton(
            btn_frame,
            text="Sí",
            font=ctk.CTkFont(size=13),
            width=80,
            fg_color=EstiloApp.BOTON_ELIMINAR,
            hover_color=EstiloApp.BOTON_ELIMINAR_HOVER,
            command=lambda: [dialog.destroy(), self.db_pool.executor.submit(_eliminar)]
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

    def on_tree_double_click(self, event):
        """Manejar doble clic en una fila del treeview"""
        seleccion = self.tree.selection()
        if not seleccion:
            return
            
        try:
            item = seleccion[0]
            valores = self.tree.item(item)['values']
            
            if not valores:
                return
                
            # Consultar los datos completos de la sanción
            def _get_sancion_completa():
                connection = self.db_pool.get_connection()
                try:
                    cursor = connection.cursor()
                    # Especificar explícitamente las columnas en el orden correcto
                    cursor.execute("""
                        SELECT id, legajo, fecha, objetivo, motivo, tipo_sancion, cantidad_dias, solicita 
                        FROM sanciones 
                        WHERE id = %s
                    """, (valores[0],))
                    resultado = cursor.fetchone()
                    if resultado:
                        self.root.after(0, lambda: self._cargar_datos_sancion(resultado))
                finally:
                    cursor.close()
                    self.db_pool.return_connection(connection)
            
            self.db_pool.executor.submit(_get_sancion_completa)
                
        except Exception as e:
            self.mostrar_mensaje("Error", "Error al cargar los datos del registro")
            self.logger.error(f"Error en double click: {str(e)}")

    def _cargar_datos_sancion(self, datos):
        """Cargar datos completos de la sanción en el formulario"""
        try:
            # Debug: imprimir los datos recibidos
            print("Datos recibidos:", datos)
            
            # Mapear los datos según el orden de la base de datos
            valores = {
                'id': datos[0],
                'legajo': datos[1],
                'fecha': datos[2].strftime("%d-%m-%Y"),
                'objetivo': datos[3],
                'motivo': datos[4],
                'tipo_sancion': datos[5],
                'cantidad_dias': datos[6],
                'solicita': datos[7]
            }
            
            # Limpiar todos los campos primero
            self.entry_legajo.delete(0, tk.END)
            self.entry_objetivo.delete(0, tk.END)
            self.text_motivo.delete("1.0", tk.END)
            self.entry_cantidad_dias.delete(0, tk.END)
            self.entry_solicita.delete(0, tk.END)
            
            # Cargar los datos usando el mapeo
            self.sancion_seleccionada_id = valores['id']
            self.entry_legajo.insert(0, str(valores['legajo']))
            self.entry_fecha.set_date(datetime.strptime(valores['fecha'], "%d-%m-%Y"))
            self.entry_objetivo.insert(0, str(valores['objetivo']))
            self.text_motivo.delete("1.0", tk.END)  # Limpiar de nuevo para asegurar
            self.text_motivo.insert("1.0", str(valores['motivo']))
            self.combo_tipo.set(str(valores['tipo_sancion']))  # Actualizar combo_tipo con el valor de la base de datos
            self.entry_cantidad_dias.insert(0, str(valores['cantidad_dias']))
            self.entry_solicita.insert(0, str(valores['solicita']))
            
            # Actualizar datos del empleado si hay legajo
            if valores['legajo']:
                self.consultar_empleado()
                
        except Exception as e:
            self.mostrar_mensaje("Error", f"Error al cargar los datos: {str(e)}")
            self.logger.error(f"Error al cargar datos: {str(e)}, datos={datos}")

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

    def modificar_sancion(self):
        """Modificar sanción seleccionada"""
        if not self.sancion_seleccionada_id:
            self.mostrar_mensaje("Error", "Debe seleccionar una sanción para modificar")
            return

        if not self.validar_campos():
            return

        def _modificar():
            connection = None
            cursor = None
            try:
                connection = self.db_pool.get_connection()
                cursor = connection.cursor()
                
                # Validar que la sanción aún existe
                cursor.execute("""
                    SELECT legajo 
                    FROM sanciones 
                    WHERE id = %s
                """, (self.sancion_seleccionada_id,))
                
                resultado = cursor.fetchone()
                if not resultado:
                    raise ValueError("La sanción seleccionada ya no existe")
                
                legajo_original = resultado[0]
                
                # Validar empleado
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM personal 
                    WHERE legajo = %s
                """, (int(self.entry_legajo.get()),))
                
                if cursor.fetchone()[0] == 0:
                    raise ValueError("El legajo no existe")
                
                # Realizar la modificación
                sql = """
                UPDATE sanciones 
                SET legajo = %s, 
                    fecha = %s, 
                    objetivo = %s,
                    motivo = %s,
                    tipo_sancion = %s,
                    cantidad_dias = %s,
                    solicita = %s
                WHERE id = %s
                """
                
                datos = (
                    int(self.entry_legajo.get()),
                    datetime.strptime(self.entry_fecha.get(), "%d-%m-%Y").strftime("%Y-%m-%d"),
                    self.entry_objetivo.get().strip(),
                    self.text_motivo.get("1.0", tk.END).strip(),
                    self.combo_tipo.get(),  # Cambiado de entry_tipo_sancion a combo_tipo
                    int(self.entry_cantidad_dias.get() or 0),  # Cambiado de entry_dias
                    self.entry_solicita.get().strip(),  # Agregado entry_solicita
                    self.sancion_seleccionada_id
                )
                
                cursor.execute(sql, datos)
                connection.commit()
                
                legajo = self.entry_legajo.get()
                self.logger.info(f"Sanción {self.sancion_seleccionada_id} modificada exitosamente")
                
                # Obtener los datos actualizados para el treeview
                cursor.execute("""
                    SELECT id, legajo, fecha, objetivo, motivo, tipo_sancion, cantidad_dias, solicita
                    FROM sanciones 
                    WHERE legajo = %s
                    ORDER BY fecha DESC
                """, (legajo,))
                
                registros = cursor.fetchall()
                registros_convertidos = []
                
                for registro in registros:
                    fecha_mysql = registro[2]
                    fecha_ui = datetime.strptime(str(fecha_mysql), '%Y-%m-%d').strftime('%d-%m-%Y')
                    registro_convertido = list(registro)
                    registro_convertido[2] = fecha_ui
                    # Truncar textos largos si es necesario
                    if len(registro[4]) > 50:  # motivo
                        registro_convertido[4] = registro[4][:47] + "..."
                    registros_convertidos.append(tuple(registro_convertido))
                
                # Actualizar estadísticas
                self._actualizar_estadisticas(cursor, legajo)
                
                if not self.is_destroyed:
                    def _actualizar_vista():
                        # Primero actualizar el treeview
                        self._clear_treeview()
                        for registro in registros_convertidos:
                            self.tree.insert("", tk.END, values=registro)
                        
                        # Luego mostrar mensaje y limpiar campos
                        self.mostrar_mensaje("Éxito", "Sanción modificada correctamente")
                        self.limpiar_campos_parcial()
                        
                        # Asegurar que el legajo permanezca seleccionado
                        self.entry_legajo.delete(0, tk.END)
                        self.entry_legajo.insert(0, str(legajo))
                    
                    self.root.after(0, _actualizar_vista)
                
            except ValueError as ve:
                if connection:
                    connection.rollback()
                if not self.is_destroyed:
                    self.root.after(0, lambda msg=str(ve): 
                        self.handle_database_error(msg, "modificar_sancion"))
                
            except Exception as e:
                if connection:
                    connection.rollback()
                self.logger.error(f"Error al modificar sanción: {str(e)}")
                if not self.is_destroyed:
                    error_msg = str(e)
                    self.root.after(0, lambda msg=error_msg: 
                        self.handle_database_error(msg, "modificar_sancion"))
                
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    self.db_pool.return_connection(connection)

        self._mostrar_dialogo_confirmacion(
            "Confirmar modificación",
            "¿Está seguro que desea modificar esta sanción?",
            lambda: self.db_pool.executor.submit(_modificar)
        )

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

    def crear_campos_formulario(self, left_panel):
        """Crear los campos del formulario"""
        label_font = ctk.CTkFont(size=14)
        entry_font = ctk.CTkFont(size=14)
        
        # Configuración de campos con posiciones específicas
        field_configs = {
            # Columna izquierda
            "legajo": {"row": 1, "column": 0, "width": 200, "height": 35},
            "objetivo": {"row": 2, "column": 0, "width": 200, "height": 35},
            "fecha": {"row": 3, "column": 0, "width": 200, "height": 35},
            "tipo": {"row": 5, "column": 0, "width": 200, "height": 35, "combo": True, 
                    "values": ["Suspensión", "Amonestación", "Apercibimiento", "Despido"]},
            "solicita": {"row": 4, "column": 0, "width": 200, "height": 35},  # Movido a la columna izquierda
            # Columna derecha (motivo)
            "motivo": {"row": 1, "column": 1, "width": 400, "height": 200, "rowspan": 5, "textbox": True},
        }

        # Crear los campos según la configuración
        for field_name, config in field_configs.items():
            # Crear label
            label = ctk.CTkLabel(
                left_panel, 
                text=f"{field_name.capitalize()}:",
                font=label_font
            )
            label.grid(row=config["row"], column=config["column"]*2, 
                      sticky='e', padx=5, pady=5)

            if field_name == "motivo":
                # TextBox para motivo que abarca múltiples filas
                widget = ctk.CTkTextbox(
                    left_panel,
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
                
            elif field_name == "fecha":
                # Frame contenedor para el DateEntry
                date_frame = ctk.CTkFrame(
                    left_panel,
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
                setattr(self, "entry_fecha", widget)
            
            elif "combo" in config and config["combo"]:
                # Combobox para campos con opciones predefinidas
                widget = ctk.CTkOptionMenu(
                    left_panel,
                    values=config["values"],
                    width=config["width"],
                    height=config["height"],
                    font=entry_font,
                    fg_color=EstiloApp.COLOR_SECUNDARIO,
                    button_color=EstiloApp.COLOR_PRINCIPAL,
                    button_hover_color=EstiloApp.COLOR_SECUNDARIO,
                    text_color="black",  # Color del texto
                    text_color_disabled="gray"  # Color del texto cuando está deshabilitado
                )
                widget.grid(row=config["row"], column=config["column"]*2+1,
                         padx=20, pady=5, sticky="w")
                widget.set(config["values"][0])  # Establecer valor predeterminado
                setattr(self, f"combo_{field_name}", widget)
                
            else:
                # Entry normal para otros campos
                widget = ctk.CTkEntry(
                    left_panel,
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
        left_panel.grid_columnconfigure(3, weight=1)  # Columna después de motivo se expande

        # Frame para cantidad de días y checkbox (debajo de todos los campos)
        dias_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        dias_frame.grid(row=6, column=0, columnspan=4, sticky="w", pady=5, padx=20)

        # Checkbox y entry para días
        self.suspension_var = tk.BooleanVar(value=False)
        self.check_suspension = ctk.CTkCheckBox(
            dias_frame,
            text="Días de suspensión",
            variable=self.suspension_var,
            command=self.toggle_dias_suspension,
            font=label_font
        )
        self.check_suspension.grid(row=0, column=0, padx=(5, 10))

        self.entry_cantidad_dias = ctk.CTkEntry(
            dias_frame,
            placeholder_text="Días",
            width=100,
            height=35,
            font=entry_font
        )
        self.entry_cantidad_dias.grid(row=0, column=1, padx=5)
        self.entry_cantidad_dias.configure(state="disabled")

    def toggle_dias_suspension(self):
        """Habilitar/deshabilitar campo de días según el checkbox"""
        if self.suspension_var.get():
            self.entry_cantidad_dias.configure(state="normal")
            self.entry_cantidad_dias.focus()
        else:
            self.entry_cantidad_dias.configure(state="disabled")
            self.entry_cantidad_dias.delete(0, tk.END)

    def insertar_sancion(self):
        """Insertar nueva sanción"""
        def _insertar():
            try:
                # Validar entrada
                if not self.validar_campos():
                    return

                connection = self.db_pool.get_connection()
                if not connection:
                    raise ConnectionError("No se pudo obtener conexión a la base de datos")

                cursor = connection.cursor()
                try:
                    # Validar empleado
                    cursor.execute("SELECT 1 FROM personal WHERE legajo = %s", 
                                 (int(self.entry_legajo.get()),))
                    
                    if not cursor.fetchone():
                        raise ValueError("El legajo no existe en la base de datos")
                    
                    # Validar fecha y convertir a formato SQL
                    fecha_ui = self.entry_fecha.get()
                    fecha_sql = datetime.strptime(fecha_ui, "%d-%m-%Y").strftime("%Y-%m-%d")
                    
                    # Determinar cantidad de días
                    cantidad_dias = 0  # Valor por defecto
                    if self.suspension_var.get() and self.entry_cantidad_dias.get():
                        cantidad_dias = int(self.entry_cantidad_dias.get())

                    # Insertar sanción
                    sql = """
                    INSERT INTO sanciones 
                    (legajo, fecha, objetivo, motivo, tipo_sancion, cantidad_dias, solicita)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    datos = (
                        int(self.entry_legajo.get()),
                        fecha_sql,
                        self.entry_objetivo.get().strip(),
                        self.text_motivo.get("1.0", tk.END).strip(),
                        self.combo_tipo.get(),
                        cantidad_dias,  # Usar el valor calculado
                        self.entry_solicita.get().strip()
                    )
                    
                    cursor.execute(sql, datos)
                    connection.commit()
                    
                    # Mostrar mensaje de éxito y actualizar vista
                    self.root.after(0, self._mostrar_exito_insercion)
                    
                except Exception as e:
                    connection.rollback()
                    error_msg = str(e)
                    self.root.after(0, lambda: self.handle_database_error(error_msg, "insertar_sancion"))
                finally:
                    cursor.close()
                    self.db_pool.return_connection(connection)
                    
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.handle_database_error(error_msg, "insertar_sancion"))

        self.db_pool.executor.submit(_insertar)

    def _mostrar_exito_insercion(self):
        """Método auxiliar para mostrar mensaje de éxito y actualizar la vista"""
        def _actualizar_todo():
            connection = self.db_pool.get_connection()
            try:
                cursor = connection.cursor()
                legajo = self.entry_legajo.get()
                
                # Actualizar estadísticas
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_sanciones,
                        COALESCE(SUM(CASE 
                            WHEN LOWER(REPLACE(tipo_sancion, 'ó', 'o')) IN ('suspension', 'suspensión', 'suspencion')
                            AND fecha >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
                            THEN cantidad_dias 
                            ELSE 0 
                        END), 0) as dias_suspension_recientes,
                        COALESCE(SUM(CASE 
                            WHEN LOWER(REPLACE(tipo_sancion, 'ó', 'o')) IN ('suspension', 'suspensión', 'suspencion')
                            THEN CAST(cantidad_dias AS SIGNED)
                            ELSE 0 
                        END), 0) as total_dias_suspension,
                        MAX(fecha) as ultima_fecha
                    FROM sanciones 
                    WHERE legajo = %s
                """, (legajo,))
                
                stats = cursor.fetchone()
                total_sanciones = stats[0]
                dias_suspension = stats[1]
                total_historico = stats[2]
                ultima_fecha = stats[3]
                
                # Actualizar lista de sanciones
                cursor.execute("""
                    SELECT id, legajo, fecha, objetivo, motivo, tipo_sancion, cantidad_dias, solicita 
                    FROM sanciones 
                    WHERE legajo = %s
                    ORDER BY fecha DESC
                """, (legajo,))
                
                registros = cursor.fetchall()
                registros_convertidos = []
                for registro in registros:
                    fecha_mysql = registro[2]
                    fecha_ui = datetime.strptime(str(fecha_mysql), '%Y-%m-%d').strftime('%d-%m-%Y')
                    registro_convertido = list(registro)
                    registro_convertido[2] = fecha_ui
                    registros_convertidos.append(tuple(registro_convertido))
                
                def _actualizar_ui():
                    # Actualizar labels estadísticos
                    self.total_sanciones_label.configure(
                        text=f"📋 Historial: {total_sanciones} sanciones registradas"
                    )
                    self.suspensiones_recientes_label.configure(
                        text=f"⚠️ Suspensiones (365 días): {dias_suspension} días"
                    )
                    self.suspensiones_historicas_label.configure(
                        text=f"📊 Total histórico suspensiones: {total_historico} días"
                    )
                    if ultima_fecha:
                        fecha_formateada = datetime.strptime(str(ultima_fecha), '%Y-%m-%d').strftime('%d-%m-%Y')
                        self.ultima_sancion_label.configure(
                            text=f"⏱️ Última sanción: {fecha_formateada}"
                        )
                    
                    # Actualizar treeview
                    self._clear_treeview()
                    for registro in registros_convertidos:
                        self.tree.insert("", tk.END, values=registro)
                    
                    # Mostrar mensaje de éxito
                    self.mostrar_mensaje("Éxito", "Sanción insertada correctamente")
                    
                    # Limpiar campos del formulario manteniendo datos del vigilador
                    self.limpiar_campos_parcial()
                
                if not self.is_destroyed:
                    self.root.after(0, _actualizar_ui)
                
            except Exception as e:
                self.logger.error(f"Error al actualizar después de inserción: {str(e)}")
                if not self.is_destroyed:
                    self.root.after(0, lambda: self.mostrar_mensaje(
                        "Error", "Error al actualizar los datos"
                    ))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)
        
        # Ejecutar actualización en thread separado
        self.db_pool.executor.submit(_actualizar_todo)

    def validar_campos(self):
        """Validar todos los campos del formulario"""
        try:
            # Imprimir valores para depuración
            campos = {
                'legajo': self.entry_legajo.get(),
                'fecha': self.entry_fecha.get(),
                'objetivo': self.entry_objetivo.get(),
                'motivo': self.text_motivo.get("1.0", tk.END).strip(),
                'tipo': self.combo_tipo.get(),
                'solicita': self.entry_solicita.get(),
                'suspension_activa': self.suspension_var.get(),
                'dias': self.entry_cantidad_dias.get() if self.suspension_var.get() else '0'
            }
            
            print("Valores de campos:", campos)

            # Validar campos obligatorios básicos uno por uno
            if not self.entry_legajo.get():
                raise ValueError("El campo Legajo es obligatorio")
            if not self.entry_fecha.get():
                raise ValueError("El campo Fecha es obligatorio")
            if not self.entry_objetivo.get():
                raise ValueError("El campo Objetivo es obligatorio")
            if not self.text_motivo.get("1.0", tk.END).strip():
                raise ValueError("El campo Motivo es obligatorio")
            if not self.combo_tipo.get():
                raise ValueError("Debe seleccionar un Tipo de Sanción")
            if not self.entry_solicita.get():
                raise ValueError("El campo Solicita es obligatorio")

            # Validar días solo si es una suspensión y el checkbox está activo
            if self.combo_tipo.get() == "Suspensión" and self.suspension_var.get():
                if not self.entry_cantidad_dias.get():
                    raise ValueError("Debe especificar la cantidad de días para la suspensión")
                try:
                    dias = int(self.entry_cantidad_dias.get())
                    if dias <= 0:
                        raise ValueError("Los días de suspensión deben ser un número positivo")
                except ValueError:
                    raise ValueError("La cantidad de días debe ser un número válido")

            # Validar legajo
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

    def consultar_sanciones(self, legajo=None):
        def _consultar():
            connection = self.db_pool.get_connection()
            if not connection:
                return

            try:
                cursor = connection.cursor()
                print(f"📋 Consultando sanciones para legajo: {legajo}")
                
                # Consulta de diagnóstico
                cursor.execute("""
                    SELECT 
                        id,
                        tipo_sancion,
                        cantidad_dias,
                        fecha,
                        LOWER(REPLACE(tipo_sancion, 'ó', 'o')) as tipo_normalizado,
                        CASE 
                            WHEN LOWER(REPLACE(tipo_sancion, 'ó', 'o')) IN ('suspension', 'suspensión', 'suspencion')
                            AND fecha >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
                            THEN cantidad_dias 
                            ELSE 0 
                        END as dias_computados,
                        fecha >= DATE_SUB(CURDATE(), INTERVAL 365 DAY) as es_ultimo_anio
                    FROM sanciones 
                    WHERE legajo = %s
                    ORDER BY fecha DESC
                """, (legajo,))
                
                # Imprimir resultados de diagnóstico
                diagnostico = cursor.fetchall()
                print("\n=== DIAGNÓSTICO DE SANCIONES ===")
                for reg in diagnostico:
                    print(f"""
                    ID: {reg[0]}
                    Tipo Original: '{reg[1]}'
                    Días: {reg[2]}
                    Fecha: {reg[3]}
                    Tipo Normalizado: '{reg[4]}'
                    Días Computados: {reg[5]}
                    Es último año: {reg[6]}
                    {'='*40}
                    """)

                # Continuar con la consulta normal...
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_sanciones,
                        COALESCE(SUM(CASE 
                            WHEN LOWER(REPLACE(tipo_sancion, 'ó', 'o')) IN ('suspension', 'suspensión', 'suspencion')
                            AND fecha >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
                            THEN CAST(cantidad_dias AS SIGNED)  -- Forzar conversión a número
                            ELSE 0 
                        END), 0) as dias_suspension_recientes,
                        COALESCE(SUM(CASE 
                            WHEN LOWER(REPLACE(tipo_sancion, 'ó', 'o')) IN ('suspension', 'suspensión', 'suspencion')
                            THEN CAST(cantidad_dias AS SIGNED)
                            ELSE 0 
                        END), 0) as total_dias_suspension,
                        MAX(fecha) as ultima_fecha
                    FROM sanciones 
                    WHERE legajo = %s
                """, (legajo,))
                
                stats = cursor.fetchone()
                total_sanciones = stats[0]
                dias_suspension = stats[1]
                total_historico = stats[2]
                ultima_fecha = stats[3]
                
                # Luego obtener los registros para el treeview
                cursor.execute("""
                    SELECT id, legajo, fecha, objetivo, motivo, tipo_sancion, cantidad_dias, solicita 
                    FROM sanciones 
                    WHERE legajo = %s
                    ORDER BY fecha DESC
                """, (legajo,))
                
                registros = cursor.fetchall()
                registros_convertidos = []
                for registro in registros:
                    fecha_mysql = registro[2]
                    fecha_ui = datetime.strptime(str(fecha_mysql), '%Y-%m-%d').strftime('%d-%m-%Y')
                    registro_convertido = list(registro)
                    registro_convertido[2] = fecha_ui
                    registros_convertidos.append(tuple(registro_convertido))
                
                def _actualizar_ui():
                    # Actualizar estadísticas
                    self.total_sanciones_label.configure(
                        text=f"📋 Historial: {total_sanciones} sanciones registradas"
                    )
                    self.suspensiones_recientes_label.configure(
                        text=f"⚠️ Suspensiones (365 días): {dias_suspension} días"
                    )
                    self.suspensiones_historicas_label.configure(
                        text=f"📊 Total histórico suspensiones: {total_historico} días"
                    )
                    if ultima_fecha:
                        fecha_formateada = datetime.strptime(str(ultima_fecha), '%Y-%m-%d').strftime('%d-%m-%Y')
                        self.ultima_sancion_label.configure(
                            text=f"⏱️ Última sanción: {fecha_formateada}"
                        )
                    
                    # Actualizar treeview
                    self._clear_treeview()
                    for registro in registros_convertidos:
                        self.tree.insert("", tk.END, values=registro)
                
                if not self.is_destroyed:
                    self.root.after(0, _actualizar_ui)
                
            except mysql.connector.Error as err:
                print(f"❌ Error en consulta SQL: {err}")
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Error", f"No se pudo consultar: {err}", tipo="error"
                ))
            finally:
                cursor.close()
                self.db_pool.return_connection(connection)

        if legajo:
            self.db_pool.executor.submit(_consultar)
        else:
            self._clear_treeview()

    def _clear_treeview(self):
        """Limpiar todos los registros del treeview"""
        for row in self.tree.get_children():
            self.tree.delete(row)

    def _update_treeview(self, registros):
        """Actualizar treeview con registros"""
        print("\n📊 Actualizando Treeview:")
        print(f"Cantidad de registros a mostrar: {len(registros)}")
        
        self._clear_treeview()
        
        for registro in registros:
            valores = list(registro)
            print(f"Registro a insertar: {valores}")
            
            valores_display = valores.copy()
            if len(valores[4]) > 50:  # Truncar motivo si es muy largo
                valores_display[4] = valores[4][:47] + "..."
            
            self.tree.insert("", tk.END, values=valores_display)
        print("✅ Treeview actualizado\n")

    def limpiar_campos(self):
        """Limpiar todos los campos del formulario"""
        # Reset variables importantes
        self.sancion_seleccionada_id = None
        self._ultimo_legajo_consultado = None
        
        # Limpiar campos de entrada
        self.entry_legajo.delete(0, tk.END)
        self.entry_objetivo.delete(0, tk.END)
        self.text_motivo.delete("1.0", tk.END)
        self.entry_cantidad_dias.delete(0, tk.END)
        self.entry_solicita.delete(0, tk.END)
        self.entry_fecha.set_date(datetime.now())
        self.combo_tipo.set("Suspensión")  # Resetear al valor por defecto

        # Limpiar canvas y datos del empleado
        self.photo_canvas.delete("all")
        self.photo_canvas.create_text(
            100, 100,
            text="Sin foto",
            fill=EstiloApp.COLOR_TEXTO
        )
        
        # Resetear labels de información
        self.nombre_completo_label.configure(text="👤 Empleado: No seleccionado")
        self.total_sanciones_label.configure(text="📋 Historial: Sin sanciones registradas")
        self.ultima_sancion_label.configure(text="⏱️ Última sanción: No registrada")
        self.suspensiones_recientes_label.configure(text="⚠️ Suspensiones (365 días): 0 días")
        self.suspensiones_historicas_label.configure(text="📊 Total histórico suspensiones: 0 días")  # Agregada esta línea
        
        # Limpiar tabla
        self._clear_treeview()

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
                self.cargas_combobox.set("No especifica")
            if hasattr(self, 'estado_civil_combobox') and self.estado_civil_combobox:
                self.estado_civil_combobox.set("No especifica")
            if hasattr(self, 'estudios_combobox') and self.estudios_combobox:
                self.estudios_combobox.set("No especifica")
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

    def mostrar_mensaje(self, titulo, mensaje, tipo="info"):
        """Mostrar mensaje en ventana emergente"""
        if not self.root.winfo_exists():
            print(f"Mensaje omitido (ventana cerrada): {titulo} - {mensaje}")
            return  # Evita abrir el mensaje si la aplicación ya está cerrada

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
        dialog.geometry(f'+{x}+{y}')
        
        # Mensaje
        label = ctk.CTkLabel(
            dialog,
            text=mensaje,
            font=ctk.CTkFont(size=14),
            wraplength=250
        )
        label.pack(pady=20)
        
        # Botón Aceptar
        btn_aceptar = ctk.CTkButton(
            dialog,
            text="Aceptar",
            font=ctk.CTkFont(size=13),
            width=100,
            fg_color=EstiloApp.BOTON_LIMPIAR,
            hover_color=EstiloApp.BOTON_LIMPIAR_HOVER,
            command=dialog.destroy
        )
        btn_aceptar.pack(pady=10)
        
        # Enfocar el botón si el diálogo aún existe
        if dialog.winfo_exists():
            btn_aceptar.focus_set()
        
        # Cerrar con Escape o Enter
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Return>", lambda e: dialog.destroy())

    def mostrar_carga(self, mensaje="Cargando..."):
        """Mostrar indicador de carga"""
        if not self.root.winfo_exists():
            return  # Evita abrir la ventana si la aplicación ya fue cerrada

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

    def ocultar_carga(self):
        """Ocultar indicador de carga"""
        if hasattr(self, 'loading_dialog') and self.loading_dialog.winfo_exists():
            self.loading_dialog.destroy()
            del self.loading_dialog

    def __del__(self):
        """Destructor de clase"""
        try:
            self.cleanup()
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def _actualizar_estadisticas(self, cursor, legajo):
        """Actualizar estadísticas de sanciones"""
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sanciones,
                COALESCE(SUM(CASE 
                    WHEN LOWER(REPLACE(tipo_sancion, 'ó', 'o')) IN ('suspension', 'suspensión', 'suspencion')
                    AND fecha >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
                    THEN cantidad_dias 
                    ELSE 0 
                END), 0) as dias_suspension_recientes
            FROM sanciones
            WHERE legajo = %s
        """, (legajo,))
        
        resultado = cursor.fetchone()
        if resultado:
            total_sanciones = resultado[0]
            dias_suspension_recientes = resultado[1]
            
            if not self.is_destroyed:
                def _actualizar_labels():
                    self.total_sanciones_label.configure(
                        text=f"📋 Historial: {total_sanciones} sanciones registradas"
                    )
                    self.suspensiones_recientes_label.configure(
                        text=f"⚠️ Suspensiones (365 días): {dias_suspension_recientes} días"
                    )
                
                self.root.after(0, _actualizar_labels)

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
        canvas = tk.Canvas(container, bg="#F0F0F0")  # Usar un color gris claro seguro
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

if __name__ == "__main__":
    app = None
    try:
        app = AplicacionSanciones()
        app.run()
    except Exception as e:
        # Configurar logging básico en caso de error antes de inicialización
        logging.basicConfig(
            filename="logs/errores_críticos_sanciones.log",
            level=logging.CRITICAL,
            format='%(asctime)s - [%(levelname)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.critical(f"Error crítico al iniciar la aplicación: {str(e)}\n{traceback.format_exc()}")
        print(f"Error al iniciar la aandicación: {e}")
        app and hasattr(app.cleanup())