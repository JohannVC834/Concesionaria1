from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import pyodbc
from config import DSN_NAME, DB_USER, DB_PASSWORD, SECRET_KEY
import os
from werkzeug.utils import secure_filename
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


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
    try:
        query = "SELECT id, marca, modelo, anio, precio, imagen FROM vehiculos"
        cursor.execute(query)
        vehiculos = cursor.fetchall()
    except pyodbc.Error as e:
        print("Error al obtener vehículos:", e)
        flash("Hubo un error al cargar los vehículos.")
        vehiculos = []
    finally:
        conn.close()

    return render_template('vehiculos.html', vehiculos=vehiculos, is_admin=current_user.is_admin)


@app.route('/vehiculos/<int:id>')
@login_required
def detalle_vehiculo(id):
    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM vehiculos WHERE id = {id}")
        vehiculo = cursor.fetchone()

        cursor.execute(f"""
            SELECT c.contenido, c.fecha, u.nombre
            FROM comentarios c
            INNER JOIN usuarios u ON c.usuario_id = u.id
            WHERE c.vehiculo_id = {id}
            ORDER BY c.fecha DESC
        """)
        comentarios = cursor.fetchall()

    except pyodbc.Error as e:
        print("Error al obtener los detalles:", e)
        flash("Hubo un error al cargar los detalles del vehículo.")
        return redirect(url_for('inicio'))
    finally:
        conn.close()

    if not vehiculo:
        flash("El vehículo no existe.")
        return redirect(url_for('inicio'))

    return render_template('detalle_vehiculo.html', vehiculo=vehiculo, comentarios=comentarios)


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
        imagen = request.files.get('imagen')


        if not marca or not modelo or not anio or not precio:
            flash("Por favor, completa todos los campos obligatorios.")
            return redirect(url_for('agregar_vehiculo'))

        imagen_ruta = None
        if imagen and allowed_file(imagen.filename):
            filename = secure_filename(imagen.filename)
            imagen_ruta = f"images/{filename}"  
            imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = conectar()
        if not conn:
            flash("No se pudo conectar a la base de datos.")
            return redirect(url_for('inicio'))

        cursor = conn.cursor()
        try:
            query = f"""
            INSERT INTO vehiculos (marca, modelo, anio, precio, imagen)
            VALUES ('{marca}', '{modelo}', {anio}, {precio}, '{imagen_ruta}')
            """
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

