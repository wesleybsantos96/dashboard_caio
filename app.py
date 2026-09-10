#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
painel_caio.py — Painel Streamlit de posições abertas do Caio.
Exibe ações e opções com cotação ao vivo via OPLAB.
Uso: streamlit run painel_caio.py
"""
import json
import os
import sqlite3
from datetime import datetime, date

import pandas as pd
import requests
import streamlit as st

# ── Configuração ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(BASE_DIR, "screener_history.db")
ACOES_PATH = os.path.join(BASE_DIR, "acoes.json")
CAIXA_PATH = os.path.join(BASE_DIR, "caixa.json")
TOKEN_PATH = os.path.join(BASE_DIR, "oplab_token.txt")

OPLAB_BASE = "https://api.oplab.com.br/v3"

st.set_page_config(
    page_title="Posições Abertas — Caio",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ── Funções auxiliares ────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_token():
    with open(TOKEN_PATH, encoding="utf-8") as f:
        return f.read().strip()


def oplab_headers():
    return {"Access-Token": load_token()}


@st.cache_data(ttl=60)
def fetch_quotes(tickers: tuple) -> dict:
    """Busca cotações em lote pela OPLAB. Retorna {ticker: preço}."""
    if not tickers:
        return {}
    url = f"{OPLAB_BASE}/market/quote?tickers={','.join(tickers)}"
    try:
        r = requests.get(url, headers=oplab_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        st.warning(f"Erro ao buscar cotações: {e}")
        return {}
    out = {}
    if isinstance(data, list):
        for item in data:
            sym = item.get("symbol")
            close = item.get("close")
            if sym and close:
                try:
                    out[sym] = float(close)
                except (TypeError, ValueError):
                    pass
    return out


def load_positions():
    """Carrega posições de opções do banco de dados."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM posicoes").fetchall()
    conn.close()
    positions = []
    for r in rows:
        snap = {}
        try:
            snap = json.loads(r["snap_json"]) if r["snap_json"] else {}
        except Exception:
            pass
        positions.append({
            "id": r["id"],
            "sym": r["sym"],
            "qty": r["qty"],
            "entry": r["entry"],
            "opened": r["opened"],
            "cat": snap.get("cat", "?"),
            "par": snap.get("par", ""),
            "K": snap.get("K"),
            "due": snap.get("due", ""),
            "cs": snap.get("cs", 100),
            "setor": snap.get("setor", ""),
            "status": snap.get("status", ""),
            "pex": snap.get("pex"),
        })
    return positions



