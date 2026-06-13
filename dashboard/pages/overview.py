import streamlit as st

from dashboard.charts import (
    METRIC_LABELS,
    cluster_composition,
    cluster_scatter,
    priority_heatmap,
    province_trend,
    urban_rural_effect_sizes,
)
from dashboard.data_loader import load_many


INDICATOR_EXPLANATIONS = {
    "garis_kemiskinan": {
        "definition": (
            "Batas minimum pengeluaran per kapita per bulan untuk memenuhi kebutuhan dasar "
            "makanan dan nonmakanan. Penduduk dengan pengeluaran di bawah batas ini dikategorikan miskin."
        ),
        "reading": (
            "Nilai lebih tinggi berarti biaya minimum kebutuhan dasar meningkat, bukan otomatis "
            "menunjukkan wilayah tersebut lebih miskin."
        ),
        "format": "Rp{:,.0f}/kapita/bulan",
        "delta_format": "Rp{:,.0f}",
    },
    "persentase_penduduk_miskin": {
        "definition": (
            "Persentase penduduk yang pengeluaran per kapitanya berada di bawah garis kemiskinan."
        ),
        "reading": "Semakin rendah nilainya, semakin kecil proporsi penduduk yang hidup di bawah garis kemiskinan.",
        "format": "{:.2f}%",
        "delta_format": "{:+.2f} poin",
    },
    "indeks_keparahan_kemiskinan": {
        "definition": (
            "Indeks yang menggambarkan ketimpangan pengeluaran di antara penduduk miskin "
            "dan seberapa jauh kondisi mereka dari garis kemiskinan."
        ),
        "reading": "Semakin tinggi nilainya, semakin parah dan semakin tidak merata kondisi kemiskinan.",
        "format": "{:.3f}",
        "delta_format": "{:+.3f}",
    },
    "indeks_pembangunan_manusia": {
        "definition": (
            "Indeks gabungan yang mencerminkan capaian kesehatan, pendidikan, dan standar hidup layak."
        ),
        "reading": "Semakin tinggi nilainya, semakin baik kualitas pembangunan manusia wilayah tersebut.",
        "format": "{:.2f}",
        "delta_format": "{:+.2f} poin",
    },
    "tingkat_pengangguran_terbuka": {
        "definition": (
            "Persentase angkatan kerja yang tidak bekerja dan sedang mencari pekerjaan "
            "atau mempersiapkan usaha."
        ),
        "reading": (
            "Semakin tinggi nilainya, semakin besar bagian angkatan kerja yang belum terserap. "
            "Data kabupaten/kota tahun 2016 tidak tersedia pada sumber."
        ),
        "format": "{:.2f}%",
        "delta_format": "{:+.2f} poin",
    },
}


def _delta(frame, metric: str) -> float:
    return float(frame.iloc[-1][metric] - frame.iloc[-2][metric])


