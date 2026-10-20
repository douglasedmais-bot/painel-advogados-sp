# Painel de Advogados — São Paulo

Painel interativo com **513 advogados de São Paulo** que possuem **Instagram e site próprio**, com número OAB, estado, cidade, data de registro e tempo de advocacia.

**Link público:** https://douglasedmais-bot.github.io/painel-advogados-sp/

## Recursos

- Busca por nome, OAB, cidade, Instagram, site ou situação
- Filtro por cidade e por situação (ativo / inativo)
- Ordenação por anos de advocacia, nº OAB ou nome
- Links clicáveis para Instagram e site de cada advogado
- Download do resultado filtrado em **CSV** (separador `;`, compatível com Excel PT-BR) e **Excel**
- Painel 100% autocontido — funciona offline, sem depender do servidor

## Dados coletados

| Métrica | Valor |
|---------|-------|
| Total de advogados | 513 |
| Com situação ativa e regular | 286 |
| Com Instagram | 511 (99,6%) |
| Com site próprio | 506 (98,6%) |
| Domínios distintos | 299 |
| Tempo de advocacia | 20 a 92 anos (mediana 51) |

## Como os dados foram obtidos

1. **advogadoperto.com/advogados/sp** — diretório jurídico com 4225 páginas de inscritos de SP; cada perfil traz nº OAB, data de registro, situação cadastral, subseção e tempo de exercício
2. **search.yahoo.com** — busca web para localizar o Instagram e o site próprio de cada advogado (validação por normalização de nome)

## Colunas

```
nome, numero_oab, estado, uf, anos_de_advocacia, data_registro, situacao,
cidade, telefone, whatsapp, instagram, instagram_url, website, url_diretorio, fonte
```

## Rodar a coleta novamente

```bash
python ../advogados_sp_sites.py --paginas 30 --min-anos 20
python ../advogados_sp_sites.py --paginas 10 --comecar 31 --min-anos 30
```

## Arquivos

- `index.html` — painel interativo (dados embutidos, funciona offline)
- `advogados_sp.csv` — 513 registros
- `advogados_sp_ativos.csv` — 286 registros ativos
