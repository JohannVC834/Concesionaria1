from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import pyodbc
from config import DSN_NAME, DB_USER, DB_PASSWORD, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY


login_manager = LoginManager(app)
login_manager.login_view = 'login'


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123" 

class Usuario(UserMixin):
    def __init__(self, id, nombre, is_admin=False):
        self.id = id
        self.nombre = nombre
        self.is_admin = is_admin
        
def conectar():
    try:
        conn = pyodbc.connect(f"DSN={DSN_NAME};UID={DB_USER};PWD={DB_PASSWORD}")
        print("Conexión a la base de datos exitosa.")
        return conn
    except pyodbc.Error as e:
        print("Error al conectar a la base de datos:", e)
        return None
    
@login_manager.user_loader
def load_user(user_id):
    if user_id == "admin":
        return Usuario(id="admin", nombre=ADMIN_USERNAME, is_admin=True)

    conn = conectar()
    if not conn:
        print("No se pudo conectar a la base de datos en load_user.")
        return None
    
    cursor = conn.cursor()
    try:
        query = f"SELECT id, nombre FROM usuarios WHERE id = {user_id}"
        cursor.execute(query)
        user_data = cursor.fetchone()
    except pyodbc.Error as e:
        print("Error en la ejecución de la consulta en load_user:", e)
        conn.close()
        return None

    conn.close()

    if user_data:
        return Usuario(user_data[0], user_data[1])
    else:
        print("No se encontró un usuario con id:", user_id)
        return None