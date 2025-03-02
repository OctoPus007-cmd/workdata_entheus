import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
import logging
import time
import mysql.connector
import os
import queue
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from mysql.connector import pooling

class ThreadManager:
    """
    Gestor de hilos para la aplicación.
    Maneja la ejecución asíncrona de tareas y la comunicación entre hilos.
    """
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.task_queue = Queue()
        self.result_queue = Queue()
        self.running = True
        self.logger = logging.getLogger(__name__)
        
        # Iniciar worker thread
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def submit_task(self, task_type: str, func, callback=None, *args, **kwargs):
        """
        Envía una tarea al gestor de hilos con callback
        """
        try:
            def wrapped_task():
                try:
                    result = func(*args, **kwargs)
                    if callback:
                        self.result_queue.put((task_type, result, callback))
                    return result
                except Exception as e:
                    self.logger.error(f"Error executing task {task_type}: {e}")
                    if callback:
                        self.result_queue.put((task_type, None, callback))
                    return None

            future = self.executor.submit(wrapped_task)
            self.task_queue.put((task_type, future))
            return future
        except Exception as e:
            self.logger.error(f"Error submitting task: {e}")

    def get_results(self):
        """
        Obtiene resultados de tareas completadas
        """
        results = []
        while not self.result_queue.empty():
            results.append(self.result_queue.get())
        return results

    def _process_queue(self):
        """
        Procesa la cola de tareas en segundo plano
        """
        while self.running:
            try:
                if not self.result_queue.empty():
                    task_type, result, callback = self.result_queue.get_nowait()
                    if callback:
                        callback(result)
                else:
                    time.sleep(0.1)
            except Exception:
                continue

    def shutdown(self):
        """
        Cierra el gestor de hilos de manera ordenada
        """
        self.running = False
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
        self.executor.shutdown(wait=True)

class DatabasePool:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabasePool, cls).__new__(cls)
            return cls._instance

    def __init__(self):
        """Inicializar el pool de conexiones"""
        if not hasattr(self, 'initialized'):
            self.pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="mypool",
                pool_size=10,  # Aumentado el tamaño del pool
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_DATABASE'),
                pool_reset_session=True,
                autocommit=True,
                use_pure=True,
                connect_timeout=3  # Reducido el timeout
            )
            self.executor = ThreadPoolExecutor(max_workers=5)  # Aumentado workers
            self._lock = threading.Lock()
            self._active_connections = set()
            self.initialized = True

    def get_connection(self):
        """Obtener una conexión del pool"""
        try:
            connection = self.pool.get_connection()
            if not connection.is_connected():
                connection.reconnect()
            with self._lock:
                self._active_connections.add(connection)
            return connection
        except Exception as e:
            print(f"Error obteniendo conexión: {e}")
            raise

    def return_connection(self, connection):
        """Devolver una conexión al pool"""
        try:
            with self._lock:
                if connection in self._active_connections:
                    self._active_connections.remove(connection)
            connection.close()
        except Exception:
            pass

    def close(self):
        """Cerrar todas las conexiones activas y el executor"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)
            
            with self._lock:
                for conn in list(self._active_connections):
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._active_connections.clear()
                
        except Exception as e:
            print(f"Error al cerrar el pool de conexiones: {str(e)}")
