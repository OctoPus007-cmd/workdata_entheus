import customtkinter as ctk
from datetime import datetime
from PIL import Image
import time
from tkinter import messagebox
from concurrent.futures import ThreadPoolExecutor
from modulos.modulo_felicitaciones import AplicacionFelicitaciones
from functools import lru_cache
import queue
from modulos.modulo_prestamos import AplicacionPrestamos as AplicacionPrestamos
from modulos.modulo_conceptos import AplicacionConceptos
from modulos.modulo_personal import PersonalManagementApp
from modulos.modulo_sanciones import AplicacionSanciones
from modulos.modulo_certificados_medicos import AplicacionCertificadosMedicos 
from modulos.modulo_licencias import AplicacionLicencias
from modulos.modulo_art import AplicacionART
import os
import sys
from pathlib import Path
from utils.thread_manager import ThreadManager
from utils.interface_manager import EstiloApp
import tkinter as tk
from tkinter import ttk
import traceback
from modulos.modulo_antecedentes import crear_modulo as crear_modulo_antecedentes

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = BASE_DIR / 'resources'
ICONS_DIR = RESOURCES_DIR / 'icons'

# Forzar tema claro por defecto
ctk.set_appearance_mode("light")

class ModuleCache:
    """Clase para manejar el caché de módulos con capacidad extendida"""
    def __init__(self):
        self.modules = {}
        self.last_accessed = {}
        self.max_cache_size = 10  # Aumentar tamaño máximo de caché
      # Aumentar tamaño máximo de caché
        self.preload_data = {}  # Nuevo: Almacenar datos precargados
        self.cache_stats = {
            'hits': 0,
            'misses': 0
        }

    def get(self, module_name):
        """Obtener módulo del caché con estadísticas"""
        if module_name in self.modules:
            self.cache_stats['hits'] += 1
            self.last_accessed[module_name] = time.time()
            # Reducir logging para mejorar rendimiento
            return self.modules[module_name]
        self.cache_stats['misses'] += 1
        return None

    def set(self, module_name, instance, preload_data=None):
        """Guardar módulo en caché con datos precargados"""
        # Limpiar caché si excede el tamaño máximo
        if len(self.modules) >= self.max_cache_size:
            oldest_module = min(self.last_accessed.items(), key=lambda x: x[1])[0]
            self.clear(oldest_module)
        
        self.modules[module_name] = instance
        self.last_accessed[module_name] = time.time()
        if preload_data:
            self.preload_data[module_name] = preload_data

    def clear(self, module_name=None):
        """Limpiar caché con manejo de recursos"""
        if module_name:
            if module_name in self.modules:
                # Limpiar recursos específicos del módulo
                module = self.modules[module_name]
                if hasattr(module, 'cleanup'):
                    module.cleanup()
                self.modules.pop(module_name)
                self.last_accessed.pop(module_name)
                self.preload_data.pop(module_name, None)
        else:
            # Limpiar todos los módulos
            for name, module in self.modules.items():
                if hasattr(module, 'cleanup'):
                    module.cleanup()
            self.modules.clear()
            self.last_accessed.clear()
            self.preload_data.clear()

class ModuleLoader:
    """Gestor de carga de módulos con precarga y caché"""
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.preload_queue = queue.Queue()
        self.cache = {}
        self.loading_status = {}
        self._initialize_preload()

    def _initialize_preload(self):
        """Iniciar precarga de módulos pesados en segundo plano"""
        def preload_modules():
            from modulos.modulo_personal import PersonalManagementApp
            from modulos.modulo_felicitaciones import AplicacionFelicitaciones
            from modulos.modulo_sanciones import AplicacionSanciones
            from modulos.modulo_conceptos import AplicacionConceptos
            from modulos.modulo_prestamos import AplicacionPrestamos
            from modulos.modulo_certificados_medicos import AplicacionCertificadosMedicos
            from modulos.modulo_licencias import AplicacionLicencias
            
            modules = {
                "Módulo Personal": PersonalManagementApp,
                "Módulo Felicitaciones": AplicacionFelicitaciones,
                "Módulo Sanciones": AplicacionSanciones,
                "Módulo Conceptos": AplicacionConceptos,
                "Módulo Préstamos": AplicacionPrestamos,
                "Módulo Certificados Médicos": AplicacionCertificadosMedicos,
                "Módulo Licencias": AplicacionLicencias
            }
            
            for name, module_class in modules.items():
                self.loading_status[name] = "preloading"
                try:
                    # Importar pero no instanciar
                    self.cache[name] = {
                        'class': module_class,
                        'status': 'ready',
                        'timestamp': time.time()
                    }
                    print(f"✓ Módulo {name} precargado")
                except Exception as e:
                    print(f"❌ Error precargando {name}: {e}")
                    self.loading_status[name] = "error"

        self.executor.submit(preload_modules)

    @lru_cache(maxsize=5)
    def get_module_instance(self, module_name, parent_frame):
        """Obtener instancia de módulo con caché"""
        try:
            if module_name not in self.cache:
                raise ValueError(f"Módulo {module_name} no encontrado")

            module_info = self.cache[module_name]
            if module_info['status'] == 'ready':
                try:
                    # Caso especial para AplicacionPrestamos
                    if module_name == "Módulo Préstamos":
                        instance = module_info['class'](parent_frame=parent_frame, root=self._get_root(parent_frame))
                    else:
                        instance = module_info['class'](parent_frame)
                    return instance
                except Exception as e:
                    raise RuntimeError(f"Error instanciando {module_name}: {e}")
            else:
                raise RuntimeError(f"Módulo {module_name} no está listo")
        except (ValueError, RuntimeError) as e:
            print(f"⚠️ Error al cargar el módulo {module_name}: {e}")
            # Intentar recargar el módulo desde cero
            return self.reload_module(module_name, parent_frame)

    def reload_module(self, module_name, parent_frame):
        """Recargar módulo desde cero si no se puede restaurar desde la caché"""
        print(f"🔄 Intentando recargar el módulo {module_name} desde cero...")
        try:
            # Aquí deberías implementar la lógica para recargar el módulo
            # Por ejemplo, podrías volver a importar el módulo y crear una nueva instancia
            if module_name == "Módulo Préstamos":
                from modulos.modulo_prestamos import AplicacionPrestamos
                instance = AplicacionPrestamos(parent_frame=parent_frame, root=self._get_root(parent_frame))
            elif module_name == "Módulo Personal":
                from modulos.modulo_personal import PersonalManagementApp
                instance = PersonalManagementApp(parent_frame)
            elif module_name == "Módulo Felicitaciones":
                from modulos.modulo_felicitaciones import AplicacionFelicitaciones
                instance = AplicacionFelicitaciones(parent_frame)
            elif module_name == "Módulo Sanciones":
                from modulos.modulo_sanciones import AplicacionSanciones
                instance = AplicacionSanciones(parent_frame=self.module_frame)
            elif module_name == "Módulo Conceptos":
                from modulos.modulo_conceptos import AplicacionConceptos
                instance = AplicacionConceptos(parent_frame=self.module_frame)
            elif module_name == "Módulo Certificados Médicos":
                from modulos.modulo_certificados_medicos import AplicacionCertificadosMedicos
                instance = AplicacionCertificadosMedicos(parent_frame=self.module_frame)
            elif module_name == "Módulo Licencias":
                from modulos.modulo_licencias import AplicacionLicencias
                instance = AplicacionLicencias(parent_frame=self.module_frame)
            elif module_name == "Módulo ART":
                from modulos.modulo_art import AplicacionART
                instance = AplicacionART(parent_frame=self.module_frame)
            elif module_name == "Antecedentes Laborales":
                # Cambiar esto para usar la función crear_modulo_antecedentes
                print("Creando instancia de Módulo Antecedentes")
                instance = crear_modulo_antecedentes(self.module_frame)
            else:
                raise ValueError(f"Módulo {module_name} no implementado para recarga")

            # Actualizar la caché con la nueva instancia
            self.cache[module_name] = {
                'class': type(instance),
                'status': 'ready',
                'timestamp': time.time()
            }
            return instance
        except Exception as e:
            print(f"❌ Error al recargar el módulo {module_name}: {e}")
            raise RuntimeError(f"No se pudo recargar el módulo {module_name}")

    def _get_root(self, widget):
        """Obtener la ventana raíz desde cualquier widget"""
        current = widget
        while current.master is not None:
            current = current.master
        return current

    def load_module_async(self, module_name, parent_frame, callback):
        """Cargar módulo de forma asíncrona"""
        def _load():
            try:
                instance = self.get_module_instance(module_name, parent_frame)
                return instance
            except Exception as e:
                raise RuntimeError(f"Error cargando {module_name}: {e}")

        future = self.executor.submit(_load)
        future.add_done_callback(lambda f: callback(f.result()))

