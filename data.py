# data.py
# Gemaakt door: Groep 2
# Hier halen we alle data op die we nodig hebben voor ons dashboard.
# We gebruiken drie bronnen:
#   1. CBS OData API  - inkomen en achtergrond per wijk
#   2. DUO Open Data  - schooladviezen per school per jaar
#   3. Amsterdam API  - schoollocaties met stadsdeel info

import requests
import pandas as pd
import numpy as np
import streamlit as st

# alle adviestypen in volgorde van laag naar hoog
ADVIES_TYPEN = [
    "Praktijkonderwijs",
    "VMBO-BBL",
    "VMBO-KBL",
    "VMBO-TL",
    "VMBO-TL/HAVO",
    "HAVO",
    "HAVO/VWO",
    "VWO",
]

# kleur per adviestype (rood = laag, groen = hoog)
ADVIES_KLEUREN = {
    "Praktijkonderwijs": "#d73027",
    "VMBO-BBL":          "#f46d43",
    "VMBO-KBL":          "#fdae61",
    "VMBO-TL":           "#fee08b",
    "VMBO-TL/HAVO":      "#d9ef8b",
    "HAVO":              "#66bd63",
    "HAVO/VWO":          "#1a9850",
    "VWO":               "#006837",
}

SCHOOLJAREN = ["2018-2019", "2019-2020", "2020-2021", "2021-2022", "2022-2023", "2023-2024"]

# De live DUO-data gebruikt numerieke adviescodes. Voor dit dashboard zetten we die
# grof om naar dezelfde 8 categorieen als in de rest van de app.
DUO_ADVIES_NAAR_TYPE = {
    1:  "Praktijkonderwijs",
    2:  "VMBO-BBL",
    3:  "VMBO-BBL",
    4:  "VMBO-KBL",
    5:  "VMBO-KBL",
    6:  "VMBO-TL",
    7:  "VMBO-TL",
    8:  "VMBO-TL/HAVO",
    9:  "HAVO",
    10: "HAVO",
    11: "HAVO/VWO",
    12: "VWO",
}


def koppel_cbs_code_aan_dashboard(wijk_code):
    code = str(wijk_code).strip()

    if code.startswith("WK0363A"):
        return "Centrum"
    if code.startswith("WK0363B"):
        return "Westelijk Havengebied"

    if code in ["WK0363EA", "WK0363EB", "WK0363EC", "WK0363ED", "WK0363EE"]:
        return "Westerpark"
    if code in ["WK0363EF", "WK0363EG", "WK0363EH", "WK0363EJ", "WK0363EK"]:
        return "Bos en Lommer"
    if code.startswith("WK0363E"):
        return "Oud-West / De Baarsjes"

    if code in ["WK0363FA", "WK0363FB", "WK0363FC", "WK0363FD", "WK0363FE"]:
        return "Geuzenveld-Slotermeer"
    if code in ["WK0363FF", "WK0363FG", "WK0363FH", "WK0363FJ", "WK0363FK"]:
        return "Osdorp"
    if code in ["WK0363FL", "WK0363FM", "WK0363FN"]:
        return "Slotervaart"
    if code in ["WK0363FP", "WK0363FQ"]:
        return "Aker, Sloten en Nieuw Sloten"

    if code in ["WK0363KA", "WK0363KB", "WK0363KC", "WK0363KD"]:
        return "Oud-Zuid"
    if code in ["WK0363KE", "WK0363KF", "WK0363KG", "WK0363KH"]:
        return "De Pijp / Rivierenbuurt"
    if code in ["WK0363KJ", "WK0363KK", "WK0363KL", "WK0363KM"]:
        return "Buitenveldert / Zuidas"
    if code in ["WK0363KN", "WK0363KP", "WK0363KQ", "WK0363KR"]:
        return "Zuideramstel"

    if code in ["WK0363MA", "WK0363MB", "WK0363MC", "WK0363MD"]:
        return "Watergraafsmeer"
    if code in ["WK0363ME", "WK0363MF", "WK0363MG", "WK0363MH"]:
        return "Indische Buurt"
    if code in ["WK0363MJ", "WK0363MK", "WK0363ML"]:
        return "IJburg / Zeeburgereiland"
    if code in ["WK0363MM", "WK0363MN", "WK0363MP", "WK0363MQ"]:
        return "De Omval / Overamstel"

    if code in ["WK0363NA", "WK0363NB", "WK0363NC", "WK0363ND", "WK0363NE", "WK0363NF", "WK0363NG"]:
        return "Noord-West"
    if code in ["WK0363NH", "WK0363NJ", "WK0363NK", "WK0363NL", "WK0363NM", "WK0363NN", "WK0363NP", "WK0363NQ"]:
        return "Noord-Oost"

    if code in ["WK0363TA", "WK0363TB", "WK0363TC", "WK0363TD"]:
        return "Bijlmer-Centrum"
    if code in ["WK0363TE", "WK0363TF", "WK0363TG", "WK0363TH"]:
        return "Bijlmer-Oost"
    if code in ["WK0363TJ", "WK0363TK", "WK0363TL", "WK0363TM"]:
        return "Gaasperdam / Driemond"

    return None