def load_history():
    """Carrega histórico de posições fechadas."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM historico ORDER BY closed DESC").fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    history = []
    for r in rows:
        history.append({
            "closed": r["closed"],
            "opened": r["opened"],
            "sym": r["sym"],
            "cat": r["cat"],
            "qty": r["qty"],
            "cs": r["cs"],
            "entry": r["entry"],
            "exit": r["exit"],
            "pl": r["pl"],
            "pct": r["pct"]
        })
    return history

def load_stocks():
    """Carrega ações do acoes.json."""
    with open(ACOES_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_caixa():
    """Carrega posições de caixa."""
    if not os.path.exists(CAIXA_PATH):
        return []
    with open(CAIXA_PATH, encoding="utf-8") as f:
        return json.load(f)


def days_to_expiry(due_str):
    """Calcula DTE a partir de data de vencimento."""
    if not due_str:
        return None
    try:
        due = datetime.strptime(due_str, "%Y-%m-%d").date()
        return (due - date.today()).days
    except ValueError:
        return None


def fmt_brl(value):
    """Formata valor em BRL."""
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value):
    """Formata percentual."""
    if value is None:
        return "—"
    return f"{value:+.1f}%"


def color_pl(val):
    """CSS condicional para P&L."""
    if val > 0:
        return "color: #00c853; font-weight: 600"
    elif val < 0:
        return "color: #ff1744; font-weight: 600"
    return "color: #9e9e9e"


def color_dist_row(row):
    """CSS condicional para Dist. Strike dependendo se é CALL ou PUT."""
    c = [""] * len(row)
    if "Dist. Strike" not in row.index or "Tipo" not in row.index:
        return c
        
    val = row["Dist. Strike"]
    cat = row["Tipo"]
    idx = row.index.get_loc("Dist. Strike")
    
    if pd.notnull(val):
        if cat == "CALL":
            # Para CALL, distância positiva (precisa subir) é segura (verde)
            c[idx] = "color: #00c853; font-weight: 600" if val > 0 else "color: #ff1744; font-weight: 600"
        else:
            # Para PUT, distância negativa (precisa cair) é segura (verde)
            c[idx] = "color: #00c853; font-weight: 600" if val < 0 else "color: #ff1744; font-weight: 600"
    return c


# ── CSS Customizado ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
        max-width: 1400px;
    }

    /* Header */
    .header-container {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .header-title {
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-sub {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.6);
        margin-top: 4px;
    }

    /* Metric Cards */
    .metric-card {
        background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 14px;
        padding: 20px 24px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
    }
    .metric-label {
        font-size: 12px;
        font-weight: 500;
        color: rgba(255, 255, 255, 0.5);
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #ffffff;
    }
    .metric-value.positive { color: #00e676; }
    .metric-value.negative { color: #ff5252; }

    /* Section Headers */
    .section-header {
        font-size: 18px;
        font-weight: 600;
        color: #e0e0e0;
        margin: 28px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(255, 255, 255, 0.08);
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Badge */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .badge-call {
        background: rgba(0, 200, 83, 0.15);
        color: #69f0ae;
        border: 1px solid rgba(0, 200, 83, 0.25);
    }
    .badge-put {
        background: rgba(255, 23, 68, 0.15);
        color: #ff8a80;
        border: 1px solid rgba(255, 23, 68, 0.25);
    }

    /* DTE badge */
    .dte-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .dte-ok { background: rgba(0, 200, 83, 0.12); color: #69f0ae; }
    .dte-warn { background: rgba(255, 193, 7, 0.15); color: #ffd740; }
    .dte-danger { background: rgba(255, 23, 68, 0.15); color: #ff8a80; }

    /* Streamlit overrides */
    .stDataFrame { border-radius: 12px; overflow: hidden; }
    div[data-testid="stMetricValue"] { font-size: 22px; }

    /* Table styling */
    table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        border-radius: 12px;
        overflow: hidden;
        font-size: 13px;
    }
    th {
        background: rgba(255, 255, 255, 0.06) !important;
        color: rgba(255, 255, 255, 0.7) !important;
        font-weight: 600 !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        padding: 12px 14px !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    td {
        padding: 10px 14px !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04) !important;
        color: #e0e0e0 !important;
    }
    tr:hover td {
        background: rgba(255, 255, 255, 0.03) !important;
    }

    /* Footer */
    .footer-note {
        text-align: center;
        color: rgba(255, 255, 255, 0.3);
        font-size: 12px;
        margin-top: 32px;
        padding: 16px;
    }

    /* Mobile Responsiveness */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 1rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }
        .header-container {
            padding: 16px 20px;
            margin-bottom: 16px;
        }
        .header-title { font-size: 22px; }
        .header-sub { font-size: 12px; }
        .metric-card {
            padding: 14px 16px;
        }
        .metric-label { font-size: 11px; }
        .metric-value { font-size: 20px; }
        .section-header { font-size: 16px; margin: 20px 0 10px 0; }
        table { font-size: 11px; }
        th { font-size: 10px !important; padding: 10px 8px !important; }
        td { padding: 8px 8px !important; font-size: 11px !important; }
        div[data-testid="stDataFrame"] > div {
            border-radius: 8px;
        }
    }
</style>
""", unsafe_allow_html=True)


# ── Dados ─────────────────────────────────────────────────────────────────────
positions = load_positions()
history_data = load_history()
stocks = load_stocks()
caixa = load_caixa()