class MainMenu(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Menú Principal - APP RRHH")
        
        # Configurar tamaño inicial relativo a la pantalla
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        window_width = int(screen_width * 0.8)
        window_height = int(screen_height * 0.8)
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(1024, 768)  # Tamaño mínimo razonable

        # Estado de la aplicación
        self.is_destroyed = False
        self.is_loading = False
        
        # Inicializar managers
        self.thread_manager = ThreadManager(max_workers=4)
        self.module_cache = ModuleCache()
        
        # Definir colores por defecto
        self.window_bg_color = "#E3F2FD"  # Azul muy claro
        self.frame_bg_color = "#BBDEFB"   # Azul claro
        self.button_bg_color = "#90CAF9"  # Azul medio
        self.button_hover_color = "#64B5F6"  # Azul hover
        self.text_color = "#000000"       # Negro para texto
        self.progress_color = "#1E88E5"   # Azul oscuro
        self.navbar_bg_color = "#E3F2FD"  # Azul muy claro para la navbar

        # Configurar colores para navbar
        self.navbar_button_color = "#90CAF9"  # Azul medio
        self.navbar_button_hover = "#64B5F6"  # Azul hover
        self.navbar_text_color = "#000000"    # Negro

        # Definir color para el texto del reloj
        self.clock_text_color = "#1A237E"  # Azul marino oscuro elegante
        # o alternativamente:
        # self.clock_text_color = "#263238"  # Azul grisáceo oscuro
        # self.clock_text_color = "#37474F"  # Azul pizarra

        # Crear la barra de navegación superior con nuevo color
        self.create_navbar()

        # Crear el frame del menú lateral
        self.menu_frame = ctk.CTkFrame(self, width=220, fg_color=self.frame_bg_color, corner_radius=0)
        self.menu_frame.pack(side="left", fill="y")

        # Crear el título del menú
        self.menu_title = ctk.CTkLabel(self.menu_frame, text="Menú Principal", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.text_color)
        self.menu_title.pack(pady=10)

        # Crear botones del menú con iconos
        self.create_menu_buttons()

        # Frame principal para cargar los módulos
        self.main_frame = ctk.CTkFrame(self, fg_color=self.window_bg_color)
        self.main_frame.pack(side="right", fill="both", expand=True)

        # Crear el frame para ejecutar los demás módulos
        self.module_frame = ctk.CTkFrame(self.main_frame, fg_color=self.window_bg_color)
        self.module_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Añadir atributo para almacenar la instancia de PersonalManagementApp
        self.current_module = None
        self.loading_progress = None

        # Inicializar caché de módulos
        self.module_cache = ModuleCache()
        
        # Añadir variable para controlar el estado de carga
        self.is_loading = False

        # Crear la pantalla de bienvenida después del frame principal
        self._create_welcome_screen()

        # Añadir atributo para almacenar la instancia de AplicacionFelicitaciones
        self.modulo_felicitaciones = None

        # Inicializar el loader de módulos
        self.module_loader = ModuleLoader()
        
        # Aumentar caché
        self.module_cache.max_cache_size = 10
        
        # Estado de carga
        self.loading_states = {}

        # Crear el frame del reloj con diseño moderno
        self.clock_frame = ctk.CTkFrame(
            self.menu_frame,
            fg_color=self.button_bg_color,
            corner_radius=15,
            border_width=2,
            border_color=self.button_hover_color
        )
        self.clock_frame.pack(side="bottom", pady=20, padx=10, fill="x")

        # Frame para la fecha
        self.date_frame = ctk.CTkFrame(
            self.clock_frame,
            fg_color="transparent"
        )
        self.date_frame.pack(pady=(5, 0))

        # Labels para el reloj digital con nuevo color
        self.time_label = ctk.CTkLabel(
            self.clock_frame,
            text="00:00:00",
            font=ctk.CTkFont(family="Roboto", size=24, weight="bold"),
            text_color=self.clock_text_color
        )
        self.time_label.pack(pady=(0, 2))

        self.date_label = ctk.CTkLabel(
            self.date_frame,
            text="",
            font=ctk.CTkFont(family="Roboto", size=12),
            text_color=self.clock_text_color
        )
        self.date_label.pack()

        self.weekday_label = ctk.CTkLabel(
            self.date_frame,
            text="",
            font=ctk.CTkFont(family="Roboto", size=14, weight="bold"),
            text_color=self.clock_text_color
        )
        self.weekday_label.pack()

        # Iniciar actualización del reloj
        self.update_clock()

    def create_navbar(self):
        """Crear barra de navegación superior"""
        navbar = ctk.CTkFrame(self, fg_color=self.navbar_bg_color)
        navbar.pack(fill="x", pady=0)

        # Botón de configuración
        settings_icon = ctk.CTkImage(Image.open(ICONS_DIR / "settings.png"), size=(20, 20))
        settings_button = ctk.CTkButton(
            navbar, 
            image=settings_icon, 
            text="",
            fg_color=self.navbar_button_color,
            hover_color=self.navbar_button_hover,
            text_color=self.navbar_text_color,
            command=self.open_settings
        )
        settings_button.pack(side="right", padx=10, pady=5)

        # Botón de cerrar sesión
        logout_button = ctk.CTkButton(
            navbar,
            text="Cerrar Sesión",
            fg_color=self.navbar_button_color,
            hover_color=self.navbar_button_hover,
            text_color=self.navbar_text_color,
            command=self.logout
        )
        logout_button.pack(side="right", padx=10, pady=5)

    def create_menu_buttons(self):
        buttons = [
            ("Módulo Personal", ICONS_DIR / "personal.png", self.load_module),
            ("Módulo Felicitaciones", ICONS_DIR / "felicitaciones.png", self.load_module),
            ("Módulo Sanciones", ICONS_DIR / "sanciones.png", self.load_module),
            ("Módulo Conceptos", ICONS_DIR / "conceptos.png", self.load_module),
            ("Módulo Préstamos", ICONS_DIR / "prestamos.png", self.load_module),
            ("Módulo Certificados Médicos", ICONS_DIR / "certificados.png", self.load_module),
            ("Módulo Licencias", ICONS_DIR / "licencias.png", self.load_module),
            ("Módulo ART", ICONS_DIR / "art.png", self.load_module)
        ]

        # Crear los botones normales
        for button_text, icon_path, command in buttons:
            icon = ctk.CTkImage(Image.open(icon_path), size=(30, 30))
            button = ctk.CTkButton(
                self.menu_frame,
                text=button_text,
                image=icon,
                compound="left",
                command=lambda bt=button_text: command(bt),
                fg_color=self.button_bg_color,
                hover_color=self.button_hover_color,
                text_color=self.text_color,
                font=ctk.CTkFont(size=16),
                corner_radius=10,
                height=50,
                anchor="w"
            )
            button.pack(pady=10, padx=20, fill="x")
        
        # Crear el botón de Antecedentes por separado
        icon = ctk.CTkImage(Image.open(ICONS_DIR / "antecedentes.png"), size=(30, 30))
        button = ctk.CTkButton(
            self.menu_frame,
            text="Antecedentes Laborales",
            image=icon,
            compound="left",
            command=self.abrir_modulo_antecedentes,  # Sin lambda
            fg_color=self.button_bg_color,
            hover_color=self.button_hover_color,
            text_color=self.text_color,
            font=ctk.CTkFont(size=16),
            corner_radius=10,
            height=50,
            anchor="w"
        )
        button.pack(pady=10, padx=20, fill="x")

    def show_loading_screen(self, module_name):
        """Mostrar pantalla de carga mejorada con animación y mensajes dinámicos"""
        # Limpiar el frame de módulos de forma segura
        if hasattr(self, 'module_frame'):
            for widget in self.module_frame.winfo_children():
                widget.destroy()

        # Frame de carga con efecto de elevación y sombra
        self.loading_frame = ctk.CTkFrame(
            self.module_frame, 
            fg_color=self.window_bg_color,
            corner_radius=20,
            border_width=2,
            border_color=self.progress_color
        )
        self.loading_frame.place(relx=0.5, rely=0.5, anchor="center")

        # Logo o ícono de carga (si existe)
        try:
            logo = ctk.CTkImage(
                light_image=Image.open(ICONS_DIR / "loading.png"),
                dark_image=Image.open(ICONS_DIR / "loading.png"),
                size=(80, 80)  # Aumentar tamaño del logo
            )
            logo_label = ctk.CTkLabel(
                self.loading_frame,
                text="",
                image=logo
            )
            logo_label.pack(pady=(20, 0))
        except Exception as e:
            print(f"Error cargando logo: {e}")
            pass

        # Título del módulo con efecto de sombra
        title_frame = ctk.CTkFrame(self.loading_frame, fg_color="transparent")
        title_frame.pack(pady=(20, 5))
        
        ctk.CTkLabel(
            title_frame,
            text=f"Cargando {module_name}",
            font=("Roboto", 28, "bold"),  # Aumentar tamaño de fuente
            text_color=self.text_color
        ).pack()

        # Mensajes de carga dinámicos
        self.loading_messages = [
            "Iniciando...",
            "Preparando interfaz...",
            "Cargando datos...",
            "Configurando componentes...",
            "Optimizando rendimiento...",
            "Casi listo...",
            "Finalizando..."
        ]
        
        self.current_message_index = 0
        
        # Mensaje de carga con estilo mejorado
        self.loading_message = ctk.CTkLabel(
            self.loading_frame,
            text=self.loading_messages[0],
            font=("Roboto", 16),
            text_color=self.text_color
        )
        self.loading_message.pack(pady=(5, 20))

        # Barra de progreso mejorada con efecto pulsante
        self.loading_progress = ctk.CTkProgressBar(
            self.loading_frame,
            orientation="horizontal",
            mode="indeterminate",
            width=350,  # Aumentar ancho
            progress_color=self.progress_color,
            height=12  # Aumentar altura
        )
        self.loading_progress.pack(padx=40, pady=(0, 30))
        self.loading_progress.start()
        
        # Iniciar la animación de mensajes
        self._animate_loading_messages()
        
    def _animate_loading_messages(self):
        """Animar los mensajes de carga para dar sensación de actividad"""
        if hasattr(self, 'loading_message') and self.loading_message.winfo_exists():
            # Cambiar el mensaje cada cierto tiempo
            self.current_message_index = (self.current_message_index + 1) % len(self.loading_messages)
            self.loading_message.configure(text=self.loading_messages[self.current_message_index])
            
            # Continuar la animación mientras se muestra la pantalla de carga
            if self.is_loading and hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists():
                self.after(800, self._animate_loading_messages)  # Cambiar mensaje cada 800ms

    def hide_loading_screen(self):
        """Ocultar pantalla de carga con efecto de desvanecimiento"""
        try:
            # Detener y limpiar la barra de progreso
            if hasattr(self, 'loading_progress') and self.loading_progress is not None:
                try:
                    self.loading_progress.stop()
                except Exception as e:
                    print(f"Error al detener barra de progreso: {e}")
            
            # Crear efecto de desvanecimiento
            if hasattr(self, 'loading_frame') and self.loading_frame is not None:
                try:
                    self._fade_out_loading_screen()
                except Exception as e:
                    print(f"Error al iniciar desvanecimiento: {e}")
                    # Si falla el desvanecimiento, intentar destruir directamente
                    try:
                        self.loading_frame.destroy()
                    except:
                        pass
                    self.loading_frame = None
            
            # Limpiar referencias explícitamente
            if not hasattr(self, 'loading_frame') or self.loading_frame is None:
                self.loading_progress = None
                self.loading_message = None
                
        except Exception as e:
            print(f"Error al ocultar pantalla de carga: {e}")
            # Asegurar que las referencias se limpien incluso si hay error
            self.loading_progress = None
            self.loading_frame = None
            self.loading_message = None
    
    def _fade_out_loading_screen(self, alpha=1.0):
        """Crear efecto de desvanecimiento para la pantalla de carga"""
        # Verificación inicial de seguridad
        if not hasattr(self, 'loading_frame') or self.loading_frame is None:
            return
        
        try:
            # Verificar si el frame todavía existe de manera segura
            frame_exists = False
            try:
                frame_exists = self.loading_frame.winfo_exists()
            except:
                frame_exists = False
            
            if alpha <= 0 or not frame_exists:
                # Cuando termina la animación o si el frame ya no existe
                try:
                    if frame_exists:
                        self.loading_frame.destroy()
                except:
                    pass
                
                # Limpiar todas las referencias
                self.loading_frame = None
                self.loading_progress = None
                self.loading_message = None
                return
            
            # Reducir la opacidad gradualmente
            new_alpha = alpha - 0.1
            
            # Actualizar mensaje para indicar que está cerrando
            if hasattr(self, 'loading_message') and self.loading_message is not None:
                try:
                    message_exists = False
                    try:
                        message_exists = self.loading_message.winfo_exists()
                    except:
                        message_exists = False
                    
                    if message_exists:
                        self.loading_message.configure(text="Completado ✓")
                except Exception as e:
                    print(f"Error al actualizar mensaje: {e}")
            
            # Continuar la animación
            self.after(50, lambda: self._fade_out_loading_screen(new_alpha))
        except Exception as e:
            print(f"Error en animación de desvanecimiento: {e}")
            # En caso de error, destruir directamente
            try:
                if hasattr(self, 'loading_frame') and self.loading_frame is not None:
                    try:
                        if self.loading_frame.winfo_exists():
                            self.loading_frame.destroy()
                    except:
                        pass
            except:
                pass
            
            # Limpiar todas las referencias
            self.loading_frame = None
            self.loading_progress = None
            self.loading_message = None

    def load_module(self, module_name):
        """Cargar módulo con manejo mejorado de caché y logging"""
        if self.is_loading:
            print(f"⚠️ Ya hay una carga en proceso para: {module_name}")
            return
        
        self.is_loading = True
        print(f"\n🔄 === INICIANDO CARGA DE MÓDULO: {module_name} ===")
        
        # Limpiar frame actual
        for widget in self.module_frame.winfo_children():
            widget.destroy()
        print("✓ Frame limpiado")
        
        self.show_loading_screen(module_name)
        
        # Tiempo mínimo de carga para efecto visual (3 segundos)
        self.loading_start_time = time.time()
        self.loading_min_time = 3.0  # segundos
        
        def create_module():
            try:
                print(f"\n🏗️ Creando nueva instancia de {module_name}")
                
                # Crear nueva instancia del módulo
                if module_name == "Módulo Préstamos":
                    # Configurar el grid del module_frame
                    self.module_frame.grid_rowconfigure(0, weight=1)
                    self.module_frame.grid_columnconfigure(0, weight=1)
                    
                    # Crear un frame contenedor con grid
                    container_frame = ctk.CTkFrame(self.module_frame, fg_color=self.window_bg_color)
                    container_frame.grid(row=0, column=0, sticky="nsew")
                    
                    # Configurar el grid del container_frame
                    container_frame.grid_rowconfigure(0, weight=1)
                    container_frame.grid_columnconfigure(0, weight=1)
                    
                    print("Configurando frame para préstamos...")
                    module_instance = AplicacionPrestamos(parent_frame=container_frame, root=self)
                    print("✓ Módulo de préstamos creado")
                    
                    # Forzar actualización de la geometría
                    container_frame.update_idletasks()
                    self.module_frame.update_idletasks()
                
                elif module_name == "Módulo Personal":
                    print("Configurando frame para personal...")
                    module_instance = PersonalManagementApp(parent_frame=self.module_frame)
                    print("✓ Módulo de personal creado")
                    
                    # Forzar actualización de la geometría
                    self.module_frame.update_idletasks()
                
                elif module_name == "Módulo Felicitaciones":
                    module_instance = AplicacionFelicitaciones(parent_frame=self.module_frame)
                elif module_name == "Módulo Sanciones":
                    module_instance = AplicacionSanciones(parent_frame=self.module_frame)
                elif module_name == "Módulo Conceptos":
                    print("Creando instancia de AplicacionConceptos")  # Debug
                    module_instance = AplicacionConceptos(parent_frame=self.module_frame)
                elif module_name == "Módulo Certificados Médicos":
                    print("Creando instancia de AplicacionCertificadosMedicos")
                    module_instance = AplicacionCertificadosMedicos(parent_frame=self.module_frame)
                elif module_name == "Módulo Licencias":
                    print("Configurando frame para licencias...")
                    
                    # Configurar el grid del module_frame
                    self.module_frame.grid_rowconfigure(0, weight=1)
                    self.module_frame.grid_columnconfigure(0, weight=1)
                    
                    # Crear un frame contenedor con grid
                    container_frame = ctk.CTkFrame(self.module_frame, fg_color=self.window_bg_color)
                    container_frame.grid(row=0, column=0, sticky="nsew")
                    
                    # Configurar el grid del container_frame
                    container_frame.grid_rowconfigure(0, weight=1)
                    container_frame.grid_columnconfigure(0, weight=1)
                    
                    module_instance = AplicacionLicencias(parent_frame=container_frame)
                    print("✓ Módulo de licencias creado")
                    
                    # Forzar actualización de la geometría
                    container_frame.update_idletasks()
                    self.module_frame.update_idletasks()
                elif module_name == "Módulo ART":
                    print("Configurando frame para ART...")
                    
                    # Configurar el grid del module_frame
                    self.module_frame.grid_rowconfigure(0, weight=1)
                    self.module_frame.grid_columnconfigure(0, weight=1)
                    
                    # Crear un frame contenedor con grid
                    container_frame = ctk.CTkFrame(self.module_frame, fg_color=self.window_bg_color)
                    container_frame.grid(row=0, column=0, sticky="nsew")
                    
                    # Configurar el grid del container_frame
                    container_frame.grid_rowconfigure(0, weight=1)
                    container_frame.grid_columnconfigure(0, weight=1)
                    
                    module_instance = AplicacionART(parent_frame=container_frame)
                    print("✓ Módulo de ART creado")
                    
                    # Forzar actualización de la geometría
                    container_frame.update_idletasks()
                    self.module_frame.update_idletasks()
                elif module_name == "Antecedentes Laborales":
                    print("Creando instancia de Módulo Antecedentes")
                    module_instance = crear_modulo_antecedentes(self.module_frame)
                else:
                    raise ValueError(f"Módulo no reconocido: {module_name}")

                print(f"✓ Módulo {module_name} creado exitosamente")
                
                if not self.is_destroyed:
                    print("Finalizando carga del módulo...")
                    # Calcular tiempo transcurrido y esperar si es necesario
                    elapsed_time = time.time() - self.loading_start_time
                    remaining_time = max(0, self.loading_min_time - elapsed_time)
                    
                    if remaining_time > 0:
                        print(f"Esperando {remaining_time:.2f} segundos adicionales para efecto visual...")
                        self.update_loading_status(f"✨ Finalizando... ({int(remaining_time)}s)")
                        self.after(int(remaining_time * 1000), lambda: self._finish_module_load(module_instance, module_name))
                    else:
                        self.after(0, lambda: self._finish_module_load(module_instance, module_name))
                    
            except Exception as e:
                print(f"❌ Error al crear módulo {module_name}: {str(e)}")
                if not self.is_destroyed:
                    self.after(0, lambda: self.show_error(f"Error creando módulo: {str(e)}"))
                    self.after(0, self.hide_loading_screen)
                self.is_loading = False

        # Verificar caché primero
        cached_module = self.module_cache.get(module_name)
        if cached_module:
            print(f"📦 Restaurando {module_name} desde caché")
            self.update_loading_status("📦 Restaurando desde caché...")
            # Incluso para módulos en caché, esperar el tiempo mínimo
            self.after(int(self.loading_min_time * 1000), lambda: self._restore_cached_module(cached_module, module_name))
            return

        # Crear módulo en thread separado
        print(f"🚀 Creando nuevo {module_name}")
        self.update_loading_status("🚀 Iniciando módulo...")
        self.thread_manager.submit_task(f"load_{module_name}", create_module)

    def _finish_module_load(self, module_instance, module_name):
        """Finalizar la carga del módulo con efectos visuales mejorados"""
        print(f"\n✨ === FINALIZANDO CARGA: {module_name} ===")
        try:
            print("1. Guardando en caché...")
            self.module_cache.set(module_name, module_instance)
            
            print("2. Actualizando módulo actual...")
            self.current_module = module_instance
            
            print("3. Verificando estado del frame...")
            if hasattr(module_instance, 'diagnostico_gui'):
                module_instance.diagnostico_gui()
            
            print("4. Preparando transición visual...")
            # Mostrar mensaje de éxito en la pantalla de carga
            if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                self.loading_message.configure(
                    text="¡Carga completada con éxito!",
                    font=("Roboto", 16, "bold"),
                    text_color="#4CAF50"  # Color verde para éxito
                )
            
            # Detener la barra de progreso y mostrarla completa
            if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                self.loading_progress.stop()
                self.loading_progress.configure(mode="determinate")
                self.loading_progress.set(1.0)  # Progreso completo
            
            # Esperar un momento para mostrar el mensaje de éxito
            self.after(800, self.hide_loading_screen)
            
            print(f"✓ Carga de {module_name} completada")
            self.is_loading = False
            
        except Exception as e:
            print(f"❌ Error finalizando carga: {str(e)}")
            self.show_error(f"Error finalizando carga: {str(e)}")
            self.is_loading = False
            self.hide_loading_screen()

    def _restore_cached_module(self, cached_module, module_name):
        """Restaurar módulo desde caché con efectos visuales mejorados"""
        print(f"\n📦 === RESTAURANDO DESDE CACHÉ: {module_name} ===")
        try:
            # Verificar que el módulo en caché no sea None
            if cached_module is None:
                print(f"❌ Error: El módulo en caché es None para {module_name}")
                raise Exception(f"Módulo en caché inválido (None) para {module_name}")
                
            # Caso especial para el Módulo Personal
            if module_name == "Módulo Personal":
                self._restore_personal_module(cached_module)
                return
            # Caso especial para el Módulo ART
            elif module_name == "Módulo ART":
                self._restore_art_module(cached_module)
                return
            # Caso especial para Antecedentes Laborales
            elif module_name == "Antecedentes Laborales":
                self._restore_antecedentes_module(cached_module)
                return
            
            print("1. Verificando estado del módulo...")
            if not hasattr(cached_module, 'show_in_frame'):
                raise Exception(f"Módulo en caché inválido: no tiene método 'show_in_frame' para {module_name}")
            
            print("2. Preparando frame...")
            # Limpiar eventos y bindings primero
            for widget in self.module_frame.winfo_children():
                try:
                    # Desconectar eventos de mousewheel
                    widget.unbind_all('<MouseWheel>')
                    widget.unbind_all('<Shift-MouseWheel>')
                    # Destruir el widget
                    widget.destroy()
                except Exception as e:
                    print(f"Error limpiando widget: {e}")
            
            self.module_frame.update_idletasks()
            
            print("3. Restaurando módulo...")
            cached_module.show_in_frame(self.module_frame)
            
            print("4. Actualizando referencias...")
            self.current_module = cached_module
            
            print("5. Preparando transición visual...")
            # Mostrar mensaje de éxito en la pantalla de carga
            if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                self.loading_message.configure(
                    text="¡Restauración completada!",
                    font=("Roboto", 16, "bold"),
                    text_color="#2196F3"  # Color azul para restauración
                )
            
            # Detener la barra de progreso y mostrarla completa
            if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                self.loading_progress.stop()
                self.loading_progress.configure(mode="determinate")
                self.loading_progress.set(1.0)  # Progreso completo
            
            # Esperar un momento para mostrar el mensaje de éxito
            self.after(800, self.hide_loading_screen)
            
            print("✓ Restauración completada")
            self.is_loading = False
            
        except Exception as e:
            print(f"❌ Error restaurando módulo: {str(e)}")
            traceback.print_exc()  # Imprimir el traceback completo para depuración
            self.show_error(f"Error en restauración: {str(e)}")
            self.module_cache.clear(module_name)
            self.is_loading = False
            # Crear un nuevo módulo como fallback
            self.after(1000, lambda: self._create_fallback_module(module_name))
    
    def _create_fallback_module(self, module_name):
        """Crear un nuevo módulo como fallback cuando falla la restauración desde caché"""
        print(f"🔄 Creando nuevo módulo {module_name} como fallback...")
        try:
            if module_name == "Módulo Personal":
                self._create_personal_module()
            elif module_name == "Módulo Felicitaciones":
                self._create_felicitaciones_module()
            elif module_name == "Módulo Sanciones":
                self._create_sanciones_module()
            elif module_name == "Módulo Conceptos":
                self._create_conceptos_module()
            elif module_name == "Módulo Préstamos":
                self._create_prestamos_module()
            elif module_name == "Módulo Certificados Médicos":
                self._create_certificados_medicos_module()
            elif module_name == "Módulo Licencias":
                self._create_licencias_module()
            elif module_name == "Módulo ART":
                self._create_art_module()
            elif module_name == "Antecedentes Laborales":
                self._create_antecedentes_module()
            else:
                print(f"⚠️ No hay método de fallback para {module_name}")
                self.is_loading = False
        except Exception as e:
            print(f"❌ Error en fallback para {module_name}: {str(e)}")
            self.is_loading = False

    def _restore_personal_module(self, cached_module, module_name="Módulo Personal"):
        """Restaurar módulo personal desde caché con manejo mejorado"""
        print(f"\n📦 === RESTAURANDO MÓDULO PERSONAL ===")
        try:
            # Limpiar frame actual de forma segura
            for widget in self.module_frame.winfo_children():
                widget.destroy()
            
            # Crear nuevo buffer frame para evitar problemas de geometría
            buffer_frame = ctk.CTkFrame(self.module_frame, fg_color=self.window_bg_color)
            buffer_frame.pack(fill="both", expand=True)
            
            # Actualizar estado de carga
            self.update_loading_status("🔄 Restaurando interfaz...")
            
            def finish_restore():
                try:
                    # Restaurar módulo con referencias limpias
                    cached_module.parent = buffer_frame
                    
                    # Verificar y restablecer conexiones
                    if hasattr(cached_module, '_reset_connections'):
                        cached_module._reset_connections()
                    
                    # Recrear la interfaz completamente
                    if hasattr(cached_module, '_setup_main_frame'):
                        cached_module._setup_main_frame()
                    
                    if hasattr(cached_module, '_create_interface'):
                        cached_module._create_interface()
                        
                    # Verificar el estado de la interfaz después de restaurar
                    if hasattr(cached_module, 'refresh_data'):
                        cached_module.refresh_data()
                    
                    self.current_module = cached_module
                    self.is_loading = False
                    self.hide_loading_screen()
                    print("✅ Módulo personal restaurado correctamente")
                    
                except Exception as e:
                    print(f"❌ Error en restauración final: {str(e)}")
                    traceback.print_exc()
                    self.show_error(f"Error restaurando módulo: {str(e)}")
                    self.module_cache.clear(module_name)
                    self.is_loading = False
                    self._create_personal_module()  # Crear nuevo como fallback
            
            # Usar after para dar tiempo a la actualización de la UI
            self.after(300, finish_restore)
            
        except Exception as e:
            print(f"❌ Error inicial al restaurar módulo personal: {str(e)}")
            traceback.print_exc()
            self.show_error(f"Error en restauración: {str(e)}")
            self.is_loading = False
            # Como fallback, intentar crear un nuevo módulo
            self.after(200, self._create_personal_module)

    def _create_personal_module(self):
        """Crear nuevo módulo personal"""
        from modulos.modulo_personal import PersonalManagementApp
        
        self.update_loading_status("🚀 Creando nuevo módulo personal...")
        
        try:
            # Limpiar frame actual
            for widget in self.module_frame.winfo_children():
                widget.destroy()
            
            # Crear módulo
            new_module = PersonalManagementApp(parent_frame=self.module_frame)
            
            # Guardar en caché y actualizar referencias
            self.module_cache.set("Módulo Personal", new_module)
            self.current_module = new_module
            
            # Finalizar carga
            self.is_loading = False
            self.hide_loading_screen()
            
        except Exception as e:
            print(f"❌ Error creando módulo personal: {str(e)}")
            traceback.print_exc()
            self.show_error(f"Error creando módulo: {str(e)}")
            self.is_loading = False

    def _restore_felicitaciones_module(self, cached_module):
        """Restaurar módulo de felicitaciones desde caché"""
        try:
            # Limpiar frame actual
            for widget in self.module_frame.winfo_children():
                widget.destroy()
                
            self.update_loading_status("🔄 Restaurando módulo...")
            cached_module.show_in_frame(self.module_frame)
            self.current_module = cached_module
            
            # Preparar transición visual
            if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                self.loading_message.configure(
                    text="¡Módulo Felicitaciones restaurado!",
                    font=("Roboto", 16, "bold"),
                    text_color="#2196F3"  # Color azul para restauración
                )
            
            # Detener la barra de progreso y mostrarla completa
            if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                self.loading_progress.stop()
                self.loading_progress.configure(mode="determinate")
                self.loading_progress.set(1.0)  # Progreso completo
            
            # Esperar un momento para mostrar el mensaje de éxito
            self.after(800, self.hide_loading_screen)
            
            self.is_loading = False
            
        except Exception as e:
            self.show_error(f"Error restaurando módulo: {str(e)}")
            self.module_cache.clear("Módulo Felicitaciones")
            self.is_loading = False

    def _create_felicitaciones_module(self):
        """Crear nuevo módulo de felicitaciones"""
        from modulos.modulo_felicitaciones import AplicacionFelicitaciones
        
        self.update_loading_status("🚀 Creando nuevo módulo de felicitaciones...")
        
        # Limpiar frame actual
        for widget in self.module_frame.winfo_children():
            widget.destroy()
        
        def create_module():
            try:
                new_module = AplicacionFelicitaciones(parent_frame=self.module_frame)
                self.current_module = new_module
                self.module_cache.set("Módulo Felicitaciones", new_module)
                
                # Preparar transición visual
                if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                    self.loading_message.configure(
                        text="¡Módulo Felicitaciones creado!",
                        font=("Roboto", 16, "bold"),
                        text_color="#4CAF50"  # Color verde para creación
                    )
                
                # Detener la barra de progreso y mostrarla completa
                if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                    self.loading_progress.stop()
                    self.loading_progress.configure(mode="determinate")
                    self.loading_progress.set(1.0)  # Progreso completo
                
                # Esperar un momento para mostrar el mensaje de éxito
                self.after(800, self.hide_loading_screen)
                
                self.is_loading = False
                
            except Exception as e:
                self.show_error(f"Error creando módulo: {str(e)}")
                self.is_loading = False
        
        # Usar after para dar tiempo a la UI de actualizarse
        self.after(200, create_module)

    def _create_sanciones_module(self):
        """Crear nuevo módulo de sanciones"""
        from modulos.modulo_sanciones import AplicacionSanciones
        
        self.update_loading_status("🚀 Creando nuevo módulo de sanciones...")
        
        # Limpiar frame actual
        for widget in self.module_frame.winfo_children():
            widget.destroy()
        
        def create_module():
            try:
                # Crear el módulo con el frame correcto
                new_module = AplicacionSanciones(parent_frame=self.module_frame)
                
                # Asignar y guardar en caché
                self.current_module = new_module
                self.module_cache.set("Módulo Sanciones", new_module)
                
                # Preparar transición visual
                if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                    self.loading_message.configure(
                        text="¡Módulo Sanciones creado!",
                        font=("Roboto", 16, "bold"),
                        text_color="#4CAF50"  # Color verde para creación
                    )
                
                # Detener la barra de progreso y mostrarla completa
                if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                    self.loading_progress.stop()
                    self.loading_progress.configure(mode="determinate")
                    self.loading_progress.set(1.0)  # Progreso completo
                
                # Esperar un momento para mostrar el mensaje de éxito
                self.after(800, self.hide_loading_screen)
                
                self.is_loading = False
                
            except Exception as e:
                self.show_error(f"Error creando módulo: {str(e)}")
                self.is_loading = False
        
        # Usar after para dar tiempo a la UI de actualizarse
        self.after(200, create_module)

    def _create_conceptos_module(self):
        """Crear nuevo módulo de conceptos"""
        from modulos.modulo_conceptos import AplicacionConceptos
        
        self.update_loading_status("🚀 Creando nuevo módulo de conceptos...")
        
        # Limpiar frame actual
        for widget in self.module_frame.winfo_children():
            widget.destroy()
        
        def create_module():
            try:
                print("Creando módulo de conceptos...")
                print(f"Frame padre: {self.module_frame}")
                
                # Crear el módulo con el frame correcto
                new_module = AplicacionConceptos(parent_frame=self.module_frame)
                
                # Verificar que se creó correctamente
                if new_module is None:
                    raise Exception("Error al crear el módulo de conceptos")
                
                print("Módulo creado exitosamente")
                
                # Asignar y guardar en caché
                self.current_module = new_module
                self.module_cache.set("Módulo Conceptos", new_module)
                
                # Preparar transición visual
                if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                    self.loading_message.configure(
                        text="¡Módulo Conceptos creado!",
                        font=("Roboto", 16, "bold"),
                        text_color="#4CAF50"  # Color verde para creación
                    )
                
                # Detener la barra de progreso y mostrarla completa
                if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                    self.loading_progress.stop()
                    self.loading_progress.configure(mode="determinate")
                    self.loading_progress.set(1.0)  # Progreso completo
                
                # Esperar un momento para mostrar el mensaje de éxito
                self.after(800, self.hide_loading_screen)
                
                self.is_loading = False
                
            except Exception as e:
                print(f"Error detallado al crear módulo: {str(e)}")
                self.show_error(f"Error creando módulo: {str(e)}")
                self.is_loading = False
        
        # Usar after para dar tiempo a la UI de actualizarse
        self.after(200, create_module)

    def _create_prestamos_module(self):
        """Crear nuevo módulo de préstamos"""
        from modulos.modulo_prestamos import AplicacionPrestamos
        
        self.update_loading_status("🚀 Creando nuevo módulo de préstamos...")
        
        # Limpiar frame actual y configurar geometría
        for widget in self.module_frame.winfo_children():
            widget.destroy()
        
        # Configurar el grid del module_frame
        self.module_frame.grid_rowconfigure(0, weight=1)
        self.module_frame.grid_columnconfigure(0, weight=1)
        
        def create_module():
            try:
                # Crear un frame contenedor con geometría específica
                container_frame = ctk.CTkFrame(self.module_frame, fg_color=self.window_bg_color)
                container_frame.pack(fill="both", expand=True)  # Cambiar de grid a pack
                
                # Crear el módulo con el container_frame
                new_module = AplicacionPrestamos(parent_frame=container_frame, root=self)
                
                # Forzar actualización de geometría
                container_frame.update_idletasks()
                self.module_frame.update_idletasks()
                
                self.current_module = new_module
                self.module_cache.set("Módulo Préstamos", new_module)
                
                # Preparar transición visual
                if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                    self.loading_message.configure(
                        text="¡Módulo Préstamos creado!",
                        font=("Roboto", 16, "bold"),
                        text_color="#4CAF50"  # Color verde para creación
                    )
                
                # Detener la barra de progreso y mostrarla completa
                if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                    self.loading_progress.stop()
                    self.loading_progress.configure(mode="determinate")
                    self.loading_progress.set(1.0)  # Progreso completo
                
                # Esperar un momento para mostrar el mensaje de éxito
                self.after(800, self.hide_loading_screen)
                
                self.is_loading = False
                
            except Exception as e:
                self.show_error(f"Error creando módulo: {str(e)}")
                self.is_loading = False
        
        # Dar tiempo para que la UI se actualice
        self.after(200, create_module)

    def _create_certificados_medicos_module(self):
        """Crear nuevo módulo de certificados médicos"""
        from modulos.modulo_certificados_medicos import AplicacionCertificadosMedicos
        
        self.update_loading_status("🚀 Creando nuevo módulo de certificados médicos...")
        
        # Limpiar frame actual
        for widget in self.module_frame.winfo_children():
            widget.destroy()
        
        def create_module():
            try:
                # Crear el módulo con el frame correcto
                new_module = AplicacionCertificadosMedicos(parent_frame=self.module_frame)
                
                # Asignar y guardar en caché
                self.current_module = new_module
                self.module_cache.set("Módulo Certificados Médicos", new_module)
                
                # Preparar transición visual
                if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                    self.loading_message.configure(
                        text="¡Módulo Certificados Médicos creado!",
                        font=("Roboto", 16, "bold"),
                        text_color="#4CAF50"  # Color verde para creación
                    )
                
                # Detener la barra de progreso y mostrarla completa
                if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                    self.loading_progress.stop()
                    self.loading_progress.configure(mode="determinate")
                    self.loading_progress.set(1.0)  # Progreso completo
                
                # Esperar un momento para mostrar el mensaje de éxito
                self.after(800, self.hide_loading_screen)
                
                self.is_loading = False
                
            except Exception as e:
                self.show_error(f"Error creando módulo: {str(e)}")
                self.is_loading = False
        
        # Usar after para dar tiempo a la UI de actualizarse
        self.after(200, create_module)

    def _restore_art_module(self, cached_module):
        """Restaurar módulo de ART desde caché"""
        try:
            # Limpiar frame actual
            for widget in self.module_frame.winfo_children():
                widget.destroy()
            
            # Configurar el grid del module_frame
            self.module_frame.grid_rowconfigure(0, weight=1)
            self.module_frame.grid_columnconfigure(0, weight=1)
            
            # Crear nuevo frame contenedor
            container_frame = ctk.CTkFrame(self.module_frame, fg_color=self.window_bg_color)
            container_frame.grid(row=0, column=0, sticky="nsew")
            
            # Configurar el grid del container_frame
            container_frame.grid_rowconfigure(0, weight=1)
            container_frame.grid_columnconfigure(0, weight=1)
            
            self.update_loading_status("🔄 Restaurando módulo...")
            cached_module.parent_frame = container_frame
            cached_module.show_in_frame(container_frame)
            
            # Forzar actualización de geometría
            container_frame.update_idletasks()
            self.module_frame.update_idletasks()
            
            self.current_module = cached_module
            
            # Preparar transición visual
            if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                self.loading_message.configure(
                    text="¡Módulo ART restaurado!",
                    font=("Roboto", 16, "bold"),
                    text_color="#2196F3"  # Color azul para restauración
                )
            
            # Detener la barra de progreso y mostrarla completa
            if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                self.loading_progress.stop()
                self.loading_progress.configure(mode="determinate")
                self.loading_progress.set(1.0)  # Progreso completo
            
            # Esperar un momento para mostrar el mensaje de éxito
            self.after(800, self.hide_loading_screen)
            
            self.is_loading = False
            
        except Exception as e:
            self.show_error(f"Error restaurando módulo: {str(e)}")
            self.module_cache.clear("Módulo ART")
            self.is_loading = False

    def _create_art_module(self):
        """Crear nuevo módulo de ART"""
        from modulos.modulo_art import AplicacionART
        
        self.update_loading_status("🚀 Creando nuevo módulo de ART...")
        
        try:
            # Limpiar frame actual
            for widget in self.module_frame.winfo_children():
                widget.destroy()
            
            # Configurar el grid del module_frame
            self.module_frame.grid_rowconfigure(0, weight=1)
            self.module_frame.grid_columnconfigure(0, weight=1)
            
            def create_module():
                try:
                    # Crear un frame contenedor con geometría específica
                    container_frame = ctk.CTkFrame(self.module_frame, fg_color=self.window_bg_color)
                    container_frame.grid(row=0, column=0, sticky="nsew")
                    
                    # Configurar el grid del container_frame
                    container_frame.grid_rowconfigure(0, weight=1)
                    container_frame.grid_columnconfigure(0, weight=1)
                    
                    # Crear el módulo con el container_frame
                    new_module = AplicacionART(parent_frame=container_frame)
                    
                    # Forzar actualización de geometría
                    container_frame.update_idletasks()
                    self.module_frame.update_idletasks()
                    
                    self.current_module = new_module
                    self.module_cache.set("Módulo ART", new_module)
                    self.is_loading = False
                    self.hide_loading_screen()
                    
                except Exception as e:
                    self.show_error(f"Error creando módulo: {str(e)}")
                    self.is_loading = False
            
            # Dar tiempo para que la UI se actualice
            self.after(200, create_module)
            
        except Exception as e:
            self.show_error(f"Error en creación: {str(e)}")
            self.is_loading = False

    def update_loading_status(self, message):
        """Actualizar mensaje de carga y consola"""
        if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
            try:
                if self.loading_message.winfo_exists():
                    self.loading_message.configure(text=message)
            except Exception as e:
                print(f"Error al actualizar mensaje de carga: {e}")
        print(message)

    def show_error(self, message):
        """Mostrar mensaje de error de forma segura"""
        self.hide_loading_screen()
        self.is_loading = False
        messagebox.showerror("Error", message)

    def update_clock(self):
        """Actualizar el reloj con formato moderno"""
        now = datetime.now()
        
        # Traducción de días de la semana
        dias = {
            0: "LUNES",
            1: "MARTES",
            2: "MIÉRCOLES",
            3: "JUEVES",
            4: "VIERNES",
            5: "SÁBADO",
            6: "DOMINGO"
        }
        
        # Traducción de meses
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }

        # Actualizar tiempo con efecto parpadeante en los dos puntos
        if now.second % 2 == 0:
            time_str = now.strftime("%H:%M:%S")
        else:
            time_str = now.strftime("%H %M %S")

        # Formatear fecha
        date_str = f"{now.day} de {meses[now.month]} de {now.year}"
        weekday_str = dias[now.weekday()]

        # Actualizar labels
        self.time_label.configure(text=time_str)
        self.date_label.configure(text=date_str)
        self.weekday_label.configure(text=weekday_str)

        # Actualizar cada 100ms para hacer el parpadeo más suave
        self.after(100, self.update_clock)

    def open_settings(self):
        print("Abrir configuración")

    def logout(self):
        """Cerrar sesión y limpiar caché"""
        try:
            # Limpiar caché de módulos
            self.module_cache.clear()
            # Cerrar conexiones si existen
            if hasattr(self, 'current_module') and self.current_module:
                if hasattr(self.current_module, 'db'):
                    self.current_module.db.close()
            print("Cerrar sesión")
        except Exception as e:
            print(f"Error al cerrar sesión: {e}")

    def _create_welcome_screen(self):
        """Crear pantalla de bienvenida en el frame principal"""
        # Limpiar el frame principal
        for widget in self.module_frame.winfo_children():
            widget.destroy()

        # Frame contenedor para la bienvenida
        welcome_frame = ctk.CTkFrame(
            self.module_frame,
            fg_color=self.window_bg_color,
        )
        welcome_frame.pack(expand=True, fill="both")

        try:
            # Cargar y mostrar el logo estático
            logo_frame = ctk.CTkFrame(
                welcome_frame,
                fg_color="transparent",
                width=200,
                height=200
            )
            logo_frame.pack(pady=20)
            logo_frame.pack_propagate(False)

            # Cargar imagen PNG
            logo_path = ICONS_DIR / "logo.png"
            logo_image = Image.open(logo_path)
            logo_image = logo_image.convert('RGBA')
            
            # Crear CTkImage con la imagen
            logo_ctk = ctk.CTkImage(
                light_image=logo_image,
                dark_image=logo_image,
                size=(120, 120)
            )

            # Label para el logo
            self.welcome_logo = ctk.CTkLabel(
                logo_frame,
                text="",
                image=logo_ctk,
                width=300,
                height=300
            )
            self.welcome_logo.pack(expand=True)

        except Exception as e:
            print(f"Error cargando logo de bienvenida: {e}")

        # Mensajes de bienvenida
        ctk.CTkLabel(
            welcome_frame,
            text="WorkData Entheus",
            font=("Roboto", 32, "bold"),
            text_color=self.text_color
        ).pack(pady=20)

        ctk.CTkLabel(
            welcome_frame,
            text="Seleccione un módulo del menú lateral para comenzar",
            font=("Roboto", 18),
            text_color=self.text_color
        ).pack()

        # Información de la empresa
        company_frame = ctk.CTkFrame(
            welcome_frame,
            fg_color="transparent"
        )
        company_frame.pack(side="bottom", pady=30)

        ctk.CTkLabel(
            company_frame,
            text="Entheus Seguridad Privada",
            font=("Roboto", 24, "bold"),
            text_color="#1A237E"
        ).pack()

        ctk.CTkLabel(
            company_frame,
            text="Plataforma de Gestión de Antecedentes Laborales",
            font=("Roboto", 16),
            text_color=self.text_color
        ).pack()

        ctk.CTkLabel(
            company_frame,
            text="© 2025 Todos los derechos reservados",
            font=("Roboto", 12),
            text_color=self.text_color
        ).pack(pady=10)

    # Función auxiliar para verificar si un widget existe de forma segura
    def _widget_exists(self, widget):
        """Verificar de forma segura si un widget existe"""
        if widget is None:
            return False
        try:
            return widget.winfo_exists()
        except:
            return False

    def abrir_modulo_antecedentes(self):
        """Método mejorado para abrir el módulo de antecedentes"""
        if self.is_loading:
            print("⚠️ Ya hay una carga en proceso")
            return
        
        self.is_loading = True
        print("\n🔄 === INICIANDO CARGA DE MÓDULO: Antecedentes Laborales ===")
        
        # Limpiar el contenido actual del frame principal
        for widget in self.module_frame.winfo_children():
            widget.destroy()
        print("✓ Frame limpiado")
        
        self.show_loading_screen("Antecedentes Laborales")
        
        # Tiempo mínimo de carga para efecto visual
        self.loading_start_time = time.time()
        self.loading_min_time = 3.0  # segundos
        
        def create_antecedentes_module():
            try:
                print("\n🏗️ Creando nueva instancia de Módulo Antecedentes")
                
                # Crear y mostrar el módulo de antecedentes
                module_instance = crear_modulo_antecedentes(self.module_frame)
                
                # Actualizar título
                self.title("Sistema RRHH - Antecedentes Laborales")
                
                # Calcular tiempo transcurrido y esperar si es necesario
                elapsed_time = time.time() - self.loading_start_time
                remaining_time = max(0, self.loading_min_time - elapsed_time)
                
                if remaining_time > 0:
                    print(f"Esperando {remaining_time:.2f} segundos adicionales para efecto visual...")
                    self.update_loading_status(f"✨ Finalizando... ({int(remaining_time)}s)")
                    self.after(int(remaining_time * 1000), lambda: self._finish_module_load(module_instance, "Antecedentes Laborales"))
                else:
                    self.after(0, lambda: self._finish_module_load(module_instance, "Antecedentes Laborales"))
                
            except Exception as e:
                print(f"❌ Error al crear módulo Antecedentes: {str(e)}")
                traceback.print_exc()
                if not self.is_destroyed:
                    self.after(0, lambda: self.show_error(f"Error creando módulo: {str(e)}"))
                    self.after(0, self.hide_loading_screen)
                self.is_loading = False
        
        # Verificar caché primero
        cached_module = self.module_cache.get("Antecedentes Laborales")
        if cached_module:
            print(f"📦 Restaurando Antecedentes Laborales desde caché")
            self.update_loading_status("📦 Restaurando desde caché...")
            # Incluso para módulos en caché, esperar el tiempo mínimo
            self.after(int(self.loading_min_time * 1000), lambda: self._restore_antecedentes_module(cached_module))
            return
        
        # Crear módulo en thread separado
        print(f"🚀 Creando nuevo Antecedentes Laborales")
        self.update_loading_status("🚀 Iniciando módulo...")
        self.thread_manager.submit_task("load_Antecedentes", create_antecedentes_module)

    def _restore_antecedentes_module(self, cached_module):
        """Restaurar módulo de antecedentes desde caché"""
        print(f"\n📦 === RESTAURANDO MÓDULO ANTECEDENTES ===")
        try:
            # Limpiar frame actual de forma segura
            for widget in self.module_frame.winfo_children():
                widget.destroy()
            
            # Actualizar estado de carga
            self.update_loading_status("🔄 Recreando módulo de antecedentes...")
            
            # En lugar de intentar restaurar, es más seguro crear uno nuevo
            # ya que el módulo puede tener referencias a widgets que ya no existen
            print("Creando nueva instancia en lugar de restaurar")
            new_module = crear_modulo_antecedentes(self.module_frame)
            
            # Actualizar título
            self.title("Sistema RRHH - Antecedentes Laborales")
            
            # Actualizar caché y referencias
            self.module_cache.set("Antecedentes Laborales", new_module)
            self.current_module = new_module
            
            # Preparar transición visual
            if hasattr(self, 'loading_message') and self._widget_exists(self.loading_message):
                self.loading_message.configure(
                    text="¡Módulo Antecedentes cargado!",
                    font=("Roboto", 16, "bold"),
                    text_color="#4CAF50"  # Color verde para éxito
                )
            
            # Detener la barra de progreso y mostrarla completa
            if hasattr(self, 'loading_progress') and self._widget_exists(self.loading_progress):
                self.loading_progress.stop()
                self.loading_progress.configure(mode="determinate")
                self.loading_progress.set(1.0)  # Progreso completo
            
            # Esperar un momento para mostrar el mensaje de éxito
            self.after(800, self.hide_loading_screen)
            
            self.is_loading = False
            print("✅ Módulo antecedentes cargado correctamente")
            
        except Exception as e:
            print(f"❌ Error al cargar módulo: {str(e)}")
            traceback.print_exc()
            self.show_error(f"Error cargando módulo: {str(e)}")
            self.module_cache.clear("Antecedentes Laborales")
            self.is_loading = False
            # Como fallback, intentar crear un nuevo módulo
            self.after(200, self._create_antecedentes_module)

if __name__ == "__main__":
    app = MainMenu()
    app.mainloop()