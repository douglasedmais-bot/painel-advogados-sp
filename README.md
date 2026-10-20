# Painel de Advogados — São Paulo

Painel interativo com **513 advogados de São Paulo** com **Instagram, site próprio e processos no e-SAJ (TJSP)**, com número OAB, cidade, tempo de advocacia e volume de processos.

**Link público:** https://douglasedmais-bot.github.io/painel-advogados-sp/

## Recursos

- Busca por nome, OAB, cidade, Instagram, site ou código fonte
- Filtro por cidade, situação (ativo/inativo) e **volume de processos** (mais de 30 / 50 / 100 / 200)
- Ordenação por processos, anos de advocacia, nº OAB ou nome
- Links clicáveis para Instagram, site e consulta no e-SAJ
- Modal com a lista de **códigos fonte** de cada advogado, com link direto para o processo
- Download do resultado filtrado em **CSV** e **Excel**, e dos **códigos fonte** em CSV
- Painel 100% autocontido — funciona offline

## Dados de processos (e-SAJ / TJSP)

Consulta pública do e-SAJ nos dois graus, por número de OAB:

- 1º grau — `esaj.tjsp.jus.br/cpopg/search.do` (códigos no formato `3K...`, `1Y...`, `RL...`)
- 2º grau — `esaj.tjsp.jus.br/cposg/search.do` (códigos no formato `RI...`, `RL...`, `RJZ...`)

O **código fonte** de cada processo é o parâmetro `processo.codigo` do link para o processo.

| Métrica | Valor |
|---------|-------|
| Advogados consultados no e-SAJ | 513 (0 erros) |
| Com mais de 30 processos | **126** |
| Maior volume | 746 processos |
| Total de processos | 16.248 |
| Total de códigos fonte | 17.829 |

### Top 10 por volume de processos

| OAB | Processos | 1º grau | 2º grau | Advogado |
|-----|-----------|---------|---------|----------|
| 252047 | 746 | 710 | 36 | ADEMIR DE OLIVEIRA COSTA JUNIOR |
| 114596 | 715 | 700 | 15 | ADEMIR BARRUECO GANDOLFI |
| 208725 | 634 | 609 | 25 | ADEMAR DE MARCHI FILHO |
| 208965 | 473 | 421 | 52 | ADEMAR FERREIRA MOTA |
| 34312 | 448 | 381 | 67 | ADALBERTO GRIFFO |
| 27024 | 387 | 231 | 156 | ADELAIDE ROSSINI DE JESUS |
| 105465 | 351 | 304 | 47 | ACACIO VALDEMAR LORENCAO JUNIOR |
| 26130 | 331 | 299 | 32 | ADEMAR VALTER COIMBRA |
| 36250 | 312 | 281 | 31 | ADALBERTO CALIL |
| 24974 | 305 | 226 | 79 | ADELINO MORELLI |

## Perfil geral dos 513

| Métrica | Valor |
|---------|-------|
| Total | 513 |
| Ativos na OAB | 286 |
| Com Instagram | 511 (99,6%) |
| Com site próprio | 506 (98,6%) |
| Domínios distintos | 299 |
| Tempo de advocacia | 20 a 92 anos (mediana 51) |

## Como os dados foram obtidos

1. **advogadoperto.com/advogados/sp** — diretório com 4225 páginas de inscritos de SP (nº OAB, data de registro, situação, subseção, tempo de exercício)
2. **search.yahoo.com** — busca do Instagram e do site próprio de cada advogado
3. **e-SAJ TJSP** — contagem de processos no 1º e 2º grau por OAB, com extração dos códigos fonte

## Colunas do CSV consolidado

```
nome, numero_oab, uf, estado, anos_de_advocacia, data_registro, situacao,
cidade, telefone, whatsapp, instagram, instagram_url, website, url_diretorio,
processos_1grau, processos_2grau, total_processos, codigos_fonte_todos, url_consulta_esaj
```

## Arquivos

- `index.html` — painel interativo (dados embutidos, funciona offline)
- `advogados_consolidado.csv` — 513 registros com processos e códigos fonte
- `advogados_esaj_30processos.csv` — 126 attorneys com mais de 30 processos
- `codigos_fonte_esaj.csv` — 14.405 linhas (advogado, grau, código fonte, url do processo)

## Rodar a coleta novamente

```bash
python ../advogados_sp_sites.py --paginas 30 --min-anos 20
python ../esaj_consulta.py 30
```
