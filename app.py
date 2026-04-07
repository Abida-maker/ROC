# app.py
# Doorstroomtoets & Kansengelijkheid in Amsterdam
# Gemaakt door: Groep 2
#
# We onderzoeken of de doorstroomtoets (ingevoerd in 2023-2024) helpt
# om de kansenongelijkheid in Amsterdam te verkleinen.
# Daarnaast kijken we naar kansengelijkheid in schooladviezen tussen Amsterdamse wijken.

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from data import laad_alle_data, haal_amsterdam_wijkgrenzen_op, maak_duo_nooddata, ADVIES_TYPEN, ADVIES_KLEUREN, SCHOOLJAREN

# ---------------------------------------------------------------
# Pagina instellingen
# ---------------------------------------------------------------
st.set_page_config(
  page_title="Doorstroomtoets Amsterdam | Groep 2",
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
with st.spinner("Data ophalen van CBS, DUO en gemeente Amsterdam..."):
  wijken_df, duo_df, bronnen = laad_alle_data()
  wijk_geojson, wijkgrenzen_df, wijkgrenzen_bron = haal_amsterdam_wijkgrenzen_op()

# ---------------------------------------------------------------
# SIDEBAR - alle filters staan hier
# ---------------------------------------------------------------
with st.sidebar:
  st.title("Filters")
  st.markdown("---")

  # --- Filter 1: Stadsdeel + Wijk (twee afhankelijke dropdowns) ---
  st.subheader("Locatie")

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
  st.subheader("Schooljaar")

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
    st.warning(" Kies een periode van minimaal 2 schooljaren.")
    jaar_van_idx = max(0, jaar_van_idx - 1)

  jaar_van = SCHOOLJAREN[jaar_van_idx]
  jaar_tot = SCHOOLJAREN[jaar_tot_idx]
  st.caption(f"Geselecteerd: **{jaar_van}** t/m **{jaar_tot}**")

  gekozen_jaren = SCHOOLJAREN[jaar_van_idx: jaar_tot_idx + 1]

  st.markdown("---")

  # --- Filter 3: Schooladvies typen (checkboxen met conflict-logica) ---
  st.subheader("Adviestypen")
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
    st.error(" Vink minimaal één adviestype aan om resultaten te zien.")
    gekozen_adviezen = ADVIES_TYPEN # terugvallen op alles

  # knop om alles te selecteren / deselecteren
  col1, col2 = st.columns(2)
  with col1:
    if st.button(" Alles"):
      for advies in ADVIES_TYPEN:
        st.session_state[f"cb_{advies}"] = True
      st.rerun()
  with col2:
    if st.button(" Geen"):
      for advies in ADVIES_TYPEN:
        st.session_state[f"cb_{advies}"] = False
      st.rerun()

  st.markdown("---")
  st.caption("Groep 2 | HvA 2024-2025")

# ---------------------------------------------------------------
# Data filteren op basis van sidebar-keuzes
# ---------------------------------------------------------------

# DUO data filteren op geselecteerde jaren en adviestypen
geldig_jaar = duo_df["schooljaar"].isin(gekozen_jaren)
geldig_advies = duo_df["advies_type"].isin(gekozen_adviezen)
duo_gefilterd = duo_df[geldig_jaar & geldig_advies]

# wijken filteren op stadsdeel
if gekozen_stadsdeel != "Alle stadsdelen":
  wijken_gefilterd = wijken_df[wijken_df["stadsdeel"] == gekozen_stadsdeel]
else:
  wijken_gefilterd = wijken_df.copy()

# wijken en duo verder filteren op wijk
if gekozen_wijk not in ["Alle wijken", "—"]:
  wijken_gefilterd = wijken_gefilterd[wijken_gefilterd["wijk_naam"] == gekozen_wijk]
  duo_gefilterd = duo_gefilterd[duo_gefilterd["wijk_naam"] == gekozen_wijk]

# ---------------------------------------------------------------
# TABS - de verschillende secties van het dashboard
# ---------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
  " Introductie",
  " Kaart Amsterdam",
  " Schooladviezen",
  " Doorstroomtoets",
  " Voorspelling",
  " Data & Methoden",
])


