"""
Daily News — Briefing de Mercado
Gerador Automático via GitHub Actions
Roda: Segunda, Quarta e Sexta às 05:00 (Brasília)
Arquitetura:
  - Serper API: busca gratuita no Google (sem custo)
  - Haiku 4.5: classifica e formata (custo ~$2/mês)
"""

import os, json, re, urllib.request, urllib.parse
from datetime import date, timedelta
from anthropic import Anthropic

client = Anthropic()

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")

TEMAS = [
    ("cartoes",    "Cartões",                ["cartões crédito débito Brasil 2026", "adquirência maquininha pagamento Brasil", "rotativo parcelado fatura cartão banco"]),
    ("pagamentos", "Meios de Pagamento",     ["Pix Open Finance pagamentos Brasil 2026", "stablecoin pagamento instantâneo Brasil", "meios pagamento regulação Banco Central"]),
    ("marketplace","Marketplace",            ["marketplace e-commerce Amazon Mercado Livre Brasil 2026", "Shopee TikTok Shop varejo digital Brasil", "e-commerce Brasil crescimento vendas julho 2026"]),
    ("varejo",     "Varejo",                 ["varejo brasileiro crescimento vendas 2026", "supermercado franquias consumo Brasil", "varejo digital físico omnichannel Brasil"]),
    ("tag",        "Tag Veicular",           ["tag veicular pedágio Free Flow Brasil 2026", "ANTT concessão rodovia pedágio eletrônico", "mobilidade frota gestão tag veicular"]),
    ("bancos",     "Bancos",                 ["bancos brasileiros crédito resultado 2026", "inadimplência financeira Brasil 2026", "Itaú Bradesco Santander Nubank resultado"]),
    ("fintechs",   "Fintechs",              ["fintechs brasileiras 2026 investimento produto", "fintech crédito digital pagamento Brasil", "Nubank Inter C6 PicPay novidades 2026"]),
    ("loyalty",    "Loyalty e Fidelização",  ["programa fidelidade pontos milhas cashback Brasil 2026", "transferência bônus milhas aéreas cartão", "loyalty parceria varejo banco Brasil"]),
    ("ia",         "Inteligência Artificial",["inteligência artificial banco fintech varejo Brasil 2026", "IA fraude pagamento automação financeiro", "ChatGPT IA generativa mercado Brasil"]),
    ("socios",     "Sócios e Parceiros",     ["Carrefour Brasil supermercado varejo 2026", "Azul LATAM companhia aérea parceria 2026", "Amazon Brasil Prime marketplace 2026", "Nubank Magazine Luiza Casas Bahia novidades 2026", "Conectcar JHSF Google Brasil parceria"]),
    ("classificados", "Classificados Automotivos", ["Webmotors Kavak Instacarro iCarros compra venda carros 2026", "OLX autos classificados veículos online Brasil", "marketplace automotivo usado seminovo Brasil 2026"]),
    ("veiculos",   "Veículos",                ["financiamento veicular crédito auto Brasil 2026", "emplacamentos vendas montadoras Fenabrave Brasil", "consórcio seguro automóvel mercado Brasil 2026"]),
]

TODOS_IDS = [t[0] for t in TEMAS]

MESES_ABR = {1:"jan",2:"fev",3:"mar",4:"abr",5:"mai",6:"jun",
             7:"jul",8:"ago",9:"set",10:"out",11:"nov",12:"dez"}
MESES_PT  = {"January":"janeiro","February":"fevereiro","March":"março",
             "April":"abril","May":"maio","June":"junho","July":"julho",
             "August":"agosto","September":"setembro","October":"outubro",
             "November":"novembro","December":"dezembro"}
DIAS_PT   = {"Monday":"Segunda-feira","Tuesday":"Terça-feira","Wednesday":"Quarta-feira",
             "Thursday":"Quinta-feira","Friday":"Sexta-feira","Saturday":"Sábado","Sunday":"Domingo"}

def fmt_date(d):
    return f"{d.day}/{MESES_ABR[d.month]}/{d.year}"


