# Simulador da Dívida Pública – Brasil

Simulação da trajetória da dívida pública brasileira em um horizonte de dez anos, para a dívida bruta do governo geral (DBGG) e para a dívida líquida do setor público (DLSP). O usuário altera juros, inflação, crescimento, câmbio, resultado primário, prêmio de risco e composição da dívida por indexador, e observa o efeito sobre a razão dívida/PIB e sobre o primário necessário para estabilizá-la.

**Dashboard:** https://davispeckr.github.io/Simulador-Divida-Publica-Brasil/

O código e o dashboard foram desenvolvidos com auxílio de inteligência artificial (*vibecoding*). As escolhas metodológicas, a calibração e a validação estão descritas abaixo para que qualquer pessoa possa conferir e reproduzir os resultados.

## 1. Motivação

A sustentabilidade da dívida pública voltou ao centro do debate econômico brasileiro, em parte pela discussão sobre a relação entre juros reais elevados, política monetária e trajetória fiscal. O objetivo do simulador é tornar explícita a aritmética que liga esses elementos: dado um conjunto de hipóteses, qual trajetória a dívida segue e qual esforço primário seria necessário para estabilizá-la. O simulador não toma posição sobre quais hipóteses são as mais prováveis.

## 2. Modelo

### 2.1 Equação de acumulação

A dívida bruta em proporção do PIB evolui segundo

```math
b_t = b_{t-1}\,\frac{1+i_t}{1+\gamma_t} - s_t
```

em que $`b_t`$ é a DBGG em % do PIB no fim do ano $`t`$, $`i_t`$ é o custo nominal médio da dívida, $`\gamma_t`$ é o crescimento do PIB nominal e $`s_t`$ é o resultado primário do setor público consolidado (superávit positivo). A variação anual se decompõe em três termos:

```math
b_t - b_{t-1} = \underbrace{\frac{b_{t-1}\,i_t}{1+\gamma_t}}_{\text{juros}} \; \underbrace{- \frac{b_{t-1}\,\gamma_t}{1+\gamma_t}}_{\text{crescimento}} \; \underbrace{- \, s_t}_{\text{primário}}
```

O primário que mantém a razão constante no ano $`t`$ é

```math
s^{*}_t = b_{t-1}\,\frac{i_t-\gamma_t}{1+\gamma_t}
```

O crescimento nominal é $`\gamma_t = (1+g_t)(1+\pi_t+\delta)-1`$, com $`g_t`$ o crescimento real, $`\pi_t`$ o IPCA e $`\delta`$ a diferença entre a variação do deflator do PIB e o IPCA (seção 3.3).

### 2.2 Custo da dívida por indexador

A dívida é dividida em quatro grupos, com pesos $`w_k`$ que somam 1 e são mantidos constantes ao longo do horizonte:

```math
i_t = w_S\,i^{S}_t + w_P\,p_t + w_I\left[(1+c_t)(1+\pi_t)-1\right] + w_C\left[(1+f)(1+e_t)-1\right]
```

- **Selic** ($`w_S`$): títulos pós-fixados (LFT) e o restante da DBGG não coberto pela Dívida Pública Federal em mercado, composto sobretudo pelas operações compromissadas do Banco Central. Paga a Selic média do ano, $`i^{S}_t`$.
- **Prefixado** ($`w_P`$): LTN e NTN-F. A taxa média do estoque $`p_t`$ só incorpora as taxas novas à medida que os títulos vencem.
- **Índices de preços** ($`w_I`$): NTN-B e NTN-C. O juro real médio do estoque $`c_t`$ se ajusta da mesma forma; o custo nominal soma a inflação do ano.
- **Câmbio** ($`w_C`$): dívida externa, que paga um juro externo $`f`$ (5% a.a.) mais a depreciação cambial $`e_t`$.

A repactuação dos grupos prefixado e de índices segue

```math
p_t = (1-\lambda_P)\,p_{t-1} + \lambda_P\,y^{pre}_t, \qquad c_t = (1-\lambda_I)\,c_{t-1} + \lambda_I\,y^{real}_t
```

em que $`\lambda`$ é a fração do estoque de cada grupo que vence em até 12 meses e $`y`$ é a taxa de emissão do ano. A hipótese implícita é que o Tesouro refinancia os vencimentos mantendo a composição e o perfil de prazos.

### 2.3 Taxas de emissão

As taxas de emissão acompanham a Selic do ano, com prêmios calibrados nas taxas correntes do Tesouro Direto:

```math
y^{pre}_t = i^{S}_t + \kappa_P + \rho_t, \qquad y^{real}_t = r_t + \kappa_I + \rho_t
```

em que $`r_t = (1+i^{S}_t)/(1+\pi_t)-1`$ é a Selic real, $`\kappa_P`$ e $`\kappa_I`$ são os prêmios observados hoje sobre a Selic do primeiro ano projetado e $`\rho_t`$ é o prêmio de risco adicional escolhido pelo usuário, aplicado a partir do segundo ano. Essa formulação evita que uma Selic mais baixa conviva com taxas longas inalteradas, o que superestimaria o custo da dívida.

