from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import pyodbc
from config import DSN_NAME, DB_USER, DB_PASSWORD, SECRET_KEY
import os
from werkzeug.utils import secure_filename
from flask import send_file
from fpdf import FPDF
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
    query = request.args.get('query', '').strip()  # Buscar por marca o modelo
    precio_min = request.args.get('precio_min')
    precio_max = request.args.get('precio_max')
    anio_min = request.args.get('anio_min')
    anio_max = request.args.get('anio_max')
    kilometraje_max = request.args.get('kilometraje_max')
    tipo = request.args.get('tipo')
    orden = request.args.get('orden', 'precio')  # Ordenar por precio por defecto

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()
    try:
        # Construir la consulta con f-strings
        query_base = f"""
        SELECT id, marca, modelo, anio, precio, color, kilometraje, tipo, transmision, descripcion, imagen
        FROM vehiculos
        WHERE 1=1
        """

        # Filtros opcionales
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

        # Ordenar resultados
        if orden == 'precio':
            query_base += " ORDER BY precio ASC"
        elif orden == 'anio':
            query_base += " ORDER BY anio DESC"

        cursor.execute(query_base)
        vehiculos = cursor.fetchall()

        # Depuración: Verificar consulta y resultados
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

@app.route('/comprar/<int:vehiculo_id>', methods=['POST'])
@login_required
def comprar_vehiculo(vehiculo_id):
    if not current_user.is_authenticated:
        flash("Debes iniciar sesión para comprar un vehículo.")
        return redirect(url_for('login'))

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()

    try:
        # Obtener información del vehículo
        cursor.execute(f"SELECT precio FROM vehiculos WHERE id = {vehiculo_id}")
        vehiculo = cursor.fetchone()

        if not vehiculo:
            flash("El vehículo no existe.")
            return redirect(url_for('inicio'))

        precio = vehiculo[0]

        # Registrar la compra
        query = f"""
        INSERT INTO compras (usuario_id, vehiculo_id, precio)
        VALUES ({current_user.id}, {vehiculo_id}, {precio})
        """
        cursor.execute(query)
        conn.commit()

        flash("¡Compra realizada con éxito! Este vehículo ahora es tuyo.")
    except pyodbc.Error as e:
        print("Error al registrar la compra:", e)
        flash("Hubo un error al realizar la compra.")
    finally:
        conn.close()

    return redirect(url_for('inicio'))

@app.route('/mis_compras')
@login_required
def ver_compras():
    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()

    try:
        # Obtener las compras del usuario
        query = f"""
        SELECT c.id, v.marca, v.modelo, v.anio, c.precio, c.fecha_compra
        FROM compras c
        JOIN vehiculos v ON c.vehiculo_id = v.id
        WHERE c.usuario_id = {current_user.id}
        """
        cursor.execute(query)
        compras = cursor.fetchall()
    except pyodbc.Error as e:
        print("Error al obtener compras:", e)
        compras = []
        flash("Hubo un error al cargar tus compras.")
    finally:
        conn.close()

    return render_template('mis_compras.html', compras=compras)


@app.route('/pago/<int:vehiculo_id>', methods=['GET', 'POST'])
@login_required
def datos_pago(vehiculo_id):
    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()

    try:
        # Obtener detalles del vehículo
        cursor.execute(f"SELECT id, marca, modelo, precio FROM vehiculos WHERE id = {vehiculo_id}")
        vehiculo = cursor.fetchone()

        if not vehiculo:
            flash("El vehículo no existe.")
            return redirect(url_for('inicio'))

        if request.method == 'POST':
            # Simular la validación de datos de pago
            nombre_tarjeta = request.form.get('nombre_tarjeta')
            numero_tarjeta = request.form.get('numero_tarjeta')
            fecha_expiracion = request.form.get('fecha_expiracion')
            cvv = request.form.get('cvv')

            if not all([nombre_tarjeta, numero_tarjeta, fecha_expiracion, cvv]):
                flash("Por favor, completa todos los datos de pago.")
                return render_template('pago.html', vehiculo=vehiculo)

            # Registrar la compra
            query = f"""
            INSERT INTO compras (usuario_id, vehiculo_id, precio)
            VALUES ({current_user.id}, {vehiculo_id}, {vehiculo[3]})
            """
            cursor.execute(query)
            conn.commit()

            flash("¡Compra realizada con éxito! Este vehículo ahora es tuyo.")
            return redirect(url_for('ver_compras'))

        return render_template('pago.html', vehiculo=vehiculo)

    except pyodbc.Error as e:
        print("Error al procesar el pago:", e)
        flash("Hubo un error al procesar el pago.")
        return redirect(url_for('inicio'))
    finally:
        conn.close()

