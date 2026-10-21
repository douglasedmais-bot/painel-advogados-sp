"""
esaj_tool.py
=============

Cliente completo e reutilizavel da busca publica do e-SAJ (Tribunal de Justica
do Estado de Sao Paulo).

Funciona com tres backends intercambiaveis:

    from esaj_tool import ESAJBusca

    # 1) requests puro (rapido - o e-SAJ renderiza no servidor)
    with ESAJBusca(backend="requests") as b:
        r = b.buscar_por_oab(13162)

    # 2) Playwright (navegador real)
    with ESAJBusca(backend="playwright", headless=False) as b:
        r = b.buscar_por_nome("ABDO HASSEM")

    # 3) Selenium
    with ESAJBusca(backend="selenium") as b:
        r = b.buscar_por_processo("0001487-97.2009.8.26.0128")

Tipos de busca (campo ``cbPesquisa`` do formulario oficial):
    processo   -> NUMPROC
    parte      -> NMPARTE
    documento  -> DOCPARTE
    advogado   -> NMADVOGADO
    oab        -> NUMOAB

Graus disponiveis:
    1grau -> /cpopg/  (comarcas)
    2grau -> /cposg/  (tribunal)

Cada processo retornado traz:
    numero             -> "0001487-97.2009.8.26.0128"  (numero unificado)
    codigo_fonte       -> "RI000FK360000"               (processo.codigo do link)
    numero_tradicional -> "(990.10.150962-8)"
    classe             -> "Apelacao Criminal"
    assunto            -> "DIREITO PENAL - ..."
    data_distribuicao  -> "12/03/2010"
    local              -> "8a Camara de Direito Criminal"
    url                -> link direto para o processo

Uso pela linha de comando:
    python esaj_tool.py --oab 13162
    python esaj_tool.py --oab 13162 --graus 1grau 2grau --csv processos.csv
    python esaj_tool.py --advogado "ABDO HASSEM" --backend playwright
    python esaj_tool.py --processo 0001487-97.2009.8.26.0128 --json
"""

from __future__ import annotations

import csv
import json
import os
import random
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    raise SystemExit("Requer beautifulsoup4 -> pip install beautifulsoup4 requests")

try:
    import requests
except ImportError:  # pragma: no cover
    raise SystemExit("Requer requests -> pip install requests")


# --------------------------------------------------------------------------- #
# Constantes do e-SAJ
# --------------------------------------------------------------------------- #

BASE = "https://esaj.tjsp.jus.br"

GRAUS: Dict[str, Dict[str, str]] = {
    "1grau": {
        "label": "1o grau (comarcas)",
        "search": f"{BASE}/cpopg/search.do",
        "trocar": f"{BASE}/cpopg/trocarPagina.do",
        "show": f"{BASE}/cpopg/show.do",
    },
    "2grau": {
        "label": "2o grau (tribunal)",
        "search": f"{BASE}/cposg/search.do",
        "trocar": f"{BASE}/cposg/trocarPagina.do",
        "show": f"{BASE}/cposg/show.do",
    },
}

TIPOS_PESQUISA: Dict[str, str] = {
    "processo": "NUMPROC",
    "parte": "NMPARTE",
    "documento": "DOCPARTE",
    "advogado": "NMADVOGADO",
    "oab": "NUMOAB",
}

RESULTADOS_POR_PAGINA = 25

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