# ---------------------------------------------------------------
# 1. CBS data ophalen - inkomen, niet-westerse achtergrond etc.
# ---------------------------------------------------------------

@st.cache_data(ttl=86400)
def haal_cbs_data_op():
    # CBS OData v3 API - Kerncijfers Wijken en Buurten 2024 (tabel 85984NED)
    url = "https://opendata.cbs.nl/ODataApi/odata/85984NED/TypedDataSet"
    params = {
        "$filter": "startswith(WijkenEnBuurten,'WK0363')",
        "$format": "json",
        "$top": 200
    }

    try:
        antwoord = requests.get(url, params=params, timeout=20)
        antwoord.raise_for_status()
        records = antwoord.json().get("value", [])

        if len(records) > 0:
            df = pd.DataFrame(records)

            # kolomnamen hernoemen naar begrijpelijke namen
            hernoem = {}
            al_gebruikt = set()

            for kolom in df.columns:
                k = kolom.lower()
                nieuwe_naam = None

                if kolom in ("RegioS", "WijkenEnBuurten"):
                    nieuwe_naam = "wijk_code"
                elif "inkomen" in k and "gemiddeld" in k and "ontvanger" in k:
                    nieuwe_naam = "gem_inkomen"
                elif "inwoners" in k and "aantal" in k:
                    nieuwe_naam = "aantal_inwoners"
                elif "nietwester" in k.replace(" ", "").replace("-", "") or ("buiten" in k and "europa" in k):
                    nieuwe_naam = "pct_niet_westers"
                elif "bijstand" in k or ("uitkering" in k and "relatief" in k):
                    nieuwe_naam = "pct_uitkering"
                elif ("basisonderwijs" in k or "vmbo" in k or "mbo1" in k) and ("laag" in k or "basis" in k or "vmbo" in k):
                    nieuwe_naam = "pct_laag_opgeleid"
                elif ("hbo" in k or "wo" in k) and ("hoog" in k or "hbo" in k):
                    nieuwe_naam = "pct_hoog_opgeleid"
                elif "woz" in k and "gemiddeld" in k:
                    nieuwe_naam = "gem_woz"

                if nieuwe_naam is not None and nieuwe_naam not in al_gebruikt:
                    hernoem[kolom] = nieuwe_naam
                    al_gebruikt.add(nieuwe_naam)

            df = df.rename(columns=hernoem)

            # dubbele kolommen verwijderen
            if df.columns.duplicated().any():
                df = df.loc[:, ~df.columns.duplicated()]

            df["wijk_code"] = df["wijk_code"].astype(str).str.strip()
            df["wijk_naam"] = df["wijk_code"].apply(koppel_cbs_code_aan_dashboard)
            df = df[df["wijk_naam"].notna()].copy()

            nooddata = maak_cbs_nooddata()
            wijk_info = nooddata[["wijk_code", "wijk_naam", "stadsdeel", "lat", "lon"]]

            # alle kolommen numeriek maken
            numerieke_kolommen = []
            overslaan = ["ID", "wijk_code", "wijk_naam", "Gemeentenaam_1", "SoortRegio_2", "Codering_3"]
            for kolom in df.columns:
                if kolom in overslaan:
                    continue
                df[kolom] = pd.to_numeric(df[kolom], errors="coerce")
                if pd.api.types.is_numeric_dtype(df[kolom]):
                    numerieke_kolommen.append(kolom)

            # per wijk samenvatten
            aggregaties = {}
            for kolom in numerieke_kolommen:
                if kolom == "aantal_inwoners":
                    aggregaties[kolom] = "sum"
                else:
                    aggregaties[kolom] = "mean"

            df = df.groupby("wijk_naam", as_index=False).agg(aggregaties)

            # percentages berekenen
            if "pct_niet_westers" in df.columns and "aantal_inwoners" in df.columns:
                df["pct_niet_westers"] = df["pct_niet_westers"] / df["aantal_inwoners"] * 100
                df["pct_niet_westers"] = df["pct_niet_westers"].round(1)

            if "pct_uitkering" in df.columns and "aantal_inwoners" in df.columns:
                df["pct_uitkering"] = df["pct_uitkering"] / df["aantal_inwoners"] * 100
                df["pct_uitkering"] = df["pct_uitkering"].round(1)

            if "pct_hoog_opgeleid" in df.columns and "pct_laag_opgeleid" in df.columns and "HavoVwoMbo24_68" in df.columns:
                totaal_opleiding = df["pct_laag_opgeleid"] + df["HavoVwoMbo24_68"] + df["pct_hoog_opgeleid"]
                df["pct_hoog_opgeleid"] = (df["pct_hoog_opgeleid"] / totaal_opleiding * 100).round(1)
                df["pct_laag_opgeleid"] = (df["pct_laag_opgeleid"] / totaal_opleiding * 100).round(1)

            df = wijk_info.merge(df, on="wijk_naam", how="left")
            return df, "Live data van CBS OData API (samengevoegd naar dashboardwijken)"

    except Exception:
        pass

    return maak_cbs_nooddata(), "Eigen data (CBS API niet bereikbaar)"


