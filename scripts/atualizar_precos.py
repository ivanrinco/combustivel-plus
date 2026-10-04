#!/usr/bin/env python3
"""Baixa o CSV semestral da ANP, filtra a região e gera precos-anp.json. Só biblioteca padrão.
Teste com arquivo manual: CSV_LOCAL=arquivo.csv python scripts/atualizar_precos.py"""
import csv, io, json, os, re, statistics, sys, unicodedata, urllib.request
from datetime import datetime, timedelta
BASE = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/dsas/ca/ca-{y}-{s:02d}.csv"
MUN = [m.strip().upper() for m in os.environ.get("MUNICIPIOS", "BELO HORIZONTE,CONTAGEM,BETIM").split(",")]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "precos-anp.json")
def norm(s): return re.sub(r"[^a-z0-9 ]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()
def prod(p):
    p = norm(p)
    return {"gasolina": "g", "etanol": "e", "diesel s10": "di"}.get(p)
def num(v):
    try: return float(str(v).replace(".", "").replace(",", ".")) if "," in str(v) else float(v)
    except: return None
def baixar():
    hoje = datetime.now(); y, s = hoje.year, 1 if hoje.month <= 6 else 2
    for _ in range(2):
        url = BASE.format(y=y, s=s)
        try:
            print("Baixando", url)
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
        except Exception as e: print("Falhou:", e)
        y, s = (y, 1) if s == 2 else (y - 1, 2)
    sys.exit("Não consegui baixar o arquivo da ANP. Nada foi alterado.")
raw = open(os.environ["CSV_LOCAL"], "rb").read() if os.environ.get("CSV_LOCAL") else baixar()
try: txt = raw.decode("utf-8-sig")
except UnicodeDecodeError: txt = raw.decode("latin-1")
rd = csv.DictReader(io.StringIO(txt), delimiter=";")
rd.fieldnames = [norm(h).replace(" ", "_") for h in rd.fieldnames]
rows = []
for r in rd:
    if (r.get("municipio") or "").strip().upper() not in MUN: continue
    k = prod(r.get("produto")); v = num(r.get("valor_de_venda"))
    try: d = datetime.strptime((r.get("data_da_coleta") or "").strip(), "%d/%m/%Y")
    except: continue
    if k and v and v > 0: rows.append((k, v, d, r))
if not rows: sys.exit("Nenhuma linha para a região. Nada foi alterado.")
fim = max(d for _, _, d, _ in rows); ini = fim - timedelta(days=13)
postos, ult = {}, {}
for k, v, d, r in rows:
    if d < ini: continue
    cnpj = (r.get("cnpj_da_revenda") or r.get("revenda") or "").strip()
    p = postos.setdefault(cnpj, {"nome": (r.get("revenda") or "").strip(), "bandeira": (r.get("bandeira") or "").strip(), "rua": (r.get("nome_da_rua") or "").strip(), "num": (r.get("numero_rua") or "").strip(), "bairro": (r.get("bairro") or "").strip(), "mun": (r.get("municipio") or "").strip()})
    if (cnpj, k) not in ult or d > ult[(cnpj, k)]:
        ult[(cnpj, k)] = d; p[k] = round(v, 2); p["data"] = d.strftime("%d/%m/%Y")
med = {k: round(statistics.median([p[k] for p in postos.values() if k in p]), 2) for k in ("g", "e", "di") if any(k in p for p in postos.values())}
out = {"fonte": "ANP - Levantamento de Preços de Combustíveis", "semana": f"{ini:%d/%m} a {fim:%d/%m/%Y}", "regiao": MUN, "medias": med, "postos": list(postos.values())}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print(f"OK: {len(postos)} postos, medianas {med}, semana {out['semana']}")
