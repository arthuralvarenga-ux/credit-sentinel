import os
import json
import datetime
import urllib.parse
import requests
import feedparser
import pandas as pd
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from portfolio_matcher import load_watchlist, match_issuers_in_text

# Palavras-chave de estresse agudo de crédito privado (Caso Americanas, Light, RJ, Waivers)
CREDIT_STRESS_KEYWORDS = [
    "recuperação judicial", "tutela cautelar", "inconsistência contábil",
    "risco sacado", "forfait", "reestruturação de dívida", "waiver",
    "assembleia de debenturistas", "agd", "quebra de covenant", "cross-default",
    "rebaixamento de rating", "downgrade", "atraso de pagamento", "default",
    "inadimplência", "bloqueio judicial", "execução de dívida", "renúncia auditor",
    "renúncia cfo", "alavancagem", "abertura de spread", "subordinação fidc", "pdd"
]

RSS_FEEDS = [
    # Google News RSS focado em Crédito Privado, Debêntures, FIDC e Recuperação Judicial no Brasil
    "https://news.google.com/rss/search?q=%22deb%C3%AAntures%22+OR+%22recupera%C3%A7%C3%A3o+judicial%22+OR+%22cr%C3%A9dito+privado%22+OR+%22FIDC%22+OR+%22fatos+relevantes%22+OR+%22rebaixamento+rating%22&hl=pt-BR&gl=BR&ceid=BR:pt-419",
    "https://news.google.com/rss/search?q=%22risco+sacado%22+OR+%22waiver%22+OR+%22covenants%22+OR+%22reestrutura%C3%A7%C3%A3o+de+d%C3%ADvida%22+OR+%22default%22&hl=pt-BR&gl=BR&ceid=BR:pt-419",
    "https://www.infomoney.com.br/feed/",
    "https://braziljournal.com/feed/"
]

class CreditEventAssessment(BaseModel):
    relevante_para_credito: bool = Field(description="True se o evento representa risco ou informação material de crédito privado.")
    emissor_identificado: str = Field(description="Nome do emissor ou grupo econômico afetado.")
    setor: str = Field(description="Setor do emissor.")
    severidade_score: int = Field(description="Nota de 1 a 10 para o risco de abertura de spread ou default (10 = RJ/Fraude/Default).")
    categoria_evento: str = Field(description="Ex: Recuperação Judicial, Quebra de Covenant / Waiver, Inconsistência Contábil, Downgrade de Rating, Deterioração de Liquidez, Desenquadramento FIDC.")
    impacto_spreads: str = Field(description="Baixo, Moderado, Alto ou Crítico")
    ativos_potencialmente_afetados: str = Field(description="Ex: Debêntures, CRI, CRA, Cotas de FIDC, Letras Financeiras")
    resumo_executivo: str = Field(description="Resumo direto de até 3 linhas explicando o evento e o impacto para a carteira.")

def load_state(state_path: str = "data/processed_events.json") -> dict:
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_urls": [], "last_run": None}