def maak_cbs_nooddata():
    # Amsterdamse wijken met echte kenmerken
    # bronnen: OIS Amsterdam 2023, CBS Kerncijfers 2023
    wijken = [
        # (wijk_code, wijk_naam, stadsdeel, gem_inkomen (x1000), pct_niet_westers,
        #  pct_uitkering, pct_hoog_opgeleid, pct_laag_opgeleid, gem_woz, lat, lon)
        ("WK036300", "Centrum",                        "Centrum",    38, 20,  8, 55, 12, 560, 52.373, 4.893),
        ("WK036301", "Oud-West / De Baarsjes",         "West",       33, 28, 11, 52, 15, 430, 52.368, 4.867),
        ("WK036302", "Westerpark",                     "West",       35, 25,  9, 54, 13, 450, 52.387, 4.868),
        ("WK036303", "Geuzenveld-Slotermeer",          "Nieuw-West", 22, 62, 22, 20, 38, 210, 52.387, 4.804),
        ("WK036304", "Osdorp",                         "Nieuw-West", 23, 55, 20, 22, 35, 220, 52.360, 4.795),
        ("WK036305", "Slotervaart",                    "Nieuw-West", 26, 48, 17, 28, 30, 240, 52.357, 4.829),
        ("WK036306", "Bos en Lommer",                  "West",       24, 55, 19, 22, 35, 280, 52.380, 4.852),
        ("WK036307", "Oud-Zuid",                       "Zuid",       52, 10,  5, 70,  8, 720, 52.349, 4.877),
        ("WK036308", "De Pijp / Rivierenbuurt",        "Zuid",       40, 18,  7, 62, 10, 520, 52.351, 4.898),
        ("WK036309", "Buitenveldert / Zuidas",         "Zuid",       42, 15,  6, 65,  9, 580, 52.335, 4.872),
        ("WK036310", "De Omval / Overamstel",          "Oost",       35, 22, 10, 48, 15, 380, 52.336, 4.928),
        ("WK036311", "Watergraafsmeer",                "Oost",       36, 20,  9, 55, 12, 420, 52.354, 4.934),
        ("WK036312", "Indische Buurt",                 "Oost",       30, 35, 14, 42, 20, 350, 52.366, 4.940),
        ("WK036313", "IJburg / Zeeburgereiland",       "Oost",       40, 18,  7, 60, 10, 440, 52.358, 4.978),
        ("WK036314", "Noord-West",                     "Noord",      28, 28, 15, 35, 25, 280, 52.407, 4.873),
        ("WK036315", "Noord-Oost",                     "Noord",      26, 32, 17, 30, 28, 260, 52.405, 4.935),
        ("WK036316", "Bijlmer-Centrum",                "Zuidoost",   20, 82, 28, 16, 42, 185, 52.314, 4.959),
        ("WK036317", "Bijlmer-Oost",                   "Zuidoost",   19, 85, 30, 14, 45, 175, 52.305, 4.978),
        ("WK036318", "Gaasperdam / Driemond",          "Zuidoost",   24, 58, 18, 22, 32, 210, 52.296, 4.993),
        ("WK036319", "Aker, Sloten en Nieuw Sloten",   "Nieuw-West", 30, 35, 12, 38, 20, 310, 52.345, 4.816),
        ("WK036320", "Zuideramstel",                   "Zuid",       38, 16,  8, 58, 11, 480, 52.330, 4.908),
        ("WK036321", "Westelijk Havengebied",          "West",       32, 18, 10, 40, 18, 290, 52.394, 4.840),
    ]

    df = pd.DataFrame(wijken, columns=[
        "wijk_code", "wijk_naam", "stadsdeel", "gem_inkomen", "pct_niet_westers",
        "pct_uitkering", "pct_hoog_opgeleid", "pct_laag_opgeleid", "gem_woz", "lat", "lon"
    ])
    return df


