#!/usr/bin/env python3
"""Baixa os CSVs das 'últimas 4 semanas' da ANP, filtra a região e gera precos-anp.json. Só biblioteca padrão.
Teste com arquivos locais: CSV_LOCAL=a.csv,b.csv python scripts/atualizar_precos.py"""
import csv, io, json, os, re, statistics, sys, unicodedata, urllib.request
from datetime import datetime, timedelta
B = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/qus/"
URLS = [B + "ultimas-4-semanas-gasolina-etanol.csv", B + "ultimas-4-semanas-diesel-gnv.csv"]
MUN = [m.strip().upper() for m in os.environ.get("MUNICIPIOS", "BELO HORIZONTE,CONTAGEM,BETIM").split(",")]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "precos-anp.json")
ALIAS = {"municipio": ["municipio", "cidade"], "revenda": ["revenda", "razao_social", "nome_da_revenda", "nome_fantasia"],
 "cnpj": ["cnpj_da_revenda", "cnpj"], "rua": ["nome_da_rua", "endereco", "logradouro"], "num": ["numero_rua", "numero"],
 "bairro": ["bairro"], "produto": ["produto"], "data": ["data_da_coleta", "data_coleta", "data"],
 "valor": ["valor_de_venda", "preco_de_venda", "valor_venda", "preco_venda", "preco_revenda"], "bandeira": ["bandeira"]}
def norm(s): return re.sub(r"[^a-z0-9 ]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()
def prod(p):
    p = norm(p)
    if p in ("gasolina", "gasolina comum", "gasolina c"): return "g"
    if p.startswith("etanol"): return "e"
    if "diesel" in p and "s10" in p.replace(" ", "").replace("-", ""): return "di"
def num(v):
    v = str(v).strip()
    try: return float(v.replace(".", "").replace(",", ".")) if "," in v else float(v)
    except: return None
def data(v):
    for f in ("%d/%m/%Y", "%Y-%m-%d"):
        try: return datetime.strptime(v.strip()[:10], f)
        except: pass
def baixar(u):
    print("Baixando", u)
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
def texto(raw):
    try: return raw.decode("utf-8-sig")
    except UnicodeDecodeError: return raw.decode("latin-1")
raws = []
if os.environ.get("CSV_LOCAL"): raws = [open(p, "rb").read() for p in os.environ["CSV_LOCAL"].split(",")]
else:
    for u in URLS:
        try: raws.append(baixar(u))
        except Exception as e: print("Falhou:", e)
if not raws: sys.exit("Não consegui baixar nenhum arquivo da ANP. Nada foi alterado.")
rows = []
for raw in raws:
    t = texto(raw); sep = ";" if t.split("\n", 1)[0].count(";") >= t.split("\n", 1)[0].count(",") else ","
    rd = csv.DictReader(io.StringIO(t), delimiter=sep)
    cols = {norm(h).replace(" ", "_"): h for h in (rd.fieldnames or [])}
    pick = {k: next((cols[a] for a in v if a in cols), None) for k, v in ALIAS.items()}
    print("Colunas:", list(cols)[:20])
    if not (pick["municipio"] and pick["produto"] and pick["valor"] and pick["data"]): print("Colunas essenciais não encontradas:", pick); continue
    for r in rd:
        g = lambda k: (r.get(pick[k]) or "").strip() if pick[k] else ""
        if g("municipio").upper() not in MUN: continue
        k, v, d = prod(g("produto")), num(g("valor")), data(g("data"))
        if k and v and v > 0 and d: rows.append((k, v, d, {x: g(x) for x in ALIAS}))
if not rows: sys.exit("Nenhuma linha para a região (veja as colunas acima). Nada foi alterado.")
fim = max(d for _, _, d, _ in rows); ini = fim - timedelta(days=13)
postos, ult = {}, {}
for k, v, d, gd in rows:
    if d < ini: continue
    c = gd["cnpj"] or gd["revenda"]
    p = postos.setdefault(c, {"nome": gd["revenda"], "bandeira": gd["bandeira"], "rua": gd["rua"], "num": gd["num"], "bairro": gd["bairro"], "mun": gd["municipio"]})
    if (c, k) not in ult or d > ult[(c, k)]: ult[(c, k)] = d; p[k] = round(v, 2); p["data"] = d.strftime("%d/%m/%Y")
med = {k: round(statistics.median([p[k] for p in postos.values() if k in p]), 2) for k in ("g", "e", "di") if any(k in p for p in postos.values())}
json.dump({"fonte": "ANP - Levantamento de Preços de Combustíveis", "semana": f"{ini:%d/%m} a {fim:%d/%m/%Y}", "regiao": MUN, "medias": med, "postos": list(postos.values())}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print(f"OK: {len(postos)} postos, medianas {med}, semana {ini:%d/%m} a {fim:%d/%m/%Y}")
