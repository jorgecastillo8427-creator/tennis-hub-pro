import streamlit as st
import pandas as pd

# 1. Configuración base
st.set_page_config(page_title="Tennis Hub Pro - Panel", layout="wide")

SHEET_ID = "18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM"
GID_JUGADORES = "0"
GID_PARTIDOS = "460951509" 

@st.cache_data(ttl=10)
def cargar_datos(gid):
    base = "https://docs.google.com/spreadsheets/d"
    url = f"{base}/{SHEET_ID}/export?format=csv&gid={gid}"
    return pd.read_csv(url)

# Título principal de la App
st.title("🎾 Tennis Hub Pro - Ranking en Vivo")
st.markdown("---")

try:
    # 2. Carga y Procesamiento
    df_jugadores = cargar_datos(GID_JUGADORES)
    df_partidos = cargar_datos(GID_PARTIDOS)

    ranking = df_jugadores.copy()
    for col in ['PJ', 'PG', 'PP', 'JG', 'JP', 'Puntos']:
        ranking[col] = 0

    for _, partido in df_partidos.iterrows():
        if partido['Estado'] == 'Jugado' and pd.notnull(partido['Score_1']):
            j1, j2 = partido['Jugador_1'], partido['Jugador_2']
            s1, s2 = int(partido['Score_1']), int(partido['Score_2'])
            for j, s_mio, s_rival in [(j1, s1, s2), (j2, s2, s1)]:
                idx = ranking[ranking['Nombre'] == j].index
                if not idx.empty:
                    ranking.loc[idx, 'PJ'] += 1
                    ranking.loc[idx, 'JG'] += s_mio
                    ranking.loc[idx, 'JP'] += s_rival
                    if s_mio > s_rival:
                        ranking.loc[idx, 'PG'] += 1
                        ranking.loc[idx, 'Puntos'] += 2
                    else:
                        ranking.loc[idx, 'PP'] += 1
    
    ranking['DJ'] = ranking['JG'] - ranking['JP']

    # 3. Sidebar con filtros (Única fuente de verdad)
    st.sidebar.header("Configuración de Vista")
    cat_list = sorted(df_jugadores['Categoría'].unique())
    sel_cat = st.sidebar.selectbox("Selecciona Categoría", cat_list)
    
    grupo_list = sorted(df_jugadores[df_jugadores['Categoría'] == sel_cat]['Grupo'].unique())
    sel_grp = st.sidebar.selectbox("Selecciona Grupo", grupo_list)

    # 4. Filtrado y Orden
    v_grupo = ranking[(ranking['Categoría'] == sel_cat) & (ranking['Grupo'] == sel_grp)]
    v_grupo = v_grupo.sort_values(by=['Puntos', 'DJ', 'JG'], ascending=False)

    # 5. Renderizado (Aquí usamos sel_grp para que el título cambie sí o sí)
    st.subheader(f"Tabla de Posiciones - Grupo: {sel_grp}")
    
    st.dataframe(
        v_grupo[['Nombre', 'PJ', 'PG', 'PP', 'JG', 'JP', 'DJ', 'Puntos']], 
        use_container_width=True, 
        hide_index=True
    )

    st.markdown("---")
    st.subheader(f"🎾 Resultados Recientes - Grupo {sel_grp}")
    
    nombres_grupo = v_grupo['Nombre'].tolist()
    partidos_grupo = df_partidos[
        (df_partidos['Jugador_1'].isin(nombres_grupo)) | 
        (df_partidos['Jugador_2'].isin(nombres_grupo))
    ]
    
    if not partidos_grupo.empty:
        jugados = partidos_grupo[partidos_grupo['Estado'] == 'Jugado']
        if not jugados.empty:
            for _, p in jugados.iterrows():
                c1, c2, c3 = st.columns([3, 1, 3])
                c1.write(f"**{p['Jugador_1']}**")
                c2.write(f"{int(p['Score_1'])} - {int(p['Score_2'])}")
                c3.write(f"**{p['Jugador_2']}**")
        else:
            st.info("No hay partidos jugados aún.")
    else:
        st.info("No hay partidos registrados.")

except Exception as e:
    st.error(f"Error: {e}")