RE_TOTAL = re.compile(r"(\d+)\s*Processos\s+encontrados", re.IGNORECASE)
RE_CODIGO = re.compile(r"processo\.codigo=([^&]+)")
# O e-SAJ bloqueia consultas rapidas demais com esta mensagem
RE_BLOQUEIO = re.compile(
    r"m[úu]ltiplas\s+consultas\s+simult[âa]neas|"
    r"consulta\s+simult[âa]nea|"
    r"m[úu]ltiples\s+consultas", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Estruturas de dados
# --------------------------------------------------------------------------- #

@dataclass
class Processo:
    """Um processo retornado pelo e-SAJ."""

    numero: str = ""                 # 0001487-97.2009.8.26.0128
    codigo_fonte: str = ""           # RI000FK360000
    numero_tradicional: str = ""     # 990.10.150962-8
    classe: str = ""                 # Apelacao Criminal
    assunto: str = ""                # DIREITO PENAL - ...
    data_distribuicao: str = ""      # 12/03/2010
    local: str = ""                  # 8a Camara de Direito Criminal
    advogado: str = ""               # Abdo Hassem
    grau: str = ""                   # 1grau / 2grau
    url: str = ""                    # link do processo

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Resultado:
    """Resultado completo de uma consulta."""

    tipo: str = ""                   # oab / advogado / processo / parte
    termo: str = ""
    graus: List[str] = field(default_factory=list)
    total: int = 0                   # soma de todos os graus
    por_grau: Dict[str, int] = field(default_factory=dict)
    processos: List[Processo] = field(default_factory=list)
    url_consulta: str = ""
    erro: str = ""

    @property
    def ok(self) -> bool:
        return not self.erro

    def por_grau_lista(self, grau: str) -> List[Processo]:
        return [p for p in self.processos if p.grau == grau]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "tipo": self.tipo,
            "termo": self.termo,
            "graus": self.graus,
            "total": self.total,
            "por_grau": self.por_grau,
            "url_consulta": self.url_consulta,
            "erro": self.erro,
            "processos": [p.as_dict() for p in self.processos],
        }


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #

class BackendError(RuntimeError):
    """Erro generico de backend."""


