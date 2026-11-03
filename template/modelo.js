// modelo.js — mesma conta de modelo.py, usada pelo dashboard e pelos testes de paridade.
// Entradas em % (a.a. ou do PIB). Ver README, seção 2.
(function (root) {
  const IDX = ["selic", "pre", "ipca", "cambio"];

  // Caminho anual dos parâmetros: 2026 fixo (dados e Focus); de 2027 a 2029 converge
  // linearmente ao valor de longo prazo, atingido em 2030 e mantido até o fim do horizonte.
  function convergir(v0, vLP, ano, anoBase, anoLP) {
    if (ano >= anoLP) return vLP;
    const k = (ano - anoBase) / (anoLP - anoBase);
    return v0 + k * (vLP - v0);
  }

  function caminho(D, P) {
    const anos = [];
    for (let a = D.ano_base + 1; a <= D.ano_fim; a++) anos.push(a);
    const b0 = D.inicio_2026, aLP = D.ano_lp, aB = D.ano_base + 1;
    return anos.map(a => {
      const sel = a === aB ? b0.selic : convergir(b0.selic, P.selic, a, aB, aLP);
      const ip = a === aB ? b0.ipca : convergir(b0.ipca, P.ipca, a, aB, aLP);
      const g = a === aB ? b0.g : convergir(b0.g, P.g, a, aB, aLP);
      const dep = a === aB ? b0.dep : convergir(b0.dep, P.dep, a, aB, aLP);
      const gap = a === aB ? b0.gap_deflator : P.gap_deflator;
      const prim = a === aB ? b0.prim
        : P.prim_ini + (P.prim_fim - P.prim_ini) * (a - (aB + 1)) / (D.ano_fim - (aB + 1));
      const rr = ((1 + sel / 100) / (1 + ip / 100) - 1) * 100;
      const premio = a === aB ? 0 : P.premio;
      return {
        ano: a, selic: sel, ipca: ip, g: g, dep: dep, prim: prim,
        gama: ((1 + g / 100) * (1 + (ip + gap) / 100) - 1) * 100,
        y_pre: sel + D.spread_pre + premio,
        y_real: rr + D.spread_real + premio,
      };
    });
  }

  function simular(D, P) {
    const ci = D.ci;
    const comp = P.comp || ci.composicao;
    let e = { b: ci.dbgg, R: ci.reservas, O: ci.outros_ativos, p: ci.taxa_estoque.pre, c: ci.taxa_estoque.ipca };
    const lp = ci.vence_12m.pre / 100, li = ci.vence_12m.ipca / 100;
    return caminho(D, P).map(x => {
      const pi = x.ipca / 100, dep = x.dep / 100, gm = x.gama / 100;
      const p = (1 - lp) * e.p + lp * x.y_pre;
      const c = (1 - li) * e.c + li * x.y_real;
      const custo = { selic: x.selic / 100, pre: p / 100, ipca: (1 + c / 100) * (1 + pi) - 1,
                      cambio: (1 + D.f_ext / 100) * (1 + dep) - 1 };
      let i = 0; IDX.forEach(k => { i += comp[k] / 100 * custo[k]; });
      const b = e.b * (1 + i) / (1 + gm) - x.prim;
      const R = e.R * (1 + D.f_res / 100) * (1 + dep) / (1 + gm);
      const O = e.O * (1 + custo.selic) / (1 + gm);
      const out = { ...x, i: i * 100, b: b, n: b - R - O,
        juros: e.b * i / (1 + gm), crescimento: -e.b * gm / (1 + gm), primario: -x.prim,
        s_estab: e.b * (i - gm) / (1 + gm) };
      e = { b: b, R: R, O: O, p: p, c: c };
      return out;
    });
  }

  const API = { caminho, simular };
  if (typeof module !== "undefined") module.exports = API; else root.Modelo = API;
})(this);