# ---------------------------------------------------------------
# 2. DUO data ophalen - schooladviezen per school per jaar
# ---------------------------------------------------------------

@st.cache_data(ttl=86400)
def haal_duo_data_op(scholen_df):
    # DUO Open Onderwijsdata - dataset wpoadvies-v1
    url = "https://onderwijsdata.duo.nl/api/3/action/package_show"
    params = {"id": "wpoadvies-v1"}

    try:
        antwoord = requests.get(url, params=params, timeout=10)
        antwoord.raise_for_status()
        package = antwoord.json().get("result", {})
        bronnen = package.get("resources", [])

        # zoek alle CSV-bestanden en pak de meest recente
        csv_bestanden = []
        for b in bronnen:
            if b.get("format", "").upper() == "CSV":
                csv_bestanden.append(b)

        if len(csv_bestanden) > 0:
            csv_bestanden_gesorteerd = sorted(csv_bestanden, key=lambda x: x.get("name", ""), reverse=True)
            nieuwste = csv_bestanden_gesorteerd[0]

            df = pd.read_csv(
                nieuwste["url"],
                sep=",",
                dtype={"INSTELLINGSCODE": str, "VESTIGINGSCODE": str},
            )

            # BRIN samenstellen uit instelling + vestigingscode
            instelling = df["INSTELLINGSCODE"].fillna("").str.strip().str.upper()
            vestiging = df["VESTIGINGSCODE"].fillna("").str.zfill(2)
            df["brin"] = instelling + vestiging

            # schooljaar maken van peiljaar (bijv. 2024 → "2023-2024")
            df["schooljaar"] = (df["PEILJAAR"] - 1).astype(str) + "-" + df["PEILJAAR"].astype(str)

            # adviescodes omzetten naar onze categorieën
            df["advies_type"] = df["ADVIES"].map(DUO_ADVIES_NAAR_TYPE)
            df["aantal_leerlingen"] = pd.to_numeric(df["AANTAL_LEERLINGEN"], errors="coerce").fillna(0)

            # alleen Amsterdam-data en geldige adviezen
            geldig_jaar = df["schooljaar"].isin(SCHOOLJAREN)
            geldig_advies = df["advies_type"].notna()
            geldig_aantal = df["aantal_leerlingen"] >= 0
            df = df[geldig_jaar & geldig_advies & geldig_aantal].copy()

            # koppelen aan schooldata via BRIN
            df = df.merge(
                scholen_df[["brin", "school_naam", "stadsdeel", "wijk_naam"]],
                on="brin",
                how="inner"
            )

            # wijkcodes toevoegen vanuit de nooddata
            wijk_info = maak_cbs_nooddata()[["wijk_code", "wijk_naam", "stadsdeel"]]
            df = df.merge(wijk_info, on=["wijk_naam", "stadsdeel"], how="left")

            if len(df) > 0 and "wijk_code" in df.columns:
                groep_kolommen = ["brin", "school_naam", "wijk_code", "wijk_naam", "stadsdeel", "schooljaar", "advies_type"]
                df = df.groupby(groep_kolommen, as_index=False)["aantal_leerlingen"].sum()
                df["bijgesteld_hoger"] = 0
                return df, "Live data van DUO Open Onderwijsdata (adviescodes samengevoegd, bijstelling niet apart beschikbaar)"

    except Exception:
        pass

    return maak_duo_nooddata(), "Eigen data (DUO API niet bereikbaar)"


