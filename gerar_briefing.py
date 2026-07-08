"""
Daily News — Briefing de Mercado
Gerador Automático via GitHub Actions
Roda: Segunda, Quarta e Sexta às 05:00 (Brasília)
Arquitetura híbrida:
  - Sonnet 4.6: busca notícias autonomamente (sem queries fixas)
  - Haiku 4.5: formata e deduplica o JSON
"""

import os, json, re
from datetime import date, timedelta
from anthropic import Anthropic

client = Anthropic()

TEMAS = [
    ("cartoes",    "Cartões"),
    ("pagamentos", "Meios de Pagamento"),
    ("marketplace","Marketplace"),
    ("varejo",     "Varejo"),
    ("tag",        "Tag Veicular"),
    ("bancos",     "Bancos"),
    ("fintechs",   "Fintechs"),
    ("loyalty",    "Loyalty e Fidelização"),
    ("ia",         "Inteligência Artificial"),
    ("socios",     "Sócios e Parceiros"),
]

SOCIOS_PARCEIROS = "Carrefour, GPA, Pão de Açúcar, Azul, LATAM, JHSF, Google, Conectcar, Casas Bahia, Ponto Frio, Amazon, Nubank, Magazine Luiza"

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


SYSTEM_BUSCA = """Você é um analista de inteligência de mercado especializado em mercado financeiro e varejo brasileiro.
Sua tarefa é buscar as notícias mais relevantes e recentes sobre o tema solicitado.
Você decide autonomamente as melhores queries — não há queries fixas.
Busque ativamente e de forma inteligente, cobrindo diferentes ângulos do tema."""

def build_prompt(tema_id, tema_label, data_inicio, data_fim):
    temas_str = ", ".join([f'"{t[0]}" ({t[1]})' for t in TEMAS])
    hoje_str = date.today().strftime('%Y-%m-%d')
    after_str = (date.today()-timedelta(days=14)).strftime('%Y-%m-%d')
    socios_hint = f"\nParceiros monitorados: {SOCIOS_PARCEIROS}" if tema_id == 'socios' else ""

    return f"""Você é um analista de inteligência de mercado.

Tema: {tema_label}
Período: {data_inicio} a {data_fim}
Data de hoje: {hoje_str}{socios_hint}

SUA TAREFA:
1. Analise o contexto atual de "{tema_label}" no Brasil
2. Decida autonomamente as melhores queries para encontrar notícias relevantes desta semana
3. Execute PELO MENOS 5 buscas com queries variadas e específicas
4. Use filtro de data: after:{after_str}
5. Cubra diferentes ângulos: empresas, regulação, produtos, parcerias, tendências

COMO VARIAR SUAS BUSCAS:
- Busca ampla: tema + Brasil + mês atual
- Busca por empresa/produto específico relevante no momento
- Busca por evento atual (Prime Day, Copa, regulação recente)
- Busca por fonte especializada: site:infomoney.com.br OR site:finsidersbrasil.com.br OR site:letsmoney.com.br
- Busca por subtema específico que está em pauta esta semana

Retorne APENAS este JSON (sem markdown):
{{
  "noticias_encontradas": [
    {{
      "titulo": "Título exato da notícia",
      "url": "https://url-exata-encontrada",
      "fonte": "Nome do veículo",
      "data_pub": "DD/mmm/YYYY",
      "trecho": "Trecho relevante da notícia"
    }}
  ]
}}

Regras:
- SOMENTE notícias publicadas entre {data_inicio} e {data_fim} — verifique cada data
- Mínimo 4, máximo 12 notícias encontradas
- URLs EXATAS da busca — não invente
- APENAS JSON, zero texto fora"""


SYSTEM_HAIKU = """Você é um analista sênior de mercado financeiro e varejo brasileiro.
Receberá notícias já pesquisadas e deve classificá-las e formatá-las.
Retorne APENAS um JSON válido, sem markdown."""