def save_state(state: dict, state_path: str = "data/processed_events.json"):
    state["last_run"] = datetime.datetime.utcnow().isoformat()
    state["processed_urls"] = state["processed_urls"][-2000:]
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def evaluate_with_gemini(title: str, summary: str, matched_issuers: list) -> CreditEventAssessment:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Fallback heurístico caso a chave da API ainda não esteja configurada
        return CreditEventAssessment(
            relevante_para_credito=True,
            emissor_identificado=matched_issuers[0]["emissor_padrao"] if matched_issuers else "MERCADO DE CRÉDITO",
            setor=matched_issuers[0]["setor"] if matched_issuers else "GERAL",
            severidade_score=8,
            categoria_evento="Alerta por Palavra-Chave / Watchlist",
            impacto_spreads="Alto",
            ativos_potencialmente_afetados="Debêntures / FIDC / Estruturados",
            resumo_executivo=f"Notícia capturada na varredura: {title}"
        )

    client = genai.Client(api_key=api_key)
    issuers_str = ", ".join([f"{m['emissor_padrao']} ({m['setor']})" for m in matched_issuers]) if matched_issuers else "Nenhum emissor direto da watchlist, avaliar impacto sistêmico"

    prompt = f"""
    Você é um Analista Sênior de Risco de Crédito Privado Institucional (Foco em Fundos de Pensão, Debêntures, FIDCs, CRIs/CRAs e Bancos).
    Avalie a notícia/fato relevante abaixo e determine se há risco de crédito, abertura de spreads, fraude contábil (estilo Americanas),
    pedido de Recuperação Judicial, pedido de waiver, rebaixamento de rating ou deterioração de FIDC/Securitizadora.

    Emissores da nossa Watchlist detectados no texto: {issuers_str}
    Título: {title}
    Resumo: {summary}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CreditEventAssessment,
            temperature=0.1,
        ),
    )
    return CreditEventAssessment.model_validate_json(response.text)

def send_notifications(assessment: CreditEventAssessment, link: str, in_watchlist: bool):
    tag_carteira = "🚨 [NA WATCHLIST DA CARTEIRA]" if in_watchlist else "⚠️ [RADAR DE MERCADO]"
    msg = (
        f"{tag_carteira}\n"
        f"*Emissor:* {assessment.emissor_identificado} ({assessment.setor})\n"
        f"*Severidade:* {assessment.severidade_score}/10 | *Impacto Spreads:* {assessment.impacto_spreads}\n"
        f"*Evento:* {assessment.categoria_evento}\n"
        f"*Ativos:* {assessment.ativos_potencialmente_afetados}\n"
        f"*Análise:* {assessment.resumo_executivo}\n"
        f"🔗 [Ler Fonte Original]({link})"
    )

    # 1. Disparo via Telegram (se configurado nos Secrets)
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        )

    # 2. Abertura automática de Issue no próprio GitHub (Funciona nativamente sem chaves externas!)
    gh_token = os.environ.get("GITHUB_TOKEN")
    gh_repo = os.environ.get("GITHUB_REPOSITORY")
    if gh_token and gh_repo and assessment.severidade_score >= 7:
        issue_title = f"[{assessment.impacto_spreads.upper()}] {assessment.emissor_identificado} - {assessment.categoria_evento}"
        requests.post(
            f"https://api.github.com/repos/{gh_repo}/issues",
            headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
            json={
                "title": issue_title,
                "body": msg,
                "labels": ["risco-credito", assessment.setor.lower()]
            }
        )

def main():
    watchlist = load_watchlist()
    state = load_state()
    new_alerts = []

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:30]:
            link = entry.get("link", "")
            if not link or link in state["processed_urls"]:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "")
            full_text = f"{title} {summary}"
            full_text_lower = full_text.lower()

            matched_issuers = match_issuers_in_text(full_text, watchlist)
            has_stress_keyword = any(kw in full_text_lower for kw in CREDIT_STRESS_KEYWORDS)

            # Aciona análise se bater em emissor da carteira + termo sensível, ou se for evento agudo de crédito no mercado
            if (matched_issuers and has_stress_keyword) or ("recuperação judicial" in full_text_lower or "inconsistência contábil" in full_text_lower or "risco sacado" in full_text_lower):
                assessment = evaluate_with_gemini(title, summary, matched_issuers)
                if assessment.relevante_para_credito and assessment.severidade_score >= 6:
                    send_notifications(assessment, link, in_watchlist=bool(matched_issuers))
                    new_alerts.append({
                        "data_hora": datetime.datetime.utcnow().isoformat(),
                        "emissor": assessment.emissor_identificado,
                        "setor": assessment.setor,
                        "severidade": assessment.severidade_score,
                        "categoria": assessment.categoria_evento,
                        "impacto_spreads": assessment.impacto_spreads,
                        "na_watchlist": bool(matched_issuers),
                        "resumo": assessment.resumo_executivo,
                        "link": link
                    })

            state["processed_urls"].append(link)

    if new_alerts:
        history_path = "data/alerts_history.csv"
        df_new = pd.DataFrame(new_alerts)
        if os.path.exists(history_path):
            df_old = pd.read_csv(history_path)
            df_new = pd.concat([df_old, df_new], ignore_index=True)
        df_new.to_csv(history_path, index=False, encoding="utf-8-sig")

    save_state(state)

if __name__ == "__main__":
    main()