class BaseBackend:
    """Interface comum: buscar uma URL e devolver o HTML."""

    nome = "base"

    def get(self, url: str) -> str:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class RequestsBackend(BaseBackend):
    """Backend com requests puro.

    O e-SAJ renderiza o resultado no servidor, portanto nao ha necessidade de
    executar JavaScript. E o backend mais rapido e leve.
    """

    nome = "requests"

    def __init__(self, timeout: int = 45, user_agent: str = USER_AGENT,
                 verify: bool = True, proxies: Optional[dict] = None):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })
        if proxies:
            self.session.proxies.update(proxies)
        self.session.verify = verify

    def get(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise BackendError(f"HTTP {resp.status_code} em {url[:120]}")
        return resp.text

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass


class PlaywrightBackend(BaseBackend):
    """Backend com Playwright (navegador real, executa JavaScript)."""

    nome = "playwright"

    def __init__(self, headless: bool = True, timeout: int = 45,
                 user_agent: str = USER_AGENT, slow_mo: int = 0,
                 executable_path: Optional[str] = None, channel: Optional[str] = None):
        self.headless = headless
        self.timeout = timeout
        self.user_agent = user_agent
        self.slow_mo = slow_mo
        self.executable_path = executable_path
        self.channel = channel
        self._pw = None
        self._browser = None
        self._ctx = None
        self._page = None
        self._iniciar()

    def _iniciar(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:  # pragma: no cover
            raise BackendError("Playwright nao instalado -> pip install playwright && playwright install chromium")
        self._pw = sync_playwright().start()
        kwargs: Dict[str, Any] = {
            "headless": self.headless,
            "args": ["--disable-blink-features=AutomationControlled"],
            "slow_mo": self.slow_mo,
        }
        if self.executable_path:
            kwargs["executable_path"] = self.executable_path
        if self.channel:
            kwargs["channel"] = self.channel
        self._browser = self._pw.chromium.launch(**kwargs)
        self._ctx = self._browser.new_context(
            locale="pt-BR",
            user_agent=self.user_agent,
            viewport={"width": 1500, "height": 950},
        )
        self._ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        self._page = self._ctx.new_page()

    def get(self, url: str) -> str:
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
        except Exception as e:
            raise BackendError(f"Falha ao navegar: {e}") from e
        time.sleep(1.2)
        return self._page.content()

    def close(self) -> None:
        for obj in (self._ctx, self._browser):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass


class SeleniumBackend(BaseBackend):
    """Backend com Selenium (WebDriver)."""

    nome = "selenium"

    def __init__(self, headless: bool = True, timeout: int = 45,
                 user_agent: str = USER_AGENT, driver_path: Optional[str] = None,
                 binary_location: Optional[str] = None):
        self.headless = headless
        self.timeout = timeout
        self.user_agent = user_agent
        self.driver_path = driver_path
        self.binary_location = binary_location
        self.driver = None
        self._iniciar()

    def _iniciar(self) -> None:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError:  # pragma: no cover
            raise BackendError("Selenium nao instalado -> pip install selenium")
        opts = Options()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument(f"--user-agent={self.user_agent}")
        opts.add_argument("--lang=pt-BR")
        if self.binary_location:
            opts.binary_location = self.binary_location
        if self.headless:
            opts.add_argument("--headless=new")
        if self.driver_path:
            from selenium.webdriver.chrome.service import Service
            self.driver = webdriver.Chrome(service=Service(self.driver_path), options=opts)
        else:
            self.driver = webdriver.Chrome(options=opts)
        self.driver.set_page_load_timeout(self.timeout)
        self.driver.implicitly_wait(5)

    def get(self, url: str) -> str:
        try:
            self.driver.get(url)
        except Exception as e:
            raise BackendError(f"Falha ao navegar: {e}") from e
        time.sleep(1.2)
        return self.driver.page_source

    def close(self) -> None:
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #

def _texto(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _primeiro(bloco, *seletores) -> str:
    if bloco is None:
        return ""
    for sel in seletores:
        try:
            v = _texto(bloco.select_one(sel))
        except Exception:
            v = ""
        if v:
            return v
    return ""


def parse_resultados(html: str, grau: str, base_url: str) -> Tuple[int, List[Processo]]:
    """Extrai (total_anunciado, processos) do HTML de resultado do e-SAJ."""
    soup = BeautifulSoup(html, "html.parser")
    texto_pagina = soup.get_text(" ", strip=True)

    m = RE_TOTAL.search(texto_pagina)
    total = int(m.group(1)) if m else 0

    processos: List[Processo] = []
    vistos = set()

    for a in soup.select("a.linkProcesso"):
        href = a.get("href") or ""
        mc = RE_CODIGO.search(href)
        codigo = mc.group(1) if mc else ""
        numero = a.get_text(strip=True)

        chave = codigo or numero
        if not chave or chave in vistos:
            continue
        vistos.add(chave)

        bloco = a.find_parent("div", class_=re.compile(r"\brow\b")) or a.parent

        tradicional = ""
        if a.parent is not None:
            sp = a.parent.find("span")
            if sp:
                tradicional = _texto(sp).strip("()")

        data_local = _primeiro(bloco, ".dataLocalDistribuicao",
                               ".dataLocalDistribuicaoProcesso")
        data = local = ""
        if data_local:
            if re.match(r"^\d{2}/\d{2}/\d{4}", data_local):
                data, local = data_local.split(" - ", 1) if " - " in data_local else (data_local, "")
            else:
                local = data_local

        url = href if href.startswith("http") else BASE + href

        processos.append(Processo(
            numero=numero,
            codigo_fonte=codigo,
            numero_tradicional=tradicional,
            classe=_primeiro(bloco, ".classeProcesso"),
            assunto=_primeiro(bloco, ".assuntoProcesso", ".assuntoPrincipalProcesso"),
            data_distribuicao=data.strip(),
            local=local.strip(),
            advogado=_primeiro(bloco, ".nomeParticipante", ".nomeParte"),
            grau=grau,
            url=url,
        ))

    return total, processos


# --------------------------------------------------------------------------- #
# Cliente principal
# --------------------------------------------------------------------------- #

class ESAJBusca:
    """Cliente de consulta ao e-SAJ com backend intercambiavel."""

    def __init__(self, backend: str = "requests", delay: float = 2.5,
                 timeout: int = 45, headless: bool = True,
                 user_agent: str = USER_AGENT, verbose: bool = False,
                 max_tentativas: int = 4, **kwargs):
        """delay: segundos entre requisicoes. O e-SAJ bloqueia ("consultas
        simultaneas") requisicoes muito proximas, por isso o padrao e 2.5s.
        Use delay=0 apenas em ambiente confiavel/local."""
        self.delay = delay
        self.verbose = verbose
        self.max_tentativas = max_tentativas
        self.backend = self._criar_backend(backend, timeout, headless, user_agent, **kwargs)

    # -- infra ------------------------------------------------------------- #

    def _criar_backend(self, nome: str, timeout: int, headless: bool,
                       user_agent: str, **kwargs) -> BaseBackend:
        nome = (nome or "requests").lower()
        if nome == "requests":
            return RequestsBackend(timeout=timeout, user_agent=user_agent,
                                   **{k: v for k, v in kwargs.items()
                                      if k in ("verify", "proxies")})
        if nome == "playwright":
            return PlaywrightBackend(headless=headless, timeout=timeout,
                                     user_agent=user_agent,
                                     **{k: v for k, v in kwargs.items()
                                        if k in ("slow_mo", "executable_path", "channel")})
        if nome == "selenium":
            return SeleniumBackend(headless=headless, timeout=timeout,
                                   user_agent=user_agent,
                                   **{k: v for k, v in kwargs.items()
                                      if k in ("driver_path", "binary_location")})
        raise ValueError(f"Backend desconhecido: {nome} (use requests|playwright|selenium)")

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def _get(self, url: str) -> str:
        """GET com retry. Se o e-SAJ responder 'consultas simultaneas',
        aguarda e tenta novamente (o bloqueio e temporario)."""
        erro = None
        espera_bloqueio = 8
        for tentativa in range(1, self.max_tentativas + 1):
            try:
                html = self.backend.get(url)
            except Exception as e:
                erro = e
                self._log(f"    [tentativa {tentativa}] falha: {str(e)[:80]}")
                time.sleep(1.5 * tentativa)
                continue

            if RE_BLOQUEIO.search(html):
                self._log(f"    [bloqueio: consultas simultaneas] aguardando {espera_bloqueio}s")
                time.sleep(espera_bloqueio)
                espera_bloqueio = min(espera_bloqueio * 2, 60)
                erro = BackendError("e-SAJ bloqueou por consultas simultaneas")
                continue

            return html

        raise BackendError(str(erro) if erro else "falha ao obter a pagina")

    @staticmethod
    def _url(grau: str, cb: str, termo: str, pagina: int = 1, trocar: bool = False) -> str:
        g = GRAUS[grau]
        base = g["trocar"] if trocar else g["search"]
        from urllib.parse import quote
        return (f"{base}?conversationId=&paginaConsulta={pagina}"
                f"&cbPesquisa={cb}&dePesquisa={quote(str(termo))}"
                f"&localPesquisa.cdLocal=-1")

    # -- consulta ---------------------------------------------------------- #

    def buscar(self, tipo: str, termo: str,
               graus: Sequence[str] = ("1grau", "2grau")) -> Resultado:
        """Consulta o e-SAJ.

        tipo  -> "oab" | "advogado" | "processo" | "parte" | "documento"
        termo -> numero da OAB, nome do advogado, numero do processo, ...
        graus -> tupla com "1grau" e/ou "2grau"
        """
        if tipo not in TIPOS_PESQUISA:
            raise ValueError(f"tipo invalido: {tipo}. Use {list(TIPOS_PESQUISA)}")
        cb = TIPOS_PESQUISA[tipo]

        res = Resultado(tipo=tipo, termo=str(termo), graus=list(graus))
        res.url_consulta = self._url(graus[0] if graus else "2grau", cb, termo)

        for grau in graus:
            if grau not in GRAUS:
                self._log(f"  grau desconhecido: {grau}")
                continue
            try:
                html = self._get(self._url(grau, cb, termo, 1))
            except Exception as e:
                self._log(f"  {grau}: erro {str(e)[:80]}")
                res.erro = str(e)
                continue

            total, procs = parse_resultados(html, grau, BASE)
            res.por_grau[grau] = total

            # paginacao: 25 resultados por pagina
            if total > len(procs):
                n_pag = (total + RESULTADOS_POR_PAGINA - 1) // RESULTADOS_POR_PAGINA
                for pg in range(2, n_pag + 1):
                    if self.delay:
                        time.sleep(self.delay * random.uniform(0.7, 1.3))
                    try:
                        html_pg = self._get(self._url(grau, cb, termo, pg, trocar=True))
                    except Exception as e:
                        self._log(f"  {grau} pag {pg}: erro {str(e)[:60]}")
                        break
                    _, procs_pg = parse_resultados(html_pg, grau, BASE)
                    novos = [p for p in procs_pg
                             if p.codigo_fonte not in {x.codigo_fonte for x in procs}]
                    procs.extend(novos)
                self._log(f"  {grau}: {len(procs)} processos em {n_pag} paginas")

            res.processos.extend(procs)
            if self.delay and len(graus) > 1:
                time.sleep(self.delay * random.uniform(0.7, 1.3))

        res.total = sum(res.por_grau.values())
        return res

    # -- atalhos ----------------------------------------------------------- #

    def buscar_por_oab(self, oab: Any, graus: Sequence[str] = ("1grau", "2grau")) -> Resultado:
        """Busca pelo numero de inscricao na OAB (digitos apenas)."""
        oab = re.sub(r"\D", "", str(oab))
        if not oab:
            raise ValueError("OAB invalido")
        return self.buscar("oab", oab, graus)

    def buscar_por_nome(self, nome: str, graus: Sequence[str] = ("1grau", "2grau")) -> Resultado:
        return self.buscar("advogado", nome, graus)

    def buscar_por_processo(self, numero: str, graus: Sequence[str] = ("1grau", "2grau")) -> Resultado:
        return self.buscar("processo", numero, graus)

    # -- exportacao -------------------------------------------------------- #

    @staticmethod
    def exportar(resultado: Resultado, caminho: str, formato: str = "csv") -> str:
        """Exporta o resultado para csv, json ou jsonl."""
        fmt = (formato or caminho.rsplit(".", 1)[-1]).lower()
        if fmt == "json":
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(resultado.as_dict(), f, ensure_ascii=False, indent=1)
        elif fmt == "jsonl":
            with open(caminho, "w", encoding="utf-8") as f:
                for p in resultado.processos:
                    f.write(json.dumps(p.as_dict(), ensure_ascii=False) + "\n")
        else:
            cols = ["grau", "numero", "codigo_fonte", "numero_tradicional", "classe",
                    "assunto", "data_distribuicao", "local", "advogado", "url"]
            with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for p in resultado.processos:
                    w.writerow(p.as_dict())
        return caminho

    # -- ciclo de vida ----------------------------------------------------- #

    def close(self) -> None:
        self.backend.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _cli() -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Consulta publica do e-SAJ (TJSP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--oab", help="numero de inscricao na OAB")
    g.add_argument("--advogado", help="nome do advogado")
    g.add_argument("--processo", help="numero unificado do processo")
    g.add_argument("--parte", help="nome da parte")
    p.add_argument("--graus", nargs="+", default=["1grau", "2grau"],
                   choices=list(GRAUS), help="graus a consultar")
    p.add_argument("--backend", default="requests",
                   choices=["requests", "playwright", "selenium"])
    p.add_argument("--headless", action="store_true", default=True)
    p.add_argument("--visible", dest="headless", action="store_false",
                   help="abre o navegador (playwright/selenium)")
    p.add_argument("--delay", type=float, default=2.5,
                   help="segundos entre requisicoes (o e-SAJ bloqueia consultas rapidas)")
    p.add_argument("--timeout", type=int, default=45)
    p.add_argument("--csv", help="exporta os processos para CSV")
    p.add_argument("--json", action="store_true", help="imprime JSON no stdout")
    p.add_argument("-v", "--verbose", action="store_true")

    a = p.parse_args()

    with ESAJBusca(backend=a.backend, delay=a.delay, timeout=a.timeout,
                   headless=a.headless, verbose=a.verbose) as b:
        if a.oab:
            r = b.buscar_por_oab(a.oab, a.graus)
        elif a.advogado:
            r = b.buscar_por_nome(a.advogado, a.graus)
        elif a.processo:
            r = b.buscar_por_processo(a.processo, a.graus)
        else:
            r = b.buscar("parte", a.parte, a.graus)

        if a.json:
            print(json.dumps(r.as_dict(), ensure_ascii=False, indent=1))
        else:
            print(f"Consulta: {r.tipo}='{r.termo}'  total={r.total}  {r.por_grau}")
            for pr in r.processos[:40]:
                print(f"  [{pr.grau}] {pr.numero:<26} {pr.codigo_fonte:<16} "
                      f"{pr.classe[:26]:<28} {pr.data_distribuicao:<12} {pr.advogado[:26]}")
            if len(r.processos) > 40:
                print(f"  ... e mais {len(r.processes)-40} processos")
        if a.csv:
            b.exportar(r, a.csv, "csv")
            print(f"\nCSV salvo em {a.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
