# 🛡️ Credit Sentinel — Early Warning System (EWS) de Crédito Privado

Sistema autônomo de monitoramento de eventos críticos de crédito privado (Fatos Relevantes, Recuperação Judicial, Quebra de Covenants/Waivers, Risco Sacado, Rebaixamentos de Rating e Estresse em FIDCs/Securitizadoras), pré-configurado com a Watchlist padronizada de **265 emissores e 21 setores**.

## 🚀 Como colocar no ar em 1 minuto

1. Suba os arquivos deste pacote para um repositório no seu GitHub (público ou privado).
2. No seu repositório do GitHub, vá em **Settings > Secrets and variables > Actions > New repository secret** e adicione:
   - `GEMINI_API_KEY`: Sua chave gratuita da API do Google Gemini (para o filtro analítico de severidade).
   - `TELEGRAM_BOT_TOKEN` *(Opcional)*: Token do seu bot no Telegram.
   - `TELEGRAM_CHAT_ID` *(Opcional)*: Seu ID de chat para receber alertas no celular.
3. Mesmo sem configurar o Telegram, o robô **abre automaticamente GitHub Issues** classificadas por severidade sempre que detectar um evento com nota >= 7 (e o GitHub envia e-mail automático para você).