def serper_search(query, num=10):
    """Busca no Google via Serper API."""
    if not SERPER_API_KEY:
        print("    ⚠ SERPER_API_KEY não configurada")
        return []

    data = json.dumps({
        "q": query,
        "num": num,
        "hl": "pt-br",
        "gl": "br",
        "tbs": f"qdr:m"  # últimos 30 dias
    }).encode()

    req = urllib.request.Request(
        "https://google.serper.dev/news",
        data=data,
        headers={
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            result = json.loads(raw)

        news_items = result.get("news", [])
        print(f"    [Serper] query='{query[:40]}' → {len(news_items)} resultados")

        noticias = []
        for item in news_items:
            noticias.append({
                "titulo": item.get("title", ""),
                "url":    item.get("link", ""),
                "fonte":  item.get("source", ""),
                "trecho": item.get("snippet", ""),
                "data_pub": item.get("date", ""),
            })
        return noticias

    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"    ⚠ Serper HTTP {e.code}: {body}")
        return []
    except Exception as e:
        print(f"    ⚠ Erro Serper: {e}")
        return []


def haiku_formata(tema_id, tema_label, data_inicio, data_fim, noticias_raw):
    """Haiku classifica e formata as notícias encontradas."""
    if not noticias_raw:
        return {"resumo": "Sem dados disponíveis", "termometro": "neutro", "noticias": []}

    temas_str = ", ".join([f'"{t[0]}" ({t[1]})' for t in TEMAS])

    noticias_txt = "\n".join([
        f"{i+1}. TÍTULO: {n.get('titulo','')}\n   URL: {n.get('url','')}\n   FONTE: {n.get('fonte','')}\n   DATA: {n.get('data_pub','')}\n   TRECHO: {n.get('trecho','')}"
        for i, n in enumerate(noticias_raw[:20])
    ])

    prompt = f"""Analise estas notícias sobre "{tema_label}" no Brasil (período: {data_inicio} a {data_fim}):

{noticias_txt}

Retorne APENAS este JSON (sem markdown):
{{
  "resumo": "2 frases sobre o cenário do período",
  "termometro": "positivo",
  "noticias": [
    {{
      "titulo": "Título da notícia",
      "fonte": "Nome do veículo",
      "url": "URL exata — não modifique",
      "destaque": "Dado ou frase mais relevante extraído do trecho",
      "categoria": "Mercado",
      "impacto": "alto",
      "data_pub": "DD/mmm/YYYY",
      "tambem_em": []
    }}
  ]
}}

Regras:
- Selecione as notícias MAIS RELEVANTES e RECENTES
- DEDUPLICAÇÃO: quando múltiplas fontes cobrem o MESMO evento, mantenha APENAS a de fonte mais confiável (Valor, Folha, Globo, InfoMoney, Finsiders, Let's Money, TIInside, Money Times, BC)
- Mínimo 3, máximo 6 notícias únicas
- Use a URL EXATAMENTE como fornecida
- data_pub no formato DD/mmm/YYYY (ex: 18/jul/2026)
- categoria: Regulatório | Mercado | Tecnologia | Competição | Tendência
- impacto: alto | médio | baixo
- termometro: positivo | neutro | negativo
- tambem_em: IDs de outros temas relacionados. Disponíveis: {temas_str}
- APENAS JSON, zero texto fora"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = "".join(b.text for b in resp.content if b.type == "text").strip()

    try:
        parsed = json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {"resumo": "Sem dados", "termometro": "neutro", "noticias": []}
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            return {"resumo": "Erro ao processar", "termometro": "neutro", "noticias": []}

    for n in parsed.get("noticias", []):
        n["tambem_em"] = [t for t in n.get("tambem_em", []) if t in TODOS_IDS and t != tema_id]

    return parsed


def buscar_tema(tema_id, tema_label, queries, data_inicio, data_fim):
    print(f"  [{tema_id}] {tema_label}...", end=" ", flush=True)

    # Busca com todas as queries do tema
    todos_resultados = []
    seen_urls = set()

    for query in queries:
        resultados = serper_search(query, num=8)
        for r in resultados:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                todos_resultados.append(r)

    print(f"{len(todos_resultados)} resultados...", end=" ", flush=True)

    # Haiku formata e deduplica
    parsed = haiku_formata(tema_id, tema_label, data_inicio, data_fim, todos_resultados)
    print(f"OK ({len(parsed.get('noticias', []))} notícias)")

    return parsed


def main():
    hoje          = date.today()
    quatorze_dias = hoje - timedelta(days=14)

    data_inicio_str = fmt_date(quatorze_dias)
    data_fim_str    = fmt_date(hoje)
    data_edicao = (f"{DIAS_PT.get(hoje.strftime('%A'), hoje.strftime('%A'))}, "
                   f"{hoje.day} de {MESES_PT.get(hoje.strftime('%B'), hoje.strftime('%B'))} de {hoje.year}")

    if not SERPER_API_KEY:
        print("❌ SERPER_API_KEY não configurada! Abortando.")
        return

    print(f"\n{'='*60}")
    print(f"Daily News — {data_edicao}")
    print(f"Período: {data_inicio_str} a {data_fim_str}")
    print(f"Busca: Serper (gratuito) | Formatação: Haiku 4.5")
    print(f"{'='*60}")

    temas_data = {}
    for tid, tlabel, queries in TEMAS:
        temas_data[tid] = buscar_tema(tid, tlabel, queries, data_inicio_str, data_fim_str)

    data = {
        "data_edicao":     data_edicao,
        "data_geracao":    f"{hoje.strftime('%d/%m/%Y')} · 05:00",
        "janela":          f"{data_inicio_str}–{data_fim_str}",
        "periodo_recente": f"{data_inicio_str} a {data_fim_str}",
        "temas":           temas_data,
    }

    os.makedirs("dados", exist_ok=True)
    fname = f"{hoje.strftime('%Y-%m-%d')}.json"
    fpath = os.path.join("dados", fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON salvo: {fpath}")

    idx_path = os.path.join("dados", "index.json")
    try:
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
    except Exception:
        idx = {"edicoes": []}

    idx["edicoes"] = [e for e in idx["edicoes"] if e.get("arquivo") != fname]
    mes_pt = MESES_PT.get(hoje.strftime("%B"), hoje.strftime("%B"))
    label  = f"{DIAS_PT.get(hoje.strftime('%A'), hoje.strftime('%A'))}, {hoje.day} de {mes_pt} de {hoje.year}"
    idx["edicoes"].insert(0, {"label": label, "arquivo": fname})
    idx["edicoes"] = idx["edicoes"][:30]

    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print(f"✅ index.json atualizado ({len(idx['edicoes'])} edições)")
    print(f"\n🎉 Daily News pronto!")


if __name__ == "__main__":
    main()