@app.route('/factura/<int:compra_id>', methods=['GET'])
@login_required
def generar_factura(compra_id):
    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('ver_compras'))

    cursor = conn.cursor()

    try:
        # Permitir que el administrador acceda a todas las facturas
        if current_user.is_admin:
            query = f"""
            SELECT c.id, v.marca, v.modelo, v.anio, c.precio, c.fecha_compra, u.nombre
            FROM compras c
            JOIN vehiculos v ON c.vehiculo_id = v.id
            JOIN usuarios u ON c.usuario_id = u.id
            WHERE c.id = {compra_id}
            """
        else:
            # Restringir acceso a las facturas del usuario actual
            query = f"""
            SELECT c.id, v.marca, v.modelo, v.anio, c.precio, c.fecha_compra, u.nombre
            FROM compras c
            JOIN vehiculos v ON c.vehiculo_id = v.id
            JOIN usuarios u ON c.usuario_id = u.id
            WHERE c.id = {compra_id} AND c.usuario_id = {current_user.id}
            """

        cursor.execute(query)
        compra = cursor.fetchone()

        if not compra:
            flash("Compra no encontrada o no tienes permiso para verla.")
            return redirect(url_for('ver_compras'))

        # Crear el PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Factura de Compra', 0, 1, 'C')
        pdf.ln(10)

        # Información de la compra
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f"ID Compra: {compra[0]}", 0, 1)
        pdf.cell(0, 10, f"Usuario: {compra[6]}", 0, 1)
        pdf.cell(0, 10, f"Vehículo: {compra[1]} {compra[2]} ({compra[3]})", 0, 1)
        pdf.cell(0, 10, f"Precio: ${compra[4]:,.2f}", 0, 1)
        pdf.cell(0, 10, f"Fecha de Compra: {compra[5]}", 0, 1)

        # Guardar el PDF temporalmente
        factura_path = os.path.join(app.config['UPLOAD_FOLDER'], f"factura_{compra_id}.pdf")
        pdf.output(factura_path)

        return send_file(factura_path, as_attachment=True, download_name=f"factura_{compra_id}.pdf")
    except pyodbc.Error as e:
        print("Error al generar la factura:", e)
        flash("Hubo un error al generar la factura.")
        return redirect(url_for('ver_compras'))
    finally:
        conn.close()


@app.route('/admin/compras')
@login_required
def ver_todas_compras():
    if not current_user.is_admin:
        flash("No tienes permiso para acceder a esta página.")
        return redirect(url_for('inicio'))

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()

    try:
        # Obtener todas las compras
        query = """
        SELECT c.id, u.nombre, v.marca, v.modelo, v.anio, c.precio, c.fecha_compra
        FROM compras c
        JOIN usuarios u ON c.usuario_id = u.id
        JOIN vehiculos v ON c.vehiculo_id = v.id
        """
        cursor.execute(query)
        compras = cursor.fetchall()
    except pyodbc.Error as e:
        print("Error al obtener compras:", e)
        flash("Hubo un error al cargar las compras.")
        compras = []
    finally:
        conn.close()

    return render_template('admin_compras.html', compras=compras)

