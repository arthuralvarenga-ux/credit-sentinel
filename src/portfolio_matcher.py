import pandas as pd
import re
import unicodedata
from typing import Dict, List, Set

STOP_TERMS = {
    "TESOURO", "CAIXA", "LFT", "PULVERIZADO", "BANCO", "FIDC", "ENERGIA", "S.A.", "LTDA"
}

def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    text = text.upper().strip()
    text = re.sub(r'\b(S\.?A\.?|S/A|LTDA\.?|PARTICIPACOES|HOLDING|COMPANHIA|CIA|FUNDO DE INVESTIMENTO EM DIREITOS CREDITORIOS|RESPONSABILIDADE LIMITADA)\b', ' ', text)
    text = re.sub(r'[^A-Z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def load_watchlist(csv_path: str = "data/watchlist_padronizada.csv") -> Dict[str, dict]:
    df = pd.read_csv(csv_path)
    watchlist = {}

    for _, row in df.iterrows():
        padrao = str(row["NOME_PADRAO"]).strip().upper()
        original = str(row["NOME_ORIGINAL"]).strip()
        setor = str(row["SETOR"]).strip().upper()

        if padrao in STOP_TERMS:
            continue

        if padrao not in watchlist:
            watchlist[padrao] = {
                "emissor_padrao": padrao,
                "setor": setor,
                "aliases": set(),
                "search_terms": set()
            }

        watchlist[padrao]["aliases"].add(original)

        for candidate in [padrao, original]:
            clean = normalize_text(candidate)
            if len(clean) >= 4 and clean not in STOP_TERMS:
                watchlist[padrao]["search_terms"].add(clean)

    return watchlist

def match_issuers_in_text(text: str, watchlist: Dict[str, dict]) -> List[dict]:
    norm_content = normalize_text(text)
    matches = []

    for padrao, info in watchlist.items():
        for term in info["search_terms"]:
            # Word boundary match to avoid partial false positives
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, norm_content):
                matches.append({
                    "emissor_padrao": padrao,
                    "setor": info["setor"],
                    "termo_detectado": term
                })
                break
    return matches