def maak_duo_nooddata():
    # Zelf gemaakte schooladviesdata voor Amsterdam
    # De verhouding per adviestype is gebaseerd op echte DUO-cijfers (2018-2024)
    rng = np.random.default_rng(42)
    cbs_df = maak_cbs_nooddata()
    rijen = []

    for _, wijk in cbs_df.iterrows():
        # inkomen_score: 0 = arm, 1 = rijk
        inkomen_score = (wijk["gem_inkomen"] - 15) / 40
        # nw_score: aandeel niet-westers (0 tot 1)
        nw_score = wijk["pct_niet_westers"] / 100

        # basisverdeling per adviestype in procenten
        verdeling = [
            max(1, 10 - inkomen_score * 8  + nw_score * 5),   # Praktijkonderwijs
            max(1, 16 - inkomen_score * 12 + nw_score * 7),   # VMBO-BBL
            max(1, 18 - inkomen_score * 10 + nw_score * 5),   # VMBO-KBL
            max(1, 20 - inkomen_score *  6 + nw_score * 3),   # VMBO-TL
            max(1,  8 + inkomen_score *  2 - nw_score * 2),   # VMBO-TL/HAVO
            max(1, 12 + inkomen_score * 10 - nw_score * 5),   # HAVO
            max(1,  5 + inkomen_score *  7 - nw_score * 3),   # HAVO/VWO
            max(1,  5 + inkomen_score * 17 - nw_score * 8),   # VWO
        ]
        totaal = sum(verdeling)
        verdeling = [v / totaal * 100 for v in verdeling]

        n_scholen = max(3, int(8 + inkomen_score * 5))

        for school_nr in range(n_scholen):
            brin = f"{wijk['wijk_code'][2:7]}{school_nr:02d}"

            for jaar in SCHOOLJAREN:
                jaar_index = SCHOOLJAREN.index(jaar)

                # kleine jaarlijkse verbetering simuleren
                verdeling_dit_jaar = verdeling.copy()
                verdeling_dit_jaar[0] = max(1, verdeling_dit_jaar[0] - jaar_index * 0.15)
                verdeling_dit_jaar[-1] = verdeling_dit_jaar[-1] + jaar_index * 0.1

                # willekeurige ruis per school toevoegen
                ruis = rng.normal(0, 2, len(ADVIES_TYPEN))
                verdeling_met_ruis = []
                for v, r in zip(verdeling_dit_jaar, ruis):
                    verdeling_met_ruis.append(max(0.5, v + r))

                totaal_jaar = sum(verdeling_met_ruis)
                verdeling_dit_jaar = [v / totaal_jaar * 100 for v in verdeling_met_ruis]

                totaal_leerlingen = int(rng.integers(40, 110))

                for i in range(len(ADVIES_TYPEN)):
                    advies = ADVIES_TYPEN[i]
                    pct = verdeling_dit_jaar[i]
                    aantal = max(0, int(round(totaal_leerlingen * pct / 100)))
                    if aantal == 0:
                        continue

                    # doorstroomtoets bijstelling alleen in 2023-2024
                    bijgesteld = 0
                    if jaar == "2023-2024":
                        kans = max(0.03, 0.18 - inkomen_score * 0.14)
                        bijgesteld = int(round(aantal * kans))

                    rijen.append({
                        "brin":              brin,
                        "school_naam":       f"Basisschool {wijk['wijk_naam']} {school_nr + 1}",
                        "wijk_code":         wijk["wijk_code"],
                        "wijk_naam":         wijk["wijk_naam"],
                        "stadsdeel":         wijk["stadsdeel"],
                        "schooljaar":        jaar,
                        "advies_type":       advies,
                        "aantal_leerlingen": aantal,
                        "bijgesteld_hoger":  bijgesteld,
                        "lat":               wijk["lat"] + rng.uniform(-0.008, 0.008),
                        "lon":               wijk["lon"] + rng.uniform(-0.008, 0.008),
                    })

    return pd.DataFrame(rijen)


# ---------------------------------------------------------------
# 3. Amsterdam schooldata ophalen
# ---------------------------------------------------------------

