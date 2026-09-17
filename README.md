# 💊 Preços de medicamentos no Brasil

Análise dos preços de medicamentos regulados pela CMED/ANVISA: quanto genéricos
e similares custam em relação a medicamentos novos, e quais apresentações têm
preço fora do padrão para a mesma substância.

> 🚧 Projeto em construção

## Dados
Lista de Preços de Medicamentos (PMC) publicada mensalmente pela CMED:
https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos

Baixe o arquivo XLSX e coloque em `data/raw/`.

## Etapas
- [x] `01_limpeza.ipynb`: leitura, padronização e tratamento dos preços
- [ ] `02_eda.ipynb`: análise exploratória
- [ ] Clustering de medicamentos por perfil de preço e concorrência
- [ ] Detecção de preços atípicos

## Como rodar
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt

Depois execute os notebooks da pasta `notebooks/` em ordem.