@app.route('/comparar', methods=['GET'])
@login_required
def comparar_vehiculos():
    ids = request.args.getlist('ids')  # Obtener los IDs de los vehículos seleccionados

    if len(ids) < 2:
        flash("Selecciona al menos dos vehículos para comparar.")
        return redirect(url_for('inicio'))

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()
    try:
        # Consulta para obtener los detalles de los vehículos seleccionados
        query = f"""
        SELECT id, marca, modelo, anio, precio, color, kilometraje, tipo, transmision, descripcion, imagen
        FROM vehiculos
        WHERE id IN ({', '.join(ids)})
        """
        cursor.execute(query)
        vehiculos = cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener vehículos para comparar: {e}")
        flash("Ocurrió un error al cargar los vehículos.")
        vehiculos = []
    finally:
        conn.close()

    return render_template('comparar.html', vehiculos=vehiculos)

@app.route('/soporte', methods=['GET', 'POST'])
@login_required
def soporte():
    if request.method == 'POST':
        asunto = request.form.get('asunto')
        mensaje = request.form.get('mensaje')

        # Validar que los campos no estén vacíos
        if not asunto or not mensaje:
            flash("Por favor, completa todos los campos antes de enviar tu mensaje.")
            return render_template('soporte.html')

        conn = conectar()
        if not conn:
            flash("No se pudo conectar a la base de datos.")
            return redirect(url_for('inicio'))

        cursor = conn.cursor()
        try:
            # Insertar mensaje en la tabla
            query = f"""
                INSERT INTO mensajes_soporte (usuario_id, asunto, mensaje)
                VALUES ({current_user.id}, '{asunto.replace("'", "''")}', '{mensaje.replace("'", "''")}')
            """
            cursor.execute(query)
            conn.commit()
            flash("Tu solicitud de soporte ha sido enviada. Nos pondremos en contacto contigo pronto.")
        except Exception as e:
            print(f"Error al guardar el mensaje de soporte: {e}")
            flash("Hubo un problema al enviar tu solicitud de soporte. Inténtalo de nuevo.")
        finally:
            conn.close()

        return redirect(url_for('inicio'))

    return render_template('soporte.html')

@app.route('/mis_mensajes_soporte')
@login_required
def mis_mensajes_soporte():
    conn = conectar()
    cursor = conn.cursor()
    try:
        # Consultar mensajes del usuario actual
        query = f"""
            SELECT id, asunto, mensaje, fecha, estado
            FROM mensajes_soporte
            WHERE usuario_id = {current_user.id}
            ORDER BY fecha DESC
        """
        cursor.execute(query)
        mensajes = cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener los mensajes de soporte: {e}")
        mensajes = []
        flash("Hubo un error al cargar tus mensajes de soporte.")
    finally:
        conn.close()

    return render_template('mis_mensajes_soporte.html', mensajes=mensajes)


@app.route('/admin/mensajes_soporte')
@login_required
def admin_mensajes_soporte():
    if not current_user.is_admin:
        flash("No tienes permiso para acceder a esta página.")
        return redirect(url_for('inicio'))

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('inicio'))

    cursor = conn.cursor()
    try:
        # Consultar todos los mensajes de soporte
        query = """
            SELECT m.id, u.nombre, m.asunto, m.mensaje, m.fecha, m.estado
            FROM mensajes_soporte m
            JOIN usuarios u ON m.usuario_id = u.id
            ORDER BY m.fecha DESC
        """
        cursor.execute(query)
        mensajes = cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener los mensajes de soporte: {e}")
        flash("Hubo un error al cargar los mensajes.")
        mensajes = []
    finally:
        conn.close()

    return render_template('admin_mensajes_soporte.html', mensajes=mensajes)




