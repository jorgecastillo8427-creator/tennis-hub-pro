import streamlit as st
import pandas as pd
import requests
import urllib.parse
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ******************************************************************************
# 1. CONFIGURACIÓN, ESTILOS E IDENTIDAD VISUAL (CABECERA)
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
    .win-tag { background-color: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-left: 5px; }
    .loss-tag { background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-left: 5px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def descargar_foto_drive(file_id):
    try:
        url = f"https://drive.google.com/uc?export=view&id={file_id}"
        response = requests.get(url)
        return response.content if response.status_code == 200 else None
    except: return None

# ******************************************************************************
# 2. MOTOR DE DATOS Y LÓGICA DE RANKING (TABLERO DE CONTROL)
# ******************************************************************************
SHEET_URL = "https://docs.google.com/spreadsheets/d/18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM/edit#gid=0"
SHEET_ID_SOLO = "18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM"
GID_PARTIDOS = "460951509"

@st.cache_data(ttl=30)
def cargar_datos_maestros():
    try:
        url_jug = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SOLO}/export?format=csv&gid=0"
        df_j = pd.read_csv(url_jug)
        df_j.columns = df_j.columns.str.strip().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        df_j['Cedula'] = df_j['Cedula'].astype(str).str.strip().str.zfill(10)
        url_part = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SOLO}/export?format=csv&gid={GID_PARTIDOS}"
        df_p = pd.read_csv(url_part)
        df_p.columns = df_p.columns.str.strip()
        return df_j, df_p
    except: return pd.DataFrame(), pd.DataFrame()

def calcular_ranking_grupo(df_j, df_p, cat, grupo):
    ranking = df_j[(df_j['Categoria'] == cat) & (df_j['Grupo'] == grupo)].copy()
    for col in ['PJ', 'PG', 'PP', 'JG', 'JP', 'Puntos']: ranking[col] = 0
    if not df_p.empty:
        partidos_v = df_p[df_p['Estado'].isin(['Jugado', 'Confirmado'])]
        for _, p in partidos_v.iterrows():
            for j, s_mio, s_rival in [(p['Jugador_1'], p['Score_1'], p['Score_2']), (p['Jugador_2'], p['Score_2'], p['Score_1'])]:
                idx = ranking[ranking['Nombre'] == j].index
                if not idx.empty:
                    ranking.loc[idx, 'PJ'] += 1
                    ranking.loc[idx, 'JG'] += int(s_mio)
                    ranking.loc[idx, 'JP'] += int(s_rival)
                    if int(s_mio) > int(s_rival):
                        ranking.loc[idx, 'PG'] += 1; ranking.loc[idx, 'Puntos'] += 2
                    else: ranking.loc[idx, 'PP'] += 1
    ranking['DJ'] = ranking['JG'] - ranking['JP']
    return ranking.sort_values(by=['Puntos', 'DJ', 'JG'], ascending=False)

