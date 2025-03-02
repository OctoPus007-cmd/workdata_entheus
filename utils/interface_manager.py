import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import Any, Callable
import logging
from PIL import Image

class InterfaceManager:
    """
    Gestor de interfaz que maneja las actualizaciones de la UI
    y la comunicación con el hilo principal de Tkinter
    """
    def __init__(self, root: Any):
        self.root = root
        self.update_callbacks = {}
        self.logger = logging.getLogger(__name__)
        
    def schedule_update(self, widget_id: str, update_func: Callable, *args, **kwargs):
        """
        Programa una actualización de la interfaz de manera segura
        """
        try:
            def safe_update():
                try:
                    if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
                        update_func(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error updating widget {widget_id}: {e}")

            self.root.after(10, safe_update)
        except Exception as e:
            self.logger.error(f"Error scheduling update: {e}")

    def register_callback(self, event_type: str, callback: Callable):
        """
        Registra callbacks para diferentes tipos de eventos
        """
        if event_type not in self.update_callbacks:
            self.update_callbacks[event_type] = []
        self.update_callbacks[event_type].append(callback)

    def trigger_callbacks(self, event_type: str, *args, **kwargs):
        """
        Ejecuta los callbacks registrados para un tipo de evento
        """
        if event_type in self.update_callbacks:
            for callback in self.update_callbacks[event_type]:
                try:
                    self.schedule_update(event_type, callback, *args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error triggering callback: {e}")

    def create_loading_overlay(self) -> tuple:
        """
        Crea un overlay de carga
        """
        overlay = ctk.CTkFrame(self.root, fg_color="rgba(0, 0, 0, 0.5)")
        label = ctk.CTkLabel(
            overlay,
            text="Cargando...",
            font=("Roboto", 16, "bold"),
            text_color="white"
        )
        label.pack(expand=True)
        return overlay, label

    def show_loading(self, message: str = "Cargando..."):
        """
        Muestra el overlay de carga
        """
        overlay, label = self.create_loading_overlay()
        label.configure(text=message)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.root.update()
        return overlay

    def hide_loading(self, overlay: ctk.CTkFrame):
        """
        Oculta el overlay de carga
        """
        if overlay:
            overlay.destroy()

class EstiloApp:
    """Clase para definir los colores y estilos de la aplicación"""
    # Colores principales
    COLOR_PRINCIPAL = "#E3F2FD"
    COLOR_SECUNDARIO = "#90CAF9"
    COLOR_TEXTO = "#000000"
    COLOR_FRAMES = "#BBDEFB"
    COLOR_HEADER = "#FFFFFF"

    # Colores para botones CRUD
    BOTON_INSERTAR = "#4CAF50"  # Verde - representa creación/nuevo
    BOTON_INSERTAR_HOVER = "#45A049"  # Verde más oscuro
    
    BOTON_MODIFICAR = "#2196F3"  # Azul - representa actualización
    BOTON_MODIFICAR_HOVER = "#1976D2"  # Azul más oscuro
    
    BOTON_ELIMINAR = "#F44336"  # Rojo - representa eliminación/peligro
    BOTON_ELIMINAR_HOVER = "#D32F2F"  # Rojo más oscuro
    
    BOTON_LIMPIAR = "#757575"  # Gris - representa acción neutral
    BOTON_LIMPIAR_HOVER = "#616161"  # Gris más oscuro

    # Colores para botones generales
    BOTON_COLOR = "#1976D2"  # Color principal para botones
    BOTON_HOVER = "#1565C0"  # Color hover para botones

class DialogManager:
    def mostrar_mensaje(self, root, titulo, mensaje, tipo="info"):
        """Muestra un mensaje en una ventana emergente con mejor manejo de la ventana principal"""
        try:
            # Asegurarse de que root sea una ventana válida
            if not isinstance(root, (tk.Tk, tk.Toplevel, ctk.CTk, ctk.CTkToplevel)):
                # Buscar la ventana principal
                root = self._find_root_window(root)
            
            # Crear la ventana emergente
            dialog = ctk.CTkToplevel(root)
            dialog.title(titulo)
            dialog.transient(root)
            dialog.grab_set()
            
            # Calcular posición centrada
            window_width = 400
            window_height = 200
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            center_x = int(screen_width/2 - window_width/2)
            center_y = int(screen_height/2 - window_height/2)
            
            dialog.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
            
            # Configurar ícono según el tipo de mensaje
            icon_label = None
            if tipo == "error":
                icon = ctk.CTkImage(Image.open("icons/error.png"), size=(32, 32))
                icon_label = ctk.CTkLabel(dialog, image=icon, text="")
            elif tipo == "success":
                icon = ctk.CTkImage(Image.open("icons/success.png"), size=(32, 32))
                icon_label = ctk.CTkLabel(dialog, image=icon, text="")
            
            if icon_label:
                icon_label.pack(pady=10)
            
            # Mensaje
            msg_label = ctk.CTkLabel(dialog, text=mensaje, wraplength=350)
            msg_label.pack(pady=20, padx=20)
            
            # Botón OK
            ok_button = ctk.CTkButton(dialog, text="OK", command=dialog.destroy)
            ok_button.pack(pady=10)
            
            # Centrar la ventana
            dialog.update_idletasks()
            
            return dialog
            
        except Exception as e:
            print(f"Error mostrando mensaje: {e}")
            # Fallback a messagebox en caso de error
            if tipo == "error":
                messagebox.showerror(titulo, mensaje)
            else:
                messagebox.showinfo(titulo, mensaje)

    def _find_root_window(self, widget):
        """Encuentra la ventana principal desde cualquier widget"""
        current = widget
        while current:
            if isinstance(current, (tk.Tk, ctk.CTk)):
                return current
            current = current.master
        return None

    def mostrar_confirmacion(self, parent, titulo, mensaje, accion_confirmacion):
        """
        Mostrar diálogo de confirmación
        
        Args:
            parent: Ventana padre
            titulo: Título del diálogo
            mensaje: Mensaje a mostrar
            accion_confirmacion: Tipo de acción a confirmar (e.g., "eliminar", "modificar")
        
        Returns:
            bool: True si el usuario confirma, False en caso contrario
        """
        return messagebox.askyesno(titulo, mensaje, parent=parent)
