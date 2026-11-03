#!/usr/bin/env python3
"""
backtest.py — teste do modelo com parâmetros realizados.

Para cada ano Y, parte do estoque observado em dezembro de Y−1 (composição, vencimentos e taxas do
estoque da DPF) e aplica um passo do modelo com Selic, IPCA, PIB nominal, câmbio e resultado primário
efetivamente observados em Y. As taxas de emissão são a média anual das taxas do Tesouro Direto
(prefixados e IPCA+ de 2 a 10 anos). Compara a dívida simulada com a observada em dezembro de Y.

    python backtest.py             # imprime a tabela e grava dados/backtest.csv
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

RAIZ = pathlib.Path(__file__).parent
sys.path.insert(0, str(RAIZ))
import calibracao as C  # noqa: E402
import dados_fontes as F  # noqa: E402
import modelo as M  # noqa: E402
from build import F_EXT, F_RES  # noqa: E402

ANOS = range(2022, 2026)


def taxa_media_ano(td: pd.DataFrame, tipo: str, ano: int) -> float:
    s = td[(td["Tipo Titulo"] == tipo) & (td.base.dt.year == ano) & td.prazo.between(2, 10)]
    return float(s["Taxa Venda Manha"].mean())


def main() -> None:
    S = {k: F.sgs(c, "2000-01-01" if k == "ipca_m" else "2015-01-01") for k, c in F.S.items()}
    est = C.preparar_estoque(F.tesouro_csv(F.URL_ESTOQUE_DPF))
    td = F.tesouro_csv(F.URL_TAXAS_TD)
    td["base"] = pd.to_datetime(td["Data Base"], dayfirst=True)
    td["prazo"] = (pd.to_datetime(td["Data Vencimento"], dayfirst=True) - td.base).dt.days / 365.25

    linhas = []
    for y in ANOS:
        d0, d1 = pd.Timestamp(f"{y-1}-12-31"), pd.Timestamp(f"{y}-12-31")
        m0, m1 = pd.Timestamp(f"{y-1}-12-01"), pd.Timestamp(f"{y}-12-01")
        ci = C.condicoes_iniciais(est, d0, S["dbgg"][m0], S["dlsp"][m0], S["pib12"][m0], S["ipca_m"],
                                  S["reservas"].asof(d0), S["cambio"].asof(d0))
        ipca = (np.prod(1 + S["ipca_m"][str(y)] / 100) - 1) * 100
        selic = float(S["selic_m"][str(y)].mean())
        x = {"selic": selic, "ipca": ipca, "g": float(S["pib_real"][pd.Timestamp(f"{y}-01-01")]),
             "dep": (S["cambio"].asof(d1) / S["cambio"].asof(d0) - 1) * 100,
             "prim": -float(S["nfsp_prim"][m1]),
             "gama": (S["pib12"][m1] / S["pib12"][m0] - 1) * 100,
             "y_pre": taxa_media_ano(td, "Tesouro Prefixado", y),
             "y_real": taxa_media_ano(td, "Tesouro IPCA+", y)}
        _, info = M.passo(M.estado_inicial(ci), x, f_ext=F_EXT, f_res=F_RES, gama=x["gama"])
        linhas.append({"ano": y, "dbgg_obs": S["dbgg"][m1], "dbgg_sim": info["b"],
                       "erro_dbgg": info["b"] - S["dbgg"][m1], "dlsp_obs": S["dlsp"][m1],
                       "dlsp_sim": info["n"], "erro_dlsp": info["n"] - S["dlsp"][m1]})
    r = pd.DataFrame(linhas).set_index("ano").round(2)
    (RAIZ / "dados").mkdir(exist_ok=True)
    r.to_csv(RAIZ / "dados" / "backtest.csv")
    print(r.to_string())


if __name__ == "__main__":
    main()