# Coletar todos os tickers para buscar cotações
all_tickers = set()
for p in positions:
    all_tickers.add(p["sym"])
    if p["par"]:
        all_tickers.add(p["par"])
for s in stocks:
    all_tickers.add(s["sym"])

# Botão de atualização no canto
col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 Atualizar Cotações", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

quotes = fetch_quotes(tuple(sorted(all_tickers)))

# ── Header ────────────────────────────────────────────────────────────────────
now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
st.markdown(f"""
<div class="header-container">
    <div class="header-title">📊 Posições Abertas — Caio</div>
    <div class="header-sub">Última atualização: {now_str} &nbsp;•&nbsp; Cotações ao vivo via OPLAB</div>
</div>
""", unsafe_allow_html=True)

tab_abertas, tab_fechadas = st.tabs(["📊 Posições Abertas", "📚 Histórico Fechado"])

with tab_abertas:



    # ── Cálculos ──────────────────────────────────────────────────────────────────
    # Ações
    stocks_data = []
    total_stocks_invested = 0
    total_stocks_current = 0
    for s in stocks:
        sym = s["sym"]
        qty = s["qty"]
        avg = s["avg"]
        price = quotes.get(sym, s.get("snap", {}).get("S"))
        invested = qty * avg
        current = qty * price if price else None
        pl = current - invested if current else None
        pl_pct = (pl / invested * 100) if (pl is not None and invested > 0) else None
        total_stocks_invested += invested
        if current:
            total_stocks_current += current
        stocks_data.append({
            "Ativo": sym,
            "PM": avg,
            "Spot": price,
            "Qtd": qty,
            "Investido": invested,
            "Valor Atual": current,
            "P&L (R$)": pl,
            "P&L (%)": pl_pct,
        })

    # Opções
    opts_data = []
    total_opts_premium = 0
    total_opts_current_value = 0
    for p in positions:
        sym = p["sym"]
        qty = p["qty"]
        entry = p["entry"]
        cat = p["cat"]
        par = p["par"]
        K = p["K"]
        due = p["due"]
        cs = p["cs"]
        dte = days_to_expiry(due)

        price_opt = quotes.get(sym)
        price_sub = quotes.get(par) if par else None

        # Prêmio recebido na venda (vendeu opção = recebeu prêmio)
        premium_received = qty * entry * (cs if cs != 1 else 1) / 100  # normalize, cs already in multiplier
        # Na verdade, o entry é o preço unitário por lote de cs.
        # qty = número de contratos (cada um de cs ações/unidades)
        # Financeiro de entrada = qty * entry (entry já é o preço total por contrato? Não...)
        # Olhando os dados: qty=1000, entry=0.15, cs=100
        # Isso significa 1000 opções vendidas a R$ 0.15 cada = R$ 150.00 recebidos
        premium_received = qty * entry

        if price_opt is not None:
            current_cost = qty * price_opt  # custo de recompra
            pl_opt = premium_received - current_cost  # Vendeu por X, recompra por Y -> lucro = X - Y
            pl_pct_opt = (pl_opt / premium_received * 100) if premium_received > 0 else None
        else:
            current_cost = None
            pl_opt = None
            pl_pct_opt = None

        total_opts_premium += premium_received
        if current_cost is not None:
            total_opts_current_value += current_cost

        # Moneyness (Distância para o Strike)
        if price_sub and K:
            moneyness = (K - price_sub) / price_sub * 100
        else:
            moneyness = None

        opts_data.append({
            "Opção": sym,
            "Tipo": cat,
            "Spot": price_sub,
            "Strike": K,
            "Dist. Strike": moneyness,
            "Prob. Exec.": p["pex"] * 100 if p["pex"] is not None else None,
            "Qtd": qty,
            "Prêmio Venda": entry,
            "Preço Atual": price_opt,
            "P&L (R$)": pl_opt,
            "P&L (%)": pl_pct_opt,
            # campos auxiliares
            "Subjacente": par,
            "Vencimento": due,
            "DTE": dte,
            "Prêmio Rec.": premium_received,
            "Custo Recompra": current_cost,
        })

    # Caixa
    total_caixa = sum(c.get("valor", 0) for c in caixa)

    # Totais
    total_pl_stocks = total_stocks_current - total_stocks_invested
    total_pl_opts = total_opts_premium - total_opts_current_value
    total_invested_all = total_stocks_invested
    total_portfolio = total_stocks_current + total_caixa
    total_pl_all = total_pl_stocks + total_pl_opts

    # ── Métricas Resumo ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)

    def metric_card(label, value, css_class=""):
        return f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value {css_class}">{value}</div>
        </div>
        """

    with c1:
        st.markdown(metric_card("Carteira Ações", fmt_brl(total_stocks_current)), unsafe_allow_html=True)
    with c2:
        cls = "positive" if total_pl_stocks >= 0 else "negative"
        st.markdown(metric_card("P&L Ações", fmt_brl(total_pl_stocks), cls), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Prêmios Recebidos", fmt_brl(total_opts_premium)), unsafe_allow_html=True)
    with c4:
        cls = "positive" if total_pl_opts >= 0 else "negative"
        st.markdown(metric_card("P&L Opções", fmt_brl(total_pl_opts), cls), unsafe_allow_html=True)
    with c5:
        st.markdown(metric_card("Caixa", fmt_brl(total_caixa)), unsafe_allow_html=True)

    st.markdown("")

    # Segunda faixa de métricas
    c6, c7, c8, c9, c10 = st.columns(5)
    with c6:
        st.markdown(metric_card("Investido (Ações)", fmt_brl(total_stocks_invested)), unsafe_allow_html=True)
    with c7:
        rent_pct = (total_pl_stocks / total_stocks_invested * 100) if total_stocks_invested > 0 else 0
        cls = "positive" if rent_pct >= 0 else "negative"
        st.markdown(metric_card("Rent. Ações", fmt_pct(rent_pct), cls), unsafe_allow_html=True)
    with c8:
        st.markdown(metric_card("Posições Opções", str(len(positions))), unsafe_allow_html=True)
    with c9:
        calls = sum(1 for p in opts_data if p["Tipo"] == "CALL")
        puts = sum(1 for p in opts_data if p["Tipo"] == "PUT")
        st.markdown(metric_card("CALL / PUT", f"{calls} / {puts}"), unsafe_allow_html=True)
    with c10:
        cls = "positive" if total_pl_all >= 0 else "negative"
        st.markdown(metric_card("P&L Total", fmt_brl(total_pl_all), cls), unsafe_allow_html=True)

    st.markdown("")

    # ── Tabela de Ações ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📈 Carteira de Ações</div>', unsafe_allow_html=True)

    df_stocks = pd.DataFrame(stocks_data)
    if not df_stocks.empty:
        df_stocks = df_stocks.sort_values("P&L (%)", ascending=False, na_position="last")
        stocks_display_cols = ["Ativo", "PM", "Spot", "Qtd", "Investido", "Valor Atual", "P&L (R$)", "P&L (%)"]
        df_stocks = df_stocks[stocks_display_cols]

        styled = df_stocks.style.format({
            "PM":          "R$ {:.2f}",
            "Spot":        lambda x: f"R$ {x:.2f}" if x else "—",
            "Qtd":         "{:,.0f}",
            "Investido":   lambda x: f"R$ {x:,.2f}",
            "Valor Atual": lambda x: f"R$ {x:,.2f}" if x else "—",
            "P&L (R$)":   lambda x: f"R$ {x:+,.2f}" if x is not None else "—",
            "P&L (%)":    lambda x: f"{x:+.1f}%" if x is not None else "—",
        }).map(lambda x: color_pl(x) if isinstance(x, (int, float)) else "",
               subset=["P&L (R$)", "P&L (%)"])

        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=min(len(df_stocks) * 38 + 40, 600),
        )
    else:
        st.info("Nenhuma ação na carteira.")

    st.markdown("")

    # ── Tabela de Opções ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🎯 Posições de Opções (Vendas)</div>', unsafe_allow_html=True)

    # Filtros
    fc1, fc2, fc3 = st.columns([1, 1, 2])
    with fc1:
        filter_type = st.selectbox("Tipo", ["Todos", "CALL", "PUT"], index=0)
    with fc2:
        vencimentos = sorted(set(p["Vencimento"] for p in opts_data if p["Vencimento"]))
        filter_due = st.selectbox("Vencimento", ["Todos"] + vencimentos, index=0)

    df_opts = pd.DataFrame(opts_data)
    if not df_opts.empty:
        if filter_type != "Todos":
            df_opts = df_opts[df_opts["Tipo"] == filter_type]
        if filter_due != "Todos":
            df_opts = df_opts[df_opts["Vencimento"] == filter_due]

        # Agrupamento por vencimento
        for due_date in sorted(df_opts["Vencimento"].unique()):
            group = df_opts[df_opts["Vencimento"] == due_date].copy()
            dte_val = group["DTE"].iloc[0] if not group.empty else None

            # DTE badge
            if dte_val is not None:
                if dte_val <= 5:
                    dte_class = "dte-danger"
                elif dte_val <= 15:
                    dte_class = "dte-warn"
                else:
                    dte_class = "dte-ok"
                dte_html = f'<span class="dte-badge {dte_class}">{dte_val}d</span>'
            else:
                dte_html = ""

            st.markdown(
                f'<div style="margin: 16px 0 6px 0; font-size: 14px; font-weight: 600; color: #b0bec5;">'
                f'📅 Vencimento: {due_date} &nbsp; {dte_html}</div>',
                unsafe_allow_html=True
            )

            # Preparar dados para exibição — colunas na ordem solicitada
            has_pex = group["Prob. Exec."].notna().any()
            display_cols = [
                "Opção", "Tipo", "Spot", "Strike", "Dist. Strike",
            ]
            if has_pex:
                display_cols.append("Prob. Exec.")
            display_cols += ["Qtd", "Prêmio Venda", "Preço Atual", "P&L (R$)", "P&L (%)"]

            display_df = group[display_cols].copy()
            display_df = display_df.sort_values("Opção")

            fmt_map = {
                "Spot":         lambda x: f"R$ {x:.2f}" if x is not None else "—",
                "Strike":       lambda x: f"R$ {x:.2f}" if x else "—",
                "Dist. Strike": lambda x: f"{x:+.1f}%" if x is not None else "—",
                "Qtd":          "{:,.0f}",
                "Prêmio Venda": "R$ {:.2f}",
                "Preço Atual":  lambda x: f"R$ {x:.2f}" if x is not None else "—",
                "P&L (R$)":    lambda x: f"R$ {x:+,.2f}" if x is not None else "—",
                "P&L (%)":     lambda x: f"{x:+.1f}%" if x is not None else "—",
            }
            if has_pex:
                fmt_map["Prob. Exec."] = lambda x: f"{x:.1f}%" if x is not None else "—"

            color_cols = [c for c in ["P&L (R$)", "P&L (%)"] if c in display_cols]
            styled_opts = display_df.style.format(fmt_map).map(
                lambda x: color_pl(x) if isinstance(x, (int, float)) else "",
                subset=color_cols
            )
            if "Dist. Strike" in display_cols:
                styled_opts = styled_opts.apply(color_dist_row, axis=1)

            st.dataframe(
                styled_opts,
                use_container_width=True,
                hide_index=True,
                height=min(len(display_df) * 38 + 40, 500),
            )

            # Subtotal do vencimento
            grp_premium = group["Prêmio Rec."].sum()
            grp_cost = group["Custo Recompra"].sum()
            grp_pl = group["P&L (R$)"].sum()
            cl = "positive" if grp_pl >= 0 else "negative"
            st.markdown(
                f'<div style="text-align:right; font-size:13px; color: rgba(255,255,255,0.5); margin-bottom: 8px;">'
                f'Subtotal: Prêmio {fmt_brl(grp_premium)} &nbsp;|&nbsp; '
                f'Recompra {fmt_brl(grp_cost)} &nbsp;|&nbsp; '
                f'<span class="metric-value {cl}" style="font-size:13px;">P&L {fmt_brl(grp_pl)}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    else:
        st.info("Nenhuma posição de opções aberta.")

    st.markdown("")

    # ── Caixa ────────────────────────────────────────────────────────────────────
    if caixa:
        st.markdown('<div class="section-header">💰 Caixa / Reservas</div>', unsafe_allow_html=True)
        df_caixa = pd.DataFrame(caixa)
        df_caixa.columns = ["Aplicação", "Valor", "Disponível"]
        df_caixa["Disponível"] = df_caixa["Disponível"].map({True: "✅ Sim", False: "❌ Não"})

        styled_caixa = df_caixa.style.format({
            "Valor": lambda x: fmt_brl(x) if isinstance(x, (int, float)) else x,
        })

        st.dataframe(styled_caixa, use_container_width=True, hide_index=True, height=120)

    # ── Exposição por Subjacente ─────────────────────────────────────────────────
    st.markdown('<div class="section-header">🔍 Exposição por Subjacente</div>', unsafe_allow_html=True)

    # Agrupar opções por subjacente
    if opts_data:
        exposure = {}
        for p in opts_data:
            par = p["Subjacente"] or "N/A"
            if par not in exposure:
                exposure[par] = {
                    "Subjacente": par,
                    "Preço Sub.": p["Spot"],
                    "Calls": 0,
                    "Puts": 0,
                    "Prêmio Total": 0,
                    "P&L Opções": 0,
                }
            if p["Tipo"] == "CALL":
                exposure[par]["Calls"] += p["Qtd"]
            else:
                exposure[par]["Puts"] += p["Qtd"]
            exposure[par]["Prêmio Total"] += p["Prêmio Rec."]
            if p["P&L (R$)"] is not None:
                exposure[par]["P&L Opções"] += p["P&L (R$)"]

        # Adicionar posição de ações
        for s in stocks_data:
            sym = s["Ativo"]
            if sym in exposure:
                exposure[sym]["Ações Qtd"] = s["Qtd"]
                exposure[sym]["Ações P&L"] = s["P&L (R$)"]
            else:
                exposure[sym] = {
                    "Subjacente": sym,
                    "Preço Sub.": s["Spot"],
                    "Calls": 0,
                    "Puts": 0,
                    "Prêmio Total": 0,
                    "P&L Opções": 0,
                    "Ações Qtd": s["Qtd"],
                    "Ações P&L": s["P&L (R$)"],
                }

        df_exposure = pd.DataFrame(exposure.values())
        if "Ações Qtd" not in df_exposure.columns:
            df_exposure["Ações Qtd"] = 0
        if "Ações P&L" not in df_exposure.columns:
            df_exposure["Ações P&L"] = 0
        df_exposure = df_exposure.fillna(0)
        df_exposure["P&L Combinado"] = df_exposure["P&L Opções"] + df_exposure["Ações P&L"]
        df_exposure = df_exposure.sort_values("Prêmio Total", ascending=False)

        styled_exp = df_exposure.style.format({
            "Preço Sub.": lambda x: f"R$ {x:.2f}" if x else "—",
            "Calls": "{:,.0f}",
            "Puts": "{:,.0f}",
            "Ações Qtd": "{:,.0f}",
            "Prêmio Total": lambda x: fmt_brl(x),
            "P&L Opções": lambda x: f"R$ {x:+,.2f}" if x else "—",
            "Ações P&L": lambda x: f"R$ {x:+,.2f}" if x else "—",
            "P&L Combinado": lambda x: f"R$ {x:+,.2f}" if x else "—",
        }).map(
            lambda x: color_pl(x) if isinstance(x, (int, float)) else "",
            subset=["P&L Opções", "Ações P&L", "P&L Combinado"]
        )

        st.dataframe(styled_exp, use_container_width=True, hide_index=True,
                     height=min(len(df_exposure) * 38 + 40, 600))


with tab_fechadas:

    # ── Aba 2: Histórico ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📚 Histórico de Operações Encerradas</div>', unsafe_allow_html=True)
    
    if not history_data:
        st.info("Nenhuma posição fechada encontrada no histórico.")
    else:
        df_hist = pd.DataFrame(history_data)
        
        # Filtros do Histórico
        hf1, hf2 = st.columns([1, 1])
        with hf1:
            meses = sorted(list(set(x[:7] for x in df_hist["closed"] if x)), reverse=True)
            filtro_mes = st.selectbox("Mês de Encerramento", ["Todos"] + meses)
        with hf2:
            filtro_tipo_hist = st.selectbox("Tipo de Ativo", ["Todos (Opções + Ações)", "Apenas Opções", "Apenas Ações", "CALL", "PUT"])
            
        if filtro_mes != "Todos":
            df_hist = df_hist[df_hist["closed"].str.startswith(filtro_mes, na=False)]
            
        if filtro_tipo_hist == "Apenas Opções":
            df_hist = df_hist[df_hist["cat"].isin(["CALL", "PUT"])]
        elif filtro_tipo_hist == "Apenas Ações":
            df_hist = df_hist[df_hist["cat"] == "ACAO"]
        elif filtro_tipo_hist in ["CALL", "PUT"]:
            df_hist = df_hist[df_hist["cat"] == filtro_tipo_hist]
            
        if df_hist.empty:
            st.warning("Nenhuma operação encontrada para os filtros selecionados.")
        else:
            # Métricas do período
            total_pl_hist = df_hist["pl"].sum()
            win_rate = (df_hist["pl"] > 0).mean() * 100
            melhor_trade = df_hist["pl"].max()
            pior_trade = df_hist["pl"].min()
            
            hc1, hc2, hc3, hc4 = st.columns(4)
            with hc1:
                cls = "positive" if total_pl_hist >= 0 else "negative"
                st.markdown(metric_card("P&L do Período", fmt_brl(total_pl_hist), cls), unsafe_allow_html=True)
            with hc2:
                st.markdown(metric_card("Taxa de Acerto (Win Rate)", f"{win_rate:.1f}%"), unsafe_allow_html=True)
            with hc3:
                st.markdown(metric_card("Melhor Trade", fmt_brl(melhor_trade), "positive"), unsafe_allow_html=True)
            with hc4:
                st.markdown(metric_card("Pior Trade", fmt_brl(pior_trade), "negative"), unsafe_allow_html=True)
                
            st.markdown("")
            
            # Formatar Tabela
            df_hist_disp = df_hist[["closed", "opened", "sym", "cat", "qty", "entry", "exit", "pl", "pct"]].copy()
            df_hist_disp.columns = ["Data Fech.", "Data Abert.", "Opção", "Tipo", "Qtd", "Entrada", "Saída", "P&L (R$)", "P&L (%)"]
            
            styled_hist = df_hist_disp.style.format({
                "Qtd": "{:,.0f}",
                "Entrada": "R$ {:.2f}",
                "Saída": lambda x: f"R$ {x:.2f}" if pd.notnull(x) else "—",
                "P&L (R$)": lambda x: f"R$ {x:+,.2f}" if pd.notnull(x) else "—",
                "P&L (%)": lambda x: f"{x:+.1f}%" if pd.notnull(x) else "—",
            }).map(lambda x: color_pl(x) if isinstance(x, (int, float)) else "",
                   subset=["P&L (R$)", "P&L (%)"])
                   
            st.dataframe(styled_hist, use_container_width=True, hide_index=True, height=min(len(df_hist_disp) * 38 + 40, 600))


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="footer-note">Dados de posições carregados de {BASE_DIR} &nbsp;•&nbsp; '
    f'Cotações via OPLAB API &nbsp;•&nbsp; Gerado em {now_str}</div>',
    unsafe_allow_html=True
)
