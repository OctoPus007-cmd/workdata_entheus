import customtkinter as ctk
from tkcalendar import DateEntry
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import mysql.connector
import threading
from concurrent.futures import ThreadPoolExecutor
from CTkTable import CTkTable
from PIL import Image, ImageTk, ImageSequence
import io
import logging
from datetime import datetime, date
import traceback
import os
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import sys

# Agregar el directorio raíz al path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from utils.thread_manager import DatabasePool
from utils.interface_manager import EstiloApp, DialogManager

# Cargar variables de entorno
load_dotenv()

# Configuración de tema y colores
ctk.set_appearance_mode("light")

class AplicacionFelicitaciones:
    def __init__(self, parent_frame=None):
        """
        Inicializar la aplicación
        :param parent_frame: Frame padre donde se mostrará el módulo
        """
        self.parent = parent_frame
        self.root = self._find_root_window(parent_frame)
        self.dialog_manager = DialogManager()
        
        self.is_standalone = parent_frame is None
        
        if self.is_standalone:
            self.root = ctk.CTk()
            self.main_container = self.root
        else:
            self.root = parent_frame
            # Cambiar a grid en lugar de pack para el main_container
            self.main_container = ctk.CTkFrame(self.root, fg_color=EstiloApp.COLOR_PRINCIPAL)
            self.main_container.grid(row=0, column=0, sticky="nsew")
            
        self.db_pool = DatabasePool()
        self.is_destroyed = False
        self.felicitacion_seleccionada_id = None
        self.actualizando_treeview = False
        self.lock = threading.Lock()
        
        # Configurar el sistema de logging
        self._setup_logging()
        
        # Iniciar la interfaz de forma asíncrona
        if self.is_standalone:
            self.root.after(100, self._init_async)
        else:
            self._init_async()

    def _find_root_window(self, widget):
        """Encuentra la ventana principal desde cualquier widget"""
        current = widget
        while current:
            if isinstance(current, (tk.Tk, ctk.CTk)):
                return current
            current = current.master
        return None

    def show_in_frame(self, parent_frame):
        """Mostrar el módulo en un frame específico usando grid consistentemente"""
        try:
            # Limpiar el frame padre primero
            for widget in parent_frame.winfo_children():
                widget.destroy()
                
            # Configurar el frame padre
            parent_frame.grid_columnconfigure(0, weight=1)
            parent_frame.grid_rowconfigure(0, weight=1)
            
            # Actualizar referencias
            self.parent = parent_frame
            self.root = self._find_root_window(parent_frame)
            
            # Crear el contenedor principal usando grid
            self.main_container = ctk.CTkFrame(parent_frame, fg_color=EstiloApp.COLOR_PRINCIPAL)
            self.main_container.grid(row=0, column=0, sticky="nsew")
            
            # Configurar el grid del contenedor principal
            self.main_container.grid_columnconfigure(0, weight=1)
            self.main_container.grid_rowconfigure(0, weight=0)  # Header
            self.main_container.grid_rowconfigure(1, weight=0)  # Separator
            self.main_container.grid_rowconfigure(2, weight=1)  # Content
            
            # Inicializar la interfaz
            self.create_gui()
            
        except Exception as e:
            self.logger.error(f"Error en show_in_frame: {str(e)}")
            raise

    def show_window(self):
        """Mostrar la ventana del módulo"""
        if not self.is_standalone:
            self.root.deiconify()
            self.root.focus_force()

    def hide_window(self):
        """Ocultar la ventana del módulo"""
        if not self.is_standalone:
            self.root.withdraw()
        else:
            self.on_closing()

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
            filename=os.path.join(log_dir, 'errores_felicitaciones.log'),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(log_format)
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        
        self.logger.info("🚀 Módulo de Felicitaciones iniciado")

    def setup_window(self):
        """Configuración inicial de la ventana"""
        if self.is_standalone:
            self.root.title("Sistema de Gestión de Felicitaciones")
            self.root.state('zoomed')
        
        # Configurar el frame principal independientemente del modo
        if isinstance(self.root, ctk.CTk):
            self.root.configure(fg_color=EstiloApp.COLOR_PRINCIPAL)
        else:
            # Si es un frame, solo configuramos el color
            self.root.configure(fg_color=EstiloApp.COLOR_PRINCIPAL)
            
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

    def _create_form(self):
        """Crear formulario de felicitaciones"""
        form_frame = ctk.CTkFrame(
            self.main_frame, 
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        form_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(5, 5))  # Reducido padding vertical
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_columnconfigure(2, weight=0)

        # Título del formulario
        title_label = ctk.CTkLabel(
            form_frame,
            text="Registre o Modifique Felicitaciones",
            font=('Roboto', 20, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(20, 20))

        # Crear campos del formulario
        self.crear_campos_formulario(form_frame)

        # Panel central con foto y datos del empleado
        info_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        info_frame.grid(row=1, column=1, rowspan=5, padx=20, pady=5, sticky="n")

        # Frame para la foto
        photo_frame = ctk.CTkFrame(
            info_frame,
            fg_color=EstiloApp.COLOR_PRINCIPAL,
            corner_radius=10,
            border_width=2,
            border_color=EstiloApp.COLOR_SECUNDARIO,
            width=200,
            height=200
        )
        photo_frame.pack(pady=(0, 10))
        photo_frame.pack_propagate(False)

        # Canvas para la foto
        self.photo_canvas = ctk.CTkCanvas(
            photo_frame,
            width=200,
            height=200,
            bg=EstiloApp.COLOR_PRINCIPAL,
            highlightthickness=0
        )
        self.photo_canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Placeholder inicial para la foto
        self.photo_canvas.create_oval(
            50, 50, 150, 150,
            fill="#E0E0E0",
            outline=""
        )
        self.photo_canvas.create_text(
            100, 100,
            text="👤",
            font=("Arial", 40),
            fill="#909090"
        )
        self.photo_canvas.create_text(
            100, 170,
            text="Sin foto",
            font=("Arial", 10),
            fill="#606060"
        )

        # Frame para datos del empleado (debajo de la foto)
        data_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        data_frame.pack(pady=(5, 0))

        # Labels de información
        self.nombre_completo_label = ctk.CTkLabel(
            data_frame,
            text="Apellido y Nombre: -",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="center",
            width=250
        )
        self.nombre_completo_label.pack(pady=(0, 5))

        self.total_felicitaciones_label = ctk.CTkLabel(
            data_frame,
            text="Total Felicitaciones: 0",
            font=ctk.CTkFont(size=14),
            anchor="center",
            width=250
        )
        self.total_felicitaciones_label.pack()

        # Panel derecho (botones CRUD)
        self._create_crud_buttons(form_frame)

    def _create_employee_info_frame(self, parent):
        """Crear panel central con foto y datos del empleado"""
        info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        info_frame.grid(row=0, column=2, rowspan=2, padx=20, pady=5, sticky="n")  # Cambiado a column=2

        # Frame para la foto
        photo_frame = ctk.CTkFrame(
            info_frame,
            fg_color=EstiloApp.COLOR_PRINCIPAL,
            corner_radius=10,
            border_width=2,
            border_color=EstiloApp.COLOR_SECUNDARIO,
            width=200,
            height=220
        )
        photo_frame.pack(pady=(0, 10))
        photo_frame.pack_propagate(False)

        # Canvas para la foto
        self.photo_canvas = ctk.CTkCanvas(
            photo_frame,
            width=200,
            height=200,
            bg=EstiloApp.COLOR_PRINCIPAL,
            highlightthickness=0
        )
        self.photo_canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Placeholder inicial
        self.photo_canvas.create_oval(
            50, 50, 150, 150,
            fill="#E0E0E0",
            outline=""
        )
        self.photo_canvas.create_text(
            100, 100,
            text="👤",
            font=("Arial", 40),
            fill="#909090"
        )
        self.photo_canvas.create_text(
            100, 170,
            text="Sin foto",
            font=("Arial", 10),
            fill="#606060"
        )

        # Frame para datos del empleado (ahora debajo de la foto)
        data_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        data_frame.pack(pady=(5, 0))  # Ajustado el padding superior

        # Labels de información
        self.nombre_completo_label = ctk.CTkLabel(
            data_frame,
            text="Apellido y Nombre: -",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="center",
            width=250
        )
        self.nombre_completo_label.pack(pady=(0, 5))

        self.total_felicitaciones_label = ctk.CTkLabel(
            data_frame,
            text="Total Felicitaciones: 0",
            font=ctk.CTkFont(size=14),
            anchor="center",
            width=250
        )
        self.total_felicitaciones_label.pack()

    def crear_campos_formulario(self, parent):
        """Crear campos del formulario con nueva disposición en grid"""
        # Frame contenedor del formulario
        form_container = ctk.CTkFrame(parent, fg_color="transparent")
        form_container.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        
        form_container.grid_columnconfigure(1, weight=1)
        form_container.grid_columnconfigure(3, weight=1)
        form_container.grid_columnconfigure(5, weight=0)

        # Definir campos y sus posiciones
        fields = [
            ("Legajo:", "entry_legajo", 0, 0, None),
            ("Fecha:", "entry_fecha", 1, 0, "date"),
            ("Objetivo:", "entry_objetivo", 0, 2),
            ("Motivo:", "text_motivo", 1, 2, "text", 2)
        ]

        # Estilo para DateEntry - Modificado para que se vea mejor
        style = ttk.Style()
        style.configure(
            'Custom.DateEntry',
            fieldbackground=EstiloApp.COLOR_PRINCIPAL,
            background=EstiloApp.COLOR_SECUNDARIO,
            foreground='black',
            arrowcolor='black',
            font=('Roboto', 14)
        )

        # Crear campos
        for field in fields:
            # Label
            label = ctk.CTkLabel(
                form_container,
                text=field[0],
                font=('Roboto', 14, 'bold')
            )
            label.grid(row=field[2], column=field[3], padx=(20, 10), pady=5, sticky="e")

            # Widget
            if len(field) > 4 and field[4] == "date":
                # Frame contenedor para el DateEntry
                date_frame = ctk.CTkFrame(
                    form_container,
                    fg_color=EstiloApp.COLOR_PRINCIPAL,
                    height=35,
                    width=200,
                    border_width=2,
                    border_color=EstiloApp.COLOR_SECUNDARIO,
                    corner_radius=8
                )
                date_frame.grid(row=field[2], column=field[3]+1, sticky="w", padx=20, pady=5)
                date_frame.grid_propagate(False)
                
                # Configurar estilo del DateEntry
                style = ttk.Style()
                style.configure(
                    'Custom.DateEntry',
                    fieldbackground=EstiloApp.COLOR_PRINCIPAL,
                    background=EstiloApp.COLOR_PRINCIPAL,
                    foreground='black',
                    arrowcolor='black',
                    borderwidth=0,
                    highlightthickness=0,
                    relief='flat'
                )
                
                widget = DateEntry(
                    date_frame,
                    width=12,
                    background=EstiloApp.COLOR_PRINCIPAL,
                    foreground='black',
                    borderwidth=0,
                    font=('Roboto', 14),
                    date_pattern='dd-mm-yyyy',
                    style='Custom.DateEntry',
                    justify='center',
                    locale='es',
                    relief='flat'
                )
                widget.pack(expand=True, fill='both', padx=5, pady=2)
                
                # Eliminar bordes adicionales
                widget._top_cal.configure(relief='flat', borderwidth=0)
                for child in widget.winfo_children():
                    if isinstance(child, tk.Entry):
                        child.configure(relief='flat', borderwidth=0, highlightthickness=0)
                
            elif len(field) > 4 and field[4] == "text":
                widget = ctk.CTkTextbox(
                    form_container,
                    height=80,
                    width=400,
                    font=('Roboto', 14),
                    border_width=2,  # Agregar borde
                    border_color=EstiloApp.COLOR_SECUNDARIO,  # Color del borde
                    corner_radius=8  # Esquinas redondeadas
                )
                widget.grid(row=field[2], column=field[3]+1, rowspan=field[5], 
                          sticky="nsew", padx=20, pady=5)
                setattr(self, field[1], widget)
                continue
            else:
                widget = ctk.CTkEntry(
                    form_container,
                    height=35,
                    width=200,
                    font=('Roboto', 14),
                    justify='center',  # Añadir justificación centrada
                    border_width=2,
                    border_color=EstiloApp.COLOR_SECUNDARIO,
                    corner_radius=8
                )
                widget.grid(row=field[2], column=field[3]+1, sticky="w", padx=20, pady=5)

            setattr(self, field[1], widget)

            # Vincular eventos al campo legajo
            if field[1] == "entry_legajo":
                widget.bind('<FocusOut>', self.consultar_empleado)
                widget.bind('<Return>', self.consultar_empleado)

    def _create_header_frame(self):
        """Crear header moderno con CTkFrame"""
        header_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=EstiloApp.COLOR_HEADER,
            corner_radius=5
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 5))
        header_frame.grid_columnconfigure(1, weight=1)

        # Logo frame
        logo_frame = ctk.CTkFrame(
            header_frame, 
            fg_color='transparent',
            width=150,
            height=150
        )
        logo_frame.grid(row=0, column=0, rowspan=3, padx=(10, 20), pady=10, sticky="w")
        logo_frame.grid_propagate(False)

        # Logo label
        self.logo_label = ctk.CTkLabel(
            logo_frame,
            text="",
            width=150,
            height=150
        )
        self.logo_label.place(relx=0.5, rely=0.5, anchor="center")

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
                not self.is_destroyed):
                
                # Actualizar el frame actual
                self.logo_label.configure(image=self.gif_frames[self.current_frame])
                self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
                
                # Programar siguiente frame
                if hasattr(self, 'main_container') and self.main_container.winfo_exists():
                    self.main_container.after(100, self._animate_gif)  # 100ms para una animación más suave
            
        except Exception as e:
            self.logger.error(f"Error en animación del logo: {e}")

    def _create_placeholder_logo(self, parent):
        """Crear logo placeholder cuando no se puede cargar el GIF"""
        placeholder = ctk.CTkLabel(
            parent,
            text="LOGO",
            font=ctk.CTkFont(size=16, weight="bold"),
            width=50,
            height=50,
            fg_color=EstiloApp.COLOR_SECUNDARIO,
            corner_radius=10
        )
        placeholder.grid(row=0, column=0, rowspan=3, padx=(10, 20), pady=5)

    def _create_crud_buttons(self, parent):
        """Crear botones CRUD"""
        buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        buttons_frame.grid(row=1, column=2, sticky="ne", padx=20, pady=20)

        buttons = [
            ("Insertar", self.insertar_felicitacion, "#2ECC71", "#27AE60"),  # Verde
            ("Modificar", self.modificar_felicitacion, "#3498DB", "#2980B9"),  # Azul
            ("Eliminar", self.eliminar_felicitacion, "#E74C3C", "#C0392B"),  # Rojo
            ("Limpiar Todo", self.limpiar_campos, "#95A5A6", "#7F8C8D")  # Gris
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

    def insertar_felicitacion(self):
        """Insertar nueva felicitación"""
        if not self.validar_campos():
            return

        try:
            # Preparar los datos
            legajo = self.entry_legajo.get()
            fecha = datetime.strptime(self.entry_fecha.get(), '%d-%m-%Y').strftime('%Y-%m-%d')
            objetivo = self.entry_objetivo.get().strip()
            motivo = self.text_motivo.get("1.0", tk.END).strip()
            
            # Usar lock para sincronizar la operación
            with self.lock:
                with self.db_pool.get_connection() as connection:
                    with connection.cursor() as cursor:
                        # Insertar felicitación
                        cursor.execute("""
                            INSERT INTO felicitaciones (legajo, fecha, objetivo, motivo)
                            VALUES (%s, %s, %s, %s)
                        """, (legajo, fecha, objetivo, motivo))
                        
                        id_insertado = cursor.lastrowid
                        connection.commit()

                        # Obtener el registro completo recién insertado
                        cursor.execute("""
                            SELECT id, legajo, fecha, objetivo, motivo 
                            FROM felicitaciones 
                            WHERE id = %s
                        """, (id_insertado,))
                        registro = cursor.fetchone()

                        # Obtener total de felicitaciones
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM felicitaciones 
                            WHERE legajo = %s
                        """, (legajo,))
                        total = cursor.fetchone()[0]

                # Actualizar UI en el hilo principal
                def actualizar_ui():
                    try:
                        if not self.is_destroyed:
                            # Insertar en treeview
                            fecha_formateada = datetime.strptime(str(registro[2]), '%Y-%m-%d').strftime('%d-%m-%Y')
                            item_id = self.tree.insert("", 0, values=(
                                registro[0], registro[1], fecha_formateada, registro[3], registro[4]
                            ))
                            
                            # Actualizar contador
                            self.total_felicitaciones_label.configure(text=f"Total Felicitaciones: {total}")
                            
                            # Seleccionar el nuevo registro
                            self.tree.selection_set(item_id)
                            self.tree.see(item_id)
                            
                            # Limpiar solo los campos de objetivo y motivo
                            self.entry_objetivo.delete(0, tk.END)
                            self.text_motivo.delete("1.0", tk.END)
                            
                            # Devolver el foco al campo objetivo
                            self.entry_objetivo.focus_set()
                            
                            self.mostrar_mensaje("Éxito", "Felicitación registrada correctamente")
                    except Exception as e:
                        self.logger.error(f"Error actualizando UI: {str(e)}")
                        self.mostrar_mensaje("Error", "Error actualizando la interfaz")

                if not self.is_destroyed:
                    self.root.after(0, actualizar_ui)
                
        except Exception as error:
            self.mostrar_mensaje("Error", f"No se pudo insertar: {str(error)}")
            self.logger.error(f"Error en insertar_felicitacion: {str(error)}")

    def _actualizar_ui_insercion(self, valores):
        """Actualizar la UI después de insertar"""
        try:
            # Formatear fecha para mostrar
            fecha_formateada = datetime.strptime(valores['fecha'], '%Y-%m-%d').strftime('%d-%m-%Y')
            
            # Insertar en treeview
            self.tree.insert("", 0, values=(
                valores['id'],
                valores['legajo'],
                fecha_formateada,
                valores['objetivo'],
                valores['motivo']
            ))
            
            # Actualizar contador
            self.total_felicitaciones_label.configure(
                text=f"Total Felicitaciones: {valores['total']}"
            )
            
            self.mostrar_mensaje("Éxito", "Felicitación registrada correctamente")
            self.limpiar_campos_parcial()
            
        except Exception as error:
            self.logger.error(f"Error actualizando UI: {str(error)}")
            self.mostrar_mensaje("Error", "Error actualizando la interfaz")

    def modificar_felicitacion(self):
        """Modificar felicitación seleccionada"""
        if not self.felicitacion_seleccionada_id or not self.validar_campos():
            self.mostrar_mensaje("Error", "Seleccione una felicitación y complete todos los campos")
            return

        try:
            with self.db_pool.get_connection() as connection:
                with connection.cursor() as cursor:
                    legajo = self.entry_legajo.get()
                    fecha = datetime.strptime(self.entry_fecha.get(), '%d-%m-%Y').strftime('%Y-%m-%d')
                    objetivo = self.entry_objetivo.get().strip()
                    motivo = self.text_motivo.get("1.0", tk.END).strip()
                    
                    # Actualizar registro
                    cursor.execute("""
                        UPDATE felicitaciones 
                        SET legajo = %s, fecha = %s, objetivo = %s, motivo = %s
                        WHERE id = %s
                    """, (legajo, fecha, objetivo, motivo, self.felicitacion_seleccionada_id))
                    
                    connection.commit()
                    
                    # Actualizar el item en el treeview
                    for item in self.tree.get_children():
                        if self.tree.item(item)['values'][0] == self.felicitacion_seleccionada_id:
                            fecha_formateada = datetime.strptime(fecha, '%Y-%m-%d').strftime('%d-%m-%Y')
                            self.tree.item(item, values=(
                                self.felicitacion_seleccionada_id,
                                legajo,
                                fecha_formateada,
                                objetivo,
                                motivo
                            ))
                            break
                    
                    self.mostrar_mensaje("Éxito", "Felicitación modificada correctamente")
                    self.limpiar_campos_parcial()
                    
        except Exception as error:
            self.mostrar_mensaje("Error", f"No se pudo modificar: {str(error)}")
            self.logger.error(f"Error en modificar_felicitacion: {str(error)}")

    def eliminar_felicitacion(self):
        """Eliminar felicitación seleccionada"""
        seleccion = self.tree.selection()
        if not seleccion:
            self.mostrar_mensaje("Error", "Seleccione una felicitación para eliminar")
            return

        try:
            item = seleccion[0]
            valores = self.tree.item(item)['values']
            if not valores:
                raise ValueError("No se pudo obtener la información de la felicitación")
            
            id_felicitacion = valores[0]
            legajo = valores[1]  # Necesitamos el legajo para actualizar el contador

            # Crear ventana modal de confirmación
            dialog = ctk.CTkToplevel(self.root)
            dialog.title("Confirmar Eliminación")
            dialog.geometry("400x200")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centrar la ventana
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
            y = (dialog.winfo_screenheight() // 2) - (200 // 2)
            dialog.geometry(f'+{x}+{y}')
            
            # Contenido de la ventana
            frame = ctk.CTkFrame(dialog, fg_color="transparent")
            frame.pack(expand=True, fill="both", padx=20, pady=20)
            
            ctk.CTkLabel(
                frame,
                text="¿Está seguro que desea eliminar esta felicitación?",
                font=("Roboto", 14, "bold")
            ).pack(pady=20)
            
            # Frame para botones
            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(pady=20)
            
            def confirmar_eliminacion():
                try:
                    with self.db_pool.get_connection() as connection:
                        with connection.cursor() as cursor:
                            cursor.execute("DELETE FROM felicitaciones WHERE id = %s", (id_felicitacion,))
                            connection.commit()
                            
                            # Eliminar del treeview
                            self.tree.delete(item)
                            
                            # Actualizar contador de felicitaciones
                            cursor.execute("""
                                SELECT COUNT(*) 
                                FROM felicitaciones 
                                WHERE legajo = %s
                            """, (legajo,))
                            total = cursor.fetchone()[0]
                            self.total_felicitaciones_label.configure(
                                text=f"Total Felicitaciones: {total}"
                            )
                            
                            self.mostrar_mensaje("Éxito", "Felicitación eliminada correctamente")
                            self.limpiar_campos_parcial()
                            
                    dialog.destroy()
                            
                except Exception as error:
                    self.mostrar_mensaje("Error", f"No se pudo eliminar: {str(error)}")
                    self.logger.error(f"Error en eliminar_felicitacion: {str(error)}")
                    dialog.destroy()
            
            # Botones
            ctk.CTkButton(
                button_frame,
                text="Confirmar",
                command=confirmar_eliminacion,
                fg_color="#E74C3C",  # Rojo para indicar acción peligrosa
                hover_color="#C0392B",
                width=100
            ).pack(side="left", padx=10)
            
            ctk.CTkButton(
                button_frame,
                text="Cancelar",
                command=dialog.destroy,
                fg_color="#95A5A6",  # Gris
                hover_color="#7F8C8D",
                width=100
            ).pack(side="left", padx=10)
            
            # Bindings para cerrar con Escape
            dialog.bind("<Escape>", lambda e: dialog.destroy())
            
        except Exception as error:
            self.mostrar_mensaje("Error", f"No se pudo procesar la eliminación: {str(error)}")
            self.logger.error(f"Error en eliminar_felicitacion: {str(error)}")

    def consultar_felicitaciones(self, legajo):
        """Consultar felicitaciones por legajo"""
        print(f"\n=== INICIO consultar_felicitaciones para legajo {legajo} ===")
        
        if not legajo:
            print("No hay legajo, limpiando treeview")
            self._clear_treeview()
            return

        try:
            with self.db_pool.get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, legajo, fecha, objetivo, motivo
                        FROM felicitaciones 
                        WHERE legajo = %s
                        ORDER BY fecha DESC
                    """, (legajo,))
                        
                    registros = cursor.fetchall()
                    print(f"Registros encontrados en BD: {len(registros)}")
                    
                    registros_procesados = []
                    for registro in registros:
                        fecha = datetime.strptime(str(registro[2]), '%Y-%m-%d').strftime('%d-%m-%Y')
                        valores = list(registro)
                        valores[2] = fecha
                        registros_procesados.append(tuple(valores))

                    print(f"Registros procesados: {len(registros_procesados)}")
                    
                    if not self.is_destroyed:
                        print("Programando actualización del treeview")
                        self.root.after(0, lambda: self._update_treeview(registros_procesados))

        except Exception as e:
            print(f"ERROR en consulta: {str(e)}")
            self.logger.error(f"Error al consultar felicitaciones: {str(e)}")

    def _create_table(self):
        """Crear tabla de felicitaciones"""
        table_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        table_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 15))  # Ajustado padding superior
        
        title_label = ctk.CTkLabel(
            table_frame,
            text="Historial de Felicitaciones",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        # Reducir el padding inferior de 20 a 10
        title_label.pack(pady=(15, 10))

        # Frame para la tabla con scrollbars
        tree_container = ctk.CTkFrame(table_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Crear Treeview
        self.tree = ttk.Treeview(
            tree_container,
            columns=("id", "legajo", "fecha", "objetivo", "motivo"),
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
            "objetivo": {"texto": "Objetivo", "ancho": 300},
            "motivo": {"texto": "Motivo", "ancho": 400}
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
        
        # Agregar el binding para doble clic y clic derecho
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.mostrar_motivo_completo)  # Agregar binding para clic derecho

    def mostrar_motivo_completo(self, event):
        """Mostrar ventana con el motivo completo al hacer clic derecho"""
        # Obtener el ítem bajo el cursor
        item = self.tree.identify_row(event.y)
        if not item:
            return
            
        valores = self.tree.item(item)['values']
        if not valores:
            return
            
        def _get_motivo_completo():
            connection = None
            try:
                connection = self.db_pool.get_connection()
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT motivo 
                    FROM felicitaciones 
                    WHERE id = %s
                """, (valores[0],))
                resultado = cursor.fetchone()
                if resultado and resultado[0]:
                    self.root.after(0, lambda m=resultado[0]: self._crear_ventana_motivo(m))
            finally:
                if connection:
                    cursor.close()
                    self.db_pool.return_connection(connection)
        
        self.db_pool.executor.submit(_get_motivo_completo)

    def _crear_ventana_motivo(self, motivo):
        """Crear ventana modal con el motivo completo"""
        try:
            # Verificar si la ventana principal existe
            if not self.root or not self.root.winfo_exists():
                return
            
            # Limpiar diálogo anterior si existe
            if hasattr(self, 'dialog_motivo'):
                try:
                    if self.dialog_motivo.winfo_exists():
                        self.dialog_motivo.grab_release()
                        self.dialog_motivo.destroy()
                except Exception:
                    pass
                finally:
                    delattr(self, 'dialog_motivo')
            
            # Crear nuevo diálogo
            self.dialog_motivo = ctk.CTkToplevel(self.root)
            self.dialog_motivo.title("Motivo Completo")
            self.dialog_motivo.geometry("500x400")
            self.dialog_motivo.configure(fg_color=EstiloApp.COLOR_FRAMES)
            
            # Hacer el diálogo modal
            self.dialog_motivo.transient(self.root)
            self.dialog_motivo.grab_set()
            
            # Frame para el texto
            text_frame = ctk.CTkFrame(self.dialog_motivo, fg_color="transparent")
            text_frame.pack(fill='both', expand=True, padx=20, pady=(20,10))
            
            # TextBox para mostrar el motivo completo
            text_widget = ctk.CTkTextbox(
                text_frame,
                wrap='word',
                font=ctk.CTkFont(size=12),
                width=460,
                height=300
            )
            text_widget.pack(fill='both', expand=True)
            text_widget.insert('1.0', motivo)
            text_widget.configure(state='disabled')
            
            def cerrar_ventana(event=None):
                """Cerrar ventana de forma segura"""
                try:
                    if hasattr(self, 'dialog_motivo') and self.dialog_motivo.winfo_exists():
                        self.dialog_motivo.grab_release()
                        self.dialog_motivo.destroy()
                        delattr(self, 'dialog_motivo')
                        
                        # Programar el cambio de foco para después del cierre
                        if not self.is_destroyed and self.root.winfo_exists():
                            self.root.after(100, self._restaurar_foco)
                except Exception as e:
                    print(f"Error al cerrar ventana: {e}")
            
            # Bindings para cerrar la ventana
            self.dialog_motivo.protocol("WM_DELETE_WINDOW", cerrar_ventana)
            self.dialog_motivo.bind("<Escape>", cerrar_ventana)
            self.dialog_motivo.bind("<Return>", cerrar_ventana)
            
            # Asegurar que la ventana tenga el foco
            self.dialog_motivo.after(100, self.dialog_motivo.focus_force)
            
        except Exception as e:
            self.logger.error(f"Error al crear ventana de motivo: {str(e)}")
            if hasattr(self, 'dialog_motivo'):
                try:
                    self.dialog_motivo.destroy()
                except Exception:
                    pass

    def _restaurar_foco(self):
        """Restaurar el foco de manera segura"""
        try:
            if (not self.is_destroyed and 
                hasattr(self, 'entry_objetivo') and 
                self.entry_objetivo.winfo_exists()):
                self.entry_objetivo.focus_set()
        except Exception:
            pass

    def on_tree_double_click(self, event=None):
        """Manejar doble clic en una fila del treeview"""
        if self.is_destroyed:
            return
        
        try:
            # Obtener datos del item seleccionado
            seleccion = self.tree.selection()
            if not seleccion:
                return
            
            item = seleccion[0]
            valores = self.tree.item(item)['values']
            if not valores:
                return
            
            id_felicitacion = valores[0]
            legajo = valores[1]
            fecha = valores[2]
            objetivo = valores[3]
            motivo = valores[4]
            
            # Actualizar UI directamente con los datos del treeview
            def actualizar_campos():
                try:
                    # Actualizar ID seleccionado
                    self.felicitacion_seleccionada_id = id_felicitacion
                    
                    # Actualizar campos
                    self.entry_legajo.delete(0, tk.END)
                    self.entry_legajo.insert(0, str(legajo))
                    
                    self.entry_objetivo.delete(0, tk.END)
                    self.entry_objetivo.insert(0, objetivo)
                    
                    self.text_motivo.delete("1.0", tk.END)
                    self.text_motivo.insert("1.0", motivo)
                    
                    # Convertir fecha del formato dd-mm-yyyy a datetime
                    fecha_dt = datetime.strptime(fecha, '%d-%m-%Y')
                    self.entry_fecha.set_date(fecha_dt)
                    
                    # Consultar datos del empleado
                    self.consultar_empleado()
                    
                except Exception as e:
                    self.logger.error(f"Error actualizando campos: {str(e)}")
                    self.mostrar_mensaje("Error", "Error al cargar los datos")
            
            # Ejecutar actualización en el hilo principal
            if not self.is_destroyed:
                self.root.after(0, actualizar_campos)
            
        except Exception as e:
            self.logger.error(f"Error en double click: {str(e)}")
            if not self.is_destroyed:
                self.mostrar_mensaje("Error", "Error al cargar los datos del registro")

    def _cargar_datos_felicitacion(self, datos):
        """Cargar datos completos de la felicitación en el formulario"""
        if self.is_destroyed:
            return
        
        try:
            # Guardar el ID de la felicitación seleccionada
            self.felicitacion_seleccionada_id = datos[0]
            
            # Verificar que los widgets existen
            if not all(hasattr(self, attr) for attr in ['entry_legajo', 'entry_objetivo', 'text_motivo', 'entry_fecha']):
                return
            
            # Limpiar y cargar datos
            self.entry_legajo.delete(0, tk.END)
            self.entry_legajo.insert(0, str(datos[1]))
            
            self.entry_objetivo.delete(0, tk.END)
            self.entry_objetivo.insert(0, str(datos[3]))
            
            self.text_motivo.delete("1.0", tk.END)
            self.text_motivo.insert("1.0", str(datos[4]))
            
            fecha = datetime.strptime(str(datos[2]), "%Y-%m-%d")
            self.entry_fecha.set_date(fecha)
            
            # Actualizar datos del empleado
            self.consultar_empleado()
            
        except Exception as e:
            self.logger.error(f"Error al cargar datos: {str(e)}")
            if not self.is_destroyed:
                self.mostrar_mensaje("Error", f"Error al cargar los datos: {str(e)}")

    def _animate_logo(self):
        """Animar el logo GIF frame por frame"""
        try:
            # Verificar que el widget y sus componentes aún existen
            if (hasattr(self, 'logo_label') and 
                self.logo_label.winfo_exists() and 
                hasattr(self, 'gif_frames') and 
                self.gif_frames and 
                not self.is_destroyed):
                
                self.logo_label.configure(image=self.gif_frames[self.current_frame])
                self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
                
                # Programar siguiente frame solo si el widget principal existe
                if self.main_container and self.main_container.winfo_exists():
                    self.main_container.after(100, self._animate_logo)
        except Exception as e:
            self.logger.error(f"Error en animación del logo: {str(e)}")
            # No reintentar si hay error

    def _init_async(self):
        """
        Inicialización asíncrona de la aplicación
        """
        try:
            # Configurar la ventana
            self.setup_window()
            
            # Crear la interfaz
            self.create_gui()
            
            # Inicializar la base de datos
            self._init_database()
            
            # Ejecutar solo en modo standalone
            if self.is_standalone:
                # Iniciar la aplicación
                self.root.mainloop()
                
        except Exception as e:
            self.logger.error(f"Error en inicialización: {str(e)}")
            messagebox.showerror("Error", f"Error al inicializar la aplicación: {str(e)}")

    def _init_database(self):
        """Inicializar conexión a base de datos"""
        try:
            if not hasattr(self, 'db_pool'):
                self.db_pool = DatabasePool()
            if not self.is_destroyed:
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Éxito", "Conexión establecida correctamente"
                ))
        except Exception as e:
            if not self.is_destroyed:
                self.root.after(0, lambda: self.mostrar_mensaje(
                    "Error", f"Error al conectar con la base de datos: {str(e)}"
                ))

    def create_gui(self):
        """Crear la interfaz gráfica usando grid consistentemente"""
        # Configurar el main_container primero
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=0)  # Header
        self.main_container.grid_rowconfigure(1, weight=0)  # Separator
        self.main_container.grid_rowconfigure(2, weight=1)  # Content
        
        # Header frame (row 0)
        header_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=EstiloApp.COLOR_HEADER,
            corner_radius=10,
            height=150  # Altura fija
        )
        header_frame.grid(row=0, column=0, sticky="new", padx=35, pady=(5, 0))
        header_frame.pack_propagate(False)
        
        # Logo frame
        logo_frame = ctk.CTkFrame(
            header_frame, 
            fg_color='transparent',
            width=150,
            height=150
        )
        logo_frame.grid(row=0, column=0, rowspan=3, padx=(10, 20), pady=0)
        logo_frame.grid_propagate(False)
        
        # Logo label
        self.logo_label = ctk.CTkLabel(
            logo_frame,
            text="",
            width=150,
            height=150
        )
        self.logo_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Cargar el logo
        self._load_gif_frames()
        
        # Títulos
        titles_frame = ctk.CTkFrame(header_frame, fg_color='transparent')
        titles_frame.grid(row=0, column=1, rowspan=3, sticky="nsw", padx=(0, 20))
        
        ctk.CTkLabel(
            titles_frame,
            text="Módulo de Felicitaciones - RRHH",
            font=('Roboto', 24, 'bold'),
            text_color=EstiloApp.COLOR_TEXTO
        ).grid(row=0, column=0, sticky="w", pady=(30, 5))
        
        ctk.CTkLabel(
            titles_frame,
            text="Entheus Seguridad",
            font=('Roboto', 16, 'bold'),
            text_color=EstiloApp.COLOR_SECUNDARIO
        ).grid(row=1, column=0, sticky="w", pady=5)
        
        ctk.CTkLabel(
            titles_frame,
            text="© 2025 Todos los derechos reservados",
            font=('Roboto', 12),
            text_color=EstiloApp.COLOR_TEXTO
        ).grid(row=2, column=0, sticky="w", pady=(5, 30))
        
        # Separator (opcional, puedes comentarlo si no lo necesitas)
        # separator = ctk.CTkFrame(
        #     self.main_container,
        #     height=2,
        #     fg_color=EstiloApp.COLOR_SECUNDARIO
        # )
        # separator.grid(row=1, column=0, sticky="ew", padx=20, pady=2)
        
        # Content frame
        self.content_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=EstiloApp.COLOR_PRINCIPAL
        )
        self.content_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 15))
        
        # Configurar content_frame
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=0)  # Form
        self.content_frame.grid_rowconfigure(1, weight=1)  # Table
        
        # Asignar main_frame
        self.main_frame = self.content_frame
        
        # Crear componentes
        self._create_form()
        self._create_table()

    def _update_treeview(self, registros):
        """Actualizar treeview con registros de manera segura"""
        print("\n=== INICIO _update_treeview ===")
        print(f"Registros recibidos: {len(registros)}")
        print(f"Thread actual: {threading.current_thread().name}")
        
        try:
            if threading.current_thread() != threading.main_thread():
                print("No estamos en el hilo principal, programando actualización...")
                if not self.is_destroyed:
                    self.root.after(0, lambda: self._update_treeview(registros))
                return

            print("Limpiando treeview...")
            self.tree.delete(*self.tree.get_children())
            
            print("Insertando registros...")
            for registro in registros:
                print(f"Insertando registro: {registro}")
                self.tree.insert("", "end", values=registro)

            print("Actualizando contador...")
            self.total_felicitaciones_label.configure(
                text=f"Total Felicitaciones: {len(registros)}"
            )
            print("=== FIN _update_treeview ===\n")

        except Exception as e:
            print(f"ERROR en _update_treeview: {str(e)}")
            self.logger.error(f"Error al actualizar treeview: {str(e)}")

    def _clear_treeview(self):
        """Limpiar todos los registros del treeview de manera segura"""
        try:
            if self.tree.winfo_exists():
                # Asegurar que la limpieza se ejecute en el hilo principal
                if threading.current_thread() != threading.main_thread():
                    self.root.after(0, self._clear_treeview)
                    return
                
                for item in self.tree.get_children():
                    self.tree.delete(item)
        except Exception as e:
            self.logger.error(f"Error al limpiar treeview: {e}")

    def limpiar_campos_parcial(self):
        """Limpiar solo los campos del formulario manteniendo legajo y datos del personal"""
        try:
            # Reset variable importante
            self.felicitacion_seleccionada_id = None
            
            # Limpiar solo campos específicos
            self.entry_objetivo.delete(0, tk.END)
            self.text_motivo.delete("1.0", tk.END)
            self.entry_fecha.set_date(datetime.now())
            
            # Mover el foco al campo objetivo
            self.entry_objetivo.focus_set()
            
        except Exception as e:
            self.logger.error(f"Error en limpiar_campos_parcial: {e}")

    def _mostrar_placeholder_foto(self):
        """Mostrar placeholder cuando no hay foto disponible"""
        self.photo_canvas.delete("all")
        
        # Dibujar un círculo como fondo para el ícono (centrado en canvas de 200x200)
        self.photo_canvas.create_oval(
            50, 50, 150, 150,
            fill="#E0E0E0",
            outline=""
        )
        
        # Agregar ícono de usuario (centrado)
        self.photo_canvas.create_text(
            100, 100,
            text="👤",
            font=("Arial", 40),
            fill="#909090"
        )
        
        # Texto abajo del ícono (centrado)
        self.photo_canvas.create_text(
            100, 170,
            text="Sin foto",
            font=("Arial", 10),
            fill="#606060"
        )

    def limpiar_campos(self):
        """Limpiar todos los campos del formulario"""
        try:
            with self.lock:  # Usar lock para sincronizar
                # Reset variables importantes
                self.felicitacion_seleccionada_id = None
                self._ultimo_legajo_consultado = None
                
                def actualizar_ui():
                    if self.is_destroyed:
                        return
                        
                    # Limpiar campos de entrada
                    self.entry_legajo.delete(0, tk.END)
                    self.entry_objetivo.delete(0, tk.END)
                    self.text_motivo.delete("1.0", tk.END)
                    self.entry_fecha.set_date(datetime.now())
                    
                    # Limpiar canvas y mostrar placeholder
                    self._mostrar_placeholder_foto()
                    
                    # Resetear labels de información
                    self.nombre_completo_label.configure(text="Apellido y Nombre: -")
                    self.total_felicitaciones_label.configure(text="Total Felicitaciones: 0")
                    
                    # Limpiar treeview
                    self._clear_treeview()
                    
                    # Devolver el foco al campo legajo
                    self.entry_legajo.focus_set()
                
                # Ejecutar actualización en el hilo principal
                if not self.is_destroyed:
                    self.root.after(0, actualizar_ui)
                
        except Exception as e:
            self.logger.error(f"Error en limpiar_campos: {e}")
            if not self.is_destroyed:
                self.mostrar_mensaje("Error", f"Error al limpiar los campos: {str(e)}")

    def limpiar_campos_modificacion(self):
        """Limpiar solo campos específicos después de una modificación"""
        try:
            # Guardar datos actuales del empleado
            legajo_actual = self.entry_legajo.get()
            nombre_actual = self.nombre_completo_label.cget("text")
            total_actual = self.total_felicitaciones_label.cget("text")
            
            # Limpiar solo los campos específicos
            self.felicitacion_seleccionada_id = None
            self.entry_objetivo.delete(0, tk.END)
            self.text_motivo.delete("1.0", tk.END)
            self.entry_fecha.set_date(datetime.now())
            
            # Restaurar datos del empleado
            if legajo_actual:
                self.entry_legajo.delete(0, tk.END)
                self.entry_legajo.insert(0, legajo_actual)
                self.nombre_completo_label.configure(text=nombre_actual)
                self.total_felicitaciones_label.configure(text=total_actual)
            
            # Mover el foco al campo objetivo
            self.entry_objetivo.focus_set()
            
        except Exception as e:
            self.logger.error(f"Error en limpiar_campos_modificacion: {e}")

    def validar_campos(self):
        """Validar todos los campos del formulario"""
        try:
            if not all([
                self.entry_legajo.get(),
                self.entry_fecha.get(),
                self.entry_objetivo.get(),
                self.text_motivo.get("1.0", tk.END).strip()
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

    def consultar_empleado(self, event=None):
        """Consultar datos del empleado por legajo"""
        try:
            # Obtener el legajo del campo de entrada
            legajo = self.entry_legajo.get()
            if not legajo:
                return
            
            with self.lock:
                with self.db_pool.get_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT apellido_nombre, foto 
                            FROM personal 
                            WHERE legajo = %s
                        """, (legajo,))
                        
                        resultado = cursor.fetchone()
                        if resultado:
                            # Obtener total de felicitaciones
                            cursor.execute("""
                                SELECT COUNT(*) 
                                FROM felicitaciones 
                                WHERE legajo = %s
                            """, (legajo,))
                            total_felicitaciones = cursor.fetchone()[0]
                            
                            # Actualizar UI con los datos
                            def actualizar_ui():
                                if not self.is_destroyed and hasattr(self, 'entry_objetivo') and self.entry_objetivo.winfo_exists():
                                    apellido_nombre, foto_blob = resultado
                                    self._actualizar_datos_empleado(
                                        apellido_nombre, foto_blob, total_felicitaciones
                                    )
                                    self.consultar_felicitaciones(legajo)
                                    
                                    # Mover el foco si se presionó Enter y el widget existe
                                    if event and event.keysym == 'Return':
                                        try:
                                            self.entry_objetivo.focus_set()
                                        except Exception:
                                            pass  # Ignorar errores de foco
                            
                            if not self.is_destroyed:
                                self.root.after(0, actualizar_ui)
                        else:
                            def mostrar_error():
                                if not self.is_destroyed and hasattr(self, 'entry_legajo') and self.entry_legajo.winfo_exists():
                                    self.mostrar_mensaje("Error", "Empleado no encontrado")
                                    self.entry_legajo.delete(0, tk.END)
                                    self._clear_treeview()
                                    self._actualizar_datos_empleado("-", None, 0)
                                    try:
                                        self.entry_legajo.focus_set()
                                    except Exception:
                                        pass  # Ignorar errores de foco
                    
        except Exception as e:
            self.logger.error(f"Error en consultar_empleado: {str(e)}")
            if not self.is_destroyed:
                self.mostrar_mensaje("Error", f"Error al consultar empleado: {str(e)}")

    def _actualizar_datos_empleado(self, apellido_nombre, foto_blob, total_felicitaciones):
        """Actualizar la UI con los datos del empleado"""
        self.nombre_completo_label.configure(text=f"Apellido y Nombre: {apellido_nombre}")
        self.total_felicitaciones_label.configure(text=f"Total Felicitaciones: {total_felicitaciones}")

        # Actualizar foto
        try:
            if foto_blob and len(foto_blob) > 0:  # Corregido de 'fando_blob'
                # Abrir la imagen desde el blob
                image = Image.open(io.BytesIO(foto_blob))
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Obtener dimensiones del canvas
                canvas_width = self.photo_canvas.winfo_width()
                canvas_height = self.photo_canvas.winfo_height()
                
                # Calcular ratio de aspecto
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
                
                # Redimensionar la imagen manteniendo la calidad
                resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Si la imagen es más pequeña que el canvas, centrarla
                if new_width < canvas_width or new_height < canvas_height:
                    # Crear una imagen en blanco del tamaño del canvas
                    background = Image.new('RGB', (canvas_width, canvas_height), 'white')
                    # Calcular posición para centrar
                    x = (canvas_width - new_width) // 2
                    y = (canvas_height - new_height) // 2
                    # Pegar la imagen redimensionada en el centro
                    background.paste(resized_image, (x, y))
                    resized_image = background
                
                photo = ImageTk.PhotoImage(resized_image)
                self.photo_canvas.delete("all")
                self.photo_canvas.create_image(
                    canvas_width // 2,
                    canvas_height // 2,
                    image=photo,
                    anchor="center"
                )
                self.photo_canvas.image = photo  # Mantener referencia
                
            else:
                raise ValueError("No hay foto disponible")
        except Exception as e:
            self.logger.error(f"Error al cargar la imagen: {str(e)}")
            self.photo_canvas.delete("all")
            self.photo_canvas.create_oval(
                50, 50, 150, 150,
                fill=EstiloApp.COLOR_SECUNDARIO,
                outline=EstiloApp.COLOR_SECUNDARIO
            )
            self.photo_canvas.create_text(
                100, 100,
                text="👤",
                font=("Arial", 40),
                fill="#909090"
            )
            self.photo_canvas.create_text(
                100, 170,
                text="Sin foto",
                font=("Arial", 10),
                fill="#606060"
            )

    def mostrar_mensaje(self, titulo, mensaje, tipo="info"):
        """Muestra mensajes usando la ventana principal correcta"""
        if not self.root:
            self.root = self._find_root_window(self.parent)
        self.dialog_manager.mostrar_mensaje(self.root, titulo, mensaje, tipo)

    def _mostrar_dialogo_confirmacion(self, titulo, mensaje, accion_confirmacion):
        """Mostrar diálogo de confirmación de manera segura"""
        if not self.is_destroyed and self.root and self.root.winfo_exists():
            self.dialog_manager.mostrar_confirmacion(
                self.root, 
                titulo, 
                mensaje,
                lambda: self.db_pool.executor.submit(accion_confirmacion)
            )

    def handle_database_error(self, error, operacion):
        """Manejar errores de base de datos"""
        error_msg = str(error)
        self.logger.error(f"Error en {operacion}: {error_msg}")
        self.mostrar_mensaje("Error", f"Error en la operación: {error_msg}")

    def on_closing(self):
        """
        Manejar el cierre de la ventana
        """
        # Marcar como destruido para evitar operaciones adicionales
        self.is_destroyed = True
        
        # Limpiar recursos y cerrar conexiones
        self.cleanup()
        
        # Si es modo standalone, cerrar completamente la aplicación
        if self.is_standalone:
            if hasattr(self, 'root') and self.root:
                self.root.quit()  # Detener el mainloop
                self.root.destroy()  # Destruir la ventana

    def cleanup(self):
        """
        Limpiar recursos al cerrar
        """
        try:
            # Cerrar la conexión a la base de datos
            if hasattr(self, 'db_pool') and self.db_pool:
                self.db_pool.close()
                
            # Detener animaciones si existen
            if hasattr(self, 'animation_running'):
                self.animation_running = False
                
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error en cleanup: {e}")
            print(f"Error en cleanup: {e}")

    def run(self):
        """Iniciar la aplicación con manejo seguro de cierre"""
        if self.is_standalone:
            try:
                # Configurar el protocolo de cierre
                self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
                self.root.mainloop()
            except Exception as e:
                print(f"Error en ejecución: {str(e)}")
            finally:
                self.cleanup()

    def _actualizar_estadisticas(self, cursor, legajo):
        """Actualizar estadísticas de felicitaciones"""
        cursor.execute("""
            SELECT COUNT(*) as total_felicitaciones
            FROM felicitaciones
            WHERE legajo = %s
        """, (legajo,))
        
        resultado = cursor.fetchone()
        if resultado:
            total_felicitaciones = resultado[0]
            
            if not self.is_destroyed:
                def _actualizar_labels():
                    self.total_felicitaciones_label.configure(
                        text=f"Total Felicitaciones: {total_felicitaciones}"
                    )
                
                self.root.after(0, _actualizar_labels)

# Modificar la sección de ejecución standalone
if __name__ == "__main__":
    try:
        print("\n🚀 Iniciando módulo de felicitaciones...")
        app = AplicacionFelicitaciones()
        app.run()
    except Exception as e:
        print(f"❌ Error crítico: {str(e)}")
        logging.basicConfig(
            filename="logs/errores_críticos_felicitaciones.log",
            level=logging.CRITICAL,
            format='%(asctime)s - [%(levelname)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.critical(f"Error crítico: {str(e)}\n{traceback.format_exc()}")