@st.cache_data(ttl=86400)
def haal_amsterdam_scholen_op():
    # Haal schooldata op van de Amsterdam schoolgebouwen API
    instellingen_url = "https://api.data.amsterdam.nl/v1/schoolgebouwen/instelling/"
    accommodaties_url = "https://api.data.amsterdam.nl/v1/schoolgebouwen/accommodatie/"

    try:
        instellingen_resp = requests.get(instellingen_url, params={"_pageSize": 2000}, timeout=30)
        accommodaties_resp = requests.get(accommodaties_url, params={"_pageSize": 2000}, timeout=30)
        instellingen_resp.raise_for_status()
        accommodaties_resp.raise_for_status()

        instellingen_records = instellingen_resp.json().get("_embedded", {}).get("instelling", [])
        accommodaties_records = accommodaties_resp.json().get("_embedded", {}).get("accommodatie", [])

        if len(instellingen_records) == 0 or len(accommodaties_records) == 0:
            raise ValueError("Amsterdam API gaf geen schoolrecords terug")

        instellingen_df = pd.DataFrame(instellingen_records)
        accommodaties_df = pd.DataFrame(accommodaties_records)

        # accommodaties hernoemen voor de koppeling
        accommodaties_klein = accommodaties_df[["instellingId", "stadsdeel", "wijk", "adresStraat", "archief", "mIsActief"]]
        accommodaties_klein = accommodaties_klein.rename(columns={
            "archief": "archief_accommodatie",
            "mIsActief": "actief_accommodatie"
        })

        scholen_df = instellingen_df.merge(accommodaties_klein, on="instellingId", how="left")

        # alleen scholen met een BRIN, naam en stadsdeel
        heeft_brin = scholen_df["brinNummerDuo"].notna()
        heeft_naam = scholen_df["naam"].notna()
        heeft_stadsdeel = scholen_df["stadsdeel"].notna()
        scholen_df = scholen_df[heeft_brin & heeft_naam & heeft_stadsdeel].copy()

        # alleen actieve scholen
        is_actief = scholen_df["mIsActief"].eq(True)
        accommodatie_actief = scholen_df["actief_accommodatie"].eq(True)
        niet_archief = scholen_df["archief"].fillna("Nee") != "Ja"
        accommodatie_niet_archief = scholen_df["archief_accommodatie"].fillna("Nee") != "Ja"
        scholen_df = scholen_df[is_actief & accommodatie_actief & niet_archief & accommodatie_niet_archief].copy()

        # alleen basisscholen en speciaal basisonderwijs
        is_basisschool = scholen_df["soort"].fillna("").str.contains("BO|SBO", case=False, regex=True)
        scholen_df = scholen_df[is_basisschool].copy()

        # BRIN klaarmaken
        scholen_df["brin"] = scholen_df["brinNummerDuo"].astype(str).str.strip().str.upper()
        scholen_df = scholen_df.rename(columns={"naam": "school_naam", "wijk": "wijk_naam"})

        # wijknamen koppelen aan onze dashboardwijken
        nieuwe_wijk_namen = []
        for _, rij in scholen_df.iterrows():
            nieuwe_naam = koppel_wijk_naam_aan_dashboard(rij["wijk_naam"], rij["stadsdeel"])
            nieuwe_wijk_namen.append(nieuwe_naam)
        scholen_df["wijk_naam"] = nieuwe_wijk_namen

        scholen_df = scholen_df[["brin", "school_naam", "stadsdeel", "wijk_naam", "adresStraat"]]
        scholen_df = scholen_df.drop_duplicates(subset=["brin"]).reset_index(drop=True)

        return scholen_df, "Live data van Amsterdam schoolgebouwen API"

    except Exception:
        return maak_amsterdam_scholen_nooddata(), "Eigen data (Amsterdam API niet bereikbaar)"


def maak_amsterdam_scholen_nooddata():
    # Als de gemeente-API niet werkt, gebruiken we de scholen uit de nooddata.
    scholen_df = maak_duo_nooddata().drop_duplicates(subset=["brin"]).copy()
    scholen_df = scholen_df[["brin", "school_naam", "stadsdeel", "wijk_naam"]]
    return scholen_df.reset_index(drop=True)


