"""
calibracao.py
=============
Condições iniciais do simulador a partir de dados observados.

1. Composição da dívida bruta por indexador (Selic, prefixado, índice de preços, câmbio):
   - DPF em mercado por título (Tesouro, estoque mensal);
   - o restante da DBGG (sobretudo operações compromissadas do BCB) é tratado como pós-fixado à Selic.
2. Fração do estoque que vence em 12 meses, por indexador, usada como velocidade de repactuação.
3. Taxa implícita no estoque: o Tesouro registra o estoque pela taxa de emissão (valor apropriado),
   então o PU de cada título revela a taxa a que ele foi emitido. Para prefixados (LTN, NTN-F) a taxa
   é nominal; para NTN-B, real, usando o VNA calculado pelo IPCA desde 15/07/2000.
4. Ativos da dívida líquida: diferença DBGG − DLSP, separada em reservas internacionais (em reais) e
   demais créditos líquidos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CUPOM_NTNB = (1.06) ** 0.5 - 1     # 2,9563% ao semestre
CUPOM_NTNF = (1.10) ** 0.5 - 1     # 4,8809% ao semestre


def indexador(tit: str, tipo: str) -> str:
    t = tit.upper()
    if "EXTERNA" in tipo.upper() or "DXTERNA" in tipo.upper():
        return "pre" if "BRL" in t else "cambio"
    if t.startswith("LFT"):
        return "selic"
    if t.startswith(("LTN", "NTN-F")):
        return "pre"
    if t.startswith(("NTN-B", "NTN-C")):
        return "ipca"            # NTN-C (IGP-M) agregada a índice de preços
    return "outros"


def preparar_estoque(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d.columns = ["tit", "venc", "valor", "qtd", "mes", "classe", "tipo"]
    d["data"] = pd.to_datetime("01/" + d.mes, dayfirst=True) + pd.offsets.MonthEnd(0)
    d["venc"] = pd.to_datetime(d.venc, dayfirst=True, errors="coerce")
    d["idx"] = [indexador(a, b) for a, b in zip(d.tit, d.tipo)]
    return d


def vna_ntnb(ipca_m: pd.Series, data: pd.Timestamp) -> float:
    """VNA da NTN-B: R$ 1.000 em 15/07/2000 corrigido pelo IPCA (aproximação mensal)."""
    s = ipca_m[(ipca_m.index >= "2000-07-01") & (ipca_m.index <= data)]
    return 1000 * float(np.prod(1 + s / 100))


def _taxa(preco: float, fluxo, lo=-0.05, hi=0.6) -> float:
    for _ in range(80):
        m = (lo + hi) / 2
        if fluxo(m) > preco:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def taxa_titulo(tit: str, pu: float, anos: float, vna: float) -> float | None:
    if anos <= 0.05 or pu <= 0:
        return None
    t = tit.upper()
    n_sem = max(1, int(np.ceil(anos * 2 - 1e-9)))
    tempos = [anos - 0.5 * k for k in range(n_sem)][::-1]
    if t.startswith("LTN"):
        return (1000 / pu) ** (1 / anos) - 1
    if t.startswith("NTN-F"):
        f = lambda y: sum(1000 * CUPOM_NTNF / (1 + y) ** tt for tt in tempos) + 1000 / (1 + y) ** anos
        return _taxa(pu, f)
    if t.startswith("NTN-B PRINCIPAL"):
        return (vna / pu) ** (1 / anos) - 1
    if t.startswith("NTN-B 1") or t == "NTN-B" or (t.startswith("NTN-B ") and t[6:7].isdigit()):
        f = lambda y: sum(vna * CUPOM_NTNB / (1 + y) ** tt for tt in tempos) + vna / (1 + y) ** anos
        return _taxa(pu, f)
    return None


def condicoes_iniciais(est: pd.DataFrame, data: pd.Timestamp, dbgg_pct: float, dlsp_pct: float,
                       pib_12m: float, ipca_m: pd.Series, reservas_usd: float, cambio: float) -> dict:
    """Tudo em % do PIB ou % a.a. `pib_12m` e `reservas_usd` em milhões."""
    x = est[(est.data == data) & (est.classe == "Mercado")].copy()
    if x.empty:
        raise ValueError(f"sem estoque da DPF em {data:%m/%Y}")
    dpf = x.valor.sum() / 1e6                      # R$ milhões
    dbgg = dbgg_pct / 100 * pib_12m
    resto = max(dbgg - dpf, 0.0)                   # compromissadas e demais, pós-fixados
    por_idx = x.groupby("idx").valor.sum() / 1e6
    total = {k: float(por_idx.get(k, 0.0)) for k in ("selic", "pre", "ipca", "cambio", "outros")}
    total["selic"] += resto + total.pop("outros")
    comp = {k: v / dbgg * 100 for k, v in total.items()}

    x["anos"] = (x.venc - data).dt.days / 365.25
    vence12 = {}
    for k in ("pre", "ipca", "cambio"):
        y = x[x.idx == k]
        vence12[k] = float(y.loc[y.anos <= 1, "valor"].sum() / y.valor.sum() * 100) if len(y) else 0.0

    vna = vna_ntnb(ipca_m, data)
    x["pu"] = x.valor / x.qtd
    x["taxa"] = [taxa_titulo(t, p, a, vna) for t, p, a in zip(x.tit, x.pu, x.anos)]
    taxas = {}
    for k, pref in (("pre", ("LTN", "NTN-F")), ("ipca", ("NTN-B",))):
        y = x[x.tit.str.upper().str.startswith(pref) & x.taxa.notna() & x.taxa.between(-0.02, 0.4)]
        taxas[k] = float(np.average(y.taxa, weights=y.valor) * 100)

    reservas_pct = reservas_usd * cambio / pib_12m * 100
    ativos = dbgg_pct - dlsp_pct
    return {
        "data": data.strftime("%Y-%m"), "dbgg": dbgg_pct, "dlsp": dlsp_pct,
        "composicao": comp, "vence_12m": vence12, "taxa_estoque": taxas,
        "reservas": reservas_pct, "outros_ativos": ativos - reservas_pct,
        "dpf_mercado_pct": dpf / pib_12m * 100, "resto_selic_pct": resto / pib_12m * 100,
        "vna_ntnb": vna,
    }
