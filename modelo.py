"""
modelo.py
=========
Dinâmica anual da dívida pública em % do PIB. A mesma conta é reproduzida em JavaScript no
dashboard (template/page.html); `testes` garantem que as duas versões dão o mesmo resultado.

Dívida bruta (DBGG):
    b_t = b_{t-1} (1 + i_t) / (1 + γ_t) − s_t

    i_t   custo nominal médio da dívida no ano, ponderado pela composição por indexador
    γ_t   crescimento do PIB nominal: (1 + g_t)(1 + π_t) − 1
    s_t   resultado primário do setor público consolidado (% PIB, superávit positivo)

Custo por indexador:
    Selic     i_S = Selic média do ano
    Prefixado p_t = (1 − λ_p) p_{t−1} + λ_p y^pre_t          (y^pre: taxa de emissão)
    Índice    c_t = (1 − λ_i) c_{t−1} + λ_i y^real_t;  custo = (1 + c_t)(1 + π_t) − 1
    Câmbio    (1 + f)(1 + e_t) − 1                         (f: juro externo; e: depreciação)

λ é a fração do estoque de cada indexador que vence em 12 meses: a parte que é refinanciada à
taxa nova no ano. A composição é mantida constante (o refinanciamento preserva os pesos).

Dívida líquida (DLSP):
    n_t = b_t − a_t,   a_t = R_t + O_t
    R_t = R_{t−1} (1 + f_R)(1 + e_t) / (1 + γ_t)            reservas internacionais
    O_t = O_{t−1} (1 + i_S) / (1 + γ_t)                      demais créditos líquidos

Primário que estabiliza a dívida bruta no ano t: s*_t = b_{t−1} (i_t − γ_t) / (1 + γ_t).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

INDEXADORES = ("selic", "pre", "ipca", "cambio")


@dataclass
class Estado:
    b: float                     # dívida bruta, % PIB
    reservas: float              # % PIB
    outros: float                # demais ativos líquidos, % PIB
    p: float                     # taxa média do estoque prefixado, % a.a.
    c: float                     # juro real médio do estoque indexado a preços, % a.a.
    comp: dict = field(default_factory=dict)   # composição da DBGG, % (soma 100)
    lam: dict = field(default_factory=dict)    # fração que vence em 12 meses, %


def passo(e: Estado, x: dict, f_ext: float = 5.0, f_res: float = 4.0, gama: float | None = None) -> tuple[Estado, dict]:
    """Um ano. `x`: selic, ipca, g, dep, prim, y_pre, y_real (todos em %). `gama` opcional (%)."""
    pct = lambda v: v / 100
    pi, g, dep = pct(x["ipca"]), pct(x["g"]), pct(x["dep"])
    gm = pct(gama) if gama is not None else (1 + g) * (1 + pi) - 1
    lp, li = pct(e.lam["pre"]), pct(e.lam["ipca"])
    p = (1 - lp) * e.p + lp * x["y_pre"]
    c = (1 - li) * e.c + li * x["y_real"]
    custo = {
        "selic": pct(x["selic"]),
        "pre": pct(p),
        "ipca": (1 + pct(c)) * (1 + pi) - 1,
        "cambio": (1 + pct(f_ext)) * (1 + dep) - 1,
    }
    w = {k: pct(e.comp[k]) for k in INDEXADORES}
    i = sum(w[k] * custo[k] for k in INDEXADORES)
    b = e.b * (1 + i) / (1 + gm) - x["prim"]
    R = e.reservas * (1 + pct(f_res)) * (1 + dep) / (1 + gm)
    O = e.outros * (1 + custo["selic"]) / (1 + gm)
    novo = Estado(b=b, reservas=R, outros=O, p=p, c=c, comp=e.comp, lam=e.lam)
    info = {"i": i * 100, "gama": gm * 100, "b": b, "n": b - R - O, "juros_brutos": e.b * i / (1 + gm),
            "s_estab": e.b * (i - gm) / (1 + gm), "custo": {k: v * 100 for k, v in custo.items()}}
    return novo, info


def simular(e0: Estado, caminho: list[dict], **kw) -> list[dict]:
    e, out = e0, []
    for x in caminho:
        e, info = passo(e, x, gama=x.get("gama"), **kw)
        out.append({**x, **info})
    return out


def estado_inicial(ci: dict, comp: dict | None = None) -> Estado:
    return Estado(b=ci["dbgg"], reservas=ci["reservas"], outros=ci["outros_ativos"],
                  p=ci["taxa_estoque"]["pre"], c=ci["taxa_estoque"]["ipca"],
                  comp=comp or ci["composicao"], lam={**ci["vence_12m"]})
