import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLORS = {
    "primary": "#2563eb",
    "positive": "#0f9d76",
    "warning": "#f59e0b",
    "danger": "#dc2626",
    "muted": "#64748b",
}

TIER_COLORS = {
    "kerentanan_tinggi": "#dc2626",
    "kerentanan_menengah": "#f59e0b",
    "kerentanan_rendah": "#0f9d76",
}

ACTION_COLORS = {
    "prioritas_segera": "#b91c1c",
    "intervensi_intensif": "#ea580c",
    "peringatan_dini": "#f59e0b",
    "pemantauan": "#3b82f6",
    "pantau": "#60a5fa",
    "rutin": "#16a34a",
}

METRIC_LABELS = {
    "garis_kemiskinan": "Garis Kemiskinan",
    "persentase_penduduk_miskin": "Penduduk Miskin (%)",
    "indeks_keparahan_kemiskinan": "Indeks Keparahan Kemiskinan",
    "indeks_pembangunan_manusia": "Indeks Pembangunan Manusia",
    "tingkat_pengangguran_terbuka": "Pengangguran Terbuka (%)",
    "skor_kerentanan_sosial": "Skor Kerentanan Sosial",
}


def polish(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=55, b=20),
        legend_title_text="",
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e2e8f0")
    return fig


def province_trend(frame: pd.DataFrame, metric: str) -> go.Figure:
    label = METRIC_LABELS[metric]
    fig = px.line(
        frame,
        x="tahun",
        y=metric,
        markers=True,
        title=f"Tren Rata-rata {label}",
        labels={"tahun": "Tahun", metric: label},
        color_discrete_sequence=[COLORS["primary"]],
    )
    return polish(fig)


def regional_trend(frame: pd.DataFrame, metric: str) -> go.Figure:
    label = METRIC_LABELS[metric]
    fig = px.line(
        frame,
        x="tahun",
        y=metric,
        color="nama_kabupaten_kota",
        markers=True,
        title=f"Tren {label} per Wilayah",
        labels={
            "tahun": "Tahun",
            metric: label,
            "nama_kabupaten_kota": "Wilayah",
        },
    )
    return polish(fig, 480)