### 2.4 Dívida líquida

A DLSP é a DBGG menos os ativos do setor público, divididos em reservas internacionais $`R`$ e demais créditos líquidos $`O`$:

```math
n_t = b_t - R_t - O_t, \qquad R_t = R_{t-1}\,\frac{(1+f_R)(1+e_t)}{1+\gamma_t}, \qquad O_t = O_{t-1}\,\frac{1+i^{S}_t}{1+\gamma_t}
```

com retorno das reservas $`f_R`$ de 4% a.a. em moeda estrangeira. O primário afeta DBGG e DLSP igualmente. Uma depreciação cambial aumenta a parcela cambial da dívida bruta, mas reduz a dívida líquida, pois o setor público é credor líquido em moeda estrangeira.

### 2.5 Caminho dos parâmetros

O primeiro ano projetado usa dados realizados (meses já divulgados da Selic) e medianas do Focus para o restante do ano. Selic, IPCA, crescimento real e depreciação cambial convergem linearmente até os valores de longo prazo escolhidos, atingidos no quinto ano projetado e mantidos até o fim do horizonte. O resultado primário segue uma reta entre o valor escolhido para o segundo ano e o valor escolhido para o último ano.

## 3. Dados e calibração

### 3.1 Condições iniciais

O ano-base é o último dezembro com estoque da Dívida Pública Federal (DPF) publicado pelo Tesouro. Para dezembro de 2025:

| Item | Valor |
|---|---:|
| DBGG | 78,6% do PIB |
| DLSP | 65,2% do PIB |
| Composição: Selic / prefixado / índices / câmbio | 55,5% / 19,0% / 22,3% / 3,2% |
| Vence em 12 meses: prefixado / índices | 29,4% / 11,2% |
| Taxa média do estoque: prefixado / índices | 12,2% / IPCA + 5,8% |
| Reservas internacionais | 15,5% do PIB |
| Demais créditos líquidos | −2,1% do PIB |

A composição combina o estoque da DPF em mercado por título com a DBGG do Banco Central. A diferença entre a DBGG e a DPF em mercado é tratada como dívida à Selic.

O Tesouro registra o estoque pelo valor apropriado à taxa de emissão. Por isso, o preço unitário de cada título (valor dividido pela quantidade) revela a taxa à qual ele foi emitido. Para LTN e NTN-B Principal a taxa sai diretamente; para NTN-F e NTN-B com cupom, por bisseção sobre o fluxo de cupons semestrais. O valor nominal atualizado da NTN-B é calculado pelo IPCA desde 15/07/2000. As taxas médias do estoque são ponderadas pelo valor de cada título.

Os ativos da DLSP são a diferença entre DBGG e DLSP. As reservas são convertidas para reais pelo câmbio do último dia do ano-base e divididas pelo PIB em 12 meses; o restante é classificado como demais créditos líquidos.

### 3.2 Cenário Focus

O cenário-base usa as medianas do Focus (Banco Central) para Selic, IPCA, PIB, câmbio e resultado primário, com os valores do quinto ano projetado como valores de longo prazo. O Focus também fornece expectativas para a DBGG e a DLSP, usadas apenas como referência no gráfico e na validação.

### 3.3 Deflator do PIB

O PIB nominal cresce com o deflator do PIB, e não com o IPCA. Entre 2010 e 2025, a variação do deflator implícito (PIB nominal em 12 meses dividido pelo crescimento real) superou o IPCA em 1,16 p.p. ao ano, em média. Esse valor é usado como padrão para $`\delta`$ e pode ser alterado no painel. Com $`\delta = 0`$, o crescimento nominal é menor e a dívida simulada fica sistematicamente acima das projeções de mercado.

### 3.4 Prêmios das taxas de emissão

Os prêmios $`\kappa_P`$ e $`\kappa_I`$ são calculados com as taxas médias de venda dos títulos prefixados e IPCA+ do Tesouro Direto com prazo entre 2 e 10 anos, no último dia disponível, em relação à Selic média esperada para o primeiro ano projetado.

## 4. Validação

### 4.1 Comparação com o Focus

No cenário-base, a DBGG simulada fica próxima da mediana do Focus até 2030 e acima dela depois. A tabela atualizada está no dashboard. Na versão de 30/10/2026:

| Ano | 2027 | 2028 | 2029 | 2030 | 2031 | 2032 | 2033 | 2034 | 2035 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Simulado | 86,5 | 90,1 | 93,4 | 96,3 | 99,0 | 101,6 | 104,2 | 106,6 | 108,9 |
| Focus | 87,4 | 90,5 | 93,2 | 95,5 | 96,9 | 98,6 | 99,9 | 100,3 | 101,7 |