@st.cache_data(ttl=86400)
def haal_amsterdam_wijkgrenzen_op():
    # Haal officiele wijkgrenzen op en koppel die aan de grotere wijkgroepen van het dashboard.
    metadata_url = "https://api.data.amsterdam.nl/v1/gebieden/wijken/"
    geojson_url = "https://api.data.amsterdam.nl/v1/gebieden/wijken/"

    try:
        metadata_resp = requests.get(metadata_url, params={"_pageSize": 500}, timeout=30)
        geojson_resp = requests.get(geojson_url, params={"_format": "geojson", "_pageSize": 500}, timeout=30)
        metadata_resp.raise_for_status()
        geojson_resp.raise_for_status()

        metadata_records = metadata_resp.json().get("_embedded", {}).get("wijken", [])
        geojson = geojson_resp.json()

        # de metadata heeft cbsCode en stadsdeel per identificatie
        # de GeoJSON heeft cbsCode NIET in properties, maar wel identificatie
        # daarom bouwen we een koppeltabel op basis van identificatie
        info_per_identificatie = {}
        for record in metadata_records:
            identificatie = record.get("identificatie")
            cbs_code = record.get("cbsCode")
            stadsdeel = record.get("_links", {}).get("ligtInStadsdeel", {}).get("title")
            if identificatie and stadsdeel:
                info_per_identificatie[identificatie] = {
                    "cbs_code": cbs_code,
                    "stadsdeel": stadsdeel,
                }

        features = []
        rijen = []
        for feature in geojson.get("features", []):
            properties = feature.get("properties", {})
            officiele_wijk_naam = properties.get("naam")

            # identificatie gebruiken om stadsdeel op te zoeken uit de metadata
            identificatie = properties.get("identificatie")
            wijk_info = info_per_identificatie.get(identificatie, {})
            cbs_code = wijk_info.get("cbs_code")
            stadsdeel = wijk_info.get("stadsdeel")

            wijk_naam = koppel_wijk_naam_aan_dashboard(officiele_wijk_naam, stadsdeel)

            if not wijk_naam:
                continue

            feature_id = feature.get("id")
            properties["feature_id"] = feature_id
            properties["dashboard_wijk_naam"] = wijk_naam
            properties["stadsdeel"] = stadsdeel

            features.append(feature)
            rijen.append({
                "feature_id": feature_id,
                "cbs_code": cbs_code,
                "officiele_wijk_naam": officiele_wijk_naam,
                "wijk_naam": wijk_naam,
                "stadsdeel": stadsdeel,
            })

        wijk_geojson = {
            "type": "FeatureCollection",
            "features": features,
        }
        wijkgrenzen_df = pd.DataFrame(rijen)

        return wijk_geojson, wijkgrenzen_df, "Live data van Amsterdam wijkgrenzen API"

    except Exception:
        return None, pd.DataFrame(), "Amsterdam wijkgrenzen API niet bereikbaar"


def koppel_wijk_naam_aan_dashboard(wijk_naam, stadsdeel):
    # De gemeente gebruikt veel kleinere buurtnamen dan ons dashboard.
    # Daarom koppelen we die hier simpel aan onze grotere wijkgroepen.
    wijk = str(wijk_naam).lower()
    stadsdeel = str(stadsdeel)

    if stadsdeel == "Centrum":
        return "Centrum"

    if stadsdeel == "West":
        if "bos en lommer" in wijk:
            return "Bos en Lommer"
        if "westerpark" in wijk or "staatslieden" in wijk or "spaarndammer" in wijk:
            return "Westerpark"
        if "haven" in wijk or "sloterdijk" in wijk:
            return "Westelijk Havengebied"
        return "Oud-West / De Baarsjes"

    if stadsdeel == "Nieuw-West":
        if "geuzenveld" in wijk or "slotermeer" in wijk:
            return "Geuzenveld-Slotermeer"
        if "osdorp" in wijk:
            return "Osdorp"
        if "aker" in wijk or "sloten" in wijk:
            return "Aker, Sloten en Nieuw Sloten"
        return "Slotervaart"

    if stadsdeel == "Zuid":
        if "buitenveldert" in wijk or "zuidas" in wijk:
            return "Buitenveldert / Zuidas"
        if "pijp" in wijk or "rivierenbuurt" in wijk:
            return "De Pijp / Rivierenbuurt"
        if "amstel" in wijk or "rai" in wijk:
            return "Zuideramstel"
        return "Oud-Zuid"

    if stadsdeel == "Oost":
        if "ijburg" in wijk or "zeeburgereiland" in wijk:
            return "IJburg / Zeeburgereiland"
        if "indische" in wijk:
            return "Indische Buurt"
        if "omval" in wijk or "overamstel" in wijk or "havengebied" in wijk:
            return "De Omval / Overamstel"
        return "Watergraafsmeer"

    if stadsdeel == "Noord":
        if "nieuwendam" in wijk or "banne" in wijk or "buikslotermeer" in wijk:
            return "Noord-Oost"
        return "Noord-West"

    if stadsdeel == "Zuidoost":
        if "gaasperdam" in wijk or "driemond" in wijk or "gein" in wijk or "reigersbos" in wijk:
            return "Gaasperdam / Driemond"
        if "bijlmer-oost" in wijk or "nellestein" in wijk:
            return "Bijlmer-Oost"
        return "Bijlmer-Centrum"

    return wijk_naam


