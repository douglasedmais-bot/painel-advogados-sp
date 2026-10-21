# Painel de Advogados — São Paulo

Painel interativo com **513 advogados de São Paulo** com **Instagram, site próprio e processos no e-SAJ (TJSP)**, incluindo o **número de cada processo**.

**Link público:** https://douglasedmais-bot.github.io/painel-advogados-sp/

## Recursos

- Busca por nome, OAB, cidade, Instagram, site, **número de processo** ou código fonte
- Filtro por cidade, situação (ativo/inativo) e **volume de processos** (mais de 30 / 50 / 100 / 200)
- Ordenação por processos, anos de advocacia, nº OAB ou nome
- **Modal com a lista completa de processos**: número unificado, código fonte, grau, classe, data de distribuição, vara e link direto ao processo
- Links clicáveis para Instagram, site e consulta no e-SAJ
- Download do resultado filtrado em **CSV** e **Excel**, e dos **processos** em CSV
- Painel 100% autocontido — funciona offline

## Dados de processos (e-SAJ / TJSP)

| Métrica | Valor |
|---------|-------|
| Advogados consultados no e-SAJ | 513 (0 erros) |
| Com mais de 30 processos | **126** |
| Maior volume | 746 processos |
| Total de processos | 16.248 |
| **Processos com número completo** | **14.403** (1º e 2º grau) |

### Top 10 por volume

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

## Ferramenta: `esaj_tool.py`

Módulo completo e reutilizável da busca do e-SAJ, com **três backends** que funcionam igualmente:

```python
from esaj_tool import ESAJBusca

# requests puro (mais rápido - o e-SAJ renderiza no servidor)
with ESAJBusca(backend="requests") as b:
    r = b.buscar_por_oab(13162)

# Playwright
with ESAJBusca(backend="playwright", headless=False) as b:
    r = b.buscar_por_nome("ABDO HASSEM")

# Selenium
with ESAJBusca(backend="selenium") as b:
    r = b.buscar_por_processo("0001487-97.2009.8.26.0128")

print(r.total, r.por_grau)
for p in r.processos:
    print(p.numero, p.codigo_fonte, p.classe, p.data_distribuicao, p.local)
```

Tipos de busca: `oab` (NUMOAB), `advogado` (NMADVOGADO), `processo` (NUMPROC), `parte` (NMPARTE), `documento` (DOCPARTE).
Graus: `1grau` (`/cpopg/`), `2grau` (`/cposg/`).

CLI:
```bash
python esaj_tool.py --oab 13162
python esaj_tool.py --advogado "ABDO HASSEM" --backend playwright
python esaj_tool.py --oab 13162 --csv processos.csv
python esaj_tool.py --oab 13162 --json
```

### Detalhes técnicos descobertos

- **Paginação:** 25 resultados por página; a troca usa `/cpopg/trocarPagina.do?paginaConsulta=N` (o parâmetro `paginaConsulta` direto em `search.do` é ignorado)
- **Bloqueio:** o e-SAJ responde *"Foram identificadas múltiplas consultas simultâneas"* e devolve uma página vazia. O módulo detecta isso e espera com backoff (8s → 16s → 32s → 60s). **Use `delay=2.5` ou mais**
- **Seletores:** `a.linkProcesso` (número do processo), `processo.codigo` no href (código fonte), `.classeProcesso`, `.assuntoProcesso` / `.assuntoPrincipalProcesso`, `.dataLocalDistribuicao` / `.dataLocalDistribuicaoProcesso`, `.nomeParticipante` / `.nomeParte`
- **Códigos fonte:** 1º grau (`3K...`, `1Y...`, `2S...`, `ZY...`), 2º grau (`RI...`, `RL...`, `RJZ...`)

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

1. **advogadoperto.com/advogados/sp** — diretório com 4225 páginas de inscritos de SP
2. **search.yahoo.com** — busca do Instagram e do site próprio
3. **e-SAJ TJSP** — contagem e extração completa dos processos via `esaj_tool.py`

## Arquivos

- `index.html` — painel interativo (dados embutidos, funciona offline)
- `advogados_consolidado.csv` — 513 registros com processos e números de processo
- `advogados_esaj_detalhe.csv` — 126 attorneys com a lista de processos em JSON
- `processos_esaj_detalhe.csv` — 14.403 processos (número, código fonte, classe, assunto, data, vara, URL)
- `codigos_fonte_esaj.csv` — lista plana de códigos fonte
- `esaj_tool.py` — módulo de consulta ao e-SAJ (requests / playwright / selenium)

## Rodar as coletas novamente

```bash
python ../advogados_sp_sites.py --paginas 30 --min-anos 20
python ../esaj_consulta.py 30
python ../esaj_reexec.py 30 requests
```