A divergência a partir de 2031 é esperada. As expectativas de mercado para a dívida não precisam ser consistentes com as expectativas individuais para juros e primário, e parte dos respondentes do Focus provavelmente incorpora ajustes fiscais ou efeitos não modelados aqui.

### 4.2 Teste com parâmetros realizados

O script `backtest.py` parte do estoque observado em dezembro de cada ano e aplica um passo do modelo com os valores realizados no ano seguinte (Selic, IPCA, PIB nominal, câmbio, primário e taxas médias do Tesouro Direto). Erro = simulado − observado, em p.p. do PIB:

| Ano | DBGG observada | DBGG simulada | Erro | DLSP observada | DLSP simulada | Erro |
|---|---:|---:|---:|---:|---:|---:|
| 2022 | 71,7 | 75,3 | +3,6 | 56,1 | 56,1 | −0,1 |
| 2023 | 73,8 | 75,7 | +1,8 | 60,4 | 62,0 | +1,6 |
| 2024 | 76,3 | 76,9 | +0,6 | 61,3 | 59,9 | −1,4 |
| 2025 | 78,6 | 79,5 | +0,9 | 65,2 | 67,2 | +2,0 |

O modelo superestima a DBGG em todos os anos. A equação não captura fluxos que reduzem a dívida bruta sem passar pelo primário, como o uso do caixa do Tesouro (Conta Única), devoluções de recursos do BNDES e variações nas operações compromissadas ligadas à liquidez do sistema bancário. Na DLSP o erro não tem sinal sistemático, o que é consistente com esses fluxos afetarem sobretudo a composição entre dívida e ativos.

## 5. Limitações

1. **Simulação contábil.** Juros, inflação, câmbio e crescimento são parâmetros exógenos. Na economia, eles respondem ao quadro fiscal e uns aos outros: uma Selic menor sem ancoragem das expectativas pode trazer mais inflação e prêmio de risco. Cabe ao usuário escolher combinações coerentes.
2. **Fluxos não modelados.** Privatizações, reconhecimento de passivos, uso do caixa do Tesouro, devoluções de bancos públicos e ajustes patrimoniais não entram na equação.
3. **Composição constante.** A estratégia de financiamento do Tesouro altera a composição ao longo do tempo; aqui ela é fixa e definida pelo usuário. No painel, as quatro parcelas somam sempre 100%: ao alterar uma, as demais são reescaladas na proporção que tinham entre si.
4. **Primário consolidado.** O resultado primário inclui governo central, governos regionais e estatais, enquanto a DBGG cobre o governo geral.
5. **Parâmetros externos fixos.** Juro da dívida externa (5% a.a.) e retorno das reservas (4% a.a.) são constantes.
6. **Não é previsão.** Os resultados mostram consequências aritméticas de hipóteses, não projeções oficiais.

## 6. Reprodução

```bash
pip install -r requirements.txt
python build.py          # baixa os dados, calibra e gera docs/index.html
python build.py --cache  # regenera a página a partir de dados/insumos.json
python backtest.py       # teste com parâmetros realizados
```

O `build.py` interrompe a geração se a simulação do cenário-base em Python (`modelo.py`) e em JavaScript (`template/modelo.js`, usada no dashboard) divergir em mais de $`10^{-9}`$ p.p. Requer Node.js para essa verificação. Um workflow do GitHub Actions atualiza os dados toda segunda-feira, após a divulgação do Focus.

| Arquivo | Conteúdo |
|---|---|
| `dados_fontes.py` | Download das séries do BCB, do Focus e do Tesouro |
| `calibracao.py` | Composição, vencimentos, taxas do estoque e ativos da DLSP |
| `modelo.py` | Equações do modelo |
| `build.py` | Montagem dos insumos, verificação de paridade e geração da página |
| `backtest.py` | Teste com parâmetros realizados |
| `template/` | Página do dashboard e versão JavaScript do modelo |
| `dados/insumos.json` | Todos os valores usados pelo dashboard |

## 7. Fontes

- Banco Central do Brasil. Sistema Gerenciador de Séries Temporais (SGS): séries 13762 (DBGG), 4513 (DLSP), 5793 e 5760 (NFSP primário e juros nominais), 4382 (PIB em 12 meses), 7326 (PIB real), 4189 (Selic), 433 (IPCA), 1 (câmbio) e 13621 (reservas internacionais).
- Banco Central do Brasil. Sistema de Expectativas de Mercado (Focus), expectativas anuais.
- Tesouro Nacional. Estoque da Dívida Pública Federal e preços e taxas do Tesouro Direto, Tesouro Transparente.
- Blanchard, O. (2019). Public debt and low interest rates. *American Economic Review*, 109(4), 1197–1229.
- Escolano, J. (2010). A practical guide to public debt dynamics, fiscal sustainability, and cyclical adjustment of budgetary aggregates. *IMF Technical Notes and Manuals*, 2010/02.

## Autor

Davi Speck Ramos · [LinkedIn](https://www.linkedin.com/in/davi-speck-ramos-a26079242)