def haiku_formata(tema_id, tema_label, data_inicio, data_fim, noticias_raw):
    temas_str = ", ".join([f'"{t[0]}" ({t[1]})' for t in TEMAS])

    noticias_txt = "\n".join([
        f"{i+1}. TÍTULO: {n.get('titulo','')}\n   URL: {n.get('url','')}\n   FONTE: {n.get('fonte','')}\n   DATA: {n.get('data_pub','')}\n   TRECHO: {n.get('trecho','')}"
        for i, n in enumerate(noticias_raw)
    ])

    prompt = f"""Classifique e formate estas notícias sobre "{tema_label}" (período: {data_inicio} a {data_fim}):

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
- DEDUPLICAÇÃO: quando múltiplas notícias cobrem o MESMO evento, mantenha APENAS a de fonte mais confiável (Valor, Folha, Globo, InfoMoney, Finsiders, Let's Money, TIInside, Money Times, BC)
- Após deduplicar: mínimo 3, máximo 6 notícias únicas
- Use a URL EXATAMENTE como fornecida — não modifique
- categoria: Regulatório | Mercado | Tecnologia | Competição | Tendência
- impacto: alto | médio | baixo
- termometro: positivo | neutro | negativo
- tambem_em: IDs de outros temas. Disponíveis: {temas_str}
- APENAS JSON, zero texto fora"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        system=SYSTEM_HAIKU,
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


def buscar_transversal(data_inicio, data_fim):
    """Busca notícias de parcerias e integrações entre empresas de diferentes temas."""
    temas_str = ", ".join([f'"{t[0]}" ({t[1]})' for t in TEMAS])
    hoje_str = date.today().strftime('%Y-%m-%d')
    after_str = (date.today()-timedelta(days=14)).strftime('%Y-%m-%d')

    prompt = f"""Você é um analista de inteligência de mercado brasileiro.

TAREFA ESPECÍFICA: Busque notícias de PARCERIAS, INTEGRAÇÕES e MOVIMENTOS ESTRATÉGICOS entre empresas de diferentes setores publicadas entre {data_inicio} e {data_fim}.

Foque em combinações como:
- Fintech + Marketplace (ex: Nubank+Amazon, PicPay+Shopee, Mercado Pago+varejo)
- Banco + E-commerce (ex: Itaú+Magazine Luiza, Bradesco+Amazon)
- Pagamento + Varejo (ex: Pix+supermercados, NuPay+lojas)
- Tag + Mobilidade (ex: Conectcar+estacionamentos, tag+pedágio+novas concessões)
- Loyalty + Parceiros (ex: milhas+cartão+varejo, cashback+marketplace)
- IA + Qualquer setor financeiro/varejo

Execute pelo menos 5 buscas específicas:
1. "parceria pagamento marketplace Brasil after:{after_str}"
2. "integração fintech varejo e-commerce Brasil after:{after_str}"
3. "NuPay Pix Prime Day checkout Brasil after:{after_str}"
4. "banco digital supermercado parceria cashback Brasil after:{after_str}"
5. Outras que julgar relevantes baseado no que está acontecendo esta semana

Retorne APENAS este JSON:
{{
  "noticias_encontradas": [
    {{
      "titulo": "Título da notícia",
      "url": "https://url-exata",
      "fonte": "Veículo",
      "data_pub": "DD/mmm/YYYY",
      "trecho": "Trecho relevante",
      "tema_principal": "ID do tema principal ({temas_str})",
      "tambem_em": ["id_tema1", "id_tema2"]
    }}
  ]
}}

