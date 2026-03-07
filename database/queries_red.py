import psycopg2
from psycopg2.extras import RealDictCursor

class QueriesRedMixin:
    """Motor de sincronización en red, manejo de conexiones, roles, latidos y tapices."""

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

    def verificar_estado_mi_conexion(self, id_conexion):
        """El Cliente pregunta si el Master lo aprobó, y si sigue siendo Master."""
        query = "SELECT tapiz_asignado, estado_conexion, es_master FROM conexiones_torneo WHERE id = %s;"
        res = self._ejecutar_select(query, (id_conexion,))
        return res[0] if res else None

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

    def rechazar_conexion_cliente(self, id_conexion):
        return self._ejecutar_insert("UPDATE conexiones_torneo SET estado_conexion = 'Rechazado' WHERE id = %s", (id_conexion,))

    def asignar_tapiz_a_cliente(self, id_conexion, tapiz_asignado):
        """El Master aprueba a un cliente y le da un Tapiz."""
        return self._ejecutar_insert("""
            UPDATE conexiones_torneo 
            SET tapiz_asignado = %s, estado_conexion = 'Aprobado', ultima_actividad = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (tapiz_asignado, id_conexion))

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

    def verificar_master_existente(self, id_torneo):
        """Revisa si alguien ya abrió este torneo como Master."""
        query = "SELECT id, nombre_dispositivo FROM conexiones_torneo WHERE id_torneo = %s AND es_master = TRUE LIMIT 1;"
        res = self._ejecutar_select(query, (id_torneo,))
        return res[0] if res else None

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

    def ping_actividad_conexion(self, id_conexion):
        """Mantiene viva la sesión (Latido)."""
        return self._ejecutar_insert("UPDATE conexiones_torneo SET ultima_actividad = CURRENT_TIMESTAMP WHERE id = %s", (id_conexion,))

    def verificar_oficial_en_uso(self, id_oficial):
        """Verifica si el oficial ya tiene una sesión abierta activa en cualquier PC."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                cur.execute("DELETE FROM sesion_app WHERE CURRENT_TIMESTAMP - ultima_actividad > INTERVAL '5 seconds'")
                conexion.commit()
                if id_oficial == 0: return False
                cur.execute("SELECT id_oficial FROM sesion_app WHERE id_oficial = %s", (id_oficial,))
                return True if cur.fetchone() else False
        except Exception as e:
            print(f"Error verificando uso: {e}")
            return False
        finally:
            if conexion: conexion.close()

    def latido_sesion_app(self, id_oficial):
        """Mantiene viva tu sesión general en el software para evitar ser purgado."""
        return self._ejecutar_insert("UPDATE sesion_app SET ultima_actividad = NOW() WHERE id_oficial = %s;", (id_oficial,))

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