# ===============================================================
# TAB 1 - INTRODUCTIE
# ===============================================================
with tab1:
  st.title(" Doorstroomtoets & Kansengelijkheid in Amsterdam")
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

  > **Helpt de doorstroomtoets kinderen in achterstandswijken van Amsterdam?**

  ### Wat je in dit dashboard vindt

  | Tab | Inhoud |
  |-----|--------|
  |  Kaart | Overzicht van Amsterdam met schooladviezen per wijk |
  |  Schooladviezen | Alle adviestypen (PrO t/m VWO) per wijk vergeleken |
  |  Doorstroomtoets | Voor en na vergelijking: is er iets veranderd? |
  |  Voorspelling | Welke wijk doet het beter/slechter dan verwacht? |

  ---
  """)

  # Sleutelcijfers bovenaan
  st.subheader(" Sleutelcijfers Amsterdam")
  col1, col2, col3, col4 = st.columns(4)

  if "pct_hoog_advies" in wijken_df.columns:
    gem_hoog = wijken_df["pct_hoog_advies"].mean()
    max_hoog = wijken_df["pct_hoog_advies"].max()
    min_hoog = wijken_df["pct_hoog_advies"].min()
    kloof   = max_hoog - min_hoog
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
  st.header(" Amsterdam in kaart")
  st.markdown("De kleur laat zien hoeveel procent van de kinderen een **hoog advies** (HAVO, HAVO/VWO of VWO) krijgt per wijk.")

  # eerst checken of we genoeg data hebben om de kaart te tekenen
  heeft_pct_kolom = "pct_hoog_advies" in wijken_gefilterd.columns
  heeft_geojson = wijk_geojson is not None
  heeft_wijkgrenzen = not wijkgrenzen_df.empty

  if heeft_pct_kolom and heeft_geojson and heeft_wijkgrenzen:

    # stap 1: verwijder rijen zonder percentage (anders crasht de kaart)
    kaart_basis = wijken_gefilterd.copy()
    kaart_basis = kaart_basis.dropna(subset=["pct_hoog_advies"])

    # stap 2: tel aantallen leerlingen op per wijk en per adviestype
    # we groeperen eerst op wijk_naam en advies_type
    groep = duo_gefilterd.groupby(["wijk_naam", "advies_type"])
    advies_aantallen = groep["aantal_leerlingen"].sum()
    advies_aantallen = advies_aantallen.reset_index()
    advies_aantallen = advies_aantallen.rename(columns={"aantal_leerlingen": "aantal"})

    # stap 3: draai de tabel zodat elk adviestype een eigen kolom wordt
    advies_breed = advies_aantallen.pivot(
      index="wijk_naam",
      columns="advies_type",
      values="aantal"
    )
    advies_breed = advies_breed.fillna(0)
    advies_breed = advies_breed.reset_index()
    advies_breed.columns.name = None # verwijder de kolomnaam "advies_type"

    # stap 4: maak kolomnamen veilig (geen /, - of spaties want dat geeft problemen)
    advies_kolommen = []  # lijst met (originele naam, nieuwe naam)
    hernoem_dict = {}   # dict voor rename()

    for advies in ADVIES_TYPEN:
      # maak een veilige kolomnaam
      nieuwe_naam = "aantal_" + advies.lower()
      nieuwe_naam = nieuwe_naam.replace("/", "_")
      nieuwe_naam = nieuwe_naam.replace("-", "_")
      nieuwe_naam = nieuwe_naam.replace(" ", "_")

      # alleen toevoegen als deze adviestype ook echt in de data zit
      if advies in advies_breed.columns:
        hernoem_dict[advies] = nieuwe_naam
        advies_kolommen.append((advies, nieuwe_naam))

    # hernoem de kolommen in de brede tabel
    advies_breed = advies_breed.rename(columns=hernoem_dict)

    # stap 5: koppel de adviescijfers aan de wijkdata
    kaart_basis = kaart_basis.merge(advies_breed, on="wijk_naam", how="left")

    # vul eventuele lege cellen op met 0
    for advies_naam, kolom_naam in advies_kolommen:
      kaart_basis[kolom_naam] = kaart_basis[kolom_naam].fillna(0)

    # stap 6: koppel wijkgrenzen (voor de polygonen op de kaart) aan de data
    kaart_polygons = wijkgrenzen_df.merge(
      kaart_basis,
      on=["wijk_naam", "stadsdeel"],
      how="inner"
    )

    # stap 7: bepaal welke kolommen we in de hover tooltip willen laten zien
    custom_data = ["stadsdeel", "gem_inkomen", "pct_hoog_advies", "pct_laag_advies"]
    for advies_naam, kolom_naam in advies_kolommen:
      custom_data.append(kolom_naam)

    # stap 8: maak de kaart met plotly
    # we gebruiken choropleth_map voor gekleurde vlakken per wijk
    fig_kaart = px.choropleth_map(
      kaart_polygons,
      geojson=wijk_geojson,
      locations="feature_id",
      featureidkey="properties.feature_id",
      color="pct_hoog_advies",
      color_continuous_scale="RdYlGn",  # rood = laag, groen = hoog
      range_color=[0, 70],
      map_style="carto-positron",
      zoom=10.5,
      center={"lat": 52.365, "lon": 4.900},
      opacity=0.55,
      hover_name="wijk_naam",
      custom_data=custom_data,
      title="% leerlingen met hoog schooladvies per wijk",
      labels={"pct_hoog_advies": "% Hoog advies"},
      height=600,
    )

    # maak de rand van elk vlak iets dikker zodat de wijken beter te zien zijn
    fig_kaart.update_traces(marker_line_width=2, marker_line_color="#1f2937")

    # stap 9: stel de hover tooltip in (wat je ziet als je met de muis over de kaart gaat)
    hoverregels = []
    hoverregels.append("<b>%{hovertext}</b>")
    hoverregels.append("Stadsdeel: %{customdata[0]}")
    hoverregels.append("Gem. inkomen: %{customdata[1]:.1f}")
    hoverregels.append("% hoog advies: %{customdata[2]:.1f}%")
    hoverregels.append("% laag advies: %{customdata[3]:.1f}%")
    hoverregels.append("<br><b>Aantallen per adviestype</b>")

    # voeg voor elk adviestype een regel toe in de tooltip
    teller = 4 # de eerste 4 posities zijn al gebruikt hierboven
    for advies_naam, kolom_naam in advies_kolommen:
      regel = f"{advies_naam}: %{{customdata[{teller}]:.0f}}"
      hoverregels.append(regel)
      teller = teller + 1

    # zet alle regels samen met een witregel ertussen
    hover_tekst = "<br>".join(hoverregels) + "<extra></extra>"
    fig_kaart.update_traces(hovertemplate=hover_tekst)

    # verwijder de marge rondom de kaart
    fig_kaart.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})

    # toon de kaart in het dashboard
    st.plotly_chart(fig_kaart, use_container_width=True)
    st.caption(f"Wijkgrenzen uit: {wijkgrenzen_bron}. Hover toont aantallen adviezen in de gekozen periode.")

  else:
    # als er geen data is, laat een melding zien
    st.info("Kaart niet beschikbaar voor de huidige selectie.")



# ===============================================================
# TAB 3 - SCHOOLADVIEZEN
# ===============================================================
with tab3:
  st.header(" Schooladviezen per wijk")
  st.markdown(f"Periode: **{jaar_van}** t/m **{jaar_tot}** | Geselecteerde adviestypen: **{len(gekozen_adviezen)}**")

  if duo_gefilterd.empty:
    st.warning("Geen data beschikbaar voor deze selectie.")
  else:
    # stap 1: aantallen per wijk, jaar en adviestype optellen
    wijk_jaar_advies = duo_gefilterd.groupby(
      ["wijk_naam", "stadsdeel", "schooljaar", "advies_type"], as_index=False
    )["aantal_leerlingen"].sum()

    # stap 2: totaal per wijk en jaar berekenen voor percentages
    wijk_jaar_totaal = wijk_jaar_advies.groupby(
      ["wijk_naam", "stadsdeel", "schooljaar"], as_index=False
    )["aantal_leerlingen"].sum()
    wijk_jaar_totaal = wijk_jaar_totaal.rename(columns={"aantal_leerlingen": "totaal"})

    # stap 3: percentages berekenen
    wijk_jaar_advies = wijk_jaar_advies.merge(
      wijk_jaar_totaal, on=["wijk_naam", "stadsdeel", "schooljaar"], how="left"
    )
    wijk_jaar_advies["pct_wijk"] = wijk_jaar_advies["aantal_leerlingen"] / wijk_jaar_advies["totaal"] * 100
    wijk_jaar_advies["pct_wijk"] = wijk_jaar_advies["pct_wijk"].round(1)

    # stap 4: zorg dat elke combinatie van wijk x jaar x adviestype bestaat (ontbrekend = 0%)
    alle_wijk_jaren = wijk_jaar_totaal[["wijk_naam", "stadsdeel", "schooljaar"]].drop_duplicates()
    alle_adviezen_df = pd.DataFrame({"advies_type": gekozen_adviezen})
    alle_wijk_jaren["sleutel"] = 1
    alle_adviezen_df["sleutel"] = 1
    volledig = alle_wijk_jaren.merge(alle_adviezen_df, on="sleutel", how="outer")
    volledig = volledig.drop(columns="sleutel")

    kolommen_nodig = ["wijk_naam", "stadsdeel", "schooljaar", "advies_type", "pct_wijk"]
    wijk_jaar_advies = volledig.merge(
      wijk_jaar_advies[kolommen_nodig],
      on=["wijk_naam", "stadsdeel", "schooljaar", "advies_type"],
      how="left"
    )
    wijk_jaar_advies["pct_wijk"] = wijk_jaar_advies["pct_wijk"].fillna(0)

    # stap 5: gemiddeld percentage per wijk over alle geselecteerde jaren
    overzicht = wijk_jaar_advies.groupby(
      ["wijk_naam", "stadsdeel", "advies_type"], as_index=False
    )["pct_wijk"].mean()
    overzicht = overzicht.rename(columns={"pct_wijk": "gem_pct"})

    aantal_wijken = len(overzicht["wijk_naam"].unique())
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
      height=max(400, aantal_wijken * 28),
    )
    fig_bar.update_layout(barmode="stack", legend_title="Adviestype", xaxis_title="Percentage (%)")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")
    st.subheader(" Vergelijking: inkomen vs. schooladvies")
    st.markdown("""
    De grafiek hieronder laat zien of er een verband is tussen het **gemiddelde inkomen**
    in een wijk en het percentage **hoge adviezen** (HAVO, HAVO/VWO, VWO).
    """)

    scatter_df = wijken_gefilterd.dropna(subset=["gem_inkomen", "pct_hoog_advies"])
    if len(scatter_df) >= 3:
      fig_scatter = px.scatter(
        scatter_df,
        x="gem_inkomen",
        y="pct_hoog_advies",
        color="stadsdeel",
        hover_name="wijk_naam",
        hover_data={"gem_inkomen": True, "pct_hoog_advies": True},
        title="Inkomen vs. % hoog schooladvies per wijk",
        labels={
          "gem_inkomen": "Gemiddeld inkomen (x€1.000)",
          "pct_hoog_advies": "% Hoog advies (HAVO+)",
        },
        height=450,
      )
      helling, intercept = np.polyfit(scatter_df["gem_inkomen"], scatter_df["pct_hoog_advies"], 1)
      x_lijn = np.linspace(scatter_df["gem_inkomen"].min(), scatter_df["gem_inkomen"].max(), 100)
      y_lijn = helling * x_lijn + intercept
      fig_scatter.add_trace(go.Scatter(
        x=x_lijn,
        y=y_lijn,
        mode="lines",
        name="Trendlijn",
        line=dict(color="#1f2937", dash="dash"),
      ))
      st.plotly_chart(fig_scatter, use_container_width=True)



# ===============================================================
# TAB 4 - DOORSTROOMTOETS
# ===============================================================
with tab4:
  st.header(" Doorstroomtoets: wat is er veranderd?")
  st.markdown("""
  De doorstroomtoets is ingevoerd in **2023-2024**. We vergelijken het laatste jaar
  van de eindtoets (**2022-2023**) met het eerste jaar van de doorstroomtoets (**2023-2024**).

  **Wat zien we?**
  - Zijn er meer hoge adviezen in 2023-2024?
  - Krijgen kinderen in armere wijken vaker een hoger bijgesteld advies?
  """)

  duo_doorstroom = duo_df.copy()
  bron_doorstroom = "live DUO-data"
  if duo_doorstroom["bijgesteld_hoger"].sum() == 0:
    duo_doorstroom = maak_duo_nooddata()
    bron_doorstroom = "projectdataset met doorstroomtoets-bijstellingen"

  st.caption(f"Bron voor deze tab: {bron_doorstroom}")

  # filter de twee vergelijkingsjaren
  voor = duo_doorstroom[duo_doorstroom["schooljaar"] == "2022-2023"]
  na  = duo_doorstroom[duo_doorstroom["schooljaar"] == "2023-2024"]

  if not voor.empty and not na.empty:
    # percentages berekenen voor 2022-2023
    voor_groep = voor.groupby("advies_type", as_index=False)["aantal_leerlingen"].sum()
    voor_groep = voor_groep.rename(columns={"aantal_leerlingen": "aantal"})
    voor_totaal = voor_groep["aantal"].sum()
    voor_groep["2022-2023"] = (voor_groep["aantal"] / voor_totaal * 100).round(1)
    voor_groep = voor_groep[["advies_type", "2022-2023"]]

    # percentages berekenen voor 2023-2024
    na_groep = na.groupby("advies_type", as_index=False)["aantal_leerlingen"].sum()
    na_groep = na_groep.rename(columns={"aantal_leerlingen": "aantal"})
    na_totaal = na_groep["aantal"].sum()
    na_groep["2023-2024"] = (na_groep["aantal"] / na_totaal * 100).round(1)
    na_groep = na_groep[["advies_type", "2023-2024"]]

    # samenvoegen en verschil berekenen
    vergelijk = voor_groep.merge(na_groep, on="advies_type")
    vergelijk["verandering"] = vergelijk["2023-2024"] - vergelijk["2022-2023"]
    vergelijk["verandering"] = vergelijk["verandering"].round(2)
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
      st.plotly_chart(fig_voorna, use_container_width=True)

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
      st.plotly_chart(fig_delta, use_container_width=True)

    if na["bijgesteld_hoger"].sum() == 0:
      st.markdown("---")
      st.info("De huidige live DUO-bron bevat geen apart bruikbare gegevens over omhoog bijgestelde adviezen per wijk.")


# ===============================================================
# TAB 5 - VOORSPELLEND MODEL
# ===============================================================
with tab5:
  st.header("Voorspellende factor: welke wijken wijken af van de verwachting?")
  st.markdown("""
  In plaats van een groot regressiemodel gebruiken we hier een compactere voorspelling
  met **een verklarende factor tegelijk**. Zo blijft duidelijk zichtbaar:
  - welke factor samenhangt met hoge adviezen
  - wat de verwachte uitkomst per wijk is
  - welke wijken beter of slechter scoren dan die verwachting
  """)

  factor_opties = {
    "Gemiddeld inkomen": "gem_inkomen",
    "% niet-westerse achtergrond": "pct_niet_westers",
    "% mensen met uitkering": "pct_uitkering",
    "% laag opgeleid": "pct_laag_opgeleid",
  }
  factor_label = st.selectbox("Kies de voorspellende factor", list(factor_opties.keys()))
  factor_kolom = factor_opties[factor_label]

  model_data = wijken_df[["wijk_naam", "stadsdeel", factor_kolom, "pct_hoog_advies"]].dropna().copy()

  if len(model_data) >= 4:
    helling, intercept = np.polyfit(model_data[factor_kolom], model_data["pct_hoog_advies"], 1)
    model_data["voorspeld"] = (helling * model_data[factor_kolom] + intercept).round(1)
    model_data["werkelijk"] = model_data["pct_hoog_advies"].round(1)
    model_data["afwijking"] = (model_data["werkelijk"] - model_data["voorspeld"]).round(1)

    ss_res = ((model_data["werkelijk"] - model_data["voorspeld"]) ** 2).sum()
    ss_tot = ((model_data["werkelijk"] - model_data["werkelijk"].mean()) ** 2).sum()
    r2 = 0 if ss_tot == 0 else 1 - (ss_res / ss_tot)

    model_data["prestatie"] = "Zoals verwacht"
    model_data.loc[model_data["afwijking"] > 3, "prestatie"] = "Beter dan verwacht"
    model_data.loc[model_data["afwijking"] < -3, "prestatie"] = "Slechter dan verwacht"

    kleur_map = {
      "Beter dan verwacht": "#1a9850",
      "Zoals verwacht": "#78909c",
      "Slechter dan verwacht": "#d73027",
    }

    st.caption(f"Verklaarde variantie met deze factor: R2 = {r2:.2f}")

    col1, col2 = st.columns(2)
    with col1:
      fig_factor = px.scatter(
        model_data,
        x=factor_kolom,
        y="werkelijk",
        color="prestatie",
        hover_name="wijk_naam",
        color_discrete_map=kleur_map,
        title=f"{factor_label} vs. % hoog advies",
        labels={factor_kolom: factor_label, "werkelijk": "% hoog advies"},
        height=430,
      )
      x_lijn = np.linspace(model_data[factor_kolom].min(), model_data[factor_kolom].max(), 100)
      y_lijn = helling * x_lijn + intercept
      fig_factor.add_trace(go.Scatter(
        x=x_lijn,
        y=y_lijn,
        mode="lines",
        name="Verwachting",
        line=dict(color="#1f2937", dash="dash")
      ))
      st.plotly_chart(fig_factor, use_container_width=True)

    with col2:
      fig_afwijking = px.bar(
        model_data.sort_values("afwijking"),
        x="afwijking",
        y="wijk_naam",
        color="prestatie",
        orientation="h",
        color_discrete_map=kleur_map,
        title="Afwijking ten opzichte van de verwachting",
        labels={"afwijking": "Afwijking (procentpunten)", "wijk_naam": "Wijk"},
        height=430,
      )
      fig_afwijking.add_vline(x=0, line_color="black", line_dash="dash")
      st.plotly_chart(fig_afwijking, use_container_width=True)

    st.markdown("---")
    st.markdown(f"""
    **Interpretatie**
    - De gekozen factor is hier **{factor_label.lower()}**.
    - De stippellijn laat zien welk % hoog advies je op basis van alleen deze factor zou verwachten.
    - Wijken rechts van nul in de staafgrafiek doen het **beter dan verwacht**.
    - Wijken links van nul doen het **slechter dan verwacht**.
    """)
  else:
    st.warning("Te weinig data voor deze voorspellende factor. Pas de filters aan.")


# ===============================================================
# TAB 6 - DATA & METHODEN
# ===============================================================
with tab6:
  st.header(" Data & Methoden")
  st.markdown("In dit dashboard gebruiken we drie publieke databronnen.")

  st.subheader(" Databronnen")
  for naam, bron in bronnen.items():
    if "Live" in bron:
      status = " Live"
    else:
      status = " Eigen data"
    st.markdown(f"**{status} — {naam}**")
    st.caption(bron)

  st.markdown("---")
  st.subheader(" Hoe de APIs werken")

  with st.expander("1. CBS OData v3 API — Kerncijfers Wijken en Buurten"):
    st.markdown("""
    **URL:** `https://opendata.cbs.nl/ODataApi/odata/85984NED/TypedDataSet`

    De CBS OData API gebruikt het OData v3 protocol. Je kunt data filteren met `$filter`,
    het aantal rijen beperken met `$top`, en het formaat kiezen met `$format=json`.

    > **Let op:** De nieuwere v4-API (`odata4.cbs.nl`) is momenteel niet bereikbaar.
    > We gebruiken daarom de stabielere v3-API via `opendata.cbs.nl`.

    **Dataset:** 85984NED = Kerncijfers Wijken en Buurten 2024.
    Bevat: gemiddeld inkomen, % niet-westers, % uitkering, WOZ-waarde etc. per wijk.
    """)

  with st.expander("2. DUO Open Onderwijsdata — Schooladviezen (wpoadvies-v1)"):
    st.markdown("""
    **URL:** `https://onderwijsdata.duo.nl/api/3/action/package_show?id=wpoadvies-v1`

    DUO gebruikt de CKAN API. Eerst halen we metadata op, dan de meest recente CSV.

    **Bevat:** per school (BRIN), per schooljaar, per adviestype het aantal leerlingen.
    """)

  with st.expander("3. Amsterdam Data API — Schoolgebouwen & Gebieden"):
    st.markdown("""
    **URL's:**
    - `https://api.data.amsterdam.nl/v1/schoolgebouwen/instelling/`
    - `https://api.data.amsterdam.nl/v1/schoolgebouwen/accommodatie/`
    - `https://api.data.amsterdam.nl/v1/gebieden/wijken/`

    We gebruiken de schoolgebouwen-data voor namen, BRIN, wijk en stadsdeel.
    De wijken-endpoint geeft de GeoJSON grenzen voor de kaart.
    """)

  st.markdown("---")
  st.subheader(" Hoe we de data hebben gecombineerd")
  st.markdown("""
  1. CBS-data geeft sociaaleconomische kenmerken per **wijk_code**
  2. DUO-data geeft schooladviezen per **BRIN** en **schooljaar**
  3. We koppelen scholen aan wijken via de Amsterdam API
  4. Daarna aggregeren we de schooladviezen per **wijk × jaar × adviestype**

  **Nieuwe variabelen:**
  - `pct_hoog_advies` = HAVO% + HAVO/VWO% + VWO%
  - `pct_laag_advies` = PrO% + VMBO-BBL% + VMBO-KBL%
  - `afwijking` = verschil werkelijk vs. voorspeld op basis van een factor
  """)

  st.markdown("---")
  st.subheader(" Ruwe data bekijken")

  with st.expander("Wijken data (CBS + advies samengevat)"):
    st.dataframe(wijken_gefilterd, use_container_width=True, height=300)

  with st.expander("Schooladvies data (DUO, gefilterd)"):
    st.dataframe(duo_gefilterd.head(500), use_container_width=True, height=300)
    if len(duo_gefilterd) > 500:
      st.caption(f"Toont 500 van {len(duo_gefilterd):,} rijen.")

  st.markdown("---")
  st.caption("Groep 2 | Hogeschool van Amsterdam | Data Science | 2024-2025")