# ******************************************************************************
# 3. FLUJO PRINCIPAL: EL PORTERO (SIDEBAR)
# ******************************************************************************
def main():
    df_jugadores, df_partidos = cargar_datos_maestros()
    conn = st.connection("gsheets", type=GSheetsConnection)

    with st.sidebar:
        st.title("🎾 Acceso")
        cedula_input = st.text_input("Ingresa tu Cédula", type="password")
        if st.button("Limpiar Sesión"): st.rerun()
        if not cedula_input:
            st.info("Inicia sesión para ver tu grupo.")
            return

    user_data = df_jugadores[df_jugadores['Cedula'] == cedula_input.strip().zfill(10)]
    if user_data.empty:
        st.error("Cédula no encontrada.")
        return

    nombre_u = user_data['Nombre'].values[0]
    cat_u = user_data['Categoria'].values[0]
    grp_u = user_data['Grupo'].values[0]
    id_foto = str(user_data['ID FOTO'].values[0]).strip() if 'ID FOTO' in user_data.columns else ""

    # CABECERA VISUAL
    st.write("")
    c_img, c_txt = st.columns([1, 4])
    with c_img:
        foto_bytes = descargar_foto_drive(id_foto) if id_foto not in ["nan", ""] else None
        if foto_bytes: st.image(foto_bytes)
        else: st.markdown("<div style='background-color:#1e2630; border-radius:50%; width:85px; height:85px; display:flex; align-items:center; justify-content:center; border:3px solid #00ffcc; font-size:40px;'>👤</div>", unsafe_allow_html=True)
    with c_txt:
        st.subheader(f"¡Hola, {nombre_u.split()[0]}! 👋")
        st.markdown(f"🏆 {cat_u} | 👥 Grupo {grp_u}")

    tab1, tab2, tab3 = st.tabs(["🏆 Clasificación", "🎾 Reportero", "👤 Mi Perfil"])

    # ******************************************************************************
    # 4. TAB 1: EL TABLERO DE CONTROL (RANKING)
    # ******************************************************************************
    with tab1:
        df_rank = calcular_ranking_grupo(df_jugadores, df_partidos, cat_u, grp_u)
        st.subheader("Tabla de Posiciones")
        st.dataframe(df_rank[['Nombre', 'PJ', 'PG', 'PP', 'Puntos', 'DJ']], use_container_width=True, hide_index=True)

    # ******************************************************************************
    # 5. TAB 2: EL ÁRBITRO DIGITAL (REPORTERO + BLINDADO + WHATSAPP)
    # ******************************************************************************
    # ******************************************************************************
    # 5. TAB 2: EL ÁRBITRO DIGITAL (REPORTERO + BLINDADO + WHATSAPP)
    # ******************************************************************************
    with tab2:
        st.subheader("Confirmaciones y Reportes")
        ahora = datetime.now()

        # 1. GESTIÓN DE PENDIENTES
        try:
            df_rep = conn.read(spreadsheet=SHEET_URL, worksheet="Reportes", ttl=0)
            df_rep.columns = [str(c).strip().capitalize() for c in df_rep.columns]
            
            # Filtramos lo que yo debo confirmar (donde soy el Perdedor)
            pendientes = df_rep[(df_rep['Perdedor'] == nombre_u) & (df_rep['Estado'] == 'Pendiente')]
            
            if not pendientes.empty:
                st.warning("⚠️ Tienes resultados por confirmar:")
                for idx, fila in pendientes.iterrows():
                    st.markdown(f"**Vs {fila['Ganador']} | Score: {fila['Score']}**")
                    c1, c2 = st.columns(2)
                    if c1.button(f"✅ Confirmar", key=f"ok_{idx}", use_container_width=True):
                        df_rep.at[idx, 'Estado'] = 'Confirmado'
                        conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_rep)
                        st.rerun()
                    if c2.button("❌ Rechazar", key=f"no_{idx}", use_container_width=True):
                        df_rep.at[idx, 'Estado'] = 'Rechazado'
                        conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_rep)
                        st.rerun()
            else:
                st.success("🎉 ¡No tienes resultados pendientes!")
        except:
            st.info("Iniciando sistema...")
            df_rep = pd.DataFrame(columns=['Fecha', 'Ganador', 'Perdedor', 'Score', 'Estado', 'Categoria', 'Grupo'])

        st.divider()

        # 2. SUBIR NUEVO RESULTADO (TU LÓGICA DE 7 DÍAS)
        with st.expander("📝 Subir Nuevo Resultado"):
            # Solo rivales de mi categoría y grupo
            df_riv = df_jugadores[(df_jugadores['Grupo'] == grp_u) & (df_jugadores['Categoria'] == cat_u) & (df_jugadores['Nombre'] != nombre_u)]
            
            with st.form("form_reporte", clear_on_submit=True):
                rival_sel = st.selectbox("¿A quién le ganaste?", df_riv['Nombre'].unique()) if not df_riv.empty else None
                c1, c2 = st.columns(2)
                mis_j = c1.number_input("Mis Juegos", 0, 8, 8)
                su_j = c2.number_input("Sus Juegos", 0, 8, 0)
                
                enviar = st.form_submit_button("🚀 Subir y Notificar", use_container_width=True)

                if enviar and rival_sel:
                    if mis_j <= su_j:
                        st.error("Debes ser el ganador para reportar.")
                    else:
                        # LEER DE NUEVO PARA EVITAR DUPLICADOS
                        df_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Reportes", ttl=0)
                        df_actual['Fecha_dt'] = pd.to_datetime(df_actual['Fecha'], format="%d/%m/%Y %H:%M", errors='coerce')
                        
                        siete_dias_atras = ahora - timedelta(days=7)
                        
                        # Buscamos si ya existe un reporte reciente (Ganador o Perdedor)
                        ya_existe = df_actual[
                            ((df_actual['Ganador'] == nombre_u) & (df_actual['Perdedor'] == rival_sel) |
                             (df_actual['Ganador'] == rival_sel) & (df_actual['Perdedor'] == nombre_u)) &
                            (df_actual['Estado'] != 'Rechazado') &
                            (df_actual['Fecha_dt'] > siete_dias_atras)
                        ]

                        if not ya_existe.empty:
                            st.warning(f"⚠️ Ya existe un reporte con {rival_sel} en los últimos 7 días.")
                        else:
                            # CREAR NUEVA FILA CON IDENTIDAD COMPLETA
                            nueva_fila = pd.DataFrame([{
                                "Fecha": ahora.strftime("%d/%m/%Y %H:%M"),
                                "Ganador": nombre_u,
                                "Perdedor": rival_sel,
                                "Score": f"{mis_j}-{su_j}",
                                "Estado": "Pendiente",
                                "Categoria": cat_u,
                                "Grupo": grp_u
                            }])
                            
                            df_final = pd.concat([df_actual.drop(columns=['Fecha_dt']), nueva_fila], ignore_index=True)
                            conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_final)
                            
                            # NOTIFICACIÓN WHATSAPP
                            tel_rival = df_riv[df_riv['Nombre'] == rival_sel]['Telefono'].values[0]
                            tel_clean = str(tel_rival).replace(" ", "").replace("+", "").split('.')[0]
                            msg = urllib.parse.quote(f"🎾 *Tennis Hub Pro*\n\nHola {rival_sel}, he registrado nuestro resultado: {mis_j}-{su_j}.\n\nConfírmalo aquí: https://tennis-hub-pro.streamlit.app")
                            
                            st.success("✅ ¡Resultado guardado!")
                            st.markdown(f'''
                                <a href="https://wa.me/{tel_clean}?text={msg}" target="_blank" style="text-decoration:none;">
                                    <div style="background-color:#25D366; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;">
                                        📲 Notificar a {rival_sel} por WhatsApp
                                    </div>
                                </a>
                            ''', unsafe_allow_html=True)
                            st.balloons()# ******************************************************************************
    # ******************************************************************************
    # 6. TAB 3: TU HOJA DE VIDA (PERFIL PRO & H2H) - JORGE EDITION
    # ******************************************************************************
    # ******************************************************************************
    # ******************************************************************************
    # ******************************************************************************
    # 6. TAB 3: TU HOJA DE VIDA (PERFIL PRO + H2H) - DINÁMICO
    # ******************************************************************************
    with tab3:
        # --- 1. MIS ÚLTIMOS 5 PARTIDOS (FORMA DEL USUARIO LOGUEADO) ---
        st.subheader("📊 Mi Estado de Forma")
        
        # Filtramos partidos donde el usuario participó y tienen score (evita filas vacías)
        mis_p = df_partidos[((df_partidos['Jugador_1'] == nombre_u) | (df_partidos['Jugador_2'] == nombre_u)) & (df_partidos['Score_1'].notnull())].copy()
        
        c1, c2 = st.columns(2)
        total_p = len(mis_p)
        
        # Cálculo de victorias basado en el usuario actual
        wins = sum(1 for _, p in mis_p.iterrows() if (p['Jugador_1']==nombre_u and int(p['Score_1'])>int(p['Score_2'])) or (p['Jugador_2']==nombre_u and int(p['Score_2'])>int(p['Score_1'])))
        
        c1.metric("Tasa de victorias", f"{int((wins/total_p*100)) if total_p > 0 else 0}%")
        c2.metric("Partidos Totales", total_p)

        # Listado Mis Últimos 5 (Unificado con "vs")
        for _, m in mis_p.tail(5).iloc[::-1].iterrows():
            soy_j1 = (m['Jugador_1'] == nombre_u)
            rival_n = m['Jugador_2'] if soy_j1 else m['Jugador_1']
            mi_s, su_s = (m['Score_1'], m['Score_2']) if soy_j1 else (m['Score_2'], m['Score_1'])
            tag = '<span class="win-tag">G</span>' if int(mi_s) > int(su_s) else '<span class="loss-tag">P</span>'
            
            st.markdown(f'''
                <div class="match-card">
                    <div><b>vs {rival_n}</b><br><small>{m.get("Fecha","")}</small></div>
                    <div class="match-card-score">{mi_s} - {su_s} {tag}</div>
                </div>
            ''', unsafe_allow_html=True)

        st.divider()

        # --- 2. SELECTOR DE RIVAL Y SU FORMA (DISEÑO UNIFORME) ---
        st.subheader("🔍 Scouting de Rivales")
        lista_rivales = sorted(list(set(df_partidos['Jugador_1'].dropna().tolist() + df_partidos['Jugador_2'].dropna().tolist())))
        if nombre_u in lista_rivales: lista_rivales.remove(nombre_u)

        rival_sel = st.selectbox("Analizar a:", ["Seleccionar rival..."] + lista_rivales)

        if rival_sel != "Seleccionar rival...":
            # Filtramos los últimos 5 partidos del rival seleccionado
            p_rival = df_partidos[((df_partidos['Jugador_1'] == rival_sel) | (df_partidos['Jugador_2'] == rival_sel)) & (df_partidos['Score_1'].notnull())].tail(5).iloc[::-1]
            
            st.write(f"📅 **Últimos 5 partidos de {rival_sel}:**")
            for _, mr in p_rival.iterrows():
                es_r_j1 = (mr['Jugador_1'] == rival_sel)
                oponente = mr['Jugador_2'] if es_r_j1 else mr['Jugador_1']
                r_mi_s, r_su_s = (mr['Score_1'], mr['Score_2']) if es_r_j1 else (mr['Score_2'], mr['Score_1'])
                r_tag = '<span class="win-tag">G</span>' if int(r_mi_s) > int(r_su_s) else '<span class="loss-tag">P</span>'
                
                st.markdown(f'''
                    <div class="match-card">
                        <div><b>vs {oponente}</b><br><small>{mr.get("Fecha","")}</small></div>
                        <div class="match-card-score">{r_mi_s} - {r_su_s} {r_tag}</div>
                    </div>
                ''', unsafe_allow_html=True)

            st.divider()

            # --- 3. EL H2H DINÁMICO (Usuario logueado vs Rival) ---
            st.subheader(f"⚔️ Cara a cara: {nombre_u} vs {rival_sel}")
            h2h_matches = mis_p[(mis_p['Jugador_1'] == rival_sel) | (mis_p['Jugador_2'] == rival_sel)]
            
            yo_gana = sum(1 for _, p in h2h_matches.iterrows() if (p['Jugador_1']==nombre_u and int(p['Score_1'])>int(p['Score_2'])) or (p['Jugador_2']==nombre_u and int(p['Score_2'])>int(p['Score_1'])))
            el_gana = len(h2h_matches) - yo_gana

            st.markdown(f'''
                <div style="background-color:#1e2130; padding:20px; border-radius:15px; text-align:center; border:1px solid #4a4a4a; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-around; align-items:center;">
                        <div><small style="color:#888;">{nombre_u.upper()}</small><br><b style="font-size:30px; color:#28a745;">{yo_gana}</b></div>
                        <div style="color:#555; font-weight:bold; font-size:20px;">VS</div>
                        <div><small style="color:#888;">{rival_sel.upper()}</small><br><b style="font-size:30px; color:#dc3545;">{el_gana}</b></div>
                    </div>
                </div>
            ''', unsafe_allow_html=True)

            if not h2h_matches.empty:
                with st.expander(f"Ver historial completo {nombre_u} vs {rival_sel}"):
                    for _, m in h2h_matches.iloc[::-1].iterrows():
                        soy_j1 = (m['Jugador_1'] == nombre_u)
                        mi_s, su_s = (m['Score_1'], m['Score_2']) if soy_j1 else (m['Score_2'], m['Score_1'])
                        res_text = "✅ Ganaste" if int(mi_s) > int(su_s) else "❌ Perdiste"
                        st.write(f"📅 {m.get('Fecha','')} | **{mi_s} - {su_s}** | {res_text}")
            else:
                st.info("No se registran enfrentamientos previos.")

# --- CIERRE DEL SCRIPT ---
if __name__ == "__main__":
    main()