# ---------------------------------------------------------------
# 4. Gecombineerde dataset maken
# ---------------------------------------------------------------

@st.cache_data(ttl=86400)
def laad_alle_data():
    cbs_df, cbs_bron = haal_cbs_data_op()
    scholen_df, amsterdam_bron = haal_amsterdam_scholen_op()
    duo_df, duo_bron = haal_duo_data_op(scholen_df)

    if "wijk_code" not in duo_df.columns:
        duo_df = maak_duo_nooddata()
        duo_bron = "Eigen data (live DUO data heeft andere structuur dan verwacht)"

    nooddata = maak_cbs_nooddata()
    cbs_wijken = set(cbs_df["wijk_code"].astype(str).str.strip()) if "wijk_code" in cbs_df.columns else set()
    duo_wijken = set(duo_df["wijk_code"].astype(str).str.strip())
    if not (duo_wijken & cbs_wijken):
        cbs_df = nooddata
        cbs_bron = "Eigen data (CBS wijk-codes komen niet overeen met DUO-data)"

    ontbrekende_kolommen = [k for k in ["wijk_naam", "stadsdeel", "lat", "lon"] if k not in cbs_df.columns]
    if len(ontbrekende_kolommen) > 0:
        extra = nooddata[["wijk_code"] + ontbrekende_kolommen]
        cbs_df = cbs_df.merge(extra, on="wijk_code", how="left")

    totaal_per_wijk_jaar = duo_df.groupby(["wijk_code", "schooljaar"])["aantal_leerlingen"].sum()
    totaal_per_wijk_jaar = totaal_per_wijk_jaar.reset_index()
    totaal_per_wijk_jaar = totaal_per_wijk_jaar.rename(columns={"aantal_leerlingen": "totaal"})

    duo_df = duo_df.merge(totaal_per_wijk_jaar, on=["wijk_code", "schooljaar"])
    duo_df["pct"] = (duo_df["aantal_leerlingen"] / duo_df["totaal"] * 100).round(1)

    aantal_niet_nul = duo_df["aantal_leerlingen"].replace(0, np.nan)
    duo_df["pct_bijgesteld"] = (duo_df["bijgesteld_hoger"] / aantal_niet_nul * 100).round(1)

    laatste_jaar = duo_df[duo_df["schooljaar"] == "2023-2024"]
    wijk_advies = laatste_jaar.groupby(["wijk_code", "advies_type"], as_index=False)["aantal_leerlingen"].sum()
    wijk_totaal = wijk_advies.groupby("wijk_code", as_index=False)["aantal_leerlingen"].sum()
    wijk_totaal = wijk_totaal.rename(columns={"aantal_leerlingen": "totaal"})
    wijk_advies = wijk_advies.merge(wijk_totaal, on="wijk_code", how="left")
    wijk_advies["pct_wijk"] = (wijk_advies["aantal_leerlingen"] / wijk_advies["totaal"] * 100).round(1)
    wijk_advies = wijk_advies.pivot(index="wijk_code", columns="advies_type", values="pct_wijk")
    wijk_advies = wijk_advies.reset_index()
    wijk_advies.columns.name = None

    wijken_df = cbs_df.merge(wijk_advies, on="wijk_code", how="left")

    hoog_kolommen = [k for k in ["HAVO", "HAVO/VWO", "VWO"] if k in wijken_df.columns]
    laag_kolommen = [k for k in ["Praktijkonderwijs", "VMBO-BBL", "VMBO-KBL"] if k in wijken_df.columns]
    wijken_df["pct_hoog_advies"] = wijken_df[hoog_kolommen].sum(axis=1, min_count=1).round(1)
    wijken_df["pct_laag_advies"] = wijken_df[laag_kolommen].sum(axis=1, min_count=1).round(1)

    bronnen = {
        "CBS Kerncijfers Wijken en Buurten 2024": cbs_bron,
        "DUO Schooladviezen per school": duo_bron,
        "Amsterdam schoolgebouwen": amsterdam_bron,
    }

    return wijken_df, duo_df, bronnen