@app.route('/vehiculos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_vehiculo(id):
    if not current_user.is_admin:
        flash("No tienes permiso para acceder a esta página.")
        return redirect(url_for('inicio'))

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()

    if request.method == 'POST':
        marca = request.form.get('marca', '').strip()
        modelo = request.form.get('modelo', '').strip()
        anio = request.form.get('anio', '').strip()
        precio = request.form.get('precio', '').strip()
        color = request.form.get('color', '').strip()
        kilometraje = request.form.get('kilometraje', '').strip()
        tipo = request.form.get('tipo', '').strip()
        transmision = request.form.get('transmision', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        file = request.files.get('imagen')

        try:
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                ruta_imagen = f"images/{filename}"
                
                query = f"""
                UPDATE vehiculos
                SET marca = '{marca}', modelo = '{modelo}', anio = {anio or 'NULL'}, precio = {precio or 'NULL'},
                    color = '{color}', kilometraje = {kilometraje or 'NULL'}, tipo = '{tipo}', 
                    transmision = '{transmision}', descripcion = '{descripcion}', imagen = '{ruta_imagen}'
                WHERE id = {id}
                """
            else:
                query = f"""
                UPDATE vehiculos
                SET marca = '{marca}', modelo = '{modelo}', anio = {anio or 'NULL'}, precio = {precio or 'NULL'},
                    color = '{color}', kilometraje = {kilometraje or 'NULL'}, tipo = '{tipo}', 
                    transmision = '{transmision}', descripcion = '{descripcion}'
                WHERE id = {id}
                """
            print(f"Consulta SQL generada: {query}")
            
            cursor.execute(query)
            conn.commit()
            flash("Vehículo actualizado con éxito.")
        except pyodbc.Error as e:
            print("Error al actualizar el vehículo:", e)
            flash("Hubo un error al actualizar el vehículo.")
        finally:
            conn.close()

        return redirect(url_for('inicio'))

    try:
        cursor.execute(f"SELECT * FROM vehiculos WHERE id = {id}")
        vehiculo = cursor.fetchone()
    except pyodbc.Error as e:
        print("Error al obtener el vehículo:", e)
        flash("Hubo un error al cargar los datos del vehículo.")
        return redirect(url_for('inicio'))
    finally:
        conn.close()

    return render_template('editar_vehiculo.html', vehiculo=vehiculo)

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

@app.route('/buscar', methods=['GET'])
@login_required
def buscar_vehiculos():
    query = request.args.get('query', '').strip()  
    precio_min = request.args.get('precio_min')
    precio_max = request.args.get('precio_max')
    anio_min = request.args.get('anio_min')
    anio_max = request.args.get('anio_max')
    kilometraje_max = request.args.get('kilometraje_max')
    tipo = request.args.get('tipo')
    orden = request.args.get('orden', 'precio')  

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()
    try:
       
        query_base = f"""
        SELECT id, marca, modelo, anio, precio, color, kilometraje, tipo, transmision, descripcion
        FROM vehiculos
        WHERE 1=1
        """

        if query:
            query_base += f" AND (marca LIKE '%{query}%' OR modelo LIKE '%{query}%')"
        if precio_min:
            query_base += f" AND precio >= {precio_min}"
        if precio_max:
            query_base += f" AND precio <= {precio_max}"
        if anio_min:
            query_base += f" AND anio >= {anio_min}"
        if anio_max:
            query_base += f" AND anio <= {anio_max}"
        if kilometraje_max:
            query_base += f" AND kilometraje <= {kilometraje_max}"
        if tipo:
            query_base += f" AND tipo LIKE '%{tipo}%'"

       
        if orden == 'precio':
            query_base += " ORDER BY precio ASC"
        elif orden == 'anio':
            query_base += " ORDER BY anio DESC"

        cursor.execute(query_base)
        vehiculos = cursor.fetchall()

        
        print(f"Consulta ejecutada: {query_base}")
        print(f"Resultados obtenidos: {vehiculos}")
    except pyodbc.Error as e:
        print("Error al buscar vehículos:", e)
        flash("Hubo un error al realizar la búsqueda.")
        vehiculos = []
    finally:
        conn.close()

    return render_template('vehiculos.html', vehiculos=vehiculos, is_admin=current_user.is_admin)



@app.route('/favoritos/agregar/<int:vehiculo_id>', methods=['POST'])
@login_required
def agregar_favorito(vehiculo_id):
    usuario_id = current_user.id  
    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()
    try:

        query_check = f"SELECT * FROM favoritos WHERE usuario_id = {usuario_id} AND vehiculo_id = {vehiculo_id}"
        cursor.execute(query_check)
        favorito_existente = cursor.fetchone()

        if favorito_existente:
            flash("El vehículo ya está en tus favoritos.")
        else:
            
            query_insert = f"""
                INSERT INTO favoritos (usuario_id, vehiculo_id)
                VALUES ({usuario_id}, {vehiculo_id})
            """
            cursor.execute(query_insert)
            conn.commit()
            flash("Vehículo agregado a favoritos.")
    except pyodbc.Error as e:
        print("Error al agregar a favoritos:", e)
        flash("Hubo un error al agregar a favoritos.")
    finally:
        conn.close()

    return redirect(url_for('inicio'))

@app.route('/favoritos', methods=['GET'])
@login_required
def ver_favoritos():
    usuario_id = current_user.id  
    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()
    try:
       
        query = f"""
        SELECT v.id, v.marca, v.modelo, v.anio, v.precio
        FROM favoritos f
        JOIN vehiculos v ON f.vehiculo_id = v.id
        WHERE f.usuario_id = {usuario_id}
        """
        cursor.execute(query)
        favoritos = cursor.fetchall()

        
        print(f"Favoritos obtenidos para usuario_id={usuario_id}: {favoritos}")
    except pyodbc.Error as e:
        print("Error al obtener favoritos:", e)
        flash("Hubo un error al cargar tus favoritos.")
        favoritos = []
    finally:
        conn.close()

    return render_template('favoritos.html', favoritos=favoritos)

@app.route('/vehiculos/<int:vehiculo_id>/comentarios/agregar', methods=['POST'])
@login_required
def agregar_comentario(vehiculo_id):
    contenido = request.form.get('contenido', '').strip()
    usuario_id = current_user.id  

    if not contenido:
        flash("El comentario no puede estar vacío.")
        return redirect(url_for('detalle_vehiculo', id=vehiculo_id))

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('detalle_vehiculo', id=vehiculo_id))

    cursor = conn.cursor()
    try:
        query = f"""
        INSERT INTO comentarios (usuario_id, vehiculo_id, contenido)
        VALUES ({usuario_id}, {vehiculo_id}, '{contenido}')
        """
        cursor.execute(query)
        conn.commit()
        flash("Comentario agregado con éxito.")
    except pyodbc.Error as e:
        print("Error al agregar comentario:", e)
        flash("Hubo un error al agregar tu comentario.")
    finally:
        conn.close()

    return redirect(url_for('detalle_vehiculo', id=vehiculo_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)