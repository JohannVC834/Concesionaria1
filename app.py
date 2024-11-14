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
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        password = request.form.get('password')

        if not nombre or not password:
            flash("Por favor, ingresa nombre de usuario y contraseña.")
            return render_template('login.html')
        if nombre == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            admin_user = Usuario(id="admin", nombre=ADMIN_USERNAME, is_admin=True)
            login_user(admin_user)
            flash("Has iniciado sesión como administrador.")
            return redirect(url_for('inicio'))

        conn = conectar()
        if not conn:
            flash("No se pudo conectar a la base de datos.")
            return render_template('login.html')

        cursor = conn.cursor()
        try:
            query = f"SELECT id, password FROM usuarios WHERE nombre = '{nombre}'"
            cursor.execute(query)
            user_data = cursor.fetchone()
        except pyodbc.Error as e:
            print("Error en la ejecución de la consulta en login:", e)
            flash(f"Error al ejecutar la consulta de inicio de sesión: {e}")
            conn.close()
            return render_template('login.html')

        conn.close()
        
        if user_data and user_data[1] == password:
            user = Usuario(user_data[0], nombre)
            login_user(user)
            return redirect(url_for('inicio'))
        else:
            flash('Credenciales incorrectas. Inténtalo de nuevo.')
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        password = request.form.get('password')

     
        if not nombre or not password:
            flash("Por favor, completa todos los campos.")
            return render_template('registro.html')

        conn = conectar()
        if not conn:
            flash("No se pudo conectar a la base de datos.")
            return render_template('registro.html')
        
        
        cursor = conn.cursor()
        try:
            query = f"INSERT INTO usuarios (nombre, password) VALUES ('{nombre}', '{password}')"
            cursor.execute(query)
            conn.commit()
            flash('Registro exitoso. Inicia sesión ahora.')
        except pyodbc.Error as e:
            print("Error al registrar el usuario:", e)
            flash("Hubo un error al registrar el usuario.")
        finally:
            conn.close()

        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/')
@login_required
def inicio():
    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('login'))
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, marca, modelo, anio, precio FROM vehiculos")
    vehiculos = cursor.fetchall()
    conn.close()
    
    return render_template('vehiculos.html', vehiculos=vehiculos, is_admin=current_user.is_admin)

@app.route('/vehiculos/<int:id>')
@login_required
def detalle_vehiculo(id):
    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('login'))

    cursor = conn.cursor()
    try:
        query = f"SELECT id, marca, modelo, anio, precio, color, kilometraje, tipo, transmision, descripcion FROM vehiculos WHERE id = {id}"
        cursor.execute(query)
        vehiculo = cursor.fetchone()
    except pyodbc.Error as e:
        print("Error en la ejecución de la consulta en detalle_vehiculo:", e)
        flash("Error al cargar los detalles del vehículo.")
        return redirect(url_for('inicio'))
    finally:
        conn.close()

    if not vehiculo:
        flash("El vehículo no existe.")
        return redirect(url_for('inicio'))

    return render_template('detalle_vehiculo.html', vehiculo=vehiculo)

@app.route('/vehiculos/agregar', methods=['GET', 'POST'])
@login_required
def agregar_vehiculo():
    if not current_user.is_admin:
        flash("No tienes permiso para acceder a esta página.")
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        anio = request.form.get('anio')
        precio = request.form.get('precio')
        color = request.form.get('color')
        kilometraje = request.form.get('kilometraje')
        tipo = request.form.get('tipo')
        transmision = request.form.get('transmision')
        descripcion = request.form.get('descripcion')

        conn = conectar()
        if not conn:
            flash("No se pudo conectar a la base de datos.")
            return redirect(url_for('inicio'))

        cursor = conn.cursor()
        try:
            query = f"INSERT INTO vehiculos (marca, modelo, anio, precio, color, kilometraje, tipo, transmision, descripcion) VALUES ('{marca}', '{modelo}', {anio}, {precio}, '{color}', {kilometraje}, '{tipo}', '{transmision}', '{descripcion}')"
            cursor.execute(query)
            conn.commit()
            flash("Vehículo agregado con éxito.")
        except pyodbc.Error as e:
            print("Error al agregar el vehículo:", e)
            flash("Hubo un error al agregar el vehículo.")
        finally:
            conn.close()
        return redirect(url_for('inicio'))

    return render_template('agregar_vehiculo.html')

@app.route('/vehiculos/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_vehiculo(id):
    if not current_user.is_admin:
        flash("No tienes permiso para realizar esta acción.")
        return redirect(url_for('inicio'))

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()
    try:
        query = f"DELETE FROM vehiculos WHERE id = {id}"
        cursor.execute(query)
        conn.commit()
        flash("Vehículo eliminado con éxito.")
    except pyodbc.Error as e:
        print("Error al eliminar el vehículo:", e)
        flash("Hubo un error al eliminar el vehículo.")
    finally:
        conn.close()
    
    return redirect(url_for('inicio'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)