"""
dados_fontes.py
===============
Ingestão dos dados do simulador de dívida pública. Fontes públicas, sem credencial:

- BCB/SGS (api.bcb.gov.br): dívida bruta e líquida, NFSP, PIB, Selic, IPCA, câmbio, reservas.
- BCB/Focus (olinda.bcb.gov.br): expectativas anuais para o cenário-base e para validação.
- Tesouro Nacional (tesourotransparente.gov.br): estoque da DPF por título e taxas do Tesouro Direto.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

UA = {"User-Agent": "simulador-divida/1.0", "Accept": "application/json, text/csv, */*"}
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{c}/dados?formato=json&dataInicial={a}&dataFinal={b}"
OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
URL_ESTOQUE_DPF = ("https://www.tesourotransparente.gov.br/ckan/dataset/0998f610-bc25-4ce3-b32c-a873447500c2/"
                   "resource/b6280ed3-ef7e-4569-954a-bded97c2c8a1/download/estoquedpf.csv")
URL_TAXAS_TD = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
                "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv")

# Séries do SGS (títulos conferidos no portal de dados abertos do BCB)
S = {
    "dbgg": 13762,      # Dívida bruta do governo geral (% PIB), metodologia a partir de 2008
    "dlsp": 4513,       # Dívida líquida do setor público (% PIB), setor público consolidado
    "nfsp_prim": 5793,  # NFSP sem desv. cambial, 12 meses, % PIB, resultado primário (positivo = déficit)
    "nfsp_jur": 5760,   # NFSP sem desv. cambial, 12 meses, % PIB, juros nominais
    "pib12": 4382,      # PIB acumulado em 12 meses, R$ milhões correntes
    "pib_real": 7326,   # PIB, variação real anual (%)
    "selic_m": 4189,    # Selic acumulada no mês anualizada (% a.a.)
    "ipca_m": 433,      # IPCA, variação mensal (%)
    "cambio": 1,        # Dólar comercial venda, diário
    "reservas": 13621,  # Reservas internacionais, conceito caixa, US$ milhões, diário
}


def _get(url: str, binario: bool = False, tentativas: int = 4):
    for i in range(tentativas):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()
            return r if binario else json.loads(r.decode("utf-8"))
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(3 * (i + 1))


def sgs(codigo: int, inicio: str = "2000-01-01") -> pd.Series:
    a, fim, partes = pd.Timestamp(inicio), pd.Timestamp(dt.date.today()), []
    while a <= fim:
        b = min(a + pd.DateOffset(years=10) - pd.Timedelta(days=1), fim)
        partes += _get(SGS.format(c=codigo, a=a.strftime("%d/%m/%Y"), b=b.strftime("%d/%m/%Y")))
        a = b + pd.Timedelta(days=1)
    s = pd.Series({pd.to_datetime(r["data"], dayfirst=True): float(r["valor"]) for r in partes})
    return s.sort_index().rename(codigo)


def focus_anuais(data: str | None = None) -> pd.DataFrame:
    """Medianas do Focus (todos os respondentes) na pesquisa mais recente, ou em `data`."""
    if data is None:
        q = {"$top": 1, "$orderby": "Data desc", "$select": "Data", "$format": "json",
             "$filter": "Indicador eq 'Selic' and baseCalculo eq 0"}
        data = _get(OLINDA + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote))["value"][0]["Data"]
    q = {"$top": 5000, "$format": "json", "$select": "Indicador,IndicadorDetalhe,DataReferencia,Mediana",
         "$filter": f"Data eq '{data}' and baseCalculo eq 0"}
    v = _get(OLINDA + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote))["value"]
    d = pd.DataFrame(v)
    d = d[d.IndicadorDetalhe.isna()].pivot_table(index="DataReferencia", columns="Indicador", values="Mediana")
    d.index = d.index.astype(int)
    d.attrs["data"] = data
    return d


def tesouro_csv(url: str) -> pd.DataFrame:
    raw = _get(url, binario=True)
    for enc in ("utf-8", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(raw), sep=";", decimal=",", encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("codificação desconhecida")