def change_ranking(frame: pd.DataFrame, limit: int = 10) -> go.Figure:
    selected = pd.concat([frame.head(limit // 2), frame.tail(limit // 2)]).sort_values(
        "perubahan_poin"
    )
    selected = selected.assign(
        arah=selected["perubahan_poin"].apply(
            lambda value: "Kemiskinan meningkat" if value > 0 else "Kemiskinan menurun"
        )
    )
    fig = px.bar(
        selected,
        x="perubahan_poin",
        y="nama_kabupaten_kota",
        orientation="h",
        color="arah",
        color_discrete_map={
            "Kemiskinan meningkat": COLORS["danger"],
            "Kemiskinan menurun": COLORS["positive"],
        },
        title="Perubahan Persentase Penduduk Miskin",
        labels={
            "perubahan_poin": "Perubahan 2010-2024 (poin persentase)",
            "nama_kabupaten_kota": "",
        },
    )
    return polish(fig, 470)


def vulnerability_ranking(frame: pd.DataFrame) -> go.Figure:
    ordered = frame.sort_values("skor_kerentanan_sosial")
    fig = px.bar(
        ordered,
        x="skor_kerentanan_sosial",
        y="nama_kabupaten_kota",
        orientation="h",
        color="kelompok",
        color_discrete_map={
            "paling_rentan": COLORS["danger"],
            "paling_tidak_rentan": COLORS["positive"],
        },
        title="Wilayah Paling dan Paling Tidak Rentan",
        labels={"skor_kerentanan_sosial": "Skor kerentanan sosial", "nama_kabupaten_kota": ""},
    )
    return polish(fig, 560)


def correlation_heatmap(frame: pd.DataFrame) -> go.Figure:
    labels = {
        "garis_kemiskinan": "Garis Kemiskinan",
        "persentase_penduduk_miskin": "Penduduk Miskin",
        "indeks_keparahan_kemiskinan": "Keparahan Kemiskinan",
        "indeks_pembangunan_manusia": "IPM",
        "tingkat_pengangguran_terbuka": "Pengangguran Terbuka",
    }
    matrix = frame.set_index("indicator")
    matrix = matrix.rename(index=labels, columns=labels)
    fig = px.imshow(
        matrix,
        text_auto=".2f",
        zmin=-1,
        zmax=1,
        color_continuous_midpoint=0,
        color_continuous_scale=["#dc2626", "#f8fafc", "#2563eb"],
        title="Korelasi Antar-Indikator",
        labels={"x": "", "y": "", "color": "Korelasi"},
        aspect="auto",
    )
    fig.update_xaxes(side="top", tickangle=0)
    fig.update_traces(
        hovertemplate="<b>%{y}</b> dan <b>%{x}</b><br>Korelasi: %{z:.2f}<extra></extra>"
    )
    return polish(fig, 590)


def poverty_ipm_scatter(frame: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        frame,
        x="indeks_pembangunan_manusia",
        y="persentase_penduduk_miskin",
        size="indeks_keparahan_kemiskinan",
        color="cluster_vulnerability_tier",
        hover_name="nama_kabupaten_kota",
        color_discrete_map=TIER_COLORS,
        title="Kemiskinan dan Pembangunan Manusia",
        labels={
            "indeks_pembangunan_manusia": "Indeks Pembangunan Manusia",
            "persentase_penduduk_miskin": "Penduduk Miskin (%)",
            "cluster_vulnerability_tier": "Cluster",
            "indeks_keparahan_kemiskinan": "Indeks keparahan",
        },
    )
    return polish(fig, 500)


def cluster_scatter(frame: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        frame,
        x="pc1",
        y="pc2",
        color="cluster_vulnerability_tier",
        symbol="tipe_administratif",
        hover_name="nama_kabupaten_kota",
        color_discrete_map=TIER_COLORS,
        title="Segmentasi Wilayah pada Ruang PCA",
        labels={"pc1": "Komponen Utama 1", "pc2": "Komponen Utama 2"},
    )
    fig.update_traces(marker=dict(size=11, line=dict(width=1, color="white")))
    return polish(fig, 500)


def priority_heatmap(frame: pd.DataFrame) -> go.Figure:
    pivot = frame.pivot(
        index="level_kerentanan", columns="tren_kemiskinan", values="jumlah_wilayah"
    ).fillna(0)
    row_order = [value for value in ["tinggi", "sedang", "rendah"] if value in pivot.index]
    col_order = [value for value in ["membaik", "stabil", "memburuk"] if value in pivot.columns]
    pivot = pivot.reindex(index=row_order, columns=col_order, fill_value=0)
    fig = px.imshow(
        pivot,
        text_auto=True,
        color_continuous_scale=["#ecfdf5", "#fef3c7", "#fee2e2", "#b91c1c"],
        title="Matriks Prioritas Intervensi",
        labels={"x": "Tren kemiskinan", "y": "Level kerentanan", "color": "Jumlah wilayah"},
        aspect="auto",
    )
    fig.update_traces(
        textfont=dict(size=18),
        hovertemplate="Kerentanan: <b>%{y}</b><br>Tren: <b>%{x}</b><br>"
        "Jumlah wilayah: <b>%{z}</b><extra></extra>",
    )
    return polish(fig, 500)


def cluster_profile_bars(frame: pd.DataFrame) -> go.Figure:
    metrics = [
        "mean_persentase_penduduk_miskin",
        "mean_indeks_keparahan_kemiskinan",
        "mean_indeks_pembangunan_manusia",
        "mean_tingkat_pengangguran_terbuka",
    ]
    normalized = frame.copy()
    for metric in metrics:
        minimum, maximum = normalized[metric].min(), normalized[metric].max()
        normalized[metric] = (normalized[metric] - minimum) / (maximum - minimum)
    long = normalized.melt(
        id_vars=["cluster_vulnerability_tier"],
        value_vars=metrics,
        var_name="indikator",
        value_name="nilai_relatif",
    )
    labels = {
        "mean_persentase_penduduk_miskin": "Kemiskinan",
        "mean_indeks_keparahan_kemiskinan": "Keparahan",
        "mean_indeks_pembangunan_manusia": "IPM",
        "mean_tingkat_pengangguran_terbuka": "Pengangguran",
    }
    long["indikator"] = long["indikator"].map(labels)
    fig = px.bar(
        long,
        x="indikator",
        y="nilai_relatif",
        color="cluster_vulnerability_tier",
        barmode="group",
        color_discrete_map=TIER_COLORS,
        title="Profil Relatif Antar-Cluster",
        labels={"indikator": "", "nilai_relatif": "Nilai relatif (0-1)"},
    )
    return polish(fig, 450)


def cluster_composition(frame: pd.DataFrame) -> go.Figure:
    composition = (
        frame.groupby(["cluster_vulnerability_tier", "tipe_administratif"])
        .size()
        .reset_index(name="jumlah_wilayah")
    )
    fig = px.bar(
        composition,
        x="cluster_vulnerability_tier",
        y="jumlah_wilayah",
        color="tipe_administratif",
        barmode="stack",
        title="Komposisi Kabupaten dan Kota per Cluster",
        labels={
            "cluster_vulnerability_tier": "Cluster kerentanan",
            "jumlah_wilayah": "Jumlah wilayah",
            "tipe_administratif": "Tipe administratif",
        },
        color_discrete_map={"kabupaten": "#2563eb", "kota": "#8b5cf6"},
    )
    return polish(fig, 420)


def urban_rural_effect_sizes(frame: pd.DataFrame) -> go.Figure:
    labels = {
        "Poverty severity index": "Indeks keparahan kemiskinan",
        "Poverty rate": "Persentase penduduk miskin",
        "Human development index": "Indeks pembangunan manusia",
        "Poverty line": "Garis kemiskinan",
        "Open unemployment rate": "Pengangguran terbuka",
    }
    ordered = frame.assign(
        indikator=frame["label"].map(labels),
        kekuatan=frame["cohens_d"].abs(),
        arah=frame["cohens_d"].apply(
            lambda value: "Lebih tinggi di urban-industri"
            if value > 0
            else "Lebih tinggi di rural-agraris"
        ),
    ).sort_values("kekuatan")
    fig = px.bar(
        ordered,
        x="kekuatan",
        y="indikator",
        orientation="h",
        color="arah",
        color_discrete_map={
            "Lebih tinggi di urban-industri": "#2563eb",
            "Lebih tinggi di rural-agraris": "#dc2626",
        },
        title="Kekuatan Pembeda Urban-Industri dan Rural-Agraris",
        labels={"kekuatan": "Kekuatan perbedaan (|Cohen's d|)", "indikator": ""},
        hover_data={"welch_p": ":.6f", "cohens_d": ":.3f"},
    )
    return polish(fig, 440)


def coverage_heatmap(frame: pd.DataFrame) -> go.Figure:
    long = frame.melt(id_vars="tahun", var_name="indikator", value_name="jumlah_wilayah")
    long["indikator"] = long["indikator"].map(METRIC_LABELS)
    pivot = long.pivot(index="indikator", columns="tahun", values="jumlah_wilayah")
    fig = px.imshow(
        pivot,
        text_auto=True,
        color_continuous_scale="Blues",
        aspect="auto",
        title="Cakupan Indikator per Tahun",
        labels={"x": "Tahun", "y": "", "color": "Jumlah wilayah"},
    )
    return polish(fig, 430)
