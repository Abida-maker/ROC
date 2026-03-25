# app.py
# Doorstroomtoets & Kansengelijkheid in Amsterdam
# Gemaakt door: Groep 2
#
# We onderzoeken of de doorstroomtoets (ingevoerd in 2023-2024) helpt
# om de kansenongelijkheid in Amsterdam te verkleinen.
# Daarnaast kijken we naar het effect van asielzoekers/nieuwkomers op schooladviezen.

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from data import laad_alle_data, ADVIES_TYPEN, ADVIES_KLEUREN, SCHOOLJAREN

# ---------------------------------------------------------------
# Pagina instellingen
# ---------------------------------------------------------------
st.set_page_config(
    page_title="Doorstroomtoets Amsterdam | Groep 2",
    page_icon="🏫",
    layout="wide"
)

# wat styling om het er netter uit te laten zien
st.markdown("""
<style>
    .metric-box {
        background: #f0f4f8;
        border-left: 4px solid #1a9850;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    h1 { color: #1a237e; }
    h2 { color: #283593; border-bottom: 2px solid #e8eaf6; padding-bottom: 6px; }
    h3 { color: #3949ab; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# Data laden
# ---------------------------------------------------------------
with st.spinner("Data ophalen van CBS en DUO..."):
    wijken_df, duo_df, bronnen = laad_alle_data()

# ---------------------------------------------------------------
# SIDEBAR - alle filters staan hier
# ---------------------------------------------------------------
with st.sidebar:
    st.title("🔧 Filters")
    st.markdown("---")

    # --- Filter 1: Stadsdeel + Wijk (twee afhankelijke dropdowns) ---
    st.subheader("📍 Locatie")

    alle_stadsdelen = sorted(wijken_df["stadsdeel"].dropna().unique().tolist())
    stadsdeel_opties = ["Alle stadsdelen"] + alle_stadsdelen

    gekozen_stadsdeel = st.selectbox(
        "Stadsdeel",
        options=stadsdeel_opties,
        help="Kies een stadsdeel om de wijken te filteren"
    )

    # de wijk-opties hangen af van het gekozen stadsdeel
    if gekozen_stadsdeel == "Alle stadsdelen":
        beschikbare_wijken = sorted(wijken_df["wijk_naam"].dropna().unique().tolist())
    else:
        gefilterd = wijken_df[wijken_df["stadsdeel"] == gekozen_stadsdeel]
        beschikbare_wijken = sorted(gefilterd["wijk_naam"].dropna().unique().tolist())

    # als er geen wijken zijn, laat een melding zien
    if len(beschikbare_wijken) == 0:
        st.warning(f"Geen wijken gevonden in {gekozen_stadsdeel}.")
        beschikbare_wijken = ["—"]

    wijk_opties = ["Alle wijken"] + beschikbare_wijken
    gekozen_wijk = st.selectbox(
        "Wijk",
        options=wijk_opties,
        help="De opties hier zijn afhankelijk van het gekozen stadsdeel"
    )

    # foutmelding als er niets te kiezen is
    if gekozen_wijk == "—":
        st.error("Selecteer eerst een geldig stadsdeel.")

    st.markdown("---")

    # --- Filter 2: Schooljaar range (twee afhankelijke sliders) ---
    st.subheader("📅 Schooljaar")

    # slider voor het begin- en eindjaar
    jaar_range = st.slider(
        "Kies een periode",
        min_value=0,
        max_value=len(SCHOOLJAREN) - 1,
        value=(0, len(SCHOOLJAREN) - 1),
        format="",
        help="Sleep de twee handles om de periode aan te passen"
    )
    jaar_van_idx, jaar_tot_idx = jaar_range

    # de twee waarden mogen niet hetzelfde zijn
    if jaar_van_idx == jaar_tot_idx:
        st.warning("⚠️ Kies een periode van minimaal 2 schooljaren.")
        jaar_van_idx = max(0, jaar_van_idx - 1)

    jaar_van = SCHOOLJAREN[jaar_van_idx]
    jaar_tot = SCHOOLJAREN[jaar_tot_idx]
    st.caption(f"Geselecteerd: **{jaar_van}** t/m **{jaar_tot}**")

    gekozen_jaren = SCHOOLJAREN[jaar_van_idx: jaar_tot_idx + 1]

    st.markdown("---")

    # --- Filter 3: Schooladvies typen (checkboxen met conflict-logica) ---
    st.subheader("🎓 Adviestypen")
    st.caption("Vink aan welke adviezen je wilt zien")

    gekozen_adviezen = []
    for advies in ADVIES_TYPEN:
        kleur = ADVIES_KLEUREN[advies]
        aangevinkt = st.checkbox(
            advies,
            value=True,
            key=f"cb_{advies}"
        )
        if aangevinkt:
            gekozen_adviezen.append(advies)

    # als de gebruiker niets aanvinkt, geef een melding
    if len(gekozen_adviezen) == 0:
        st.error("⚠️ Vink minimaal één adviestype aan om resultaten te zien.")
        gekozen_adviezen = ADVIES_TYPEN  # terugvallen op alles

    # knop om alles te selecteren / deselecteren
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Alles"):
            for advies in ADVIES_TYPEN:
                st.session_state[f"cb_{advies}"] = True
            st.rerun()
    with col2:
        if st.button("❌ Geen"):
            for advies in ADVIES_TYPEN:
                st.session_state[f"cb_{advies}"] = False
            st.rerun()

    st.markdown("---")
    st.caption("Groep 2 | HvA 2024-2025")

# ---------------------------------------------------------------
# Data filteren op basis van sidebar-keuzes
# ---------------------------------------------------------------
# filter duo data op gekozen jaren en adviestypen
duo_gefilterd = duo_df[
    (duo_df["schooljaar"].isin(gekozen_jaren)) &
    (duo_df["advies_type"].isin(gekozen_adviezen))
]

# filter wijken op stadsdeel/wijk
if gekozen_stadsdeel != "Alle stadsdelen":
    wijken_gefilterd = wijken_df[wijken_df["stadsdeel"] == gekozen_stadsdeel]
else:
    wijken_gefilterd = wijken_df.copy()

if gekozen_wijk not in ["Alle wijken", "—"]:
    wijken_gefilterd = wijken_gefilterd[wijken_gefilterd["wijk_naam"] == gekozen_wijk]
    duo_gefilterd    = duo_gefilterd[duo_gefilterd["wijk_naam"] == gekozen_wijk]

# ---------------------------------------------------------------
# TABS - de verschillende secties van het dashboard
# ---------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏠 Introductie",
    "🗺️ Kaart Amsterdam",
    "📊 Schooladviezen",
    "🎓 Doorstroomtoets",
    "🌍 Asielzoekers",
    "🔮 Voorspelling",
    "📚 Data & Methoden",
])


# ===============================================================
# TAB 1 - INTRODUCTIE
# ===============================================================
with tab1:
    st.title("🏫 Doorstroomtoets & Kansengelijkheid in Amsterdam")
    st.markdown("""
    **Gemaakt door Groep 2 | Hogeschool van Amsterdam | 2024-2025**

    ---

    ### Wat is de doorstroomtoets?

    Vroeger heette het de **eindtoets** (CITO). Vanaf het schooljaar **2023-2024** heet het
    de **doorstroomtoets**. Het grote verschil:

    - Bij de *eindtoets* kon de score het schooladvies omhoog **of omlaag** bijstellen.
    - Bij de *doorstroomtoets* kan het advies alleen nog maar **omhoog** worden bijgesteld.

    Het doel is om kansenongelijkheid te verkleinen: kinderen uit armere wijken werden
    vroeger vaker te laag ingeschat, ook al scoorden ze goed op de toets.

    ### Onze onderzoeksvraag

    > **Helpt de doorstroomtoets kinderen in achterstandswijken van Amsterdam?
    > En wat is het effect van asielzoekers en nieuwkomers op de schooladviezen?**

    ### Wat je in dit dashboard vindt

    | Tab | Inhoud |
    |-----|--------|
    | 🗺️ Kaart | Overzicht van Amsterdam met schooladviezen per wijk |
    | 📊 Schooladviezen | Alle adviestypen (PrO t/m VWO) per wijk vergeleken |
    | 🎓 Doorstroomtoets | Voor en na vergelijking: is er iets veranderd? |
    | 🌍 Asielzoekers | Samenhang tussen nieuwkomers en schooladviezen |
    | 🔮 Voorspelling | Welke wijk doet het beter/slechter dan verwacht? |

    ---
    """)

    # Sleutelcijfers bovenaan
    st.subheader("📈 Sleutelcijfers Amsterdam")
    col1, col2, col3, col4 = st.columns(4)

    if "pct_hoog_advies" in wijken_df.columns:
        gem_hoog  = wijken_df["pct_hoog_advies"].mean()
        max_hoog  = wijken_df["pct_hoog_advies"].max()
        min_hoog  = wijken_df["pct_hoog_advies"].min()
        kloof     = max_hoog - min_hoog
        best_wijk = wijken_df.loc[wijken_df["pct_hoog_advies"].idxmax(), "wijk_naam"]
        laag_wijk = wijken_df.loc[wijken_df["pct_hoog_advies"].idxmin(), "wijk_naam"]

        col1.metric("Gem. % hoog advies (HAVO+)", f"{gem_hoog:.1f}%")
        col2.metric("Hoogste wijk", f"{max_hoog:.1f}%", best_wijk)
        col3.metric("Laagste wijk", f"{min_hoog:.1f}%", laag_wijk)
        col4.metric("Kloof tussen wijken", f"{kloof:.1f}%", delta_color="inverse")

    st.markdown("---")
    st.markdown("""
    ### Over de doorstroomtoets in Amsterdam

    Amsterdam heeft grote verschillen tussen wijken. In Oud-Zuid wonen veel hoogopgeleide
    gezinnen met hoge inkomens. In de Bijlmer (Zuidoost) en Nieuw-West zijn er veel gezinnen
    met een lagere sociaaleconomische positie en een niet-westerse migratieachtergrond.

    Onderzoek laat al jaren zien dat kinderen uit armere gezinnen en met een niet-westerse
    achtergrond gemiddeld **lagere schooladviezen** krijgen dan je zou verwachten op basis
    van hun capaciteiten. De doorstroomtoets is bedoeld om dit te corrigeren.

    Wij analyseren of dat ook echt werkt in Amsterdam.
    """)


# ===============================================================
# TAB 2 - KAART VAN AMSTERDAM
# ===============================================================
with tab2:
    st.header("🗺️ Amsterdam in kaart")
    st.markdown("De kleur laat zien hoeveel procent van de kinderen een **hoog advies** (HAVO, HAVO/VWO of VWO) krijgt per wijk.")

    if "pct_hoog_advies" in wijken_gefilterd.columns and "lat" in wijken_gefilterd.columns:
        kaart_df = wijken_gefilterd.dropna(subset=["lat", "lon", "pct_hoog_advies"])

        fig_kaart = px.scatter_map(
            kaart_df,
            lat="lat",
            lon="lon",
            color="pct_hoog_advies",
            size="pct_hoog_advies",
            size_max=35,
            hover_name="wijk_naam",
            hover_data={
                "stadsdeel": True,
                "pct_hoog_advies": ":.1f",
                "pct_laag_advies": ":.1f",
                "gem_inkomen": True,
                "pct_niet_westers": True,
                "lat": False,
                "lon": False,
            },
            color_continuous_scale="RdYlGn",
            range_color=[0, 70],
            map_style="carto-positron",
            zoom=10.5,
            center={"lat": 52.365, "lon": 4.900},
            title="% leerlingen met hoog schooladvies (HAVO/VWO) per wijk",
            labels={"pct_hoog_advies": "% Hoog advies"},
            height=550,
        )
        fig_kaart.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
        st.plotly_chart(fig_kaart, width="stretch")
    else:
        st.info("Kaart niet beschikbaar voor de huidige selectie.")

    st.markdown("---")
    st.subheader("📍 Schoollocaties")
    st.markdown("Hieronder zie je alle basisscholen op de kaart, gekleurd per stadsdeel.")

    scholen_df = duo_gefilterd[duo_gefilterd["schooljaar"] == gekozen_jaren[-1]].drop_duplicates("brin")
    if not scholen_df.empty and "lat" in scholen_df.columns:
        fig_scholen = px.scatter_map(
            scholen_df,
            lat="lat",
            lon="lon",
            color="stadsdeel",
            hover_name="school_naam",
            hover_data={"wijk_naam": True, "stadsdeel": True, "lat": False, "lon": False},
            map_style="carto-positron",
            zoom=10.5,
            center={"lat": 52.365, "lon": 4.900},
            title=f"Basisscholen in Amsterdam ({gekozen_jaren[-1]})",
            height=450,
        )
        fig_scholen.update_traces(marker=dict(size=8))
        fig_scholen.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
        st.plotly_chart(fig_scholen, width="stretch")


# ===============================================================
# TAB 3 - SCHOOLADVIEZEN
# ===============================================================
with tab3:
    st.header("📊 Schooladviezen per wijk")
    st.markdown(f"Periode: **{jaar_van}** t/m **{jaar_tot}** | Geselecteerde adviestypen: **{len(gekozen_adviezen)}**")

    if duo_gefilterd.empty:
        st.warning("Geen data beschikbaar voor deze selectie.")
    else:
        # gemiddeld per wijk en adviestype over de gekozen jaren
        overzicht = (
            duo_gefilterd
            .groupby(["wijk_naam", "stadsdeel", "advies_type"], as_index=False)
            .agg(gem_pct=("pct", "mean"))
        )

        fig_bar = px.bar(
            overzicht,
            x="gem_pct",
            y="wijk_naam",
            color="advies_type",
            orientation="h",
            color_discrete_map=ADVIES_KLEUREN,
            category_orders={"advies_type": gekozen_adviezen},
            title="Adviesverdeling per wijk (alle typen)",
            labels={"gem_pct": "Gemiddeld %", "wijk_naam": "Wijk", "advies_type": "Adviestype"},
            height=max(400, len(overzicht["wijk_naam"].unique()) * 28),
        )
        fig_bar.update_layout(barmode="stack", legend_title="Adviestype", xaxis_title="Percentage (%)")
        st.plotly_chart(fig_bar, width="stretch")

        st.markdown("---")
        st.subheader("📉 Vergelijking: inkomen vs. schooladvies")
        st.markdown("""
        De grafiek hieronder laat zien of er een verband is tussen het **gemiddelde inkomen**
        in een wijk en het percentage **hoge adviezen** (HAVO, HAVO/VWO, VWO).
        """)

        scatter_df = wijken_gefilterd.dropna(subset=["gem_inkomen", "pct_hoog_advies"])
        if len(scatter_df) >= 3:
            # Pearson correlatie berekenen
            r, p = stats.pearsonr(scatter_df["gem_inkomen"], scatter_df["pct_hoog_advies"])

            fig_scatter = px.scatter(
                scatter_df,
                x="gem_inkomen",
                y="pct_hoog_advies",
                color="stadsdeel",
                size="pct_niet_westers",
                hover_name="wijk_naam",
                hover_data={"gem_inkomen": True, "pct_hoog_advies": True, "pct_niet_westers": True},
                trendline="ols",
                trendline_scope="overall",
                title="Inkomen vs. % hoog schooladvies per wijk",
                labels={
                    "gem_inkomen": "Gemiddeld inkomen (x€1.000)",
                    "pct_hoog_advies": "% Hoog advies (HAVO+)",
                    "pct_niet_westers": "% Niet-westers",
                },
                height=450,
            )
            st.plotly_chart(fig_scatter, width="stretch")

            ster = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "niet significant"
            st.info(f"**Pearson correlatie:** r = {r:.3f} | p-waarde = {p:.4f} ({ster})")
            st.markdown(f"""
            Een correlatie van **r = {r:.2f}** betekent dat er een **{"sterk" if abs(r) > 0.6 else "matig" if abs(r) > 0.3 else "zwak"} {"positief" if r > 0 else "negatief"} verband**
            is tussen inkomen en schooladvies. Hoe rijker de wijk, hoe hoger het advies.
            """)

        st.markdown("---")
        st.subheader("📊 Adviesverdeling als heatmap")

        heatmap_df = (
            duo_gefilterd
            .groupby(["wijk_naam", "advies_type"], as_index=False)
            .agg(gem_pct=("pct", "mean"))
            .pivot(index="wijk_naam", columns="advies_type", values="gem_pct")
            .fillna(0)
        )
        # sorteren op meeste hoge adviezen
        if "VWO" in heatmap_df.columns:
            heatmap_df = heatmap_df.sort_values("VWO", ascending=False)

        fig_heatmap = px.imshow(
            heatmap_df,
            color_continuous_scale="RdYlGn",
            title="Heatmap: % per adviestype per wijk",
            labels={"color": "%", "x": "Adviestype", "y": "Wijk"},
            height=max(400, len(heatmap_df) * 22),
            aspect="auto",
        )
        st.plotly_chart(fig_heatmap, width="stretch")


# ===============================================================
# TAB 4 - DOORSTROOMTOETS
# ===============================================================
with tab4:
    st.header("🎓 Doorstroomtoets: wat is er veranderd?")
    st.markdown("""
    De doorstroomtoets is ingevoerd in **2023-2024**. We vergelijken het laatste jaar
    van de eindtoets (**2022-2023**) met het eerste jaar van de doorstroomtoets (**2023-2024**).

    **Wat zien we?**
    - Zijn er meer hoge adviezen in 2023-2024?
    - Krijgen kinderen in armere wijken vaker een hoger bijgesteld advies?
    """)

    # voor/na vergelijking per adviestype
    voor = duo_df[duo_df["schooljaar"] == "2022-2023"]
    na   = duo_df[duo_df["schooljaar"] == "2023-2024"]

    if not voor.empty and not na.empty:
        # gemiddeld per adviestype voor heel Amsterdam
        voor_gem = voor.groupby("advies_type")["pct"].mean().reset_index().rename(columns={"pct": "2022-2023"})
        na_gem   = na.groupby("advies_type")["pct"].mean().reset_index().rename(columns={"pct": "2023-2024"})

        vergelijk = voor_gem.merge(na_gem, on="advies_type")
        vergelijk["verandering"] = (vergelijk["2023-2024"] - vergelijk["2022-2023"]).round(2)
        vergelijk = vergelijk[vergelijk["advies_type"].isin(gekozen_adviezen)]

        col1, col2 = st.columns(2)

        with col1:
            fig_voorna = go.Figure()
            fig_voorna.add_trace(go.Bar(
                name="2022-2023 (eindtoets)",
                x=vergelijk["advies_type"],
                y=vergelijk["2022-2023"],
                marker_color="#90a4ae"
            ))
            fig_voorna.add_trace(go.Bar(
                name="2023-2024 (doorstroomtoets)",
                x=vergelijk["advies_type"],
                y=vergelijk["2023-2024"],
                marker_color="#1a9850"
            ))
            fig_voorna.update_layout(
                title="Adviesverdeling: voor vs. na doorstroomtoets",
                barmode="group",
                xaxis_title="Adviestype",
                yaxis_title="Gemiddeld %",
                height=400,
                xaxis_tickangle=-30,
            )
            st.plotly_chart(fig_voorna, width="stretch")

        with col2:
            fig_delta = px.bar(
                vergelijk,
                x="advies_type",
                y="verandering",
                color="verandering",
                color_continuous_scale=["#d73027", "#fee08b", "#1a9850"],
                color_continuous_midpoint=0,
                title="Verandering per adviestype (procentpunten)",
                labels={"advies_type": "Adviestype", "verandering": "Verandering (pp)"},
                height=400,
            )
            fig_delta.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig_delta, width="stretch")

        st.markdown("---")
        st.subheader("📍 Bijgesteld advies per wijk")
        st.markdown("""
        In 2023-2024 konden leerlingen een **hoger bijgesteld advies** krijgen na de toets.
        Hieronder zie je welke wijken hier het meest van profiteerden.
        De verwachting is dat dit effect groter is in wijken met een lager inkomen.
        """)

        bijstelling = (
            na.groupby(["wijk_naam", "stadsdeel"], as_index=False)
            .agg(
                totaal=("aantal_leerlingen", "sum"),
                bijgesteld=("bijgesteld_hoger", "sum")
            )
        )
        bijstelling["pct_bijgesteld"] = (bijstelling["bijgesteld"] / bijstelling["totaal"] * 100).round(1)
        bijstelling = bijstelling.merge(
            wijken_df[["wijk_naam", "gem_inkomen", "pct_niet_westers"]],
            on="wijk_naam", how="left"
        )
        bijstelling = bijstelling.sort_values("pct_bijgesteld", ascending=False)

        fig_bij = px.bar(
            bijstelling,
            x="wijk_naam",
            y="pct_bijgesteld",
            color="gem_inkomen",
            color_continuous_scale="RdYlGn",
            title="% leerlingen met omhoog bijgesteld advies (2023-2024)",
            labels={
                "wijk_naam": "Wijk",
                "pct_bijgesteld": "% bijgesteld hoger",
                "gem_inkomen": "Gem. inkomen (x€1.000)",
            },
            height=420,
        )
        fig_bij.update_layout(xaxis_tickangle=-35)
        st.plotly_chart(fig_bij, width="stretch")

        st.markdown("""
        **Conclusie:** Wijken met een **lager gemiddeld inkomen** (rood/oranje) hebben een
        **hoger percentage bijstellingen**. Dit is precies wat de doorstroomtoets beoogde:
        kinderen die onderschat worden krijgen nu vaker een hoger advies.
        """)


# ===============================================================
# TAB 5 - ASIELZOEKERS & NIEUWKOMERS
# ===============================================================
with tab5:
    st.header("🌍 Asielzoekers & Nieuwkomers in het onderwijs")
    st.markdown("""
    Amsterdam heeft veel wijken met een hoog aandeel inwoners met een **niet-westerse
    migratieachtergrond**. Een deel hiervan zijn (voormalige) asielzoekers en statushouders.

    We gebruiken het **% niet-westerse achtergrond per wijk** (CBS 2024) als proxy,
    omdat er geen openbare data is over exacte aantallen asielzoekers per wijk.

    **Vraag:** Krijgen kinderen in wijken met veel nieuwkomers een lager schooladvies?
    En helpt de doorstroomtoets hen meer dan kinderen in andere wijken?
    """)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        scatter2_df = wijken_gefilterd.dropna(subset=["pct_niet_westers", "pct_hoog_advies"])
        if len(scatter2_df) >= 3:
            r2, p2 = stats.pearsonr(scatter2_df["pct_niet_westers"], scatter2_df["pct_hoog_advies"])
            fig_nw = px.scatter(
                scatter2_df,
                x="pct_niet_westers",
                y="pct_hoog_advies",
                color="stadsdeel",
                hover_name="wijk_naam",
                trendline="ols",
                trendline_scope="overall",
                title="% Niet-westers vs. % hoog schooladvies",
                labels={
                    "pct_niet_westers": "% Niet-westerse achtergrond",
                    "pct_hoog_advies": "% Hoog advies (HAVO+)",
                },
                height=400,
            )
            st.plotly_chart(fig_nw, width="stretch")
            ster2 = "***" if p2 < 0.001 else "**" if p2 < 0.01 else "*" if p2 < 0.05 else "niet significant"
            st.info(f"Correlatie: r = {r2:.3f} | p = {p2:.4f} ({ster2})")

    with col2:
        # bijstelling vs niet-westerse achtergrond
        na_df = duo_df[duo_df["schooljaar"] == "2023-2024"]
        bij2 = (
            na_df.groupby(["wijk_naam"], as_index=False)
            .agg(totaal=("aantal_leerlingen", "sum"), bijgesteld=("bijgesteld_hoger", "sum"))
        )
        bij2["pct_bijgesteld"] = (bij2["bijgesteld"] / bij2["totaal"] * 100).round(1)
        bij2 = bij2.merge(wijken_df[["wijk_naam", "pct_niet_westers", "stadsdeel"]], on="wijk_naam", how="left")
        bij2 = bij2.dropna(subset=["pct_niet_westers", "pct_bijgesteld"])

        if len(bij2) >= 3:
            r3, p3 = stats.pearsonr(bij2["pct_niet_westers"], bij2["pct_bijgesteld"])
            fig_bij2 = px.scatter(
                bij2,
                x="pct_niet_westers",
                y="pct_bijgesteld",
                color="stadsdeel",
                hover_name="wijk_naam",
                trendline="ols",
                trendline_scope="overall",
                title="% Niet-westers vs. % bijgesteld advies (2023-2024)",
                labels={
                    "pct_niet_westers": "% Niet-westerse achtergrond",
                    "pct_bijgesteld": "% Bijgesteld advies hoger",
                },
                height=400,
            )
            st.plotly_chart(fig_bij2, width="stretch")
            ster3 = "***" if p3 < 0.001 else "**" if p3 < 0.01 else "*" if p3 < 0.05 else "niet significant"
            st.info(f"Correlatie: r = {r3:.3f} | p = {p3:.4f} ({ster3})")

    st.markdown("---")
    st.subheader("📊 Wijken gegroepeerd: hoog vs. laag niet-westers aandeel")

    if not wijken_gefilterd.empty:
        mediaan_nw = wijken_df["pct_niet_westers"].median()
        wijken_gefilterd = wijken_gefilterd.copy()
        wijken_gefilterd["nw_groep"] = wijken_gefilterd["pct_niet_westers"].apply(
            lambda x: f"Hoog (>{mediaan_nw:.0f}%)" if x > mediaan_nw else f"Laag (≤{mediaan_nw:.0f}%)"
            if pd.notna(x) else "Onbekend"
        )

        fig_box = px.box(
            wijken_gefilterd.dropna(subset=["pct_hoog_advies"]),
            x="nw_groep",
            y="pct_hoog_advies",
            color="nw_groep",
            color_discrete_map={
                f"Hoog (>{mediaan_nw:.0f}%)": "#d73027",
                f"Laag (≤{mediaan_nw:.0f}%)": "#1a9850",
            },
            title="Hoog advies % in wijken met hoog vs. laag niet-westers aandeel",
            labels={"nw_groep": "Groep", "pct_hoog_advies": "% Hoog advies"},
            points="all",
            height=400,
        )
        st.plotly_chart(fig_box, width="stretch")

    st.markdown("""
    **Wat zien we?** Wijken met veel inwoners met een niet-westerse achtergrond hebben
    gemiddeld een **lager percentage hoge schooladviezen**. Dit suggereert dat de
    sociaaleconomische achterstand en taalbarrières die asielzoekers en nieuwkomers
    meebrengen, effect hebben op schoolprestaties.

    De doorstroomtoets kan helpen, maar is geen oplossing voor bredere achterstanden.
    Extra taalondersteuning en nieuwkomersklassen zijn ook belangrijk.
    """)


# ===============================================================
# TAB 6 - VOORSPELLEND MODEL
# ===============================================================
with tab6:
    st.header("🔮 Voorspellend model: welke wijk doet het beter dan verwacht?")
    st.markdown("""
    We bouwen een **lineair regressiemodel** dat probeert te voorspellen hoeveel
    procent hoge adviezen een wijk zou moeten hebben op basis van:
    - Gemiddeld inkomen
    - % niet-westerse achtergrond
    - % mensen met uitkering
    - % laag opgeleiden

    Wijken die **beter** scoren dan het model voorspelt, doen het goed ondanks hun
    achterstand. Wijken die **slechter** scoren, verdienen meer aandacht.
    """)

    features = ["gem_inkomen", "pct_niet_westers", "pct_uitkering", "pct_laag_opgeleid"]
    target   = "pct_hoog_advies"

    # alleen rijen waar alle kolommen beschikbaar zijn
    model_data = wijken_df[features + [target, "wijk_naam", "stadsdeel"]].dropna()

    if len(model_data) >= 6:
        X = model_data[features].values
        y = model_data[target].values

        # standaardiseren zodat de coëfficiënten vergelijkbaar zijn
        scaler = StandardScaler()
        X_sc   = scaler.fit_transform(X)

        model = LinearRegression()
        model.fit(X_sc, y)

        y_pred = model.predict(X_sc)
        residu = y - y_pred

        # R² berekenen
        ss_res = ((y - y_pred) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2     = 1 - ss_res / ss_tot

        model_data = model_data.copy()
        model_data["voorspeld"] = y_pred.round(1)
        model_data["werkelijk"] = y.round(1)
        model_data["residu"]    = residu.round(1)
        model_data["prestatie"] = model_data["residu"].apply(
            lambda r: "Beter dan verwacht" if r > 3
            else "Slechter dan verwacht" if r < -3
            else "Zoals verwacht"
        )

        st.markdown(f"**Model R² = {r2:.3f}** — het model verklaart {r2*100:.1f}% van de variatie in schooladvies.")

        col1, col2 = st.columns(2)
        with col1:
            fig_model = px.scatter(
                model_data,
                x="voorspeld",
                y="werkelijk",
                color="prestatie",
                text="wijk_naam",
                color_discrete_map={
                    "Beter dan verwacht":    "#1a9850",
                    "Zoals verwacht":        "#78909c",
                    "Slechter dan verwacht": "#d73027",
                },
                title="Voorspeld vs. werkelijk % hoog advies",
                labels={"voorspeld": "Voorspeld %", "werkelijk": "Werkelijk %"},
                height=450,
            )
            # diagonale lijn (perfecte voorspelling)
            fig_model.add_shape(
                type="line",
                x0=model_data["voorspeld"].min(), y0=model_data["voorspeld"].min(),
                x1=model_data["voorspeld"].max(), y1=model_data["voorspeld"].max(),
                line=dict(color="gray", dash="dash"),
            )
            fig_model.update_traces(textposition="top center", textfont_size=9)
            st.plotly_chart(fig_model, width="stretch")

        with col2:
            fig_residu = px.bar(
                model_data.sort_values("residu"),
                x="residu",
                y="wijk_naam",
                color="prestatie",
                orientation="h",
                color_discrete_map={
                    "Beter dan verwacht":    "#1a9850",
                    "Zoals verwacht":        "#78909c",
                    "Slechter dan verwacht": "#d73027",
                },
                title="Afwijking van de voorspelling per wijk",
                labels={"residu": "Afwijking (procentpunten)", "wijk_naam": "Wijk"},
                height=450,
            )
            fig_residu.add_vline(x=0, line_color="black", line_dash="dash")
            st.plotly_chart(fig_residu, width="stretch")

        st.markdown("---")
        st.subheader("📊 Gewicht van de factoren")

        coef_df = pd.DataFrame({
            "Factor":           features,
            "Gewicht (bèta)":   model.coef_.round(3),
            "Richting":         ["positief" if c > 0 else "negatief" for c in model.coef_],
        }).sort_values("Gewicht (bèta)", key=abs, ascending=False)

        fig_coef = px.bar(
            coef_df,
            x="Gewicht (bèta)",
            y="Factor",
            color="Richting",
            orientation="h",
            color_discrete_map={"positief": "#1a9850", "negatief": "#d73027"},
            title="Invloed van elke factor op het % hoog schooladvies",
            height=300,
        )
        fig_coef.add_vline(x=0, line_color="black")
        st.plotly_chart(fig_coef, width="stretch")

        st.markdown("""
        **Hoe lees je dit?**
        - Een **positief** gewicht betekent: hoe hoger de waarde, hoe meer hoge adviezen.
        - Een **negatief** gewicht betekent: hoe hoger de waarde, hoe minder hoge adviezen.
        - Inkomen heeft het grootste positieve effect, % niet-westers het grootste negatieve.
        """)

        # tabel met over/onderpresterende wijken
        st.markdown("---")
        st.subheader("🏆 Opvallende wijken")
        top_beter   = model_data[model_data["prestatie"] == "Beter dan verwacht"][["wijk_naam", "stadsdeel", "werkelijk", "voorspeld", "residu"]]
        top_slechter = model_data[model_data["prestatie"] == "Slechter dan verwacht"][["wijk_naam", "stadsdeel", "werkelijk", "voorspeld", "residu"]]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Beter dan verwacht** (verdiend nader onderzoek naar good practices)")
            st.dataframe(top_beter.sort_values("residu", ascending=False), hide_index=True, width="stretch")
        with col2:
            st.markdown("**Slechter dan verwacht** (verdienen extra aandacht)")
            st.dataframe(top_slechter.sort_values("residu"), hide_index=True, width="stretch")
    else:
        st.warning("Te weinig data voor het regressiemodel. Pas de filters aan.")


# ===============================================================
# TAB 7 - DATA & METHODEN
# ===============================================================
with tab7:
    st.header("📚 Data & Methoden")
    st.markdown("""
    In dit dashboard gebruiken we drie publieke databronnen. Hieronder leggen we uit
    hoe de APIs werken en hoe we de data hebben gecombineerd.
    """)

    st.subheader("🔗 Databronnen")
    for naam, bron in bronnen.items():
        status = "✅ Live" if "Live" in bron else "⚠️ Eigen data"
        st.markdown(f"**{status} — {naam}**")
        st.caption(bron)

    st.markdown("---")
    st.subheader("🛠️ Hoe de APIs werken")

    with st.expander("1. CBS OData v4 API — Kerncijfers Wijken en Buurten"):
        st.markdown("""
        **URL:** `https://odata4.cbs.nl/CBS/85984NED/TypedDataSet`

        De CBS OData API gebruikt het OData v4 protocol. Je kunt data filteren met `$filter`,
        het aantal rijen beperken met `$top`, en het formaat kiezen met `$format=json`.

        **Ons verzoek:**
        ```
        $filter=startswith(RegioS,'WK0363')   ← alleen Amsterdam-wijken
        $top=200                               ← maximaal 200 rijen
        $format=json                           ← JSON formaat
        ```

        **Dataset:** 85984NED = Kerncijfers Wijken en Buurten 2024.
        Bevat: gemiddeld inkomen, % niet-westers, % uitkering, WOZ-waarde etc. per wijk.
        """)

    with st.expander("2. DUO Open Onderwijsdata — Schooladviezen (wpoadvies-v1)"):
        st.markdown("""
        **URL:** `https://onderwijsdata.duo.nl/api/3/action/package_show?id=wpoadvies-v1`

        DUO gebruikt de CKAN API (ook gebruikt door data.overheid.nl).
        Eerst halen we de metadata op (welke bestanden zijn beschikbaar?),
        dan downloaden we de meest recente CSV.

        **Bevat:** per school (BRIN-nummer), per schooljaar, per adviestype
        (PrO, VMBO-BBL, VMBO-KBL, VMBO-TL, VMBO-TL/HAVO, HAVO, HAVO/VWO, VWO):
        - Aantal leerlingen met dit advies
        - Bijgesteld advies na doorstroomtoets (2023-2024)
        """)

    with st.expander("3. Amsterdam Data API — Schoolwijzer & Gebieden"):
        st.markdown("""
        **URL:** `https://api.data.amsterdam.nl/v1/schoolwijzer/scholen/`

        De Amsterdam Data API v1 biedt open data van de gemeente Amsterdam.
        We gebruiken de Schoolwijzer-data voor schoollocaties (lat/lon, stadsdeel).

        **GeoJSON wijkgrenzen:**
        `https://api.data.amsterdam.nl/v1/gebieden/wijken/?_format=geojson`
        """)

    st.markdown("---")
    st.subheader("🔗 Hoe we de data hebben gecombineerd")
    st.markdown("""
    **Join-strategie:**
    1. CBS-data geeft sociaaleconomische kenmerken per **wijk_code** (bijv. WK036316)
    2. DUO-data geeft schooladviezen per **school** (BRIN-nummer) en **schooljaar**
    3. We koppelen scholen aan wijken via **postcode → wijk**
    4. Daarna aggregeren we de schooladviezen per **wijk × jaar × adviestype**
    5. Het eindresultaat is één dataset met sociaaleconomische én onderwijsdata per wijk

    **Nieuwe variabelen die we hebben aangemaakt:**
    - `pct_hoog_advies` = HAVO% + HAVO/VWO% + VWO%
    - `pct_laag_advies` = PrO% + VMBO-BBL% + VMBO-KBL%
    - `pct_bijgesteld` = % leerlingen met omhoog bijgesteld advies
    - `residu` = verschil tussen werkelijk en voorspeld hoog-advies% (regressiemodel)
    """)

    st.markdown("---")
    st.subheader("📋 Ruwe data bekijken")

    with st.expander("Wijken data (CBS + advies samengevat)"):
        st.dataframe(wijken_gefilterd, width="stretch", height=300)

    with st.expander("Schooladvies data (DUO, gefilterd)"):
        st.dataframe(
            duo_gefilterd.head(500),
            width="stretch",
            height=300
        )
        if len(duo_gefilterd) > 500:
            st.caption(f"Toont 500 van {len(duo_gefilterd):,} rijen.")

    st.markdown("---")
    st.caption("Groep 2 | Hogeschool van Amsterdam | Data Science | 2024-2025")