def _indicator_card(trend, metric: str) -> None:
    explanation = INDICATOR_EXPLANATIONS[metric]
    latest = trend.iloc[-1]
    latest_value = explanation["format"].format(latest[metric])
    delta_value = explanation["delta_format"].format(_delta(trend, metric))
    st.markdown(
        f"""
        <div class="indicator-card">
            <h3>{METRIC_LABELS[metric]}</h3>
            <p>{explanation["definition"]}</p>
            <p><strong>Cara membaca:</strong> {explanation["reading"]}</p>
            <p class="reading">Rata-rata {int(latest["tahun"])}: {latest_value}
            &nbsp; | &nbsp; Perubahan tahunan: {delta_value}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Ringkasan Kemiskinan Jawa Barat</h1>
            <p>Temuan utama, pola kerentanan, dan prioritas intervensi kabupaten/kota tahun 2024.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    data = load_many("trend", "clusters", "priority_matrix", "urban_rural")
    trend = data["trend"].sort_values("tahun")
    clusters = data["clusters"]
    latest = trend.iloc[-1]
    year = int(latest["tahun"])

    immediate = int((clusters["prioritas_aksi"] == "prioritas_segera").sum())
    columns = st.columns(5)
    cards = [
        ("Penduduk miskin", latest["persentase_penduduk_miskin"], _delta(trend, "persentase_penduduk_miskin"), "{:.2f}%"),
        ("Indeks keparahan", latest["indeks_keparahan_kemiskinan"], _delta(trend, "indeks_keparahan_kemiskinan"), "{:.3f}"),
        ("IPM", latest["indeks_pembangunan_manusia"], _delta(trend, "indeks_pembangunan_manusia"), "{:.2f}"),
        ("Pengangguran terbuka", latest["tingkat_pengangguran_terbuka"], _delta(trend, "tingkat_pengangguran_terbuka"), "{:.2f}%"),
    ]
    for index, (column, (label, value, delta, pattern)) in enumerate(zip(columns[:4], cards)):
        column.metric(
            label,
            pattern.format(value),
            pattern.format(delta),
            delta_color="normal" if index == 2 else "inverse",
        )
    columns[4].metric("Prioritas segera", f"{immediate} wilayah")

    st.caption(
        f"Snapshot {year}, mencakup {len(clusters)} kabupaten/kota. "
        "Delta membandingkan rata-rata dengan tahun sebelumnya."
    )

    st.divider()
    st.header("Rumusan Masalah")

    with st.container(border=True):
        st.subheader("1. Bagaimana pola klasterisasi wilayah?")
        st.markdown(
            "Kabupaten/kota membentuk **tiga pola kerentanan**: "
            "**7 wilayah tinggi** yang seluruhnya kabupaten rural-agraris, "
            "**12 wilayah menengah** dengan karakter campuran, dan "
            "**8 wilayah rendah** yang didominasi kota urban-industri."
        )
        left, right = st.columns([1.1, 1])
        with left:
            st.plotly_chart(cluster_composition(clusters), width="stretch")
        with right:
            st.plotly_chart(cluster_scatter(clusters), width="stretch")
        st.warning(
            "Bagian **desa belum dapat dijawab** karena sumber data hanya tersedia pada "
            "tingkat kabupaten/kota. Label rural-agraris dan urban-industri merupakan "
            "profil hasil model, bukan klasifikasi resmi desa/kota."
        )

    with st.container(border=True):
        st.subheader("2. Variabel apa yang paling membedakan karakter wilayah?")
        st.markdown(
            "Pembeda terkuat adalah **indeks keparahan kemiskinan**, diikuti "
            "**persentase penduduk miskin** dan **IPM**. Rural-agraris memiliki "
            "kemiskinan dan keparahan lebih tinggi; urban-industri memiliki IPM, "
            "garis kemiskinan, dan pengangguran terbuka lebih tinggi."
        )
        st.plotly_chart(urban_rural_effect_sizes(data["urban_rural"]), width="stretch")
        st.warning(
            "Bagian **variabel demografis belum dapat dijawab** karena dataset tidak memuat "
            "umur, jenis kelamin, kepadatan penduduk, atau struktur rumah tangga."
        )

    with st.container(border=True):
        st.subheader("3. Wilayah mana yang membutuhkan intervensi paling cepat?")
        urgent = clusters.loc[
            clusters["prioritas_aksi"] == "prioritas_segera",
            [
                "nama_kabupaten_kota",
                "skor_kerentanan_sosial",
                "persentase_penduduk_miskin",
                "tren_kemiskinan",
                "prioritas_aksi",
            ],
        ].sort_values("skor_kerentanan_sosial", ascending=False)
        top_priority = urgent.iloc[0]["nama_kabupaten_kota"].title()
        st.markdown(
            f"Terdapat **{len(urgent)} wilayah prioritas segera** karena kerentanannya "
            f"tinggi dan tren kemiskinannya memburuk. Berdasarkan skor kerentanan, "
            f"wilayah pertama yang perlu ditangani adalah **{top_priority}**."
        )
        st.plotly_chart(priority_heatmap(data["priority_matrix"]), width="stretch")

        st.subheader("Urutan Wilayah Prioritas Segera")
        priority_display = urgent.rename(
            columns={
                "nama_kabupaten_kota": "Wilayah",
                "skor_kerentanan_sosial": "Skor",
                "persentase_penduduk_miskin": "Kemiskinan (%)",
                "tren_kemiskinan": "Tren",
                "prioritas_aksi": "Prioritas",
            }
        )
        priority_display["Wilayah"] = priority_display["Wilayah"].str.title()
        priority_display["Prioritas"] = priority_display["Prioritas"].str.replace("_", " ").str.title()
        priority_display.insert(0, "Urutan", range(1, len(priority_display) + 1))
        st.dataframe(
            priority_display,
            hide_index=True,
            width="stretch",
            height=38 * (len(priority_display) + 1),
            column_config={
                "Urutan": st.column_config.NumberColumn("Urutan", width="small"),
                "Wilayah": st.column_config.TextColumn("Wilayah", width="large"),
                "Skor": st.column_config.NumberColumn("Skor Kerentanan", format="%.4f"),
                "Kemiskinan (%)": st.column_config.NumberColumn("Kemiskinan (%)", format="%.2f"),
                "Tren": st.column_config.TextColumn("Tren", width="medium"),
                "Prioritas": st.column_config.TextColumn("Prioritas", width="medium"),
            },
        )

    st.divider()
    st.header("Konteks Tren Provinsi")
    metric = st.selectbox(
        "Pilih indikator",
        list(METRIC_LABELS)[:5],
        format_func=METRIC_LABELS.get,
        key="overview_metric",
    )
    st.plotly_chart(province_trend(trend, metric), width="stretch")
    _indicator_card(trend, metric)