@app.route('/admin/mensajes_soporte/resolver/<int:id>', methods=['POST'])
@login_required
def admin_resolver_mensaje(id):
    if not current_user.is_admin:
        flash("No tienes permiso para realizar esta acción.")
        return redirect(url_for('inicio'))

    conn = conectar()
    if not conn:
        flash("No se pudo conectar a la base de datos.")
        return redirect(url_for('admin_mensajes_soporte'))

    cursor = conn.cursor()
    try:
        # Eliminar el mensaje de la base de datos
        query = f"""
            DELETE FROM mensajes_soporte
            WHERE id = {id}
        """
        cursor.execute(query)
        conn.commit()
        flash("El mensaje ha sido eliminado correctamente.")
    except Exception as e:
        print(f"Error al eliminar el mensaje: {e}")
        flash("Hubo un problema al eliminar el mensaje.")
    finally:
        conn.close()

    return redirect(url_for('admin_mensajes_soporte'))


@app.route('/reservar/<int:vehiculo_id>', methods=['POST'])
@login_required
def reservar(vehiculo_id):
    # Obtener la fecha ingresada en el formulario
    fecha = request.form.get('fecha')
    if not fecha:
        flash("Por favor, selecciona una fecha válida para la reserva.")
        return redirect(url_for('detalle_vehiculo', id=vehiculo_id))

    conn = conectar()
    cursor = conn.cursor()
    try:
        # Insertar la reserva en la base de datos
        query = f"""
            INSERT INTO reservas (usuario_id, vehiculo_id, fecha)
            VALUES ({current_user.id}, {vehiculo_id}, '{fecha}')
        """
        cursor.execute(query)
        conn.commit()
        flash("Reserva realizada con éxito. Nos pondremos en contacto contigo para confirmar.")
    except Exception as e:
        print(f"Error al realizar la reserva: {e}")
        flash("Hubo un error al realizar la reserva. Inténtalo de nuevo.")
    finally:
        conn.close()

    return redirect(url_for('detalle_vehiculo', id=vehiculo_id))

@app.route('/mis_reservas')
@login_required
def mis_reservas():
    conn = conectar()
    cursor = conn.cursor()
    try:
        # Consultar las reservas del usuario actual
        query = f"""
            SELECT r.id, v.marca, v.modelo, v.anio, r.fecha, r.estado
            FROM reservas r
            JOIN vehiculos v ON r.vehiculo_id = v.id
            WHERE r.usuario_id = {current_user.id}
            ORDER BY r.fecha DESC
        """
        cursor.execute(query)
        reservas = cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener las reservas: {e}")
        reservas = []
        flash("Hubo un error al cargar tus reservas.")
    finally:
        conn.close()

    return render_template('mis_reservas.html', reservas=reservas)


@app.route('/admin/reservas')
@login_required
def admin_reservas():
    if not current_user.is_admin:
        flash("No tienes permiso para acceder a esta página.")
        return redirect(url_for('inicio'))

    conn = conectar()
    cursor = conn.cursor()
    try:
        # Consultar todas las reservas
        query = """
            SELECT r.id, u.nombre, v.marca, v.modelo, v.anio, r.fecha, r.estado
            FROM reservas r
            JOIN usuarios u ON r.usuario_id = u.id
            JOIN vehiculos v ON r.vehiculo_id = v.id
            ORDER BY r.fecha DESC
        """
        cursor.execute(query)
        reservas = cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener las reservas: {e}")
        reservas = []
        flash("Hubo un error al cargar las reservas.")
    finally:
        conn.close()

    return render_template('admin_reservas.html', reservas=reservas)



@app.route('/admin/reservas/resolver/<int:id>', methods=['POST'])
@login_required
def admin_resolver_reserva(id):
    if not current_user.is_admin:
        flash("No tienes permiso para realizar esta acción.")
        return redirect(url_for('inicio'))

    conn = conectar()
    cursor = conn.cursor()
    try:
        # Eliminar la reserva de la base de datos
        query = f"DELETE FROM reservas WHERE id = {id}"
        cursor.execute(query)
        conn.commit()
        flash("La reserva ha sido eliminada correctamente.")
    except Exception as e:
        print(f"Error al eliminar la reserva: {e}")
        flash("Hubo un problema al eliminar la reserva.")
    finally:
        conn.close()

    return redirect(url_for('admin_reservas'))





@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)