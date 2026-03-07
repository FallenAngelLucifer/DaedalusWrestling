import psycopg2
from psycopg2.extras import RealDictCursor

class QueriesPareoMixin:
    """Consultas referentes a las llaves, combates individuales, puntuaciones y reportes."""

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

    def guardar_resultado_combate(self, id_torneo, estilo, peso_str, match_id, id_peleador_rojo, id_peleador_azul, id_peleador_ganador, motivo_str, id_arbitro=None, id_juez=None, id_jefe_tapiz=None, puntos_rojo=0, puntos_azul=0, historial=None):
        peso_max = int(peso_str.lower().replace("kg", "").replace(" ", "").strip())
        codigo_uww = motivo_str.split(" - ")[0].strip() 
        
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cur:
                # 1. Obtener la división
                cur.execute("""
                    SELECT td.id FROM torneo_division td
                    JOIN peso_oficial_uww p ON td.id_peso_oficial_uww = p.id
                    JOIN estilo_lucha e ON p.id_estilo_lucha = e.id
                    WHERE td.id_torneo = %s AND e.nombre = %s AND p.peso_maximo = %s
                """, (id_torneo, estilo, peso_max))
                res = cur.fetchone()
                if not res: return False
                id_td = res[0]

                # 2. Función interna segura para obtener IDs de inscripción
                def get_id_inscripcion(id_pel):
                    if not id_pel or id_pel == -1: return None # Ignora fantasmas
                    cur.execute("SELECT id FROM inscripcion WHERE id_torneo_division = %s AND id_peleador = %s", (id_td, id_pel))
                    r = cur.fetchone()
                    return r[0] if r else None
                    
                id_ins_rojo = get_id_inscripcion(id_peleador_rojo)
                id_ins_azul = get_id_inscripcion(id_peleador_azul)
                id_ins_ganador = get_id_inscripcion(id_peleador_ganador)

                # 3. Obtener el ID del tipo de victoria
                cur.execute("SELECT id FROM tipo_victoria WHERE codigo_uww = %s", (codigo_uww,))
                tv_res = cur.fetchone()
                id_tv = tv_res[0] if tv_res else None

                # 4. Comprobar si el combate ya existe
                cur.execute("SELECT id FROM combate WHERE id_torneo_division = %s AND identificador_llave = %s", (id_td, match_id))
                comb_existente = cur.fetchone()

                id_combate = None

                if comb_existente:
                    # Si ya existe, actualizamos
                    id_combate = comb_existente[0]
                    cur.execute("""
                        UPDATE combate 
                        SET id_inscripcion_ganador = %s, id_tipo_victoria = %s, 
                            id_arbitro = %s, id_juez = %s, id_jefe_tapiz = %s, estado = 'Finalizado',
                            puntos_tecnicos_rojo = %s, puntos_tecnicos_azul = %s, hora_fin = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (id_ins_ganador, id_tv, id_arbitro, id_juez, id_jefe_tapiz, puntos_rojo, puntos_azul, id_combate))
                else:
                    # Si NO existe, insertamos. Extraemos id_fase de forma segura para evitar crasheos.
                    cur.execute("SELECT id FROM fase_combate ORDER BY id ASC LIMIT 1")
                    fase_res = cur.fetchone()
                    id_fase_val = fase_res[0] if fase_res else None

                    cur.execute("""
                        INSERT INTO combate (
                            id_torneo_division, id_fase, id_inscripcion_rojo, id_inscripcion_azul, 
                            id_inscripcion_ganador, id_tipo_victoria, id_arbitro, id_juez, 
                            id_jefe_tapiz, puntos_tecnicos_rojo, puntos_tecnicos_azul, 
                            orden_pelea, estado, identificador_llave, hora_fin
                        )
                        VALUES (
                            %s, %s, %s, %s, 
                            %s, %s, %s, %s, 
                            %s, %s, %s, 
                            1, 'Finalizado', %s, CURRENT_TIMESTAMP
                        ) RETURNING id
                    """, (id_td, id_fase_val, id_ins_rojo, id_ins_azul, id_ins_ganador, id_tv, id_arbitro, id_juez, id_jefe_tapiz, puntos_rojo, puntos_azul, match_id))
                    id_combate = cur.fetchone()[0]

                # 5. Insertar historial de puntos
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
            # Ahora imprimimos el error exacto en consola para saber qué falló si vuelve a ocurrir
            print(f"Error CRÍTICO guardando resultado de combate: {e}")
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

    def obtener_puntuacion_combate(self, id_combate):
        """Consulta el historial de puntos exactos de un combate desde la BD."""
        # AÑADIMOS 'tipo_accion' A LA CONSULTA SQL
        query = "SELECT color_esquina, periodo, valor_puntos, tipo_accion FROM puntuacion_combate WHERE id_combate = %s ORDER BY orden_anotacion;"
        return self._ejecutar_select(query, (id_combate,))

    def actualizar_estado_combate(self, id_torneo, estilo, peso_str, match_id, id_peleador_rojo, id_peleador_azul, estado):
        """Inyecta un combate temporal a la BD para bloquearlo en otras computadoras, o lo borra si se cancela."""
        peso_max = int(peso_str.lower().replace("kg", "").replace(" ", "").strip())
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

    def actualizar_estado_combate(self, id_torneo, estilo, peso_str, match_id, id_peleador_rojo, id_peleador_azul, estado):
        """Inyecta un combate temporal a la BD para bloquearlo en otras computadoras, o lo borra si se cancela."""
        peso_max = int(peso_str.lower().replace("kg", "").replace(" ", "").strip())
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
