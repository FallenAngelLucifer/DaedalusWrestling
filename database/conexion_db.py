import psycopg2
from psycopg2.extras import RealDictCursor

class ConexionDB:
    def __init__(self):
        # Configura estos parámetros con los de tu servidor PostgreSQL
        self.host = "localhost"
        self.database = "DaedalusWrestling"
        self.user = "postgres"
        self.password = "sk8erace1mortadela1@"
        self.port = "5432"

    def conectar(self):
        try:
            conexion = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port,
                options="-c search_path=lucha_olimpica" # Apuntamos al esquema correcto
            )
            return conexion
        except psycopg2.Error as e:
            print(f"Error conectando a PostgreSQL: {e}")
            return None

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

    def obtener_categorias(self):
        # Ahora traemos también las edades para poder hacer el filtro en la interfaz
        query = "SELECT id, nombre, edad_minima, edad_maxima FROM categoria_edad ORDER BY edad_minima;"
        return self._ejecutar_select(query)

    def _ejecutar_select(self, query, params=None):
        conexion = self.conectar()
        if not conexion: return []
        
        try:
            # RealDictCursor nos devuelve los resultados como diccionarios en lugar de tuplas
            with conexion.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                resultados = cursor.fetchall()
                return resultados
        except psycopg2.Error as e:
            print(f"Error ejecutando consulta: {e}")
            return []
        finally:
            conexion.close()

    # --- NUEVAS FUNCIONES PARA LEER CATÁLOGOS ---
    def obtener_departamentos(self):
        return self._ejecutar_select("SELECT id, nombre FROM departamento ORDER BY nombre;")

    def obtener_ciudades(self):
        # Traemos la ciudad junto con el nombre de su departamento para mayor claridad
        query = """
            SELECT c.id, c.nombre, d.nombre as departamento 
            FROM ciudad c 
            JOIN departamento d ON c.id_departamento = d.id 
            ORDER BY c.nombre;
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

    def obtener_colegios(self):
        return self._ejecutar_select("SELECT id, nombre FROM colegio WHERE activo = TRUE ORDER BY nombre;")

    def obtener_oficiales(self):
        # Ahora trae la cédula, correo y celular para poder editarlos
        query = "SELECT id, nombre, apellidos, cedula, correo, celular FROM oficial_arbitraje WHERE activo = TRUE ORDER BY apellidos, nombre;"
        return self._ejecutar_select(query)

    # --- NUEVAS FUNCIONES PARA INSERTAR DATOS ---
    def _ejecutar_insert(self, query, params):
        """Función genérica para ejecutar INSERTS y hacer commit."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cursor:
                cursor.execute(query, params)
                conexion.commit()
                return True
        except psycopg2.Error as e:
            print(f"Error en INSERT: {e}")
            conexion.rollback()
            return False
        finally:
            conexion.close()

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

    def obtener_pesos_oficiales(self):
        """Trae los límites de peso de la UWW para poder auto-asignar la división."""
        query = "SELECT id, id_categoria_edad, id_estilo_lucha, peso_minimo, peso_maximo FROM peso_oficial_uww;"
        return self._ejecutar_select(query)

    def obtener_lista_torneos_debug(self):
        """Devuelve la lista de torneos con sus estados clave para cargar."""
        conexion = self.conectar()
        if not conexion: return []
        try:
            # Importante usar RealDictCursor si no lo has importado: from psycopg2.extras import RealDictCursor
            from psycopg2.extras import RealDictCursor
            with conexion.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT t.id, t.nombre, TO_CHAR(t.fecha_inicio, 'DD/MM/YYYY') as fecha, 
                           c.nombre as categoria, t.fecha_fin,
                           (SELECT COUNT(*) FROM conexiones_torneo ct 
                            WHERE ct.id_torneo = t.id AND ct.es_master = TRUE 
                            AND CURRENT_TIMESTAMP - ct.ultima_actividad <= INTERVAL '5 seconds') > 0 as tiene_master
                    FROM torneo t
                    LEFT JOIN categoria_edad c ON t.id_categoria_edad = c.id
                    ORDER BY t.id DESC;
                """)
                return cur.fetchall()
        except Exception as e:
            print(f"Error obteniendo torneos debug: {e}")
            return []
        finally:
            if conexion: conexion.close()

    def obtener_torneo_completo_debug(self, id_torneo):
        query_torneo = """
            SELECT t.nombre, t.lugar_exacto as lugar, ciu.nombre as ciudad_nombre,
                   to_char(t.fecha_inicio, 'DD/MM/YYYY') as fecha, c.nombre as categoria,
                   t.fecha_fin, t.num_tapices
            FROM torneo t
            JOIN categoria_edad c ON t.id_categoria_edad = c.id
            LEFT JOIN ciudad ciu ON t.id_ciudad = ciu.id
            WHERE t.id = %s
        """
        query_inscripciones = """
            SELECT 
                i.id_peleador, p.nombre, p.apellidos, p.sexo, 
                cl.nombre as club, ci.nombre as ciudad, 
                i.peso_pesaje, el.nombre as estilo, 
                po.peso_maximo, po.id as id_division
            FROM inscripcion i
            JOIN peleador p ON i.id_peleador = p.id
            LEFT JOIN club cl ON p.id_club = cl.id
            LEFT JOIN ciudad ci ON cl.id_ciudad = ci.id
            JOIN torneo_division td ON i.id_torneo_division = td.id
            JOIN peso_oficial_uww po ON td.id_peso_oficial_uww = po.id
            JOIN estilo_lucha el ON po.id_estilo_lucha = el.id
            WHERE td.id_torneo = %s
        """
        conexion = self.conectar()
        if not conexion: return None, []
        try:
            with conexion.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query_torneo, (id_torneo,))
                datos_torneo = cur.fetchone()
                
                cur.execute(query_inscripciones, (id_torneo,))
                inscripciones = cur.fetchall()
                
                return datos_torneo, inscripciones
        except Exception as e:
            print("Error al obtener torneo debug:", e)
            return None, []
        finally:
            conexion.close()

    def guardar_torneo_completo(self, datos_torneo, inscripciones):
        conexion = self.conectar()
        if not conexion: return None
        try:
            with conexion.cursor() as cursor:
                num_tapices = datos_torneo.get('num_tapices', 1)
                cursor.execute("""
                    INSERT INTO torneo (nombre, id_categoria_edad, lugar_exacto, id_ciudad, fecha_inicio, fecha_fin, num_tapices) 
                    VALUES (%s, %s, %s, %s, %s, NULL, %s) RETURNING id
                """, (datos_torneo['nombre'], datos_torneo['id_categoria'], datos_torneo['lugar'], datos_torneo['id_ciudad'], datos_torneo['fecha'], num_tapices))
                id_torneo = cursor.fetchone()[0]

                divisiones_creadas = {} 
                for ins in inscripciones:
                    for id_peso_oficial in ins['ids_divisiones']:
                        if id_peso_oficial not in divisiones_creadas:
                            cursor.execute("""
                                INSERT INTO torneo_division (id_torneo, id_peso_oficial_uww) 
                                VALUES (%s, %s) RETURNING id
                            """, (id_torneo, id_peso_oficial))
                            divisiones_creadas[id_peso_oficial] = cursor.fetchone()[0]
                            
                        id_torneo_division = divisiones_creadas[id_peso_oficial]
                        
                        cursor.execute("""
                            INSERT INTO inscripcion (id_peleador, id_torneo_division, peso_pesaje) 
                            VALUES (%s, %s, %s)
                        """, (ins['id_atleta'], id_torneo_division, ins['peso']))
                
                conexion.commit()
                return id_torneo
        except Exception as e:
            print(f"Error guardando torneo: {e}")
            conexion.rollback()
            return None
        finally:
            conexion.close()

    def obtener_inscripciones_pareo(self, id_torneo):
        """Devuelve los atletas de un torneo ordenados para generar las llaves."""
        query = """
            SELECT e.nombre as estilo, p_uww.peso_maximo as peso_cat, 
                   pel.id as id_peleador, pel.nombre, pel.apellidos, c.nombre as club
            FROM inscripcion i
            JOIN torneo_division td ON i.id_torneo_division = td.id
            JOIN peso_oficial_uww p_uww ON td.id_peso_oficial_uww = p_uww.id
            JOIN estilo_lucha e ON p_uww.id_estilo_lucha = e.id
            JOIN peleador pel ON i.id_peleador = pel.id
            LEFT JOIN club c ON pel.id_club = c.id
            WHERE td.id_torneo = %s
            ORDER BY e.nombre, p_uww.peso_maximo, pel.apellidos;
        """
        return self._ejecutar_select(query, (id_torneo,))

    def bloquear_y_guardar_llave(self, id_torneo, nombre_estilo, peso_str, llave_array):
        """Guarda la posición exacta de cada atleta al bloquear la llave."""
        # Limpiar el string "74 kg" para obtener solo el número
        peso_max = int(peso_str.lower().replace("kg", "").replace(" ", "").strip())
        
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                # 1. Encontrar el ID de la división (Torneo + Estilo + Peso)
                cur.execute("""
                    SELECT td.id FROM torneo_division td
                    JOIN peso_oficial_uww p ON td.id_peso_oficial_uww = p.id
                    JOIN estilo_lucha e ON p.id_estilo_lucha = e.id
                    WHERE td.id_torneo = %s AND e.nombre = %s AND p.peso_maximo = %s
                """, (id_torneo, nombre_estilo, peso_max))
                res = cur.fetchone()
                if not res: return False
                id_td = res[0]

                # 2. Guardar el orden de siembra
                for index, atleta in enumerate(llave_array):
                    if atleta is not None:
                        cur.execute("""
                            UPDATE inscripcion 
                            SET orden_siembra = %s 
                            WHERE id_torneo_division = %s AND id_peleador = %s
                        """, (index, id_td, atleta['id']))
                
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error bloqueando llave: {e}")
            conexion.rollback()
            return False
        finally:
            conexion.close()

    def cargar_llave_bloqueada(self, id_torneo, nombre_estilo, peso_str, potencia):
        """Si la llave ya fue bloqueada antes, la devuelve ordenada. Si no, devuelve None."""
        peso_max = int(peso_str.lower().replace("kg", "").replace(" ", "").strip())
        conexion = self.conectar()
        if not conexion: return None
        try:
            with conexion.cursor(cursor_factory=RealDictCursor) as cur:
                # Verificar si ya tienen un orden de siembra asignado
                cur.execute("""
                    SELECT i.orden_siembra, p.id, p.nombre, p.apellidos, c.nombre as club, ciu.nombre as ciudad
                    FROM inscripcion i
                    JOIN torneo_division td ON i.id_torneo_division = td.id
                    JOIN peso_oficial_uww po ON td.id_peso_oficial_uww = po.id
                    JOIN estilo_lucha e ON po.id_estilo_lucha = e.id
                    JOIN peleador p ON i.id_peleador = p.id
                    LEFT JOIN club c ON p.id_club = c.id
                    LEFT JOIN ciudad ciu ON c.id_ciudad = ciu.id
                    WHERE td.id_torneo = %s AND e.nombre = %s AND po.peso_maximo = %s
                      AND i.orden_siembra IS NOT NULL
                """, (id_torneo, nombre_estilo, peso_max))
                
                atletas_bloqueados = cur.fetchall()
                
                if not atletas_bloqueados:
                    return None # Significa que nunca se le ha dado a "Confirmar Llave"
                    
                # Reconstruir el array usando la matemática guardada
                llave_array = [None] * potencia
                for a in atletas_bloqueados:
                    idx = a['orden_siembra']
                    if idx < potencia:
                        llave_array[idx] = {
                            "id": a['id'],
                            "nombre": f"{a['apellidos']}, {a['nombre']}",
                            "club": a['club'] or "Sin Club",
                            "ciudad": a['ciudad'] or "No especificada"
                        }
                return llave_array
        except Exception as e:
            print(f"Error cargando llave bloqueada: {e}")
            return None
        finally:
            conexion.close()

    def guardar_resultado_combate(self, id_torneo, estilo, peso_str, match_id, id_peleador_rojo, id_peleador_azul, id_peleador_ganador, motivo_str, id_arbitro=None, id_juez=None, id_jefe_tapiz=None, puntos_rojo=0, puntos_azul=0, historial=None):
        peso_max = int(peso_str.lower().replace("kg", "").replace(" ", "").strip())
        codigo_uww = motivo_str.split(" - ")[0].strip() 
        
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                cur.execute("""
                    SELECT td.id FROM torneo_division td
                    JOIN peso_oficial_uww p ON td.id_peso_oficial_uww = p.id
                    JOIN estilo_lucha e ON p.id_estilo_lucha = e.id
                    WHERE td.id_torneo = %s AND e.nombre = %s AND p.peso_maximo = %s
                """, (id_torneo, estilo, peso_max))
                res = cur.fetchone()
                if not res: return False
                id_td = res[0]

                def get_id_inscripcion(id_pel):
                    if not id_pel: return None
                    cur.execute("SELECT id FROM inscripcion WHERE id_torneo_division = %s AND id_peleador = %s", (id_td, id_pel))
                    r = cur.fetchone()
                    return r[0] if r else None
                    
                id_ins_rojo = get_id_inscripcion(id_peleador_rojo)
                id_ins_azul = get_id_inscripcion(id_peleador_azul)
                id_ins_ganador = get_id_inscripcion(id_peleador_ganador)

                if not id_ins_rojo or not id_ins_azul: return False

                cur.execute("SELECT id FROM tipo_victoria WHERE codigo_uww = %s", (codigo_uww,))
                tv_res = cur.fetchone()
                id_tv = tv_res[0] if tv_res else None

                cur.execute("SELECT id FROM combate WHERE id_torneo_division = %s AND identificador_llave = %s", (id_td, match_id))
                comb_existente = cur.fetchone()

                id_combate = None

                if comb_existente:
                    id_combate = comb_existente[0]
                    cur.execute("""
                        UPDATE combate 
                        SET id_inscripcion_ganador = %s, id_tipo_victoria = %s, 
                            id_arbitro = %s, id_juez = %s, id_jefe_tapiz = %s, estado = 'Finalizado',
                            puntos_tecnicos_rojo = %s, puntos_tecnicos_azul = %s, hora_fin = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (id_ins_ganador, id_tv, id_arbitro, id_juez, id_jefe_tapiz, puntos_rojo, puntos_azul, id_combate))
                else:
                    cur.execute("""
                        INSERT INTO combate (
                            id_torneo_division, id_fase, id_inscripcion_rojo, id_inscripcion_azul, 
                            id_inscripcion_ganador, id_tipo_victoria, id_arbitro, id_juez, 
                            id_jefe_tapiz, puntos_tecnicos_rojo, puntos_tecnicos_azul, 
                            orden_pelea, estado, identificador_llave, hora_fin
                        )
                        VALUES (
                            %s, (SELECT id FROM fase_combate LIMIT 1), %s, %s, 
                            %s, %s, %s, %s, 
                            %s, %s, %s, 
                            1, 'Finalizado', %s, CURRENT_TIMESTAMP
                        ) RETURNING id
                    """, (id_td, id_ins_rojo, id_ins_azul, id_ins_ganador, id_tv, id_arbitro, id_juez, id_jefe_tapiz, puntos_rojo, puntos_azul, match_id))
                    id_combate = cur.fetchone()[0]

                # Insertar historial de puntos (Solo si venimos del marcador en vivo)
                if historial is not None:
                    cur.execute("DELETE FROM puntuacion_combate WHERE id_combate = %s", (id_combate,))
                    for acc in historial:
                        tipo_accion = 'Penalización' if acc['is_p'] else 'Técnica'
                        esquina = 'Rojo' if acc['esquina'] == 'rojo' else 'Azul'
                        cur.execute("""
                            INSERT INTO puntuacion_combate (id_combate, color_esquina, periodo, valor_puntos, tipo_accion, orden_anotacion)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (id_combate, esquina, acc['periodo'], acc['puntos'], tipo_accion, acc['orden']))

                conexion.commit()
                return True
        except Exception as e:
            print(f"Error guardando resultado de combate: {e}")
            conexion.rollback()
            return False
        finally:
            conexion.close()

    def cargar_resultados_combates(self, id_torneo):
        """Carga en memoria todos los combates jugados o en proceso."""
        conexion = self.conectar()
        if not conexion: return {}
        try:
            with conexion.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT e.nombre as estilo, p.peso_maximo, c.identificador_llave,
                           c.id as id_combate, c.id_arbitro, c.id_juez, c.id_jefe_tapiz, c.estado,
                           pel.id as id_ganador, pel.nombre, pel.apellidos, 
                           cl.nombre as club, ci.nombre as ciudad,
                           tv.codigo_uww, tv.descripcion as motivo_desc
                    FROM combate c
                    JOIN torneo_division td ON c.id_torneo_division = td.id
                    JOIN peso_oficial_uww p ON td.id_peso_oficial_uww = p.id
                    JOIN estilo_lucha e ON p.id_estilo_lucha = e.id
                    LEFT JOIN inscripcion i_gan ON c.id_inscripcion_ganador = i_gan.id
                    LEFT JOIN peleador pel ON i_gan.id_peleador = pel.id
                    LEFT JOIN club cl ON pel.id_club = cl.id
                    LEFT JOIN ciudad ci ON cl.id_ciudad = ci.id
                    LEFT JOIN tipo_victoria tv ON c.id_tipo_victoria = tv.id
                    WHERE td.id_torneo = %s AND c.identificador_llave IS NOT NULL
                """, (id_torneo,))
                
                resultados = cur.fetchall()
                dict_resultados = {}
                
                for r in resultados:
                    llave_key = f"{r['estilo']}-{r['peso_maximo']} kg"
                    if llave_key not in dict_resultados:
                        dict_resultados[llave_key] = {}
                        
                    if r['estado'] == 'En Proceso':
                        dict_resultados[llave_key][r['identificador_llave']] = {"estado": "En Proceso"}
                    else:
                        motivo = f"{r['codigo_uww']} - {r['motivo_desc']}" if r['codigo_uww'] else "Decisión"
                        
                        if r['id_ganador'] is None:
                            dict_resultados[llave_key][r['identificador_llave']] = {
                                "id": -1, "nombre": "Doble Descalificación", "club": "---", "ciudad": "---",
                                "motivo_victoria": "2DSQ - Ambos descalificados", "id_combate": r['id_combate'],
                                "id_arbitro": r['id_arbitro'], "id_juez": r['id_juez'], "id_jefe_tapiz": r['id_jefe_tapiz'],
                                "estado": "Finalizado"
                            }
                        else:
                            dict_resultados[llave_key][r['identificador_llave']] = {
                                "id": r['id_ganador'], "nombre": f"{r['apellidos']}, {r['nombre']}",
                                "club": r['club'] or "Sin Club", "ciudad": r['ciudad'] or "No especificada",
                                "motivo_victoria": motivo, "id_combate": r['id_combate'],
                                "id_arbitro": r['id_arbitro'], "id_juez": r['id_juez'], "id_jefe_tapiz": r['id_jefe_tapiz'],
                                "estado": "Finalizado"
                            }
                return dict_resultados
        except Exception as e:
            print(f"Error cargando resultados de combates: {e}")
            return {}
        finally:
            conexion.close()

    def obtener_puntuacion_combate(self, id_combate):
        """Consulta el historial de puntos exactos de un combate desde la BD."""
        # AÑADIMOS 'tipo_accion' A LA CONSULTA SQL
        query = "SELECT color_esquina, periodo, valor_puntos, tipo_accion FROM puntuacion_combate WHERE id_combate = %s ORDER BY orden_anotacion;"
        return self._ejecutar_select(query, (id_combate,))

    def obtener_datos_reporte(self, id_torneo):
        """Obtiene la lista completa de inscritos con sus datos detallados para el PDF final."""
        query = """
            SELECT 
                e.nombre as estilo, p_uww.peso_maximo as peso_cat,
                pel.id as id_peleador, pel.nombre, pel.apellidos, 
                EXTRACT(YEAR FROM pel.fecha_nacimiento) as anio_nac,
                c.nombre as club, col.nombre as colegio,
                ciu.nombre as ciudad, dep.nombre as departamento
            FROM inscripcion i
            JOIN torneo_division td ON i.id_torneo_division = td.id
            JOIN peso_oficial_uww p_uww ON td.id_peso_oficial_uww = p_uww.id
            JOIN estilo_lucha e ON p_uww.id_estilo_lucha = e.id
            JOIN peleador pel ON i.id_peleador = pel.id
            LEFT JOIN club c ON pel.id_club = c.id
            LEFT JOIN ciudad ciu ON c.id_ciudad = ciu.id
            LEFT JOIN departamento dep ON ciu.id_departamento = dep.id
            LEFT JOIN colegio col ON pel.id_colegio = col.id
            WHERE td.id_torneo = %s
            ORDER BY e.nombre, p_uww.peso_maximo, pel.apellidos;
        """
        return self._ejecutar_select(query, (id_torneo,))

    def finalizar_torneo(self, id_torneo):
        """Actualiza la fecha_fin del torneo a la hora exacta en la que se cierra."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                cur.execute("""
                    UPDATE torneo 
                    SET fecha_fin = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (id_torneo,))
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error al finalizar torneo: {e}")
            return False
        finally:
            conexion.close()

    def obtener_oficiales_reporte(self, id_torneo):
        """Extrae dinámicamente los árbitros con toda su información y los roles desempeñados."""
        query = """
            WITH roles AS (
                SELECT DISTINCT o.id, o.nombre, o.apellidos, o.cedula, o.correo, o.celular, 'Árbitro' as rol
                FROM combate c
                JOIN torneo_division td ON c.id_torneo_division = td.id
                JOIN oficial_arbitraje o ON c.id_arbitro = o.id
                WHERE td.id_torneo = %s
                UNION
                SELECT DISTINCT o.id, o.nombre, o.apellidos, o.cedula, o.correo, o.celular, 'Juez' as rol
                FROM combate c
                JOIN torneo_division td ON c.id_torneo_division = td.id
                JOIN oficial_arbitraje o ON c.id_juez = o.id
                WHERE td.id_torneo = %s
                UNION
                SELECT DISTINCT o.id, o.nombre, o.apellidos, o.cedula, o.correo, o.celular, 'Jefe de Tapiz' as rol
                FROM combate c
                JOIN torneo_division td ON c.id_torneo_division = td.id
                JOIN oficial_arbitraje o ON c.id_jefe_tapiz = o.id
                WHERE td.id_torneo = %s
            )
            SELECT nombre, apellidos, cedula, correo, celular, string_agg(rol, ', ') as roles_desempenados
            FROM roles
            GROUP BY id, nombre, apellidos, cedula, correo, celular
            ORDER BY apellidos, nombre;
        """
        return self._ejecutar_select(query, (id_torneo, id_torneo, id_torneo))

    def obtener_divisiones_bloqueadas(self, id_torneo):
        """Devuelve un set con los IDs de peso_oficial_uww que ya tienen la llave confirmada."""
        query = """
            SELECT DISTINCT td.id_peso_oficial_uww 
            FROM torneo_division td
            JOIN inscripcion i ON i.id_torneo_division = td.id
            WHERE td.id_torneo = %s AND i.orden_siembra IS NOT NULL
        """
        res = self._ejecutar_select(query, (id_torneo,))
        return set(r['id_peso_oficial_uww'] for r in res)

    def insertar_colegio(self, nombre):
        return self._ejecutar_insert("INSERT INTO colegio (nombre) VALUES (%s)", (nombre,))

    def insertar_oficial(self, nombre, apellidos, cedula, correo, celular):
        query = """
            INSERT INTO oficial_arbitraje (nombre, apellidos, cedula, correo, celular) 
            VALUES (%s, %s, %s, %s, %s)
        """
        return self._ejecutar_insert(query, (nombre, apellidos, cedula, correo, celular))

    def actualizar_club(self, id_club, id_ciudad, nombre):
        return self._ejecutar_insert("UPDATE club SET id_ciudad = %s, nombre = %s WHERE id = %s", (id_ciudad, nombre, id_club))

    def actualizar_colegio(self, id_colegio, nombre):
        return self._ejecutar_insert("UPDATE colegio SET nombre = %s WHERE id = %s", (nombre, id_colegio))

    def actualizar_ciudad(self, id_ciudad, id_departamento, nombre):
        return self._ejecutar_insert("UPDATE ciudad SET id_departamento = %s, nombre = %s WHERE id = %s", (id_departamento, nombre, id_ciudad))

    def actualizar_oficial(self, id_oficial, nombre, apellidos, cedula, correo, celular):
        query = """
            UPDATE oficial_arbitraje 
            SET nombre = %s, apellidos = %s, cedula = %s, correo = %s, celular = %s 
            WHERE id = %s
        """
        return self._ejecutar_insert(query, (nombre, apellidos, cedula, correo, celular, id_oficial))

    def sincronizar_inscripciones(self, id_torneo, inscripciones):
        """Actualiza las inscripciones en la BD respetando las llaves ya bloqueadas."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cursor:
                # 1. Obtener divisiones actuales del torneo
                cursor.execute("SELECT id_peso_oficial_uww, id FROM torneo_division WHERE id_torneo = %s", (id_torneo,))
                divisiones_creadas = {r[0]: r[1] for r in cursor.fetchall()}
                
                inscripciones_memoria_tuplas = set()
                
                # 2. Insertar divisiones e inscripciones nuevas
                for ins in inscripciones:
                    for id_peso_oficial in ins['ids_divisiones']:
                        if id_peso_oficial not in divisiones_creadas:
                            cursor.execute("INSERT INTO torneo_division (id_torneo, id_peso_oficial_uww) VALUES (%s, %s) RETURNING id", (id_torneo, id_peso_oficial))
                            divisiones_creadas[id_peso_oficial] = cursor.fetchone()[0]
                            
                        id_td = divisiones_creadas[id_peso_oficial]
                        inscripciones_memoria_tuplas.add((ins['id_atleta'], id_td))
                        
                        cursor.execute("SELECT id FROM inscripcion WHERE id_peleador = %s AND id_torneo_division = %s", (ins['id_atleta'], id_td))
                        if not cursor.fetchone():
                            cursor.execute("INSERT INTO inscripcion (id_peleador, id_torneo_division, peso_pesaje) VALUES (%s, %s, %s)", (ins['id_atleta'], id_td, ins['peso']))
                
                # 3. Eliminar inscripciones que fueron quitadas en la UI (si NO están bloqueadas)
                cursor.execute("""
                    SELECT i.id, i.id_peleador, i.id_torneo_division 
                    FROM inscripcion i 
                    JOIN torneo_division td ON i.id_torneo_division = td.id 
                    WHERE td.id_torneo = %s AND i.orden_siembra IS NULL
                """, (id_torneo,))
                for row in cursor.fetchall():
                    id_ins, id_pel, id_td = row[0], row[1], row[2]
                    if (id_pel, id_td) not in inscripciones_memoria_tuplas:
                        cursor.execute("DELETE FROM inscripcion WHERE id = %s", (id_ins,))
                
                conexion.commit()
                return True
        except Exception as e:
            print("Error sincronizando inscripciones:", e)
            conexion.rollback()
            return False
        finally:
            conexion.close()

    def obtener_peleadores_descalificados(self, id_torneo):
        """Devuelve un set de IDs de atletas que han sido descalificados en el torneo."""
        conexion = self.conectar()
        if not conexion: return set()
        descalificados = set()
        try:
            with conexion.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT i_rojo.id_peleador as id_rojo, 
                           i_azul.id_peleador as id_azul, 
                           i_gan.id_peleador as id_ganador,
                           tv.codigo_uww
                    FROM combate c
                    JOIN torneo_division td ON c.id_torneo_division = td.id
                    LEFT JOIN tipo_victoria tv ON c.id_tipo_victoria = tv.id
                    LEFT JOIN inscripcion i_rojo ON c.id_inscripcion_rojo = i_rojo.id
                    LEFT JOIN inscripcion i_azul ON c.id_inscripcion_azul = i_azul.id
                    LEFT JOIN inscripcion i_gan ON c.id_inscripcion_ganador = i_gan.id
                    WHERE td.id_torneo = %s AND c.estado = 'Finalizado'
                """, (id_torneo,))
                
                for r in cur.fetchall():
                    # Si es 2DSQ (No hay ganador en la BD)
                    if r['id_ganador'] is None:
                        if r['id_rojo']: descalificados.add(r['id_rojo'])
                        if r['id_azul']: descalificados.add(r['id_azul'])
                    # Si es DSQ normal, el perdedor es el descalificado
                    elif r['codigo_uww'] == 'DSQ':
                        if r['id_rojo'] and r['id_rojo'] != r['id_ganador']:
                            descalificados.add(r['id_rojo'])
                        if r['id_azul'] and r['id_azul'] != r['id_ganador']:
                            descalificados.add(r['id_azul'])
        except Exception as e:
            print(f"Error obteniendo descalificados: {e}")
        finally:
            conexion.close()
        return descalificados

    def actualizar_estado_combate(self, id_torneo, estilo, peso_str, match_id, id_peleador_rojo, id_peleador_azul, estado):
        """Inyecta un combate temporal a la BD para bloquearlo en otras computadoras, o lo borra si se cancela."""
        peso_max = int(peso_str.lower().replace("kg", "").replace(" ", "").strip())
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                # 1. Obtener el ID de la División
                cur.execute("""
                    SELECT td.id FROM torneo_division td
                    JOIN peso_oficial_uww p ON td.id_peso_oficial_uww = p.id
                    JOIN estilo_lucha e ON p.id_estilo_lucha = e.id
                    WHERE td.id_torneo = %s AND e.nombre = %s AND p.peso_maximo = %s
                """, (id_torneo, estilo, peso_max))
                res = cur.fetchone()
                if not res: return False
                id_td = res[0]
                
                # 2. Comprobar si ya alguien lo creó en BD
                cur.execute("SELECT id FROM combate WHERE id_torneo_division = %s AND identificador_llave = %s", (id_td, match_id))
                comb_existente = cur.fetchone()
                
                if comb_existente:
                    if estado == "Pendiente":
                        cur.execute("DELETE FROM combate WHERE id = %s", (comb_existente[0],))
                    else:
                        cur.execute("UPDATE combate SET estado = %s WHERE id = %s", (estado, comb_existente[0]))
                else:
                    if estado == "En Proceso":
                        cur.execute("SELECT id FROM inscripcion WHERE id_torneo_division = %s AND id_peleador = %s", (id_td, id_peleador_rojo))
                        id_ins_rojo = (cur.fetchone() or [None])[0]
                        cur.execute("SELECT id FROM inscripcion WHERE id_torneo_division = %s AND id_peleador = %s", (id_td, id_peleador_azul))
                        id_ins_azul = (cur.fetchone() or [None])[0]
                        
                        cur.execute("""
                            INSERT INTO combate (id_torneo_division, id_fase, id_inscripcion_rojo, id_inscripcion_azul, orden_pelea, estado, identificador_llave)
                            VALUES (%s, (SELECT id FROM fase_combate LIMIT 1), %s, %s, 1, %s, %s)
                        """, (id_td, id_ins_rojo, id_ins_azul, estado, match_id))
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error actualizando estado combate concurrente: {e}")
            conexion.rollback()
            return False
        finally:
            conexion.close()

    # =================================================================
    # --- SISTEMA DE RED Y CONEXIONES (MASTER / CLIENTES) ---
    # =================================================================

    def verificar_master_existente(self, id_torneo):
        """Revisa si alguien ya abrió este torneo como Master."""
        query = "SELECT id, nombre_dispositivo FROM conexiones_torneo WHERE id_torneo = %s AND es_master = TRUE LIMIT 1;"
        res = self._ejecutar_select(query, (id_torneo,))
        return res[0] if res else None

    def registrar_conexion_instancia(self, id_torneo, id_oficial, nombre_dispositivo, es_master=False):
        """Registra una computadora en la sala de espera del torneo."""
        conexion = self.conectar()
        if not conexion: return None
        try:
            with conexion.cursor() as cur:
                estado = 'Aprobado' if es_master else 'Esperando'
                tapiz = 'Tapiz A' if es_master else 'Pendiente'
                cur.execute("""
                    INSERT INTO conexiones_torneo (id_torneo, nombre_dispositivo, id_oficial, es_master, tapiz_asignado, estado_conexion)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """, (id_torneo, nombre_dispositivo, id_oficial, es_master, tapiz, estado))
                conexion.commit()
                return cur.fetchone()[0]
        except Exception as e:
            print(f"Error registrando instancia de red: {e}")
            conexion.rollback()
            return None
        finally:
            conexion.close()

    def obtener_conexiones_torneo(self, id_torneo):
        """Devuelve la lista de computadoras con un orden estable para evitar parpadeos."""
        query = """
            SELECT c.id as id_conexion, c.nombre_dispositivo, c.es_master, 
                   c.tapiz_asignado, c.estado_conexion,
                   o.id as id_oficial, o.nombre, o.apellidos
            FROM conexiones_torneo c
            JOIN oficial_arbitraje o ON c.id_oficial = o.id
            WHERE c.id_torneo = %s
            -- CORRECCIÓN: Ordenamos por Master y luego por ID fijo, NO por actividad
            ORDER BY c.es_master DESC, c.id ASC;
        """
        return self._ejecutar_select(query, (id_torneo,))

    def asignar_tapiz_a_cliente(self, id_conexion, tapiz_asignado):
        """El Master aprueba a un cliente y le da un Tapiz."""
        return self._ejecutar_insert("""
            UPDATE conexiones_torneo 
            SET tapiz_asignado = %s, estado_conexion = 'Aprobado', ultima_actividad = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (tapiz_asignado, id_conexion))

    def rechazar_conexion_cliente(self, id_conexion):
        return self._ejecutar_insert("UPDATE conexiones_torneo SET estado_conexion = 'Rechazado' WHERE id = %s", (id_conexion,))

    def ping_actividad_conexion(self, id_conexion):
        """Mantiene viva la sesión (Latido)."""
        return self._ejecutar_insert("UPDATE conexiones_torneo SET ultima_actividad = CURRENT_TIMESTAMP WHERE id = %s", (id_conexion,))
    
    def verificar_estado_mi_conexion(self, id_conexion):
        """El Cliente pregunta si el Master lo aprobó, y si sigue siendo Master."""
        query = "SELECT tapiz_asignado, estado_conexion, es_master FROM conexiones_torneo WHERE id = %s;"
        res = self._ejecutar_select(query, (id_conexion,))
        return res[0] if res else None

    def eliminar_conexion_instancia(self, id_conexion):
        """Elimina la conexión, hereda el Máster si es necesario y reorganiza los tapices para no dejar huecos."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                # 1. Obtener ID del torneo antes de borrar
                cur.execute("SELECT id_torneo FROM conexiones_torneo WHERE id = %s", (id_conexion,))
                res = cur.fetchone()
                if not res: return False
                id_torneo = res[0]

                # 2. Borrar la conexión de la persona que se fue
                cur.execute("DELETE FROM conexiones_torneo WHERE id = %s", (id_conexion,))

                # 3. Reorganizar tapices y heredar Master
                cur.execute("""
                    SELECT id, estado_conexion 
                    FROM conexiones_torneo 
                    WHERE id_torneo = %s 
                    ORDER BY estado_conexion ASC, tapiz_asignado ASC, id ASC
                """, (id_torneo,))
                restantes = cur.fetchall()

                if restantes:
                    ascii_letra = 65 # Empezar en 'A'
                    for idx, row in enumerate(restantes):
                        conn_id = row[0]
                        estado = row[1]
                        nuevo_es_master = (idx == 0) # El primero de la lista hereda el trono
                        
                        if nuevo_es_master:
                            nuevo_tapiz = f"Tapiz {chr(ascii_letra)}"
                            nuevo_estado = 'Aprobado'
                            ascii_letra += 1
                        else:
                            nuevo_estado = estado
                            if estado == 'Aprobado':
                                nuevo_tapiz = f"Tapiz {chr(ascii_letra)}"
                                ascii_letra += 1
                            else:
                                nuevo_tapiz = 'Pendiente'
                                
                        cur.execute("""
                            UPDATE conexiones_torneo 
                            SET es_master = %s, tapiz_asignado = %s, estado_conexion = %s
                            WHERE id = %s
                        """, (nuevo_es_master, nuevo_tapiz, nuevo_estado, conn_id))
                
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error al eliminar conexión y reorganizar: {e}")
            conexion.rollback()
            return False
        finally:
            conexion.close()

    def limpiar_conexiones_muertas(self, id_torneo):
        """Limpia periódicamente la tabla de conexiones de clientes inactivos."""
        conexion = self.conectar()
        if not conexion: return
        try:
            with conexion.cursor() as cur:
                cur.execute("""
                    SELECT id FROM conexiones_torneo 
                    WHERE id_torneo = %s AND CURRENT_TIMESTAMP - ultima_actividad > INTERVAL '5 seconds'
                """, (id_torneo,))
                muertos = cur.fetchall()
                
                for m in muertos:
                    self.eliminar_conexion_instancia(m['id'] if isinstance(m, dict) else m[0])
                conexion.commit()
        except Exception as e:
            print(f"Error limpiando conexiones muertas: {e}")
        finally:
            if conexion: conexion.close()

    def verificar_master_activo(self, id_torneo):
        """Verifica si hay un admin vivo operando el torneo."""
        conexion = self.conectar()
        if not conexion: return None
        try:
            with conexion.cursor() as cursor:
                # Limpiamos antes de verificar para asegurar que el estado es real
                cursor.execute("""
                    DELETE FROM conexiones_torneo 
                    WHERE id_torneo = %s AND CURRENT_TIMESTAMP - ultima_actividad > INTERVAL '5 seconds'
                """, (id_torneo,))
                conexion.commit()
                
                cursor.execute("""
                    SELECT nombre_dispositivo 
                    FROM conexiones_torneo 
                    WHERE id_torneo = %s AND es_master = TRUE
                    LIMIT 1
                """, (id_torneo,))
                resultado = cursor.fetchone()
                if resultado:
                    return resultado['nombre_dispositivo'] if isinstance(resultado, dict) else resultado[0]
                return None
        except Exception as e:
            print(f"Error verificando master: {e}")
            return None
        finally:
            if conexion: conexion.close()

    def verificar_oficial_en_uso(self, id_oficial):
        """Verifica si el oficial ya tiene una sesión abierta activa en cualquier PC."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                # Reducido a 5 segundos para limpieza ultrarrápida
                cur.execute("DELETE FROM sesion_app WHERE CURRENT_TIMESTAMP - ultima_actividad > INTERVAL '5 seconds'")
                conexion.commit()
                
                if id_oficial == 0: return False # Solo limpieza
                
                cur.execute("SELECT id_oficial FROM sesion_app WHERE id_oficial = %s", (id_oficial,))
                return True if cur.fetchone() else False
        except Exception as e:
            print(f"Error verificando uso: {e}")
            return False
        finally:
            if conexion: conexion.close()

    def latido_sesion_app(self, id_oficial):
        """Mantiene viva tu sesión general en el software para evitar ser purgado."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                cur.execute("UPDATE sesion_app SET ultima_actividad = NOW() WHERE id_oficial = %s;", (id_oficial,))
                conexion.commit()
                return True
        except Exception:
            return False
        finally:
            conexion.close()

    # =================================================================
    # --- SISTEMA DE PRESENCIA GLOBAL (LOGIN DE LA APP) ---
    # =================================================================

    def registrar_sesion_app(self, id_oficial, nombre_dispositivo):
        """Registra que un árbitro acaba de iniciar sesión en el menú principal."""
        query = """
            INSERT INTO sesion_app (id_oficial, nombre_dispositivo, ultima_actividad)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id_oficial) DO UPDATE 
            SET nombre_dispositivo = EXCLUDED.nombre_dispositivo, ultima_actividad = CURRENT_TIMESTAMP;
        """
        return self._ejecutar_insert(query, (id_oficial, nombre_dispositivo))

    def eliminar_sesion_app(self, id_oficial):
        """Borra la sesión global cuando el usuario cierra sesión o cierra el programa."""
        return self._ejecutar_insert("DELETE FROM sesion_app WHERE id_oficial = %s", (id_oficial,))

    def ping_sesion_app(self, id_oficial):
        """Mantiene viva la sesión global en la base de datos (Latido de la App)."""
        return self._ejecutar_insert("UPDATE sesion_app SET ultima_actividad = CURRENT_TIMESTAMP WHERE id_oficial = %s", (id_oficial,))

    def actualizar_oficial_conexion(self, id_conexion, id_oficial_nuevo):
        """Actualiza el ID del oficial en una conexión existente (Cambio rápido de árbitro)."""
        return self._ejecutar_insert("UPDATE conexiones_torneo SET id_oficial = %s WHERE id = %s", (id_oficial_nuevo, id_conexion))

    # =================================================================
    # --- SISTEMA DE CANDADOS EN RED (COMBATES EN CURSO) ---
    # =================================================================
    def marcar_combate_en_curso(self, id_torneo, llave_key, match_id, tapiz):
        """Bloquea un combate de forma estricta tras limpiar zombis."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS combates_activos (
                        id_torneo INT, llave_key VARCHAR(100), match_id VARCHAR(50), tapiz VARCHAR(50),
                        ultima_actividad TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id_torneo, llave_key, match_id)
                    );
                """)
                cur.execute("ALTER TABLE combates_activos ADD COLUMN IF NOT EXISTS ultima_actividad TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                
                # LA MAGIA 1: Purga preventiva de combates que dejaron de latir hace 8 segundos
                cur.execute("DELETE FROM combates_activos WHERE CURRENT_TIMESTAMP - ultima_actividad > INTERVAL '8 seconds';")
                
                cur.execute("""
                    INSERT INTO combates_activos (id_torneo, llave_key, match_id, tapiz, ultima_actividad) 
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP) 
                    ON CONFLICT (id_torneo, llave_key, match_id) DO NOTHING;
                """, (id_torneo, llave_key, match_id, tapiz))
                
                if cur.rowcount == 0:
                    cur.execute("SELECT tapiz FROM combates_activos WHERE id_torneo = %s AND llave_key = %s AND match_id = %s", (id_torneo, llave_key, match_id))
                    res = cur.fetchone()
                    if res and res[0] != tapiz:
                        return False
                        
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error bloqueando combate: {e}")
            return False
        finally:
            conexion.close()

    def liberar_combate_en_curso(self, id_torneo, llave_key, match_id):
        """Suelta el candado de un combate (porque terminó o se canceló)."""
        return self._ejecutar_insert("DELETE FROM combates_activos WHERE id_torneo = %s AND llave_key = %s AND match_id = %s;", (id_torneo, llave_key, match_id))

    def obtener_combates_en_curso(self, id_torneo):
        """Devuelve todos los combates que están siendo operados y purga inactivos."""
        conexion = self.conectar()
        if not conexion: return {}
        try:
            with conexion.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS combates_activos (
                        id_torneo INT, llave_key VARCHAR(100), match_id VARCHAR(50), tapiz VARCHAR(50),
                        ultima_actividad TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id_torneo, llave_key, match_id)
                    );
                """)
                cur.execute("ALTER TABLE combates_activos ADD COLUMN IF NOT EXISTS ultima_actividad TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                
                # LA MAGIA 2: Purga activa para la cartelera de todos los clientes de la red
                cur.execute("DELETE FROM combates_activos WHERE CURRENT_TIMESTAMP - ultima_actividad > INTERVAL '8 seconds';")
                conexion.commit() # Aseguramos que la red entera vea la limpieza

                cur.execute("SELECT llave_key, match_id, tapiz FROM combates_activos WHERE id_torneo = %s;", (id_torneo,))
                res = cur.fetchall()
                activos = {}
                if res:
                    for r in res:
                        lk = r['llave_key'] if isinstance(r, dict) else r[0]
                        mi = r['match_id'] if isinstance(r, dict) else r[1]
                        tp = r['tapiz'] if isinstance(r, dict) else r[2]
                        if lk not in activos: activos[lk] = {}
                        activos[lk][mi] = tp
                return activos
        except Exception as e:
            print(f"Error obteniendo combates activos: {e}")
            return {}
        finally:
            if conexion: conexion.close()

    def transferir_master(self, id_torneo, id_nuevo_master):
        """Transfiere los privilegios de Máster a otro usuario conectado."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                # 1. Quitar privilegios a todos en la sala (Tabla real: conexiones_torneo)
                cur.execute("UPDATE conexiones_torneo SET es_master = FALSE WHERE id_torneo = %s;", (id_torneo,))
                # 2. Dar privilegios al nuevo Máster y asegurar que esté aprobado
                cur.execute("UPDATE conexiones_torneo SET es_master = TRUE, estado_conexion = 'Aprobado' WHERE id = %s AND id_torneo = %s;", (id_nuevo_master, id_torneo))
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error al transferir Máster: {e}")
            return False
        finally:
            conexion.close()

    def heredar_master(self, id_torneo, id_mi_conexion):
        """Verifica si la sala no tiene Máster y, de ser así, asume el control automáticamente."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                # 1. Comprobamos si no hay nadie con la corona en esta sala
                cur.execute("SELECT id FROM conexiones_torneo WHERE id_torneo = %s AND es_master = TRUE;", (id_torneo,))
                if not cur.fetchone():
                    # 2. Si está vacía, me pongo la corona
                    cur.execute("UPDATE conexiones_torneo SET es_master = TRUE, estado_conexion = 'Aprobado' WHERE id = %s;", (id_mi_conexion,))
                    conexion.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error heredando Máster: {e}")
            return False
        finally:
            conexion.close()

    def mantener_latido_conexion(self, id_conexion):
        """Actualiza la marca de tiempo para evitar ser eliminado por el limpiador de fantasmas."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                cur.execute("UPDATE conexiones_torneo SET ultima_actividad = CURRENT_TIMESTAMP WHERE id = %s;", (id_conexion,))
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error en latido de red: {e}")
            return False
        finally:
            conexion.close()

    def mantener_latido_combate(self, id_torneo, llave_key, match_id):
        """Mantiene vivo el candado del combate enviando un pulso de tiempo."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                cur.execute("""
                    UPDATE combates_activos 
                    SET ultima_actividad = CURRENT_TIMESTAMP 
                    WHERE id_torneo = %s AND llave_key = %s AND match_id = %s;
                """, (id_torneo, llave_key, match_id))
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error en latido de combate: {e}")
            return False
        finally:
            conexion.close()