import psycopg2
from psycopg2.extras import RealDictCursor

class QueriesAtletasMixin:
    """Contiene todas las consultas relacionadas con los catálogos base (Atletas, Clubes, Oficiales, etc.)."""
    
    def obtener_atletas(self):
        """Devuelve todos los atletas activos con el nombre de su club, ciudad y colegio."""
        query = """
            SELECT p.id, p.nombre, p.apellidos, p.fecha_nacimiento, p.sexo, 
                   c.nombre as club, ciu.nombre as ciudad, col.nombre as colegio
            FROM peleador p
            LEFT JOIN club c ON p.id_club = c.id
            LEFT JOIN ciudad ciu ON c.id_ciudad = ciu.id
            LEFT JOIN colegio col ON p.id_colegio = col.id
            WHERE p.activo = TRUE
            ORDER BY p.apellidos, p.nombre;
        """
        return self._ejecutar_select(query)

    def obtener_clubes(self):
        query = """
            SELECT c.id, c.nombre, ciu.nombre as ciudad, d.nombre as departamento 
            FROM club c 
            JOIN ciudad ciu ON c.id_ciudad = ciu.id 
            JOIN departamento d ON ciu.id_departamento = d.id
            WHERE c.activo = TRUE ORDER BY c.nombre;
        """
        return self._ejecutar_select(query)
        
    def obtener_ciudades(self):
        # Traemos la ciudad junto con el nombre de su departamento para mayor claridad
        query = """
            SELECT c.id, c.nombre, d.nombre as departamento 
            FROM ciudad c 
            JOIN departamento d ON c.id_departamento = d.id 
            ORDER BY c.nombre;
        """
        return self._ejecutar_select(query)
        
    def obtener_categorias(self):
        # Ahora traemos también las edades para poder hacer el filtro en la interfaz
        query = "SELECT id, nombre, edad_minima, edad_maxima FROM categoria_edad ORDER BY edad_minima;"
        return self._ejecutar_select(query)
        
    def obtener_pesos_oficiales(self):
        """Trae los límites de peso de la UWW para poder auto-asignar la división."""
        query = "SELECT id, id_categoria_edad, id_estilo_lucha, peso_minimo, peso_maximo FROM peso_oficial_uww;"
        return self._ejecutar_select(query)
        
    def obtener_oficiales(self):
        # Ahora trae la cédula, correo y celular para poder editarlos
        query = "SELECT id, nombre, apellidos, cedula, correo, celular FROM oficial_arbitraje WHERE activo = TRUE ORDER BY apellidos, nombre;"
        return self._ejecutar_select(query)

    def obtener_departamentos(self):
        return self._ejecutar_select("SELECT id, nombre FROM departamento ORDER BY nombre;")

    def obtener_colegios(self):
        return self._ejecutar_select("SELECT id, nombre FROM colegio WHERE activo = TRUE ORDER BY nombre;")

    def insertar_departamento(self, nombre):
        return self._ejecutar_insert("INSERT INTO departamento (nombre) VALUES (%s)", (nombre,))

    def insertar_ciudad(self, id_departamento, nombre):
        return self._ejecutar_insert("INSERT INTO ciudad (id_departamento, nombre) VALUES (%s, %s)", (id_departamento, nombre))

    def insertar_club(self, id_ciudad, nombre):
        return self._ejecutar_insert("INSERT INTO club (id_ciudad, nombre) VALUES (%s, %s)", (id_ciudad, nombre))

    def insertar_peleador(self, nombre, apellidos, fecha_nac, sexo, id_club, id_colegio):
        query = """
            INSERT INTO peleador (nombre, apellidos, fecha_nacimiento, sexo, id_club, id_colegio) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self._ejecutar_insert(query, (nombre, apellidos, fecha_nac, sexo, id_club, id_colegio))

    def actualizar_peleador(self, id_peleador, nombre, apellidos, fecha_nac, sexo, id_club, id_colegio):
        query = """
            UPDATE peleador 
            SET nombre = %s, apellidos = %s, fecha_nacimiento = %s, sexo = %s, id_club = %s, id_colegio = %s
            WHERE id = %s
        """
        return self._ejecutar_insert(query, (nombre, apellidos, fecha_nac, sexo, id_club, id_colegio, id_peleador))

    def insertar_colegio(self, nombre):
        return self._ejecutar_insert("INSERT INTO colegio (nombre) VALUES (%s)", (nombre,))

    def insertar_oficial(self, nombre, apellidos, cedula, correo, celular):
        query = "INSERT INTO oficial_arbitraje (nombre, apellidos, cedula, correo, celular) VALUES (%s, %s, %s, %s, %s)"
        return self._ejecutar_insert(query, (nombre, apellidos, cedula, correo, celular))

    def actualizar_club(self, id_club, id_ciudad, nombre):
        return self._ejecutar_insert("UPDATE club SET id_ciudad = %s, nombre = %s WHERE id = %s", (id_ciudad, nombre, id_club))

    def actualizar_colegio(self, id_colegio, nombre):
        return self._ejecutar_insert("UPDATE colegio SET nombre = %s WHERE id = %s", (nombre, id_colegio))

    def actualizar_ciudad(self, id_ciudad, id_departamento, nombre):
        return self._ejecutar_insert("UPDATE ciudad SET id_departamento = %s, nombre = %s WHERE id = %s", (id_departamento, nombre, id_ciudad))

    def actualizar_oficial(self, id_oficial, nombre, apellidos, cedula, correo, celular):
        query = "UPDATE oficial_arbitraje SET nombre = %s, apellidos = %s, cedula = %s, correo = %s, celular = %s WHERE id = %s"
        return self._ejecutar_insert(query, (nombre, apellidos, cedula, correo, celular, id_oficial))
