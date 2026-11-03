#!/usr/bin/env python3
"""
build.py — dados e página do Simulador da Dívida Pública.

    python build.py            # baixa BCB, Focus e Tesouro; calibra; gera docs/index.html
    python build.py --cache    # reusa dados/insumos.json e só regenera a página

Saídas: dados/insumos.json (tudo o que a página usa), docs/index.html, docs/fragment.html.
Falha se a simulação do cenário-base em Python e em JavaScript divergir.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd

RAIZ = pathlib.Path(__file__).parent
sys.path.insert(0, str(RAIZ))
import calibracao as C  # noqa: E402
import dados_fontes as F  # noqa: E402
import modelo as M  # noqa: E402

DADOS, DOCS, TPL = RAIZ / "dados", RAIZ / "docs", RAIZ / "template"
HORIZONTE = 10
GAP_JANELA = (2010, 2025)        # média histórica deflator do PIB − IPCA
F_EXT, F_RES = 5.0, 4.0          # juro da dívida externa e retorno das reservas, % a.a. (em moeda estrangeira)


def media_taxa_td(td: pd.DataFrame, tipo: str, data: pd.Timestamp) -> float:
    td = td.copy()
    td["base"] = pd.to_datetime(td["Data Base"], dayfirst=True)
    td["venc"] = pd.to_datetime(td["Data Vencimento"], dayfirst=True)
    td["prazo"] = (td.venc - td.base).dt.days / 365.25
    s = td[(td["Tipo Titulo"] == tipo) & (td.base == data) & td.prazo.between(2, 10)]
    return float(s["Taxa Venda Manha"].mean())


def montar_insumos() -> dict:
    print("→ BCB/SGS")
    S = {k: F.sgs(c, "2000-01-01" if k == "ipca_m" else ("2015-01-01" if k in ("cambio", "reservas") else "2002-01-01"))
         for k, c in F.S.items()}
    print("→ Focus")
    foc = F.focus_anuais()
    print("→ Tesouro: estoque da DPF e taxas do Tesouro Direto")
    est = C.preparar_estoque(F.tesouro_csv(F.URL_ESTOQUE_DPF))
    td = F.tesouro_csv(F.URL_TAXAS_TD)

    # ano-base: último dezembro com estoque da DPF publicado
    dez = sorted(d for d in est.data.unique() if pd.Timestamp(d).month == 12)
    base = pd.Timestamp(dez[-1])
    ab = base.year
    m = pd.Timestamp(f"{ab}-12-01")
    ci = C.condicoes_iniciais(est, base, S["dbgg"][m], S["dlsp"][m], S["pib12"][m], S["ipca_m"],
                              S["reservas"].asof(base), S["cambio"].asof(base))

    # deflator do PIB − IPCA, média histórica
    gaps = []
    for y in range(GAP_JANELA[0], GAP_JANELA[1] + 1):
        gm = S["pib12"][pd.Timestamp(f"{y}-12-01")] / S["pib12"][pd.Timestamp(f"{y-1}-12-01")] - 1
        g = S["pib_real"][pd.Timestamp(f"{y}-01-01")] / 100
        ip = np.prod(1 + S["ipca_m"][str(y)] / 100) - 1
        gaps.append(((1 + gm) / (1 + g) - 1 - ip) * 100)
    gap = float(np.mean(gaps))

    # ano 1 (ano-base + 1): meses realizados da Selic + expectativa de fim de ano para os restantes
    a1 = ab + 1
    sm = S["selic_m"][str(a1)]
    selic_a1 = float((sm.sum() + (12 - len(sm)) * foc.loc[a1, "Selic"]) / 12)
    cambio_base = float(S["cambio"].asof(base))
    inicio = {"selic": selic_a1, "ipca": float(foc.loc[a1, "IPCA"]), "g": float(foc.loc[a1, "PIB Total"]),
              "dep": (float(foc.loc[a1, "Câmbio"]) / cambio_base - 1) * 100,
              "prim": float(foc.loc[a1, "Resultado primário"]), "gap_deflator": gap}

    # taxas de emissão hoje e prêmios sobre a Selic do ano 1
    ult_td = pd.to_datetime(td["Data Base"], dayfirst=True).max()
    y_pre = media_taxa_td(td, "Tesouro Prefixado", ult_td)
    y_real = media_taxa_td(td, "Tesouro IPCA+", ult_td)
    rr1 = ((1 + selic_a1 / 100) / (1 + inicio["ipca"] / 100) - 1) * 100
    ano_lp = a1 + 4
    lp = min(ano_lp, int(foc.index.max()))
    cam_lp = (float(foc.loc[lp, "Câmbio"]) / float(foc.loc[lp - 1, "Câmbio"]) - 1) * 100

    hist = {
        "dbgg": {str(d.year): float(v) for d, v in S["dbgg"].items() if d.month == 12 and d.year >= 2008},
        "dlsp": {str(d.year): float(v) for d, v in S["dlsp"].items() if d.month == 12 and d.year >= 2008},
        "ultimo": {"mes": S["dbgg"].index[-1].strftime("%Y-%m"), "dbgg": float(S["dbgg"].iloc[-1]),
                   "dlsp": float(S["dlsp"].iloc[-1])},
    }
    focus_div = {
        "dbgg": {str(a): float(v) for a, v in foc["Dívida bruta do governo geral"].dropna().items() if a > ab},
        "dlsp": {str(a): float(v) for a, v in foc["Dívida líquida do setor público"].dropna().items() if a > ab},
    }
    padrao = {"selic": float(foc.loc[lp, "Selic"]), "ipca": float(foc.loc[lp, "IPCA"]),
              "g": float(foc.loc[lp, "PIB Total"]), "dep": round(cam_lp, 2), "gap_deflator": round(gap, 2),
              "prim_ini": float(foc.loc[a1 + 1, "Resultado primário"]),
              "prim_fim": float(foc["Resultado primário"].dropna().iloc[-1]), "premio": 0.0,
              "comp": {k: round(v, 1) for k, v in ci["composicao"].items()}}
    return {
        "gerado": dt.date.today().isoformat(), "focus_data": foc.attrs["data"], "td_data": ult_td.strftime("%Y-%m-%d"),
        "ano_base": ab, "ano_fim": ab + 1 + HORIZONTE, "ano_lp": ano_lp,
        "ci": ci, "inicio_2026": inicio, "padrao": padrao,
        "spread_pre": y_pre - selic_a1, "spread_real": y_real - rr1, "y_pre_hoje": y_pre, "y_real_hoje": y_real,
        "f_ext": F_EXT, "f_res": F_RES, "gap_janela": list(GAP_JANELA),
        "historico": hist, "focus_divida": focus_div,
    }


# ------------------------------------------------------------- paridade Python × JS

def caminho_py(D: dict, P: dict) -> list[dict]:
    b0, aB, aLP, aF = D["inicio_2026"], D["ano_base"] + 1, D["ano_lp"], D["ano_fim"]
    conv = lambda v0, v, a: v if a >= aLP else v0 + (a - aB) / (aLP - aB) * (v - v0)
    out = []
    for a in range(aB, aF + 1):
        f = (lambda k: b0[k]) if a == aB else (lambda k: conv(b0[k], P[k], a))
        sel, ip, g, dep = f("selic"), f("ipca"), f("g"), f("dep")
        gap = b0["gap_deflator"] if a == aB else P["gap_deflator"]
        prim = b0["prim"] if a == aB else P["prim_ini"] + (P["prim_fim"] - P["prim_ini"]) * (a - (aB + 1)) / (aF - (aB + 1))
        rr = ((1 + sel / 100) / (1 + ip / 100) - 1) * 100
        pr = 0 if a == aB else P["premio"]
        out.append({"ano": a, "selic": sel, "ipca": ip, "g": g, "dep": dep, "prim": prim,
                    "gama": ((1 + g / 100) * (1 + (ip + gap) / 100) - 1) * 100,
                    "y_pre": sel + D["spread_pre"] + pr, "y_real": rr + D["spread_real"] + pr})
    return out


def simular_py(D: dict, P: dict) -> list[dict]:
    e0 = M.estado_inicial(D["ci"], comp=P.get("comp"))
    return M.simular(e0, caminho_py(D, P), f_ext=D["f_ext"], f_res=D["f_res"])


def checar_paridade(D: dict) -> float:
    js = (TPL / "modelo.js").read_text(encoding="utf-8")
    codigo = js + f"\nconsole.log(JSON.stringify(module.exports.simular({json.dumps(D)}, {json.dumps(D['padrao'])})));"
    r = subprocess.run(["node", "-e", "const module={exports:{}};" + codigo], capture_output=True, text=True, check=True)
    sj = json.loads(r.stdout)
    sp = simular_py(D, D["padrao"])
    return max(max(abs(a["b"] - b["b"]), abs(a["n"] - b["n"])) for a, b in zip(sj, sp))


def main(cache: bool) -> None:
    DADOS.mkdir(exist_ok=True); DOCS.mkdir(exist_ok=True)
    arq = DADOS / "insumos.json"
    D = json.loads(arq.read_text()) if cache and arq.exists() else montar_insumos()
    D["ano_fim"] = D["ano_base"] + 1 + HORIZONTE
    arq.write_text(json.dumps(D, ensure_ascii=False, indent=1), encoding="utf-8")

    dif = checar_paridade(D)
    if dif > 1e-9:
        raise SystemExit(f"ABORTADO: Python e JavaScript divergem em {dif:.2e} p.p.")
    base = simular_py(D, D["padrao"])

    pag = (TPL / "page.html").read_text(encoding="utf-8")
    pag = pag.replace("/*__MODELO__*/", (TPL / "modelo.js").read_text(encoding="utf-8"))
    pag = pag.replace("/*__DATA__*/", json.dumps(D, ensure_ascii=False, separators=(",", ":")))
    (DOCS / "fragment.html").write_text(pag, encoding="utf-8")
    html = ('<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + pag.replace('\n<div class="wrap">', '\n</head>\n<body>\n<div class="wrap">', 1) + "\n</body>\n</html>\n")
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(f"OK · base {D['ci']['data']} · DBGG {D['ci']['dbgg']:.1f}% → {base[-1]['b']:.1f}% em {base[-1]['ano']} · "
          f"DLSP {D['ci']['dlsp']:.1f}% → {base[-1]['n']:.1f}% · paridade {dif:.1e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", action="store_true")
    main(**vars(ap.parse_args()))
