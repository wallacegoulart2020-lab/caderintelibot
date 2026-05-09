import logging
import re
import os
from datetime import datetime, timezone, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN não definido nas variáveis de ambiente!")

BR = timezone(timedelta(hours=-3))

LINE_CONFIG = {
    "512": {"emoji": "🟢", "label": "Linha 512", "local": "Enchedora"},
    "513": {"emoji": "🟡", "label": "Linha 513", "local": "Enchedora"},
    "514": {"emoji": "🔴", "label": "Linha 514", "local": "Enchedora"},
    "galpao": {"emoji": "🔵", "label": "Galpão", "local": "Galpão"},
}

KEYWORDS = {
    "512": ["512", "l512", "linha 512"],
    "513": ["513", "l513", "linha 513"],
    "514": ["514", "l514", "linha 514"],
    "galpao": ["galpão", "galpao", "galp"],
}

HASHTAG_MAP = {
    r"\bmal.?cheia\b": "#MalCheia",
    r"\bcrash\b": "#Crash",
    r"\bquebra\b": "#Quebra",
    r"\bipl\b": "#IPL",
    r"\bipe\b": "#IPE",
    r"\btpo\b": "#TPO",
    r"\bco2\b": "#CO2",
    r"\bepc\b": "#EPC",
    r"\bpaletizadora\b": "#Paletizadora",
    r"\benchedora\b": "#Enchedora",
    r"\bseamer\b": "#Seamer",
    r"\bvalvula\b": "#Valvula",
    r"\btucho\b": "#Tucho",
    r"\bacionamento\b": "#Acionamento",
    r"\bparada\b": "#Parada",
    r"\bpreventiv\w+\b": "#Preventiva",
    r"\bcorretiv\w+\b": "#Corretiva",
    r"\bregulagem\b": "#Regulagem",
    r"\bsensor\b": "#Sensor",
    r"\bjumper\b": "#Jumper",
    r"\bbatimento\b": "#Batimento",
    r"\blote\b": "#Lote",
    r"\bskol\b": "#Skol",
    r"\bbrahma\b": "#Brahma",
}

KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🟢 L512"), KeyboardButton("🟡 L513")],
        [KeyboardButton("🔴 L514"), KeyboardButton("🔵 Galpão")],
    ],
    resize_keyboard=True,
)

def agora_br():
    return datetime.now(BR)

def detectar_linha(texto):
    tl = texto.lower()
    for linha, palavras in KEYWORDS.items():
        if any(p in tl for p in palavras):
            return linha
    return "galpao"

def detectar_tipo(texto):
    tl = texto.lower()
    if any(k in tl for k in ["preventiv", "rotina"]):
        return "Preventiva"
    if any(k in tl for k in ["corretiv", "troca", "ajuste"]):
        return "Corretiva"
    return "Operacional"

def gerar_hashtags(texto, linha):
    tags = set()
    tag_linha = f"#L{linha}" if linha != "galpao" else "#Galpao"
    tags.add(tag_linha)
    tl = texto.lower()
    for padrao, tag in HASHTAG_MAP.items():
        if re.search(padrao, tl):
            tags.add(tag)
    for v in re.findall(r'\bv(\d{1,3})\b', tl):
        tags.add(f"#V{v}")
    return " ".join(sorted(tags))

def formatar(texto, linha):
    cfg = LINE_CONFIG[linha]
    tipo = detectar_tipo(texto)
    now = agora_br()
    hoje = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M")
    data_curta = now.strftime("%d/%m")
    tags = gerar_hashtags(texto, linha)
    label = f"L{linha}" if linha != "galpao" else "Galpão"
    corpo = re.sub(r'\b(V\d{1,3})\b', r'*\1*', texto, flags=re.IGNORECASE)

    return (
        f"{cfg['emoji']} *{tipo} — {label} ({data_curta})*\n"
        f"📅 {hoje} às {hora} | 📍 {cfg['local']}\n"
        f"{'─' * 28}\n\n"
        f"{corpo}\n\n"
        f"{'─' * 28}\n"
        f"🏷️ {tags}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *CaderInteliBot ativo!*\n\n"
        "Manda a anotação bruta aqui.\n"
        "Mencione *512*, *513* ou *514* que identifico a linha automaticamente.\n\n"
        "Ou usa os botões abaixo para fixar a linha.",
        parse_mode="Markdown",
        reply_markup=KEYBOARD,
    )

async def selecionar_linha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mapa = {"🟢 L512": "512", "🟡 L513": "513", "🔴 L514": "514", "🔵 Galpão": "galpao"}
    linha = mapa.get(update.message.text)
    if linha:
        context.user_data["linha_ativa"] = linha
        cfg = LINE_CONFIG[linha]
        label = f"L{linha}" if linha != "galpao" else "Galpão"
        await update.message.reply_text(
            f"{cfg['emoji']} *{label} ativa!* Agora escreva sua anotação:",
            parse_mode="Markdown",
        )

async def receber_anotacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    msg_id = update.message.message_id
    chat_id = update.effective_chat.id

    if len(texto) < 5:
        await update.message.reply_text("✏️ Anotação muito curta. Escreva mais detalhes.")
        return

    linha_forcada = context.user_data.pop("linha_ativa", None)
    linha = linha_forcada or detectar_linha(texto)

    try:
        nota = formatar(texto, linha)
        cfg = LINE_CONFIG[linha]
        label = f"L{linha}" if linha != "galpao" else "Galpão"

        # Apaga a mensagem original do usuário
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass  # Se não conseguir apagar, continua normalmente

        # Envia a versão formatada
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ {cfg['emoji']} *Salvo — {label}*\n\n{nota}",
            parse_mode="Markdown",
            reply_markup=KEYBOARD,
        )
        logger.info("Salvo | %s | %s", label, update.effective_user.first_name)

    except Exception as e:
        logger.error("Erro: %s", e)
        await update.message.reply_text(f"✅ Anotação salva!\n\n{texto}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^(🟢 L512|🟡 L513|🔴 L514|🔵 Galpão)$"),
        selecionar_linha
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receber_anotacao))
    logger.info("🤖 CaderInteliBot iniciado")
    app.run_polling()

if __name__ == '__main__':
    main()
