import psycopg2
from psycopg2.extras import RealDictCursor

class QueriesTorneoMixin:
    """Maneja la creación, búsqueda, finalización y sincronización masiva de inscripciones de los torneos."""

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