Regras:
- SOMENTE notícias de {data_inicio} a {data_fim}
- Foque em notícias que CONECTAM dois ou mais setores
- Mínimo 3, máximo 8 notícias transversais
- APENAS JSON"""

    messages = [{{"role": "user", "content": prompt}}]

    for _ in range(15):
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            system=SYSTEM_BUSCA,
            tools=[{{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}}],
            messages=messages,
        )
        messages.append({{"role": "assistant", "content": resp.content}})
        if resp.stop_reason == "end_turn":
            break
        if resp.stop_reason == "tool_use":
            tool_results = [
                {{"type": "tool_result", "tool_use_id": b.id, "content": "ok"}}
                for b in resp.content if b.type == "tool_use"
            ]
            if tool_results:
                messages.append({{"role": "user", "content": tool_results}})

    text = "".join(b.text for b in resp.content if b.type == "text").strip()

    try:
        parsed = json.loads(text)
        noticias = parsed.get("noticias_encontradas", [])
    except Exception:
        m = re.search(r"\{{[\s\S]*\}}", text)
        if m:
            try:
                parsed = json.loads(m.group(0))
                noticias = parsed.get("noticias_encontradas", [])
            except:
                noticias = []
        else:
            noticias = []

    # Sanitiza tambem_em
    for n in noticias:
        n["tambem_em"] = [t for t in n.get("tambem_em", []) if t in TODOS_IDS]
        if n.get("tema_principal") not in TODOS_IDS:
            n["tema_principal"] = n["tambem_em"][0] if n["tambem_em"] else "marketplace"
        # Adiciona campos padrão
        n.setdefault("categoria", "Mercado")
        n.setdefault("impacto", "alto")
        n.setdefault("destaque", n.get("trecho", "")[:200])

    return noticias


def buscar_tema(tema_id, tema_label, data_inicio, data_fim):
    print(f"  [{tema_id}] {tema_label} — buscando autonomamente...", end=" ", flush=True)

    prompt = build_prompt(tema_id, tema_label, data_inicio, data_fim)
    messages = [{"role": "user", "content": prompt}]

    for _ in range(15):
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=SYSTEM_BUSCA,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "end_turn":
            break
        if resp.stop_reason == "tool_use":
            tool_results = [
                {"type": "tool_result", "tool_use_id": b.id, "content": "ok"}
                for b in resp.content if b.type == "tool_use"
            ]
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

    text = "".join(b.text for b in resp.content if b.type == "text").strip()

    try:
        parsed = json.loads(text)
        noticias_raw = parsed.get("noticias_encontradas", [])
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                parsed = json.loads(m.group(0))
                noticias_raw = parsed.get("noticias_encontradas", [])
            except:
                noticias_raw = []
        else:
            noticias_raw = []

    print(f"Sonnet: {len(noticias_raw)} notícias...", end=" ", flush=True)

    if not noticias_raw:
        print("SEM RESULTADOS")
        return {"resumo": "Sem dados disponíveis", "termometro": "neutro", "noticias": []}

    parsed = haiku_formata(tema_id, tema_label, data_inicio, data_fim, noticias_raw)
    print(f"OK ({len(parsed.get('noticias', []))} notícias únicas)")

    return parsed


def main():
    hoje         = date.today()
    quatorze_dias = hoje - timedelta(days=14)

    data_inicio_str = fmt_date(quatorze_dias)
    data_fim_str    = fmt_date(hoje)  # inclui hoje
    data_edicao = (f"{DIAS_PT.get(hoje.strftime('%A'), hoje.strftime('%A'))}, "
                   f"{hoje.day} de {MESES_PT.get(hoje.strftime('%B'), hoje.strftime('%B'))} de {hoje.year}")

    print(f"\n{'='*60}")
    print(f"Daily News — {data_edicao}")
    print(f"Período: {data_inicio_str} a {data_fim_str}")
    print(f"Busca: Sonnet 4.6 autônomo | Formatação: Haiku 4.5")
    print(f"{'='*60}")

    temas_data = {}

    # Etapa 1: Busca por tema
    for tid, tlabel in TEMAS:
        temas_data[tid] = buscar_tema(tid, tlabel, data_inicio_str, data_fim_str)

    # Etapa 2: Busca transversal — parcerias e integrações entre empresas
    print(f"\n  [transversal] Buscando parcerias e notícias entre temas...", end=" ", flush=True)
    noticias_transversais = buscar_transversal(data_inicio_str, data_fim_str)
    print(f"{len(noticias_transversais)} notícias transversais encontradas")

    # Distribui notícias transversais nos temas corretos
    for noticia in noticias_transversais:
        temas_alvo = noticia.get("tambem_em", []) + [noticia.get("tema_principal", "")]
        for tid in temas_alvo:
            if tid in temas_data and "noticias" in temas_data[tid]:
                # Verifica se já não existe notícia similar
                titulos = [n.get("titulo","").lower() for n in temas_data[tid]["noticias"]]
                titulo_novo = noticia.get("titulo","").lower()
                # Adiciona se não for duplicata (verifica primeiras 30 chars)
                if not any(titulo_novo[:30] in t for t in titulos):
                    temas_data[tid]["noticias"].append(noticia)

    janela_ini = fmt_date(hoje - timedelta(days=14))
    data = {
        "data_edicao":     data_edicao,
        "data_geracao":    f"{hoje.strftime('%d/%m/%Y')} · 05:00",
        "janela":          f"{janela_ini}–{data_fim_str}",
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
