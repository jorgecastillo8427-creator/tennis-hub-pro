import streamlit as st
import pandas as pd
import requests
import urllib.parse
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ******************************************************************************
# 1. CONFIGURACIÓN DE PÁGINA E IDENTIDAD VISUAL (ESTILOS CSS)
# ******************************************************************************
st.set_page_config(page_title="Tennis Hub Pro", layout="centered", page_icon="🎾")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #00ffcc; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1e1e1e; border-radius: 10px; padding: 10px; color: white; }
    [data-testid="stImage"] img { border-radius: 50% !important; border: 3px solid #00ffcc; object-fit: cover; width: 85px !important; height: 85px !important; }
    .match-card { background: #1e2630; padding: 12px; border-radius: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; color: white !important; }
    .feed-card { background: #161b22; padding: 15px; border-radius: 15px; border-left: 5px solid #00ffcc; margin-bottom: 10px; border: 1px solid #30363d; }
    .win-tag { background-color: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-left: 5px; }
    .loss-tag { background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-left: 5px; }
    </style>
    """, unsafe_allow_html=True)

# ******************************************************************************
@st.cache_data(show_spinner=False)
def descargar_foto_drive(file_id):
    if not file_id or str(file_id).lower() in ["nan", "none", ""]:
        return None
    try:
        # Añadimos un "User-Agent" para engañar a Google y que crea que soy un navegador
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://drive.google.com/uc?export=view&id={file_id}"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.content
        return None
    except:
        return None

# ******************************************************************************
# 3. VARIABLES DE CONEXIÓN Y CONFIGURACIÓN DE GOOGLE SHEETS
# ******************************************************************************
SHEET_ID_SOLO = "18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM"
GID_JUGADORES = "0"
GID_REPORTES = "1569954908"

# ******************************************************************************
# 4. CARGA Y LIMPIEZA DE DATOS MAESTROS (JUGADORES Y PARTIDOS)
# ******************************************************************************
@st.cache_data(ttl=30)
def cargar_datos_maestros():
    try:
        # 1. Cargar Jugadores
        url_jug = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SOLO}/export?format=csv&gid={GID_JUGADORES}"
        df_j = pd.read_csv(url_jug)
        df_j.columns = df_j.columns.str.strip().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        df_j.columns = [c.replace('cedula', 'Cedula').replace('CEDULA', 'Cedula') for c in df_j.columns]
        
        if 'Cedula' in df_j.columns:
            df_j['Cedula'] = df_j['Cedula'].astype(str).str.strip().str.zfill(10)
        
        # 2. Cargar Reportes (Partidos)
        url_part = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SOLO}/export?format=csv&gid={GID_REPORTES}"
        df_p = pd.read_csv(url_part)
        df_p.columns = df_p.columns.str.strip()
        
        return df_j, df_p
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ******************************************************************************
# 5. LÓGICA DE CÁLCULO PARA EL RANKING / TABLA DE POSICIONES
# ******************************************************************************
def calcular_ranking_grupo(df_j, df_p, cat, grupo):
    ranking = df_j[(df_j['Categoria'] == cat) & (df_j['Grupo'].astype(str) == str(grupo))].copy()
    for col in ['PJ', 'PG', 'PP', 'JG', 'JP', 'Puntos']: 
        ranking[col] = 0
    
    if not df_p.empty:
        partidos_v = df_p[df_p['Estado'] == 'Confirmado']
        for _, p in partidos_v.iterrows():
            ganador = str(p['Ganador']).strip()
            perdedor = str(p['Perdedor']).strip()
            try:
                score_partes = str(p['Score']).split('-')
                s_ganador = int(score_partes[0])
                s_perdedor = int(score_partes[1])
            except: continue 

            idx_g = ranking[ranking['Nombre'] == ganador].index
            if not idx_g.empty:
                ranking.loc[idx_g, 'PJ'] += 1
                ranking.loc[idx_g, 'PG'] += 1
                ranking.loc[idx_g, 'JG'] += s_ganador
                ranking.loc[idx_g, 'JP'] += s_perdedor
                ranking.loc[idx_g, 'Puntos'] += 2

            idx_p = ranking[ranking['Nombre'] == perdedor].index
            if not idx_p.empty:
                ranking.loc[idx_p, 'PJ'] += 1
                ranking.loc[idx_p, 'PP'] += 1
                ranking.loc[idx_p, 'JG'] += s_perdedor
                ranking.loc[idx_p, 'JP'] += s_ganador

    ranking['DJ'] = ranking['JG'] - ranking['JP']
    return ranking.sort_values(by=['Puntos', 'DJ', 'JG'], ascending=False)

# ******************************************************************************
# **************************************************************************
   # **************************************************************************
    # TAB 1: FEED SOCIAL - FORZADO
    # **************************************************************************
    with tab1:
        st.subheader("📢 Muro de Resultados")
        
        import base64
        # Intentamos leer la hoja Reportes
        try:
            df_feed_social = conn.read(spreadsheet=SHEET_URL, worksheet="Reportes", ttl=0)
        except:
            st.error("No se pudo leer la hoja 'Reportes'. Revisa el nombre.")
            df_feed_social = pd.DataFrame()

        if not df_feed_social.empty:
            # Mostramos los últimos 5 sin filtros para ver si algo sale
            ultimos_5 = df_feed_social.tail(5).iloc[::-1]
            
            for idx, fila in ultimos_5.iterrows():
                # Variables seguras
                p_id = str(fila.get('ID', idx))
                ganador = str(fila.get('Ganador', 'Jugador 1'))
                perdedor = str(fila.get('Perdedor', 'Jugador 2'))
                score = str(fila.get('Score', '0-0'))
                
                # Buscamos fotos (si falla, ponemos placeholder)
                def get_img_p(nombre):
                    try:
                        id_f = df_jugadores[df_jugadores['Nombre'] == nombre]['ID FOTO'].values[0]
                        binario = descargar_foto_drive(id_f)
                        if binario:
                            return f'data:image/png;base64,{base64.b64encode(binario).decode()}'
                    except: pass
                    return "https://via.placeholder.com/60"

                img_g = get_img_p(ganador)
                img_p = get_img_p(perdedor)

                # Tarjeta Visual
                st.markdown(f'''
                    <div style="background:#1e2130; padding:15px; border-radius:15px; border:1px solid #444; margin-bottom:10px;">
                        <div style="display: flex; justify-content: space-around; align-items: center; text-align: center;">
                            <div style="width: 30%;">
                                <img src="{img_g}" style="width: 55px; height: 55px; border-radius: 50%; border: 2px solid #28a745; object-fit: cover;">
                                <p style="font-size: 11px; margin-top: 5px; color: white;">{ganador.split()[0]}</p>
                            </div>
                            <div style="width: 30%;">
                                <h2 style="margin: 0; color: #00ffcc; font-size: 22px;">{score}</h2>
                                <small style="color: #888;">{fila.get('Fecha', '')}</small>
                            </div>
                            <div style="width: 30%;">
                                <img src="{img_p}" style="width: 55px; height: 55px; border-radius: 50%; border: 2px solid #dc3545; object-fit: cover;">
                                <p style="font-size: 11px; margin-top: 5px; color: white;">{perdedor.split()[0]}</p>
                            </div>
                        </div>
                    </div>
                ''', unsafe_allow_html=True)

                # Botones (Forzados con columnas simples)
                c1, c2, c3 = st.columns(3)
                u_mail = st.session_state.get('user_email', 'Invitado')
                
                with c1: st.button(f"👍", key=f"l_{p_id}", on_click=guardar_reaccion, args=(conn, p_id, u_mail, "like"))
                with c2: st.button(f"🔥", key=f"f_{p_id}", on_click=guardar_reaccion, args=(conn, p_id, u_mail, "fire"))
                with c3: st.button(f"😱", key=f"s_{p_id}", on_click=guardar_reaccion, args=(conn, p_id, u_mail, "surprise"))
                
                st.write("---")
        else:
            st.warning("La hoja de Reportes parece estar vacía.")
# ******************************************************************************
# 7. MOTOR DE INTELIGENCIA ARTIFICIAL (PREDICCIÓN DE PROBABILIDADES)
# ******************************************************************************
def calcular_probabilidad_ia(j1, j2, df_p):
    def get_wins(nombre):
        m = df_p[((df_p['Ganador'] == nombre) | (df_p['Perdedor'] == nombre)) & (df_p['Score'].notnull())]
        w = len(m[m['Ganador'] == nombre])
        return w, len(m)

    try:
        (w1, t1), (w2, t2) = get_wins(j1), get_wins(j2)
        r1 = (w1 / t1) if t1 > 0 else 0.5
        r2 = (w2 / t2) if t2 > 0 else 0.5
        prob1 = round((r1 / (r1 + r2)) * 100) if (r1 + r2) > 0 else 50
        return prob1, 100 - prob1
    except: return 50, 50

# ******************************************************************************
# 8. FUNCIÓN PRINCIPAL: INTERFAZ DE USUARIO (MAIN)
# ******************************************************************************
def main():
    # **************************************************************************
    # ESTILOS ADICIONALES PARA MODO OSCURO
    # **************************************************************************
    st.markdown("""
        <style>
            .stApp { background-color: #0e1117; color: white; }
            h1, h2, h3, p, span, label, div { color: white !important; }
            [data-testid="stMetricValue"] { color: #28a745 !important; }
            [data-testid="stHeader"] { background: rgba(0,0,0,0); }
            .stTabs [data-baseweb="tab-list"] { gap: 8px; }
            .stTabs [data-baseweb="tab"] { background-color: #1e2130; border-radius: 5px; padding: 8px; font-size: 14px; }
        </style>
    """, unsafe_allow_html=True)

    df_jugadores, df_partidos = cargar_datos_maestros()
    
    # **************************************************************************
    # LÓGICA DE LOGIN (CONTROL DE ACCESO POR CÉDULA)
    # **************************************************************************
    if 'auth' not in st.session_state:
        st.title("🎾 Tennis Hub Pro")
        cedula_input = st.text_input("Ingresa tu Cédula:")
        if st.button("Entrar"):
            user_data = df_jugadores[df_jugadores['Cedula'] == cedula_input.strip().zfill(10)]
            if not user_data.empty:
                st.session_state['auth'] = True
                st.session_state['user'] = user_data.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("Cédula no encontrada.")
        return

    # **************************************************************************
    # CONFIGURACIÓN DE SESIÓN Y CONEXIÓN A GOOGLE SHEETS
    # **************************************************************************
    user = st.session_state['user']
    nombre_u = user['Nombre']
    cat_u = user['Categoria']
    grupo_u = user['Grupo']
    SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SOLO}"
    conn = st.connection("gsheets", type=GSheetsConnection)

    # **************************************************************************
    # **************************************************************************
    # **************************************************************************
    # 8. HEADER VISUAL (FOTO DE DRIVE + SALUDO PERSONALIZADO) - FIX FINAL
    # **************************************************************************
    
    # 1. Obtención del ID (Usando el nombre exacto de tu columna)
    id_foto = str(user.get('ID FOTO', '')) 
    foto_bytes = descargar_foto_drive(id_foto)

    # 2. Conversión a Base64 para el HTML
    import base64
    def get_base64(bin_file):
        if bin_file:
            return base64.b64encode(bin_file).decode()
        return None

    img_base64 = get_base64(foto_bytes)

    # 3. HTML Único para mantener todo en una sola fila (Desktop y Móvil)
    if img_base64:
        # Si la foto se descargó correctamente
        header_html = f'''
            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 15px;">
                <img src="data:image/png;base64,{img_base64}" 
                     style="width: 75px; height: 75px; border-radius: 50%; border: 2px solid #00ffcc; object-fit: cover;">
                <div>
                    <h3 style="margin: 0; color: white; font-size: 20px;">¡Hola, {nombre_u.split()[0]}!</h3>
                    <p style="margin: 0; color: #00ffcc; font-size: 14px;">🏆 {cat_u} | 👥 G{grupo_u}</p>
                </div>
            </div>
        '''
    else:
        # Avatar de respaldo si la celda está vacía o el ID no funciona
        header_html = f'''
            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 15px;">
                <div style="background-color:#1e2630; border-radius:50%; width:75px; height:75px; 
                            display:flex; align-items:center; justify-content:center; border:2px solid #00ffcc; font-size:35px;">
                    👤
                </div>
                <div>
                    <h3 style="margin: 0; color: white; font-size: 20px;">¡Hola, {nombre_u.split()[0]}!</h3>
                    <p style="margin: 0; color: #00ffcc; font-size: 14px;">🏆 {cat_u} | 👥 G{grupo_u}</p>
                </div>
            </div>
        '''

    st.markdown(header_html, unsafe_allow_html=True)
    st.write("---")
    # **************************************************************************
    # NAVEGACIÓN POR PESTAÑAS (TABS)
    # **************************************************************************
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 Feed", "🏆 Ranking", "👤 Perfil", "🎾 Árbitro"])

    # **************************************************************************
    # TAB 1: FEED DE NOTICIAS (ÚLTIMOS RESULTADOS)
    # **************************************************************************
    with tab1:
        st.subheader("Últimas Noticias")
        if not df_partidos.empty:
            noticias = df_partidos[df_partidos['Estado'] == 'Confirmado'].tail(5).iloc[::-1]
            for _, p in noticias.iterrows():
                st.markdown(f'''<div style="background:#1e2130; padding:12px; border-radius:10px; border-left:5px solid #28a745; margin-bottom:10px; border:1px solid #333;">
                    <small style="color:#888;">{p['Fecha']}</small><br>
                    <b>🏆 {p['Ganador']} venció a {p['Perdedor']}</b><br>
                    <span>Resultado: {p['Score']}</span></div>''', unsafe_allow_html=True)
        else: st.info("Sin noticias.")

    # **************************************************************************
    # TAB 2: TABLA DE POSICIONES (RANKING AUTOMÁTICO)
    # **************************************************************************
    with tab2:
        st.subheader("Tabla de Posiciones")
        df_rank = calcular_ranking_grupo(df_jugadores, df_partidos, cat_u, grupo_u)
        if not df_rank.empty:
            st.dataframe(df_rank[['Nombre', 'PJ', 'PG', 'PP', 'Puntos', 'DJ']], use_container_width=True, hide_index=True)
        else: st.info("Sin datos.")

    # **************************************************************************
    # TAB 3: MI PERFIL (ESTADÍSTICAS Y SCOUTING)
    # **************************************************************************
    with tab3:
        st.subheader("📊 Mi Estado")
        mis_p = df_partidos[((df_partidos['Ganador'] == nombre_u) | (df_partidos['Perdedor'] == nombre_u)) & (df_partidos['Score'].notnull())]
        if not mis_p.empty:
            c1, c2 = st.columns(2)
            wins = len(mis_p[mis_p['Ganador'] == nombre_u])
            c1.metric("Win Rate", f"{int((wins/len(mis_p)*100))}%")
            c2.metric("Partidos", len(mis_p))
        
        st.divider()
        st.subheader("🔍 Scouting")
        lista_riv = sorted(list(set(df_partidos['Ganador'].tolist() + df_partidos['Perdedor'].tolist())))
        if nombre_u in lista_riv: lista_riv.remove(nombre_u)
        rival_sel = st.selectbox("Analizar a:", ["Seleccionar..."] + lista_riv)
        if rival_sel != "Seleccionar...":
            p1, p2 = calcular_probabilidad_ia(nombre_u, rival_sel, df_partidos)
            st.write(f"🔮 **Predicción IA:** {nombre_u} ({p1}%) vs {rival_sel} ({p2}%)")
            st.progress(p1/100)

    # **************************************************************************
    # TAB 4: EL ÁRBITRO DIGITAL (CONFIRMAR Y REPORTAR RESULTADOS)
    # **************************************************************************
    with tab4:
        st.subheader("Confirmaciones y Reportes")
        ahora = datetime.now()

        # 1. GESTIÓN DE PENDIENTES
        try:
            df_rep = df_partidos.copy()
            pendientes = df_rep[(df_rep['Perdedor'] == nombre_u) & (df_rep['Estado'] == 'Pendiente')]
            if not pendientes.empty:
                st.warning("⚠️ Debes confirmar estos resultados:")
                for idx, fila in pendientes.iterrows():
                    st.write(f"**Vs {fila['Ganador']} | Score: {fila['Score']}**")
                    c1, c2 = st.columns(2)
                    if c1.button(f"✅ Confirmar", key=f"ok_{idx}"):
                        st.success("Confirmado (Requiere actualización en Excel)")
                    if c2.button("❌ Rechazar", key=f"no_{idx}"):
                        st.error("Rechazado")
            else: st.success("🎉 ¡Todo al día!")
        except: st.info("Iniciando sistema de reportes...")

        st.divider()

        # 2. SUBIR NUEVO RESULTADO
        with st.expander("📝 Subir Nuevo Resultado"):
            df_riv_g = df_jugadores[(df_jugadores['Grupo'] == grupo_u) & (df_jugadores['Categoria'] == cat_u) & (df_jugadores['Nombre'] != nombre_u)]
            with st.form("form_reporte", clear_on_submit=True):
                rival_sel = st.selectbox("¿A quién le ganaste?", df_riv_g['Nombre'].unique()) if not df_riv_g.empty else None
                c1, c2 = st.columns(2)
                mis_j = c1.number_input("Mis Juegos", 0, 8, 8)
                su_j = c2.number_input("Sus Juegos", 0, 8, 0)
                enviar = st.form_submit_button("🚀 Subir y Notificar")

                if enviar and rival_sel:
                    if mis_j <= su_j: st.error("Debes ser el ganador para reportar.")
                    else:
                        st.success(f"✅ ¡Resultado enviado! Notifica a {rival_sel}:")
                        msg = urllib.parse.quote(f"🎾 *Tennis Hub Pro*\n\nHola {rival_sel}, registré nuestro resultado: {mis_j}-{su_j}.\n\nConfírmalo aquí: https://tennis-hub-pro.streamlit.app")
                        st.markdown(f'''<a href="https://wa.me/?text={msg}" target="_blank" style="text-decoration:none;">
                            <div style="background-color:#25D366; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;">📲 Notificar por WhatsApp</div></a>''', unsafe_allow_html=True)

# ******************************************************************************
# INICIO DE LA APLICACIÓN
# ******************************************************************************
if __name__ == "__main__":
    main()