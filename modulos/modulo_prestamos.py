import customtkinter as ctk
from tkcalendar import DateEntry
import tkinter as tk
from tkinter import ttk, messagebox, TclError
from datetime import datetime
import mysql.connector
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk, ImageSequence
import io
import logging
from datetime import datetime, date
import traceback
import os
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de tema y colores
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class EstiloApp:
    """Clase para definir los colores y estilos de la aplicación"""
    COLOR_PRINCIPAL = "#E3F2FD"  # Azul muy claro para fondo
    COLOR_SECUNDARIO = "#BBDEFB"  # Azul claro para frames
    COLOR_HOVER = "#64B5F6"      # Azul medio
    COLOR_TEXTO = "#1A237E"      # Azul oscuro para texto
    COLOR_FRAMES = "#FFFFFF"     # Blanco para frames
    COLOR_HEADER = "#90CAF9"     # Azul medio para header (actualizado)

class PrestamosMemento:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state

class AplicacionPrestamos:
    def __init__(self, parent_frame=None, root=None):
        self.parent_frame = parent_frame
        self.root = root
        self.standalone = parent_frame is None
        self.state = {}  # Diccionario para almacenar el estado

        if self.standalone:
            self.root = ctk.CTk()
            self.root.title("Sistema de Gestión de Préstamos")
            self.root.geometry("1200x800")
            self.parent_frame = ctk.CTkFrame(self.root)
            self.parent_frame.pack(fill="both", expand=True)

        self.setup_window()
        self.create_gui()
        self.configurar_actualizacion_automatica()
        
        # Crear menú solo si estamos en modo standalone o si root está disponible
        if self.standalone or self.root:
            self.create_menu_bar()
        
    def setup_window(self):
        """Configuración inicial de la ventana"""
        # Configurar el frame principal para que se expanda
        self.parent_frame.configure(fg_color=EstiloApp.COLOR_PRINCIPAL)
        
        # Eliminar configuraciones previas de grid para evitar conflictos
        self.parent_frame.grid_forget() if hasattr(self.parent_frame, 'grid_forget') else None
        
        # Usar pack en lugar de grid para llenar completamente el contenedor padre
        if not self.standalone:
            self.parent_frame.pack(fill="both", expand=True)
        
        # Crear un frame contenedor principal que ocupará todo el espacio
        self.container_frame = ctk.CTkFrame(self.parent_frame, fg_color=EstiloApp.COLOR_PRINCIPAL)
        self.container_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Configurar el grid en este contenedor principal (no en el parent_frame)
        self.container_frame.grid_columnconfigure(0, weight=1)
        self.container_frame.grid_rowconfigure(0, weight=0)  # Header
        self.container_frame.grid_rowconfigure(1, weight=1)  # Contenido principal

    def create_gui(self):
        """Crear la interfaz gráfica completa"""
        print("\n=== Creando GUI de Préstamos ===")
        try:
            # Header (row 0)
            print("1. Creando header...")
            self._create_header()
            
            # Main content (row 1)
            print("2. Creando layout principal...")
            self.create_main_layout()
            
            # Asegurar que el contenido principal se expanda
            self.container_frame.grid_rowconfigure(1, weight=1)
            
            print("3. Creando frame de búsqueda...")
            self.create_search_frame()
            
            print("4. Creando frame de pagos...")
            self.create_payments_frame()
            
            print("5. Creando tabla...")
            self._create_table()
            
            # Forzar actualización de geometría
            self.container_frame.update_idletasks()
            self.parent_frame.update_idletasks()
            
            print("=== GUI creada exitosamente ===\n")
        except Exception as e:
            print(f"❌ Error creando GUI: {str(e)}")
            traceback.print_exc()

    def _create_header(self):
        """Crear header con diseño consistente y estandarizado"""
        header_frame = ctk.CTkFrame(
            self.container_frame,
            fg_color="white",
            corner_radius=10,
            height=130  # Cambiado de 200 a 120 para estandarizar
        )
        header_frame.grid(row=0, column=0, sticky="new", padx=20, pady=(10, 5))  # Ajuste de padding
        header_frame.grid_propagate(False)
        header_frame.grid_columnconfigure(1, weight=1)

        # Frame específico para el logo con dimensiones ajustadas
        logo_container = ctk.CTkFrame(
            header_frame,
            fg_color="transparent",
            width=100,  # Cambiado de 150 a 100
            height=100  # Cambiado de 150 a 100 para mantener proporción
        )
        logo_container.grid(row=0, column=0, rowspan=3, padx=(15, 10), pady=5, sticky="nsew")
        logo_container.grid_propagate(False)

        # Logo GIF animado - mantenemos la lógica pero ajustamos el tamaño
        try:
            # Debug: Imprimir rutas
            print("\nDebug de rutas:")
            print(f"Directorio actual: {os.getcwd()}")
            print(f"Directorio del módulo: {os.path.dirname(__file__)}")
            
            # Intentar diferentes rutas
            possible_paths = [
                os.path.join("resources", "icons_gifs", "logo.gif"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                            "resources", "icons_gifs", "logo.gif"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                            "resources", "icons", "logo.gif")
            ]
            
            # Intentar cada ruta posible
            gif_path = None
            for path in possible_paths:
                print(f"Intentando ruta: {path}")
                if os.path.exists(path):
                    print(f"✓ Encontrado en: {path}")
                    gif_path = path
                    break
                else:
                    print(f"✗ No encontrado en: {path}")
            
            if gif_path is None:
                raise FileNotFoundError("No se pudo encontrar logo.gif en ninguna ubicación")

            # Cargar y procesar el GIF manteniendo proporción original
            gif = Image.open(gif_path)
            frames = []
            
            # Calcular el tamaño manteniendo la proporción
            target_height = 160  # Ajustado de 200 a 90
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
            # Centrar el label en el contenedor
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
            print(f"Error detallado al cargar el logo: {str(e)}")
            print(f"Tipo de error: {type(e)}")
            if isinstance(e, FileNotFoundError):
                print(f"Directorio actual: {os.getcwd()}")
                print("Contenido del directorio resources:")
                resources_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")
                if os.path.exists(resources_dir):
                    print(os.listdir(resources_dir))

        # Títulos ajustados para mejor disposición
        title_label = ctk.CTkLabel(
            header_frame,
            text="Módulo de Préstamos - RRHH",
            font=ctk.CTkFont(size=20, weight="bold"),  # Tamaño de fuente ajustado
            text_color="black"
        )
        title_label.grid(row=0, column=1, sticky="sw", padx=(0, 10), pady=(15, 0))
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Entheus Seguridad",
            font=ctk.CTkFont(size=14),  # Tamaño de fuente ajustado
            text_color="black"
        )
        subtitle_label.grid(row=1, column=1, sticky="nw", padx=(0, 10), pady=(0, 5))
        
        copyright_label = ctk.CTkLabel(
            header_frame,
            text="© 2025 Todos los derechos reservados",
            font=ctk.CTkFont(size=12),
            text_color="black"  # Cambiado a negro
        )
        copyright_label.grid(row=2, column=1, sticky="nw", padx=(0, 10), pady=(0, 5))

    def smooth_scroll(self, widget, target_offset, current_offset=None, steps=15):
        """Realizar desplazamiento suave optimizado"""
        if current_offset is None:
            current_offset = widget.yview()[0]
        
        # Si estamos muy cerca del objetivo, saltamos directamente
        if abs(target_offset - current_offset) < 0.01:
            if isinstance(widget, ttk.Treeview):
                widget.yview_moveto(target_offset)
            else:
                widget.yview_moveto(target_offset)
            return
        
        # Cálculo de movimiento más directo
        next_offset = current_offset + (target_offset - current_offset) * 0.25
        
        if isinstance(widget, ttk.Treeview):
            widget.yview_moveto(next_offset)
        else:
            widget.yview_moveto(next_offset)
            
        # Menor delay y menos pasos
        widget.after(8, lambda: self.smooth_scroll(widget, target_offset, next_offset, steps))

    def create_main_layout(self):
        """Crear el diseño principal con scrollbar moderno"""
        # Contenedor principal con scrollbar
        scroll_container = ctk.CTkFrame(
            self.container_frame,  # Cambiado de parent_frame a container_frame
            fg_color=EstiloApp.COLOR_PRINCIPAL
        )
        scroll_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        scroll_container.grid_columnconfigure(0, weight=1)
        scroll_container.grid_rowconfigure(0, weight=1)

        # Canvas principal para el scroll
        canvas = tk.Canvas(
            scroll_container,
            bg=EstiloApp.COLOR_PRINCIPAL,
            highlightthickness=0
        )
        canvas.grid(row=0, column=0, sticky="nsew")

        # Crear scrollbar moderno usando el mismo método que los treeviews
        scrollbar = self.create_modern_scrollbar(scroll_container, canvas, "vertical")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Frame principal dentro del canvas
        self.main_frame = ctk.CTkFrame(
            canvas, 
            fg_color=EstiloApp.COLOR_PRINCIPAL
        )
        
        # Crear ventana del canvas
        canvas_window = canvas.create_window(
            (0, 0), 
            window=self.main_frame, 
            anchor="nw",
            width=scroll_container.winfo_width()
        )

        # Configurar el grid del main_frame
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)  # Search frame
        self.main_frame.grid_rowconfigure(1, weight=2)  # Payments frame
        self.main_frame.grid_rowconfigure(2, weight=2)  # History frame

        # Crear los frames internos
        self.search_and_employees_frame = ctk.CTkFrame(
            self.main_frame, 
            fg_color=EstiloApp.COLOR_HEADER
        )
        self.search_and_employees_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        self.payments_frame = ctk.CTkFrame(
            self.main_frame, 
            fg_color=EstiloApp.COLOR_HEADER
        )
        self.payments_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        self.history_frame = ctk.CTkFrame(
            self.main_frame, 
            fg_color=EstiloApp.COLOR_HEADER
        )
        self.history_frame.grid(row=2, column=0, sticky="nsew")

        # Configurar scroll
        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        def _on_mousewheel(event, canvas):
            """Maneja el evento de la rueda del ratón con verificación de widget"""
            try:
                # Verificar si el canvas aún existe y es válido
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except (tk.TclError, AttributeError, Exception) as e:
                # El canvas ya no existe, desactivar este manejador
                try:
                    # Intentar desregistrar este evento específico
                    canvas.unbind_all("<MouseWheel>")
                    canvas.unbind_all("<Shift-MouseWheel>")
                except Exception:
                    pass  # Ignorar errores de limpieza

        # Bindings
        self.main_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind_all("<MouseWheel>", lambda event: _on_mousewheel(event, canvas))

    def create_search_frame(self):
        """Crear marco de búsqueda con diseño mejorado y compacto"""
        # Frame principal - usar grid en lugar de pack para mejor control
        search_frame = ctk.CTkFrame(
            self.search_and_employees_frame,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        search_frame.pack(fill="both", expand=True, pady=(5, 2), padx=15)

        # CONTENEDOR PRINCIPAL
        container_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        container_frame.pack(fill="both", expand=True, pady=(10, 5), padx=20)

        # Título centrado
        title_label = ctk.CTkLabel(
            container_frame,
            text="Búsqueda de Empleados",
            font=('Roboto', 18, 'bold')
        )
        title_label.pack(pady=(0, 10))

        # Frame horizontal para contener búsqueda, foto y lista de empleados
        horizontal_container = ctk.CTkFrame(container_frame, fg_color="transparent")
        horizontal_container.pack(fill="both", expand=True)

        # Frame izquierdo para búsqueda y foto
        left_container = ctk.CTkFrame(horizontal_container, fg_color="transparent")
        left_container.pack(side="left", padx=(0, 10), fill="both")

        # Frame para campos
        fields_frame = ctk.CTkFrame(left_container, fg_color="transparent")
        fields_frame.pack(fill="x")

        # Canvas para la foto - Asegurar tamaño fijo y visibilidad
        self.photo_canvas = tk.Canvas(
            left_container,
            width=200,
            height=200,
            bg=EstiloApp.COLOR_FRAMES,
            highlightthickness=1
        )
        self.photo_canvas.pack(pady=10, fill="both", expand=True)

        # Frame derecho para el treeview - Usar pack con expand
        right_container = ctk.CTkFrame(horizontal_container, fg_color="transparent")
        right_container.pack(side="right", fill="both", expand=True)

        # Treeview con scrollbar
        tree_frame = ctk.CTkFrame(right_container, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True)
        
        # Configurar el grid del tree_frame
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        # Crear las variables de entrada primero
        self.entry_legajo = None
        self.entry_nombre = None

        # Configurar las columnas del grid para alineación vertical
        fields_frame.grid_columnconfigure(1, weight=1)  # La columna de los entries expande
        fields_frame.grid_columnconfigure(0, minsize=70)  # Ancho fijo para labels

        # Campos de búsqueda alineados verticalmente
        label_texts = ["Legajo:", "Apellido:"]
        entry_configs = [
            {"width": 100, "justify": "center"},
            {"width": 200, "justify": "left"}
        ]

        # Crear los campos de forma ordenada
        for idx, (label_text, config) in enumerate(zip(label_texts, entry_configs)):
            # Label alineado a la derecha
            label = ctk.CTkLabel(
                fields_frame,
                text=label_text,
                font=('Roboto', 12),
                anchor="e"  # Alineación derecha del texto
            )
            label.grid(row=idx, column=0, padx=(5, 10), pady=2, sticky="e")

            # Entry
            entry = ctk.CTkEntry(
                fields_frame,
                height=30,
                font=('Roboto', 12),
                **config
            )
            entry.grid(row=idx, column=1, padx=(0, 5), pady=2, sticky="w")

            # Asignar referencias
            if label_text == "Legajo:":
                self.entry_legajo = entry
            else:
                self.entry_nombre = entry

        # Frame para botones
        button_frame = ctk.CTkFrame(left_container, fg_color="transparent")
        button_frame.pack(pady=5)

        ctk.CTkButton(
            button_frame,
            text="Buscar",
            command=self.buscar_empleado_ui,
            width=100,
            height=30,
            font=('Roboto', 12)
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text="Limpiar",
            command=self.limpiar_todo,
            width=100,
            height=30,
            font=('Roboto', 12)
        ).pack(side="left", padx=5)

        # Frame para foto
        photo_container = ctk.CTkFrame(left_container, fg_color="transparent")
        photo_container.pack()

        # Etiqueta para el nombre del empleado
        self.photo_label = ctk.CTkLabel(
            photo_container,
            text="",
            font=('Roboto', 12)
        )
        self.photo_label.pack(pady=(0, 5))

        # Frame derecho para lista de empleados
        tree_container = ctk.CTkFrame(horizontal_container, fg_color="transparent")
        tree_container.pack(side="left", fill="both", expand=True)

        # Crear el TreeView de empleados
        columns = ("Legajo", "Nombre", "Apellido")
        self.lista_empleados = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            height=10,
            style="Custom.Treeview"
        )

        # Configurar columnas
        widths = {"Legajo": 80, "Nombre": 150, "Apellido": 150}
        for col in columns:
            self.lista_empleados.heading(col, text=col, anchor="center")
            self.lista_empleados.column(col, width=widths[col], anchor="center")

        # Agregar scrollbars modernos
        y_scrollbar = self.create_modern_scrollbar(tree_container, self.lista_empleados, "vertical")
        
        # Colocar componentes
        self.lista_empleados.pack(side="left", fill="both", expand=True)
        y_scrollbar.pack(side="right", fill="y")

        # Agregar menú contextual y bindings
        self.menu_empleados = tk.Menu(self.parent_frame, tearoff=0)
        self.menu_empleados.add_command(label="Registrar Préstamo", command=self.mostrar_ventana_prestamo)
        self.menu_empleados.add_command(label="Ver Cuotas", command=self.mostrar_cuotas)
        
        self.lista_empleados.bind("<Button-3>", self.mostrar_menu_empleados)
        self.lista_empleados.bind("<Double-1>", lambda e: self.mostrar_cuotas())

        # Configurar validaciones y eventos
        def validate_legajo(P):
            return len(P) <= 5 and (P.isdigit() or P == "")
        
        vcmd = (self.parent_frame.register(validate_legajo), '%P')
        self.entry_legajo.configure(validate="key", validatecommand=vcmd)
        
        # Eventos Enter
        self.entry_legajo.bind("<Return>", lambda e: self.buscar_empleado_ui())
        self.entry_nombre.bind("<Return>", lambda e: self.buscar_empleado_ui())

        # Mostrar foto default inicial
        self.mostrar_foto_default()

    def limpiar_todo(self):
        """Limpiar todos los elementos de la interfaz"""
        # Limpiar campos de entrada
        self.entry_legajo.delete(0, 'end')
        self.entry_nombre.delete(0, 'end')
        
        # Limpiar TreeViews
        self.lista_empleados.delete(*self.lista_empleados.get_children())
        self.lista_cuotas.delete(*self.lista_cuotas.get_children())
        self.tree.delete(*self.tree.get_children())
        
        # Limpiar canvas de foto
        self.mostrar_foto_default()
        
        # Limpiar etiqueta de nombre
        self.photo_label.configure(text="")

        # Dar foco al campo de legajo
        self.entry_legajo.focus()

    def mostrar_foto_empleado(self, legajo):
        """Mostrar la foto del empleado en el canvas"""
        try:
            db = self.conectar_db()
            cursor = db.cursor(dictionary=True)
            
            # Obtener foto y nombre del empleado
            cursor.execute("""
                SELECT foto, apellido_nombre
                FROM personal 
                WHERE legajo = %s
            """, (legajo,))
            
            result = cursor.fetchone()
            
            if result and result['foto']:
                try:
                    image_data = io.BytesIO(result['foto'])
                    image = Image.open(image_data)
                    
                    # Aumentar el tamaño máximo de la imagen
                    image.thumbnail((200, 250), Image.Resampling.LANCZOS)  # Aumentado de 150,200 a 200,250
                    
                    # Crear un PhotoImage
                    photo = ImageTk.PhotoImage(image)
                    
                    # Obtener dimensiones del canvas
                    canvas_width = self.photo_canvas.winfo_width()
                    canvas_height = self.photo_canvas.winfo_height()
                    
                    # Calcular posición centrada
                    x = canvas_width // 2
                    y = canvas_height // 2
                    
                    # Limpiar canvas y mostrar nueva imagen
                    self.photo_canvas.delete("all")
                    self.photo_canvas.create_image(
                        x,  # Centrado horizontalmente
                        y,  # Centrado verticalmente
                        image=photo,
                        anchor="center"
                    )
                    self.photo_canvas.image = photo  # Mantener referencia
                    
                    # Actualizar etiqueta con nombre
                    self.photo_label.configure(text=result['apellido_nombre'])
                    
                except Exception as e:
                    print(f"Error procesando imagen: {e}")
                    self.mostrar_foto_default()
            else:
                self.mostrar_foto_default()
                
        except mysql.connector.Error as err:
            print(f"Error de base de datos: {err}")
            self.mostrar_foto_default()
        finally:
            if 'db' in locals():
                db.close()

    def mostrar_foto_default(self):
        """Mostrar imagen por defecto cuando no hay foto"""
        self.photo_canvas.delete("all")
        
        # Obtener dimensiones del canvas o usar valores por defecto
        canvas_width = self.photo_canvas.winfo_reqwidth() or 200  # Usar 200 si no hay width
        canvas_height = self.photo_canvas.winfo_reqheight() or 200  # Usar 200 si no hay height
        
        # Centrar el texto
        x = canvas_width / 2
        y = canvas_height / 2
        
        self.photo_canvas.create_text(130, 90, text="👤", font=("Segoe UI Emoji", 90), fill="#64B5F6", tags="user_emoji", anchor="center")


    def create_modern_scrollbar(self, parent, tree, orient="vertical"):
        """Crear scrollbar moderno para Treeview con scroll suave"""
        def smooth_scroll_command(*args):
            if len(args) == 2:
                if orient == "vertical":
                    tree.yview(*args)
                else:
                    tree.xview(*args)
            else:
                try:
                    if orient == "vertical":
                        tree.yview_moveto(args[0])
                    else:
                        tree.xview_moveto(args[0])
                except (ValueError, TclError):
                    pass

        scrollbar = ctk.CTkScrollbar(
            parent,
            orientation=orient,
            command=smooth_scroll_command,
            button_color=EstiloApp.COLOR_HOVER,
            button_hover_color=EstiloApp.COLOR_TEXTO,
            fg_color="transparent"
        )
        
        if orient == "vertical":
            tree.configure(yscrollcommand=scrollbar.set)
        else:
            tree.configure(xscrollcommand=scrollbar.set)
            
        return scrollbar

    def create_table_container(self, parent, title, columns, height=10):
        """Función auxiliar para crear contenedores de tabla con diseño consistente"""
        container = ctk.CTkFrame(parent, fg_color=EstiloApp.COLOR_FRAMES)
        container.pack(fill="both", expand=True, padx=15, pady=10)

        # Título
        ctk.CTkLabel(
            container,
            text=title,
            font=('Roboto', 18, 'bold')
        ).pack(pady=(15, 10))

        # Frame para la tabla
        table_frame = ctk.CTkFrame(container, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Crear Treeview
        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=height,
            style="Custom.Treeview"
        )

        # Configurar estilo de fuente más grande
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            background=EstiloApp.COLOR_PRINCIPAL,
            foreground="black",
            fieldbackground=EstiloApp.COLOR_PRINCIPAL,
            rowheight=30,
            font=('Roboto', 13)  # Aumentar tamaño de fuente
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=EstiloApp.COLOR_SECUNDARIO,
            foreground="black",
            font=('Roboto', 13, 'bold')  # Aumentar tamaño de fuente del encabezado
        )

        # Scrollbars modernos
        y_scrollbar = self.create_modern_scrollbar(table_frame, tree, "vertical")
        x_scrollbar = self.create_modern_scrollbar(table_frame, tree, "horizontal")

        # Grid layout mejorado
        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        # Configurar expansión
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        # Agregar binding para el mousewheel
        def handle_scroll(event):
            tree = event.widget
            delta = event.delta / 600  # Aumentar sensibilidad
            
            if event.state & 4:  # Shift presionado
                current_view = tree.xview()[0]
                target_view = max(0, min(1, current_view - delta))
                self.smooth_scroll(tree, target_view)
            else:
                current_view = tree.yview()[0]
                target_view = max(0, min(1, current_view - delta))
                self.smooth_scroll(tree, target_view)
            return "break"

        tree.bind("<MouseWheel>", handle_scroll)
        tree.bind("<Shift-MouseWheel>", handle_scroll)

        return container, tree

    def create_employee_table(self):
        """Crear tabla de empleados usando el contenedor mejorado"""
        columns = ("Legajo", "Nombre", "Apellido")
        container, self.lista_empleados = self.create_table_container(
            self.search_and_employees_frame,
            "Listado de Empleados",
            columns
        )

        # Configurar columnas con anchos apropiados
        widths = {"Legajo": 80, "Nombre": 150, "Apellido": 150}
        for col in columns:
            self.lista_empleados.heading(col, text=col, anchor="center")
            self.lista_empleados.column(col, width=widths[col], anchor="center")

        # Agregar menú contextual (eliminado el botón "Ver Cuotas Pendientes")
        self.menu_empleados = tk.Menu(self.parent_frame, tearoff=0)
        self.menu_empleados.add_command(label="Registrar Préstamo", command=self.mostrar_ventana_prestamo)
        self.menu_empleados.add_command(label="Ver Cuotas", command=self.mostrar_cuotas)
        
        # Vincular eventos
        self.lista_empleados.bind("<Button-3>", self.mostrar_menu_empleados)
        self.lista_empleados.bind("<Double-1>", lambda e: self.mostrar_cuotas())

    def create_payments_frame(self):
        """Crear marco de pagos con diseño mejorado"""
        payments_container = ctk.CTkFrame(
            self.payments_frame,  # Cambiar el parent frame
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        payments_container.pack(fill="both", expand=True, padx=15, pady=10)

        # Título del marco de pagos
        title_label = ctk.CTkLabel(
            payments_container,
            text="Cuotas Pendientes",
            font=('Roboto', 18, 'bold')
        )
        title_label.pack(pady=(15, 10))

        # Contenedor para la tabla de cuotas
        tree_container = ctk.CTkFrame(payments_container, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Crear y configurar Treeview para cuotas
        columns = ("ID", "Número de Cuota", "Monto", "Fecha de Vencimiento", "Estado")
        self.lista_cuotas = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Custom.Treeview",
            height=10
        )

        # Configurar columnas
        for col in columns:
            self.lista_cuotas.heading(col, text=col, anchor="center")
            self.lista_cuotas.column(col, width=120, anchor="center")

        # Agregar scrollbars
        y_scrollbar = self.create_modern_scrollbar(tree_container, self.lista_cuotas, "vertical")
        x_scrollbar = self.create_modern_scrollbar(tree_container, self.lista_cuotas, "horizontal")

        # Colocar componentes
        self.lista_cuotas.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        # Agregar binding para el mousewheel específico para este Treeview
        def handle_scroll(event):
            if event.state & 4:  # Shift presionado
                self.lista_cuotas.xview_scroll(int(-1*(event.delta/120)), "units")
            else:
                self.lista_cuotas.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"  # Prevenir que el evento se propague

        self.lista_cuotas.bind("<MouseWheel>", handle_scroll)
        self.lista_cuotas.bind("<Shift-MouseWheel>", handle_scroll)

        # Agregar menú contextual para la lista de cuotas
        self.menu_cuotas = tk.Menu(self.parent_frame, tearoff=0)
        self.menu_cuotas.add_command(label="Pagar Cuota", command=self.mostrar_ventana_pago)
        self.menu_cuotas.add_command(label="Pagar Todas las Cuotas", command=self.mostrar_ventana_pago_total_prestamo)
        
        # Vincular eventos
        self.lista_cuotas.bind("<Button-3>", self.mostrar_menu_cuotas)
        self.lista_cuotas.bind("<Double-1>", lambda e: self.mostrar_ventana_pago())

    def create_loan_registration_form(self):
        """Crear formulario de registro de préstamos"""
        loan_frame = ctk.CTkFrame(
            self.right_frame,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        loan_frame.pack(fill="both", expand=True, padx=15, pady=(10, 0))

        # Se elimina el título y se deja el frame vacío para mantener el espacio visual

    def _create_table(self):
        """Crear tabla de préstamos"""
        table_frame = ctk.CTkFrame(
            self.history_frame,
            fg_color=EstiloApp.COLOR_FRAMES,
            corner_radius=10
        )
        table_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Configurar expansión del frame de la tabla
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)

        # Título de la tabla
        title_label = ctk.CTkLabel(
            table_frame,
            text="Historial de Préstamos",
            font=('Roboto', 18, 'bold')
        )
        title_label.pack(pady=(15, 10))

        # Contenedor para la tabla
        tree_container = ctk.CTkFrame(table_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Estilo para el Treeview
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            background=EstiloApp.COLOR_PRINCIPAL,
            foreground="black",
            fieldbackground=EstiloApp.COLOR_PRINCIPAL,
            rowheight=30
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=EstiloApp.COLOR_SECUNDARIO,
            foreground="black",
            font=('Roboto', 12, 'bold')
        )

        # Crear Treeview
        self.tree = ttk.Treeview(
            tree_container,
            columns=self.get_history_columns(),
            show="headings",
            style="Custom.Treeview"
        )

        # Configurar columnas
        for col, config in self.get_history_column_config().items():
            self.tree.heading(col, text=config["text"], anchor="center")
            self.tree.column(col, width=config["width"], anchor="center")

        # Scrollbars modernos
        y_scrollbar = self.create_modern_scrollbar(tree_container, self.tree, "vertical")
        x_scrollbar = self.create_modern_scrollbar(tree_container, self.tree, "horizontal")

        # Colocar componentes
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        # Configurar expansión
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        # Agregar binding para el mousewheel
        def handle_scroll(event):
            if event.state & 4:  # Shift presionado
                self.tree.xview_scroll(int(-1*(event.delta/120)), "units")
            else:
                self.tree.yview_scroll(int(-1*(event.delta/120)), "units")

        self.tree.bind("<MouseWheel>", handle_scroll)
        self.tree.bind("<Shift-MouseWheel>", handle_scroll)

        # Agregar menú contextual para el historial
        self.menu_historial = tk.Menu(self.parent_frame, tearoff=0)
        self.menu_historial.add_command(
            label="Ver Historial de Pagos", 
            command=self.mostrar_historial_pagos
        )
        
        # Vincular el menú contextual al treeview
        self.tree.bind("<Button-3>", self.mostrar_menu_historial)

    # Métodos auxiliares para _create_table
    def get_history_columns(self):
        return ("id_prestamos", "legajo", "monto_total", "cuotas", "fecha_inicio", "motivo", "estado")

    def get_history_column_config(self):
        return {
            "id_prestamos": {"text": "ID", "width": 80},
            "legajo": {"text": "Legajo", "width": 100},
            "monto_total": {"text": "Monto Total", "width": 120},
            "cuotas": {"text": "Cuotas", "width": 100},
            "fecha_inicio": {"text": "Fecha Inicio", "width": 120},
            "motivo": {"text": "Motivo", "width": 200},
            "estado": {"text": "Estado", "width": 100}
        }

    def format_date_for_display(self, fecha):
        """Convertir fecha a formato dd-nombre_mes-de-yyyy"""
        meses = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
            5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
            9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }
        return f"{fecha.day} {meses[fecha.month]} de {fecha.year}"

    def format_date_for_mysql(self, fecha):
        """Convertir fecha al formato de MySQL (yyyy-mm-dd)"""
        return fecha.strftime('%Y-%m-%d')

    def cargar_historial_prestamos(self, legajo=None):
        """Cargar datos en el historial de préstamos para un legajo específico"""
        try:
            db = self.conectar_db()
            cursor = db.cursor(dictionary=True)
            
            # Limpiar la tabla
            self.tree.delete(*self.tree.get_children())
            
            if legajo is None:
                return  # Si no hay legajo, dejar la tabla vacía
            
            query = """
                SELECT id_prestamos, legajo, monto_total, cuotas, fecha_inicio, motivo,
                       CASE 
                           WHEN EXISTS (SELECT 1 FROM pagos p WHERE p.id_prestamos = pr.id_prestamos AND p.estado = 'Pendiente')
                           THEN 'Pendiente'
                           ELSE 'Pagado'
                       END as estado
                FROM prestamos pr
                WHERE legajo = %s
            """
            cursor.execute(query, (legajo,))
            prestamos = cursor.fetchall()
            
            for prestamo in prestamos:
                fecha_formateada = self.format_date_for_display(prestamo['fecha_inicio'])
                self.tree.insert("", "end", values=(
                    prestamo['id_prestamos'],
                    prestamo['legajo'],
                    prestamo['monto_total'],
                    prestamo['cuotas'],
                    fecha_formateada,  # Fecha formateada
                    prestamo['motivo'],
                    prestamo['estado']
                ))
                
        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error de base de datos: {err}")
        finally:
            if 'db' in locals():
                db.close()

    def conectar_db(self):
        """Establecer conexión a la base de datos usando variables de entorno"""
        return mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_DATABASE')
        )
        
    def buscar_empleado_ui(self):
        self.lista_empleados.delete(*self.lista_empleados.get_children())
        nombre = self.entry_nombre.get()
        legajo = self.entry_legajo.get()
        
        try:
            db = self.conectar_db()
            cursor = db.cursor(dictionary=True)
            
            if legajo:
                cursor.execute("""
                    SELECT legajo, apellido_nombre
                    FROM personal 
                    WHERE legajo = %s
                """, (legajo,))
            elif nombre:
                cursor.execute("""
                    SELECT legajo, apellido_nombre
                    FROM personal 
                    WHERE apellido_nombre LIKE %s
                """, (f"%{nombre}%",))
            
            empleados = cursor.fetchall()
            
            for emp in empleados:
                # Dividir apellido_nombre en dos columnas para la visualización
                nombre_completo = emp['apellido_nombre'].split(',') if ',' in emp['apellido_nombre'] else ['', emp['apellido_nombre']]
                apellido = nombre_completo[0].strip()
                nombre = nombre_completo[1].strip() if len(nombre_completo) > 1 else ''
                
                self.lista_empleados.insert("", "end", 
                                          values=(emp['legajo'], nombre, apellido))
                
                # Si solo hay un empleado, mostrar su foto
                if len(empleados) == 1:
                    self.mostrar_foto_empleado(emp['legajo'])
                else:
                    self.mostrar_foto_default()

            # Agregar binding al Treeview para mostrar foto al seleccionar
            self.lista_empleados.bind('<<TreeviewSelect>>', self.on_empleado_select)

            if not empleados:
                messagebox.showinfo("Búsqueda", "No se encontraron empleados")
                
        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error de base de datos: {err}")
        finally:
            db.close()

    def on_empleado_select(self, event):
        """Manejador de evento para selección en el Treeview"""
        selected = self.lista_empleados.selection()
        if selected:
            item = self.lista_empleados.item(selected[0])
            legajo = item['values'][0]
            self.mostrar_foto_empleado(legajo)
            
    def mostrar_cuotas(self):
        """Mostrar cuotas y cargar historial del empleado seleccionado"""
        seleccionado = self.lista_empleados.focus()
        if not seleccionado:
            messagebox.showerror("Error", "Por favor, seleccione un empleado")
            return
            
        item = self.lista_empleados.item(seleccionado)
        legajo = item['values'][0]
        
        # Cargar el historial de préstamos del empleado
        self.cargar_historial_prestamos(legajo)
        
        # Resto del código para mostrar cuotas
        try:
            db = self.conectar_db()
            cursor = db.cursor(dictionary=True)
            
            # Actualizar primero las cuotas vencidas
            cursor.execute("""
                UPDATE pagos
                SET estado = 'Pagado',
                    fecha_pago = fecha_vencimiento
                WHERE estado = 'Pendiente'
                AND fecha_vencimiento <= CURDATE()
            """)
            db.commit()

            query = """
                SELECT p.id_prestamos, p.numero_cuota, p.monto_cuota, p.fecha_vencimiento, p.estado
                FROM pagos p
                JOIN prestamos pr ON p.id_prestamos = pr.id_prestamos
                WHERE pr.legajo = %s AND p.estado = 'Pendiente'
            """
            cursor.execute(query, (legajo,))
            cuotas = cursor.fetchall()
            
            self.lista_cuotas.delete(*self.lista_cuotas.get_children())
            
            for cuota in cuotas:
                fecha_formateada = self.format_date_for_display(cuota['fecha_vencimiento'])
                self.lista_cuotas.insert("", "end", values=(
                    cuota['id_prestamos'],
                    cuota['numero_cuota'],
                    f"${cuota['monto_cuota']:.2f}",
                    fecha_formateada,  # Fecha formateada
                    cuota['estado']
                ))
                
        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error de base de datos: {err}")
        finally:
            db.close()

    def registrar_prestamo_ui(self, legajo, monto_total, cuotas, fecha_inicio, motivo):
        """Registrar préstamo con los datos proporcionados"""
        if not (legajo and
         monto_total and cuotas and fecha_inicio):
           messagebox.showerror("Error", "Todos los campos son obligatorios.")
           return

        # Mostrar mensaje informativo sobre la acreditación automática
        mensaje = """
        INFORMACIÓN IMPORTANTE:
        
        • El monto de cada cuota se calcula automáticamente dividiendo el\n 
          monto total 
          por la cantidad de cuotas ingresadas.

        • Las cuotas se generan mensualmente a partir de la fecha de inicio.

        • El estado de las cuotas cambiará automáticamente a 'Pagado'\n 
         cuando llegue 
          su fecha de vencimiento.

        • La fecha de vencimiento de cada cuota se establece tomando\n 
          como referencia
          el día seleccionado en 'Fecha Inicio'.
        """
        messagebox.showinfo("Acreditación y Pagos Automáticos", mensaje)

        try:
            db = self.conectar_db()
            cursor = db.cursor()

            # Validar que el legajo existe
            cursor.execute("SELECT COUNT(*) FROM personal WHERE legajo = %s", (legajo,))
            if cursor.fetchone()[0] == 0:
               messagebox.showerror("Error", "El legajo no existe.")
               return

            # Insertar el préstamo
            fecha_mysql = self.format_date_for_mysql(fecha_inicio)
            query = """
                INSERT INTO prestamos (legajo, monto_total, cuotas, fecha_inicio, motivo)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (legajo, monto_total, cuotas, fecha_mysql, motivo))
            db.commit()

            # Obtener el ID del préstamo recién insertado
            id_prestamo = cursor.lastrowid

            # Llamar al procedimiento almacenado para generar las cuotas
            cursor.callproc('generar_cuotas', (id_prestamo, float(monto_total), int(cuotas), fecha_inicio))
            db.commit()

            messagebox.showinfo("Éxito", "Préstamo registrado y cuotas generadas correctamente.")
            
            # Actualizar la vista de cuotas
            self.mostrar_cuotas()

        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error de base de datos: {err}")
        finally:
            db.close()

    def clear_loan_form(self):
        self.entry_legajo_prestamo.delete(0, 'end')
        self.entry_monto_total.delete(0, 'end')
        self.entry_cuotas.delete(0, 'end')
        self.entry_motivo.delete(0, 'end')
        self.fecha_inicio_prestamo.set_date(datetime.now())        
        
            
    def registrar_pago_ui(self):
    # Obtener la cuota seleccionada
        seleccionado = self.lista_cuotas.focus()
        if not seleccionado:
            messagebox.showerror("Error", "Por favor, seleccione una cuota")
            return

    # Obtener los valores de la cuota seleccionada
        item = self.lista_cuotas.item(seleccionado)
        id_prestamo = item['values'][0]  # ID del préstamo
        numero_cuota = item['values'][1]  # Número de cuota
        fecha_vencimiento = item['values'][3]  # Fecha de vencimiento

        try:
        # Obtener la fecha de pago
            fecha_pago = self.fecha_pago.get_date()
        
        # Conexión a la base de datos
            db = self.conectar_db()
            cursor = db.cursor()

        # Actualizar el estado de la cuota específica a 'Pagado'
            query = """
                UPDATE pagos 
                SET estado = 'Pagado', fecha_pago = %s 
                WHERE id_prestamos = %s 
                AND numero_cuota = %s 
                AND estado = 'Pendiente'
            """
            cursor.execute(query, (fecha_pago.strftime('%Y-%m-%d'), id_prestamo, numero_cuota))
        
        # Necesitamos hacer commit para que los cambios se apliquen
            db.commit()

            if cursor.rowcount > 0:
                messagebox.showinfo("Éxito", f"Pago de la cuota {numero_cuota} registrado correctamente")
            else:
                messagebox.showwarning("Advertencia", "No se pudo registrar el pago. La cuota podría estar ya pagada.")

        # Actualizar la vista de cuotas
            self.mostrar_cuotas()

        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error al registrar el pago: {err}")
        finally:
            if 'db' in locals():
                db.close()

    def pagar_todas_cuotas_ui(self):
    # Obtener el empleado seleccionado
        seleccionado = self.lista_empleados.focus()
        if not seleccionado:
            messagebox.showerror("Error", "Por favor, seleccione un empleado")
            return

    # Obtener el legajo del empleado
        item = self.lista_empleados.item(seleccionado)
        legajo = item['values'][0]

        try:
        # Obtener la fecha de pago
            fecha_pago = self.fecha_pago.get_date()
        
        # Conexión a la base de datos
            db = self.conectar_db()
            cursor = db.cursor()

        # Primero verificamos si hay cuotas pendientes
            cursor.execute("""
               SELECT COUNT(*) 
               FROM pagos p
               JOIN prestamos pr ON p.id_prestamos = pr.id_prestamos
               WHERE pr.legajo = %s AND p.estado = 'Pendiente'
            """, (legajo,))
        
            cantidad_pendientes = cursor.fetchone()[0]
            if cantidad_pendientes == 0:
                messagebox.showinfo("Info", "No hay cuotas pendientes para pagar")
                return

        # Obtener todos los préstamos del empleado con cuotas pendientes
            cursor.execute("""
               SELECT DISTINCT p.id_prestamos
               FROM pagos p
               JOIN prestamos pr ON p.id_prestamos = pr.id_prestamos
               WHERE pr.legajo = %s AND p.estado = 'Pendiente'
            """, (legajo,))
        
            prestamos = cursor.fetchall()
        
        # Pagar todas las cuotas de cada préstamo
            for (id_prestamo,) in prestamos:
                cursor.callproc('pagar_todas_cuotas', 
                          (id_prestamo, fecha_pago.strftime('%Y-%m-%d')))
            db.commit()

            messagebox.showinfo("Éxito", 
                          f"Se han pagado todas las cuotas pendientes del empleado {legajo}")
        
        # Actualizar la vista de cuotas
            self.mostrar_cuotas()

        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error al pagar las cuotas: {err}")
        finally:
            if 'db' in locals():
                db.close()  
            
    def mostrar_menu_empleados(self, event):
        """Mostrar menú contextual de empleados"""
        # Verificar si hay un empleado seleccionado
        if self.lista_empleados.selection():
            self.menu_empleados.post(event.x_root, event.y_root)

    def mostrar_menu_cuotas(self, event):
        """Mostrar menú contextual de cuotas"""
        if self.lista_cuotas.selection():
            self.menu_cuotas.post(event.x_root, event.y_root)

    def mostrar_ventana_prestamo(self):
        """Mostrar ventana flotante para registrar préstamo"""
        ventana = tk.Toplevel(self.parent_frame)
        ventana.title("Registrar Préstamo")
        ventana.geometry("600x950")
        
        # Centrar la ventana
        ventana.geometry(f"+{self.parent_frame.winfo_x() + 50}+{self.parent_frame.winfo_y() + 50}")
        
        # Crear frame del formulario con más espacio
        frame = ctk.CTkFrame(ventana)
        frame.pack(fill="both", expand=True, padx=40, pady=40)
        
        # Obtener datos del empleado seleccionado
        item = self.lista_empleados.item(self.lista_empleados.selection()[0])
        legajo = item['values'][0]
        
        # Campos del formulario
        ctk.CTkLabel(frame, text=f"Legajo: {legajo}").pack(pady=5)
        
        # Configurar estilo para el DateEntry
        style = ttk.Style()
        style.configure(
            'Custom.DateEntry',
            fieldbackground='white',
            background='white',
            foreground='black',
            arrowcolor='black',
            font=('Roboto', 12)
        )
        
        campos = [
            ("Monto Total:", ctk.CTkEntry(frame)),
            ("Cuotas:", ctk.CTkEntry(frame)),
            ("Fecha Inicio:", DateEntry(
                frame,
                style='Custom.DateEntry',
                font=('Roboto', 12),
                width=20,
                date_pattern='dd/mm/yyyy'  # Cambiar el patrón de fecha
            )),
            ("Motivo:", ctk.CTkEntry(frame))
        ]
        
        for label, widget in campos:
            ctk.CTkLabel(frame, text=label).pack(pady=5)
            widget.pack(pady=5)
            
        # Botón guardar
        ctk.CTkButton(
            frame,
            text="Guardar",
            command=lambda: self.guardar_prestamo(ventana, legajo, *[w for _, w in campos])
        ).pack(pady=20)

        # Actualizar el texto informativo para que sea más claro
        info_text = """
        INFORMACIÓN IMPORTANTE:

        • El monto de cada cuota se calcula automáticamente dividiendo el monto total por la cantidad de cuotas ingresadas.

        • Las cuotas se generan mensualmente a partir de la fecha de inicio.

        • El estado de las cuotas cambiará automáticamente a 'Pagado' cuando llegue su fecha de vencimiento.

        • La fecha de vencimiento de cada cuota se establece tomando como referencia el día seleccionado en 'Fecha Inicio'.
        """
        
        info_label = ctk.CTkLabel(
            frame,
            text=info_text,
            wraplength=400,
            justify="left",
            text_color="#344767",  # Color oscuro más legible
            font=('Roboto', 12)
        )
        info_label.pack(pady=20)

    def mostrar_ventana_pago(self):
        """Mostrar ventana flotante para registrar pago"""
        ventana = tk.Toplevel(self.parent_frame)
        ventana.title("Registrar Pago")
        ventana.geometry("500x500")  # Ventana más grande
        
        # Centrar la ventana
        ventana.geometry(f"+{self.parent_frame.winfo_x() + 50}+{self.parent_frame.winfo_y() + 50}")
        
        frame = ctk.CTkFrame(ventana)
        frame.pack(fill="both", expand=True, padx=40, pady=40)
        
        # Obtener datos de la cuota seleccionada
        item = self.lista_cuotas.item(self.lista_cuotas.selection()[0])
        
        # Mostrar información de la cuota
        ctk.CTkLabel(frame, text=f"Cuota N°: {item['values'][1]}").pack(pady=5)
        ctk.CTkLabel(frame, text=f"Monto: {item['values'][2]}").pack(pady=5)
        
        # Campo fecha de pago
        ctk.CTkLabel(frame, text="Fecha de Pago:").pack(pady=5)
        fecha_pago = DateEntry(frame)
        fecha_pago.pack(pady=5)
        
        # Botón confirmar
        ctk.CTkButton(
            frame,
            text="Confirmar Pago",
            command=lambda: self.confirmar_pago(ventana, item['values'][0], item['values'][1], fecha_pago)
        ).pack(pady=20)

    def mostrar_ventana_pago_total(self):
        """Mostrar ventana flotante para pago total"""
        ventana = tk.Toplevel(self.parent_frame)
        ventana.title("Pago Total")
        ventana.geometry("500x500")  # Ventana más grande
        
        # Centrar la ventana
        ventana.geometry(f"+{self.parent_frame.winfo_x() + 50}+{self.parent_frame.winfo_y() + 50}")
        
        frame = ctk.CTkFrame(ventana)
        frame.pack(fill="both", expand=True, padx=40, pady=40)
        
        # Obtener legajo del empleado
        item = self.lista_empleados.item(self.lista_empleados.selection()[0])
        legajo = item['values'][0]
        
        ctk.CTkLabel(frame, text="Fecha de Pago Total:").pack(pady=5)
        fecha_pago = DateEntry(frame)
        fecha_pago.pack(pady=5)
        
        ctk.CTkButton(
            frame,
            text="Confirmar Pago Total",
            command=lambda: self.confirmar_pago_total(ventana, legajo, fecha_pago)
        ).pack(pady=20)

    def mostrar_ventana_pago_total_prestamo(self):
        """Mostrar ventana flotante para pagar todas las cuotas de un préstamo"""
        # Obtener la cuota seleccionada
        seleccionado = self.lista_cuotas.selection()
        if not seleccionado:
            messagebox.showerror("Error", "Por favor, seleccione una cuota")
            return
            
        item = self.lista_cuotas.item(seleccionado[0])
        id_prestamo = item['values'][0]  # ID del préstamo
        
        # Crear ventana de diálogo
        ventana = tk.Toplevel(self.parent_frame)
        ventana.title("Pagar Todas las Cuotas")
        ventana.geometry("400x400")
        
        # Centrar la ventana
        ventana.geometry(f"+{self.parent_frame.winfo_x() + 50}+{self.parent_frame.winfo_y() + 50}")
        
        # Frame principal
        frame = ctk.CTkFrame(ventana)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Título
        ctk.CTkLabel(
            frame,
            text="Pagar Todas las Cuotas Pendientes",
            font=('Roboto', 16, 'bold')
        ).pack(pady=10)
        
        # Información del préstamo
        ctk.CTkLabel(
            frame,
            text=f"ID Préstamo: {id_prestamo}",
            font=('Roboto', 12)
        ).pack(pady=5)
        
        # Campo fecha de pago
        ctk.CTkLabel(frame, text="Fecha de Pago:").pack(pady=5)
        fecha_pago = DateEntry(frame)
        fecha_pago.pack(pady=10)
        
        # Mensaje de advertencia
        mensaje = "Esta acción marcará todas las cuotas pendientes como pagadas."
        ctk.CTkLabel(
            frame,
            text=mensaje,
            text_color="red",
            wraplength=300
        ).pack(pady=20)
        
        # Botón confirmar
        ctk.CTkButton(
            frame,
            text="Confirmar Pago Total",
            command=lambda: self.confirmar_pago_total_prestamo(ventana, id_prestamo, fecha_pago)
        ).pack(pady=10)

    def guardar_prestamo(self, ventana, legajo, monto, cuotas, fecha, motivo):
        """Guardar préstamo desde ventana flotante"""
        try:
            # Obtener los valores de los widgets
            monto_valor = monto.get()
            cuotas_valor = cuotas.get()
            fecha_valor = fecha.get_date()
            motivo_valor = motivo.get()
            
            # Registrar el préstamo directamente
            self.registrar_prestamo_ui(
                legajo=legajo,
                monto_total=monto_valor,
                cuotas=cuotas_valor,
                fecha_inicio=fecha_valor,
                motivo=motivo_valor
            )
            
            # Cerrar la ventana
            ventana.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar el préstamo: {str(e)}")

    def confirmar_pago(self, ventana, id_prestamo, numero_cuota, fecha_pago):
        """Confirmar pago de cuota"""
        try:
            # Obtener la fecha de pago
            fecha_mysql = self.format_date_for_mysql(fecha_pago.get_date())
            
            db = self.conectar_db()
            cursor = db.cursor()

            # Actualizar el estado de la cuota
            query = """
                UPDATE pagos 
                SET estado = 'Pagado', fecha_pago = %s 
                WHERE id_prestamos = %s 
                AND numero_cuota = %s 
                AND estado = 'Pendiente'
            """
            cursor.execute(query, (fecha_mysql, id_prestamo, numero_cuota))
            db.commit()

            if cursor.rowcount > 0:
                messagebox.showinfo("Éxito", f"Pago de la cuota {numero_cuota} registrado correctamente")
                ventana.destroy()
                self.mostrar_cuotas()  # Actualizar vista de cuotas
            else:
                messagebox.showwarning("Advertencia", "No se pudo registrar el pago")

        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error al registrar el pago: {err}")
        finally:
            if 'db' in locals():
                db.close()

    def confirmar_pago_total(self, ventana, legajo, fecha_pago):
        """Confirmar pago total de cuotas"""
        try:
            fecha_mysql = self.format_date_for_mysql(fecha_pago.get_date())
            db = self.conectar_db()
            cursor = db.cursor()

            # Obtener préstamos con cuotas pendientes
            cursor.execute("""
               SELECT DISTINCT p.id_prestamos
               FROM pagos p
               JOIN prestamos pr ON p.id_prestamos = pr.id_prestamos
               WHERE pr.legajo = %s AND p.estado = 'Pendiente'
            """, (legajo,))
            
            prestamos = cursor.fetchall()
            
            if not prestamos:
                messagebox.showinfo("Info", "No hay cuotas pendientes para pagar")
                ventana.destroy()
                return

            # Pagar todas las cuotas
            for (id_prestamo,) in prestamos:
                cursor.callproc('pagar_todas_cuotas', 
                          (id_prestamo, fecha_mysql))
            db.commit()

            messagebox.showinfo("Éxito", 
                          f"Se han pagado todas las cuotas pendientes del empleado {legajo}")
            ventana.destroy()
            self.mostrar_cuotas()  # Actualizar vista de cuotas

        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error al realizar el pago total: {err}")
        finally:
            if 'db' in locals():
                db.close()

    def confirmar_pago_total_prestamo(self, ventana, id_prestamo, fecha_pago):
        """Confirmar pago total de todas las cuotas de un préstamo"""
        try:
            fecha_mysql = self.format_date_for_mysql(fecha_pago.get_date())
            db = self.conectar_db()
            cursor = db.cursor()

            # Llamar al procedimiento almacenado
            cursor.callproc('pagar_todas_cuotas', (id_prestamo, fecha_mysql))
            db.commit()

            messagebox.showinfo("Éxito", "Se han pagado todas las cuotas pendientes del préstamo")
            ventana.destroy()
            self.mostrar_cuotas()  # Actualizar vista de cuotas

        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error al realizar el pago total: {err}")
        finally:
            if 'db' in locals():
                db.close()

    def configurar_actualizacion_automatica(self):
        """Configurar el evento de actualización automática de cuotas"""
        try:
            db = self.conectar_db()
            cursor = db.cursor()
            
            # Habilitar el Event Scheduler
            cursor.execute("SET GLOBAL event_scheduler = ON")
            
            # Eliminar el evento si ya existe
            cursor.execute("DROP EVENT IF EXISTS actualizar_cuotas_automaticamente")
            
            # Crear el evento que se ejecutará diariamente
            evento_sql = """
                CREATE EVENT actualizar_cuotas_automaticamente
                ON SCHEDULE EVERY 1 DAY
                STARTS CURRENT_TIMESTAMP
                DO
                BEGIN
                    UPDATE pagos
                    SET estado = 'Pagado',
                        fecha_pago = fecha_vencimiento
                    WHERE estado = 'Pendiente'
                    AND fecha_vencimiento <= CURDATE();
                END
            """
            cursor.execute(evento_sql)
            
        except mysql.connector.Error as err:
            print(f"Error al configurar actualización automática: {err}")
        finally:
            if 'db' in locals():
                db.close()

    def create_menu_bar(self):
        """Crear barra de menú"""
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        # Menú Herramientas
        tools_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Herramientas", menu=tools_menu)
        tools_menu.add_command(label="Exportar formato CSV para préstamos históricos", 
                             command=self.exportar_formato_csv)
        tools_menu.add_command(label="Importar préstamos históricos desde CSV", 
                             command=self.importar_prestamos_csv)

    def importar_prestamos_csv(self):
        """Importar préstamos históricos desde archivo CSV"""
        try:
            from tkinter import filedialog
            import csv
            from datetime import datetime
            
            # Seleccionar archivo CSV
            filename = filedialog.askopenfilename(
                defaultextension='.csv',
                filetypes=[("CSV files", "*.csv")],
                title="Seleccionar archivo CSV de préstamos históricos"
            )
            
            if not filename:
                return
                
            db = self.conectar_db()
            cursor = db.cursor()
            
            prestamos_procesados = 0
            errores = []
            
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    try:
                        # Validar que el legajo existe
                        cursor.execute("SELECT COUNT(*) FROM personal WHERE legajo = %s", 
                                    (row['legajo'],))
                        if cursor.fetchone()[0] == 0:
                            errores.append(f"Legajo {row['legajo']} no existe")
                            continue
                        
                        # Insertar el préstamo
                        query = """
                            INSERT INTO prestamos (legajo, monto_total, cuotas, 
                                                 fecha_inicio, motivo)
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        cursor.execute(query, (
                            row['legajo'],
                            float(row['monto_total']),
                            int(row['cuotas']),
                            row['fecha_inicio'],
                            row['motivo']
                        ))
                        
                        id_prestamo = cursor.lastrowid
                        monto_cuota = float(row['monto_total']) / int(row['cuotas'])
                        
                        # Generar y actualizar cuotas
                        cursor.callproc('generar_cuotas', (
                            id_prestamo,
                            float(row['monto_total']),
                            int(row['cuotas']),
                            datetime.strptime(row['fecha_inicio'], '%Y-%m-%d')
                        ))
                        
                        # Si el préstamo está pagado, marcar cuotas como pagadas
                        if row['estado'].lower() == 'pagado':
                            update_query = """
                                UPDATE pagos 
                                SET estado = 'Pagado',
                                    fecha_pago = CASE
                                        WHEN fecha_vencimiento <= %s THEN fecha_vencimiento
                                        ELSE NULL
                                    END
                                WHERE id_prestamos = %s
                                AND fecha_vencimiento <= %s
                            """
                            cursor.execute(update_query, (
                                row['fecha_ultima_cuota'],
                                id_prestamo,
                                row['fecha_ultima_cuota']
                            ))
                        
                        db.commit()
                        prestamos_procesados += 1
                        
                    except Exception as e:
                        errores.append(f"Error en legajo {row['legajo']}: {str(e)}")
                        db.rollback()
            
            # Mostrar resumen
            mensaje = f"Préstamos procesados: {prestamos_procesados}\n"
            if errores:
                mensaje += "\nErrores encontrados:\n" + "\n".join(errores)
            
            if prestamos_procesados > 0:
                messagebox.showinfo("Importación Completada", mensaje)
            else:
                messagebox.showwarning("Importación", mensaje)
                
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Error al importar los préstamos: {str(e)}"
            )
        finally:
            if 'db' in locals():
                db.close()

    def exportar_formato_csv(self):
        """Exportar plantilla CSV para importación de préstamos históricos"""
        try:
            from tkinter import filedialog
            import csv
            from datetime import datetime
            
            # Obtener ubicación para guardar el archivo
            filename = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[("CSV files", "*.csv")],
                title="Guardar plantilla CSV"
            )
            
            if not filename:
                return
            
            # Encabezados para el CSV
            headers = [
                'legajo',
                'monto_total',
                'cuotas',
                'fecha_inicio',
                'fecha_ultima_cuota',
                'motivo',
                'estado'
            ]
            
            # Crear el archivo CSV con los encabezados y una fila de ejemplo
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(headers)
                
                # Agregar una fila de ejemplo
                ejemplo = [
                    '12345',  # legajo
                    '50000',  # monto_total
                    '12',     # cuotas
                    '2023-01-01',  # fecha_inicio
                    '2023-12-01',  # fecha_ultima_cuota
                    'Préstamo personal',  # motivo
                    'Pagado'    # estado
                ]
                writer.writerow(ejemplo)
            
            # Crear archivo de instrucciones
            instrucciones = """INSTRUCCIONES PARA COMPLETAR EL ARCHIVO CSV:

1. Formato de fechas: YYYY-MM-DD (ejemplo: 2023-01-31)
2. Campos:
   - legajo: número de legajo del empleado
   - monto_total: monto total del préstamo (sin símbolos de moneda)
   - cuotas: número total de cuotas
   - fecha_inicio: fecha en que se otorgó el préstamo
   - fecha_ultima_cuota: fecha en que se pagó la última cuota
   - motivo: motivo del préstamo
   - estado: debe ser 'Pagado' o 'Pendiente'

3. No usar comillas ni caracteres especiales
4. Separar los campos con coma
5. No dejar espacios entre las comas
6. Para números decimales usar punto (no coma)

Ejemplo:
12345,50000,12,2023-01-01,2023-12-01,Préstamo personal,Pagado
"""
            
            # Guardar archivo de instrucciones junto al CSV
            instrucciones_path = filename.rsplit('.', 1)[0] + '_instrucciones.txt'
            with open(instrucciones_path, 'w', encoding='utf-8') as f:
                f.write(instrucciones)
            
            messagebox.showinfo(
                "Exportación exitosa",
                f"Se ha creado el archivo CSV en:\n{filename}\n\n"
                f"Las instrucciones están en:\n{instrucciones_path}"
            )
            
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Error al exportar el archivo: {str(e)}"
            )

    def run(self):
        """Iniciar la aplicación"""
        if self.standalone:
            self.root.mainloop()
        # En modo integrado no necesitamos llamar a mainloop

    def show_in_frame(self, new_parent_frame):
        """Método para mostrar el módulo en un nuevo frame padre con limpieza mejorada"""
        # Limpiar eventos y recursos previos
        if hasattr(self, 'cleanup'):
            self.cleanup()
        
        self.is_destroyed = False  # Reiniciar bandera
        self.parent_frame = new_parent_frame
        
        # Limpiar configuraciones previas
        self.parent_frame.pack_forget() if hasattr(self.parent_frame, 'pack_forget') else None
        self.parent_frame.grid_forget() if hasattr(self.parent_frame, 'grid_forget') else None
        
        # Asegurar que el parent_frame use pack para expandirse completamente
        self.parent_frame.pack(fill="both", expand=True)
        
        # Configurar el frame principal
        self.setup_window()
        
        # Crear la GUI asegurando que los frames se expandan correctamente
        self.create_gui()
        
        # Forzar actualización de geometría
        self.parent_frame.update_idletasks()
        if hasattr(self, 'container_frame'):
            self.container_frame.update_idletasks()
        
        self.configurar_actualizacion_automatica()
        if hasattr(self, 'standalone') and self.standalone:
            self.create_menu_bar()

    def mostrar_menu_historial(self, event):
        """Mostrar menú contextual del historial"""
        if self.tree.selection():  # Solo si hay una fila seleccionada
            self.menu_historial.post(event.x_root, event.y_root)

    def mostrar_historial_pagos(self):
        """Mostrar ventana con historial de pagos de un préstamo"""
        # Obtener el ID del préstamo seleccionado
        seleccionado = self.tree.selection()[0]
        item = self.tree.item(seleccionado)
        id_prestamo = item['values'][0]
        
        try:
            db = self.conectar_db()
            cursor = db.cursor(dictionary=True)
            
            # Verificar si existen pagos para este préstamo
            query = """
                SELECT COUNT(*) as total_pagos
                FROM pagos
                WHERE id_prestamos = %s
            """
            cursor.execute(query, (id_prestamo,))
            result = cursor.fetchone()
            
            if result['total_pagos'] == 0:
                # Si no hay pagos, mostrar ventana modal informativa
                ventana = tk.Toplevel(self.parent_frame)
                ventana.title("Sin Historial de Pagos")
                ventana.geometry("500x500")
                ventana.transient(self.parent_frame)
                ventana.grab_set()
                
                # Centrar la ventana
                ventana.geometry(f"+{self.parent_frame.winfo_x() + 100}+{self.parent_frame.winfo_y() + 100}")
                
                # Frame principal
                frame = ctk.CTkFrame(ventana)
                frame.pack(fill="both", expand=True, padx=20, pady=20)
                
                # Ícono de información (emoji)
                icon_label = ctk.CTkLabel(
                    frame,
                    text="ℹ️",
                    font=('Roboto', 48)
                )
                icon_label.pack(pady=(20, 10))
                
                # Título
                ctk.CTkLabel(
                    frame,
                    text="Préstamo sin Historial",
                    font=('Roboto', 20, 'bold')
                ).pack(pady=(0, 20))
                
                # Mensaje informativo
                mensaje = (
                    "Este préstamo fue importado desde un archivo CSV\n"
                    "y no cuenta con un historial detallado de pagos.\n\n"
                    "Los préstamos importados solo mantienen su información básica\n"
                    "y estado final, pero no el registro de pagos individuales."
                )
                
                ctk.CTkLabel(
                    frame,
                    text=mensaje,
                    font=('Roboto', 12),
                    justify="center",
                    wraplength=400
                ).pack(pady=20)
                
                # Botón cerrar
                ctk.CTkButton(
                    frame,
                    text="Entendido",
                    command=ventana.destroy,
                    width=100
                ).pack(pady=20)
                
                return
                
            # Si hay pagos, mostrar la ventana normal de historial
            query = """
                SELECT 
                    p.numero_cuota,
                    p.monto_cuota,
                    p.fecha_vencimiento,
                    p.fecha_pago,
                    p.estado,
                    CASE 
                        WHEN p.fecha_pago > p.fecha_vencimiento THEN 'Atrasado'
                        WHEN p.fecha_pago <= p.fecha_vencimiento THEN 'A tiempo'
                        ELSE '-'
                    END as tipo_pago
                FROM pagos p
                WHERE p.id_prestamos = %s
                ORDER BY p.numero_cuota
            """
            cursor.execute(query, (id_prestamo,))
            pagos = cursor.fetchall()

            # Crear ventana de historial
            ventana = tk.Toplevel(self.parent_frame)
            ventana.title("Historial de Pagos")
            ventana.geometry("800x700")
            ventana.transient(self.parent_frame)
            ventana.grab_set()

            # Centrar la ventana
            ventana.geometry(f"+{self.parent_frame.winfo_x() + 50}+{self.parent_frame.winfo_y() + 50}")

            # Frame principal
            frame = ctk.CTkFrame(ventana)
            frame.pack(fill="both", expand=True, padx=20, pady=20)

            # Título
            ctk.CTkLabel(
                frame,
                text=f"Historial de Pagos - Préstamo #{id_prestamo}",
                font=('Roboto', 20, 'bold')
            ).pack(pady=10)

            # Crear tabla de pagos
            tree_frame = ctk.CTkFrame(frame)
            tree_frame.pack(fill="both", expand=True, pady=(10, 20))

            # Treeview para mostrar los pagos
            columns = ("Cuota", "Monto", "Vencimiento", "Fecha Pago", "Estado", "Tipo")
            tree = ttk.Treeview(
                tree_frame,
                columns=columns,
                show="headings",
                style="Custom.Treeview"
            )

            # Configurar columnas
            for col in columns:
                tree.heading(col, text=col, anchor="center")
                tree.column(col, anchor="center", width=120)

            # Insertar datos
            for pago in pagos:
                fecha_vencimiento = self.format_date_for_display(pago['fecha_vencimiento'])
                fecha_pago = self.format_date_for_display(pago['fecha_pago']) if pago['fecha_pago'] else '-'
                
                # Determinar color de la fila según el tipo de pago
                tag = "atrasado" if pago['tipo_pago'] == 'Atrasado' else "normal"
                
                tree.insert("", "end", values=(
                    pago['numero_cuota'],
                    f"${pago['monto_cuota']:.2f}",
                    fecha_vencimiento,
                    fecha_pago,
                    pago['estado'],
                    pago['tipo_pago']
                ), tags=(tag,))

            # Configurar colores para los tags
            tree.tag_configure("atrasado", foreground="red")
            tree.tag_configure("normal", foreground="black")

            # Scrollbars (corregido)
            y_scrollbar = self.create_modern_scrollbar(tree_frame, tree, "vertical")
            x_scrollbar = self.create_modern_scrollbar(tree_frame, tree, "horizontal")

            # Layout con grid
            tree.grid(row=0, column=0, sticky="nsew")
            y_scrollbar.grid(row=0, column=1, sticky="ns")
            x_scrollbar.grid(row=1, column=0, sticky="ew")

            # Configuración del grid
            tree_frame.grid_columnconfigure(0, weight=1)
            tree_frame.grid_rowconfigure(0, weight=1)

            # Binding para mousewheel
            def handle_scroll(event):
                if event.state & 4:  # Shift presionado
                    tree.xview_scroll(int(-1*(event.delta/120)), "units")
                else:
                    tree.yview_scroll(int(-1*(event.delta/120)), "units")
                return "break"

            tree.bind("<MouseWheel>", handle_scroll)
            tree.bind("<Shift-MouseWheel>", handle_scroll)

            # Resumen de pagos
            resumen_frame = ctk.CTkFrame(frame)
            resumen_frame.pack(fill="x", pady=(0, 10))

            # Calcular estadísticas
            total_cuotas = len(pagos)
            pagos_atrasados = sum(1 for p in pagos if p['tipo_pago'] == 'Atrasado')
            pagos_tiempo = sum(1 for p in pagos if p['tipo_pago'] == 'A tiempo')
            cuotas_pendientes = sum(1 for p in pagos if p['estado'] == 'Pendiente')

            # Mostrar estadísticas
            stats_text = f"""
            Total de cuotas: {total_cuotas}
            Pagos a tiempo: {pagos_tiempo}
            Pagos atrasados: {pagos_atrasados}
            Cuotas pendientes: {cuotas_pendientes}
            """

            ctk.CTkLabel(
                resumen_frame,
                text=stats_text,
                font=('Roboto', 12),
                justify="left"
            ).pack(pady=10)

            # Botón cerrar
            ctk.CTkButton(
                frame,
                text="Cerrar",
                command=ventana.destroy,
                width=100
            ).pack(pady=10)

        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error de base de datos: {err}")
        finally:
            if 'db' in locals():
                db.close()

    def cleanup(self):
        """Método para limpiar recursos y eventos antes de destruir el módulo"""
        print("Limpiando recursos del módulo de préstamos...")
        try:
            # Desconectar TODOS los eventos de mousewheel
            widgets = [self.container_frame, self.parent_frame]
            
            # Buscar también los canvas que pudieran tener eventos
            canvases = []
            if hasattr(self, 'content_canvas'):
                canvases.append(self.content_canvas)
            if hasattr(self, 'loans_canvas'):
                canvases.append(self.loans_canvas)
            if hasattr(self, 'payments_canvas'):
                canvases.append(self.payments_canvas)
            
            for widget in widgets + canvases:
                if widget and hasattr(widget, 'winfo_exists') and widget.winfo_exists():
                    try:
                        widget.unbind_all("<MouseWheel>")
                        widget.unbind_all("<Shift-MouseWheel>")
                    except Exception as e:
                        print(f"Error limpiando eventos: {e}")
                        
            # Marcar el módulo como destruido para evitar actualizaciones
            self.is_destroyed = True
            
        except Exception as e:
            print(f"Error en cleanup: {e}")

    def _configure_mousewheel(self, canvas, scrollable_frame=None):
        """Configura eventos de rueda de ratón con mejor manejo de errores"""
        # Guardar referencia al canvas para limpieza posterior
        if not hasattr(self, '_registered_canvases'):
            self._registered_canvases = []
        self._registered_canvases.append(canvas)
        
        # Función para verificar si el widget existe antes de hacer scroll
        def _safe_scroll(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        
        # Función para desconectar este canvas específico
        def _unbind_canvas():
            try:
                canvas.unbind_all("<MouseWheel>")
                canvas.unbind_all("<Shift-MouseWheel>")
            except Exception:
                pass
        
        # Agregar método de desconexión al canvas
        canvas._unbind_mousewheel = _unbind_canvas
        
        # Registrar eventos con manejo seguro
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _safe_scroll))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # Cuando se destruye el canvas, limpiar sus eventos
        canvas.bind("<Destroy>", lambda e: _unbind_canvas())

    def format_date_for_mysql(self, date_str):
        """Convertir fecha de dd/mm/yyyy a formato MySQL yyyy-mm-dd"""
        if isinstance(date_str, str):
            day, month, year = date_str.split('/')
            return f"{year}-{month}-{day}"
        return date_str.strftime('%Y-%m-%d')

    def reset_state(self):
        """Restablecer el estado del módulo a su estado inicial"""
        self.state = {
            'data_loaded': False,
            'current_user': None,
            'loan_data': []
        }
        # Restablecer cualquier otro estado necesario

    def save_state(self):
        """Guardar el estado actual en un memento"""
        return PrestamosMemento(self.state.copy())

    def restore_state(self, memento):
        """Restaurar el estado desde un memento"""
        self.state = memento.get_state()
        # Actualizar la interfaz o cualquier otro componente según el estado restaurado

if __name__ == "__main__":
    # Crear instancia en modo standalone
    app = AplicacionPrestamos()
    app.run()
