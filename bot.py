import logging
import re
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── TOKEN via variável de ambiente (seguro) ────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN não definido nas variáveis de ambiente!")

# ── CONFIG DE LINHAS ───────────────────────────────────────────────────────────
LINE_CONFIG = {
    "512": {"emoji": "🟢", "label": "Linha 512", "local": "Enchedora"},
    "513": {"emoji": "🟡", "label": "Linha 513", "local": "Enchedora"},
    "514": {"emoji": "🔴", "label": "Linha 514", "local": "Enchedora"},
    "galpao": {"emoji": "🔵", "label": "Galpão", "local": "Galpão"},
}

KEYWORDS = {
    "512": ["512", "l512", "linha 512", "enchedora 512"],
    "513": ["513", "l513", "linha 513", "enchedora 513"],
    "514": ["514", "l514", "linha 514", "enchedora 514"],
    "galpao": ["galpão", "galpao", "galp"],
}

HASHTAG_MAP = {
    r"\bmal.?cheia\b":       "#MalCheia",
    r"\bcrash\b":            "#Crash",
    r"\bquebra\b":           "#Quebra",
    r"\bipl\b":              "#IPL",
    r"\bipe\b":              "#IPE",
    r"\btpo\b":              "#TPO",
    r"\bco2\b":              "#CO2",
    r"\bepc\b":              "#EPC",
    r"\bpaletizadora\b":     "#Paletizadora",
    r"\benchedora\b":        "#Enchedora",
    r"\bseamer\b":           "#Seamer",
    r"\bv[aá]lvula\b":       "#Valvula",
    r"\btucho\b":            "#Tucho",
    r"\bacionamento\b":      "#Acionamento",
    r"\bparafuso\b":         "#Parafuso",
    r"\bmosca\b":            "#Mosca",
    r"\bparada\b":           "#Parada",
    r"\bpreventiv\w+\b":     "#Preventiva",
    r"\bcorretiv\w+\b":      "#Corretiva",
    r"\bregulagem\b":        "#Regulagem",
    r"\bpress[aã]o\b":       "#Pressao",
    r"\bsensor\b":           "#Sensor",
    r"\bjumper\b":           "#Jumper",
    r"\blogist\w+\b":        "#Logistica",
    r"\bbatimento\b":        "#Batimento",
    r"\blote\b":             "#Lote",
    r"\bskol\b":             "#Skol",
    r"\bbrahma\b":           "#Brahma",
    r"\bantarctica\b":       "#Antarctica",
    r"\bbeats\b":            "#Beats",
    r"\bspaten\b":           "#Spaten",
}

# ── TECLADO ────────────────────────────────────────────────────────────────────
KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🟢 L512"), KeyboardButton("🟡 L513")],
        [KeyboardButton("🔴 L514"), KeyboardButton("🔵 Galpão")],
    ],
    resize_keyboard=True,
    persistent=True,
)

# ── FUNÇÕES AUXILIARES ─────────────────────────────────────────────────────────
def detectar_linha(texto: str) -> str:
    tl = texto.lower()
    for linha, palavras in KEYWORDS.items():
        if any(p in tl for p in palavras):
            return linha
    return "galpao"  # default seguro

def detectar_tipo(texto: str) -> str:
    tl = texto.lower()
    if any(k in tl for k in ["preventiv", "rotina", "periódic", "periodic"]):
        return "Preventiva"
    if any(k in tl for k in ["corretiv", "troca", "ajuste", "regulagem"]):
        return "Corretiva"
    if any(k in tl for k in ["diagnóst", "diagnost", "análise", "analise", "avaliação"]):
        return "Diagnóstico"
    return "Operacional"

def gerar_hashtags(texto: str, linha: str) -> str:
    tags = set()
    tag_linha = f"#L{linha}" if linha != "galpao" else "#Galpao"
    tags.add(tag_linha)
    tl = texto.lower()
    for padrao, tag in HASHTAG_MAP.items():
        if re.search(padrao, tl):
            tags.add(tag)
    # Válvulas mencionadas (ex: V67, V147)
    for v in re.findall(r'\bv(\d{1,3})\b', tl):
        tags.add(f"#V{v}")
    return " ".join(sorted(tags))

def negrito_equipamentos(texto: str) -> str:
    # Negrito em válvulas: V67 → *V67*
    texto = re.sub(r'\b(V\d{1,3})\b', r'*\1*', texto, flags=re.IGNORECASE)
    return texto

def separar_secoes(texto: str) -> dict:
    """Tenta separar o texto em seções baseado em marcadores."""
    secoes = {"ajustes": [], "atuacoes": [], "outros": []}
    linhas = texto.strip().split('\n')
    secao_atual = "ajustes"
    for linha in linhas:
        ll = linha.lower()
        if any(k in ll for k in ["atuaç", "atuac", "seguindo", "em seguida", "próximo", "proximo"]):
            secao_atual = "atuacoes"
        linha_fmt = negrito_equipamentos(linha.strip())
        if linha_fmt:
            secoes[secao_atual].append(linha_fmt)
    return secoes

def formatar_anotacao(texto: str, linha_forcada: str = None) -> str:
    linha   = linha_forcada or detectar_linha(texto)
    cfg     = LINE_CONFIG[linha]
    tipo    = detectar_tipo(texto)
    hoje    = datetime.now().strftime("%d/%m/%Y")
    hora    = datetime.now().strftime("%H:%M")
    data_curta = datetime.now().strftime("%d/%m")
    tags    = gerar_hashtags(texto, linha)
    secoes  = separar_secoes(texto)

    # Monta seção de ajustes
    bloco_ajustes = ""
    if secoes["ajustes"]:
        itens = "\n".join(f"• {i}" for i in secoes["ajustes"])
        bloco_ajustes = f"📋 *1\\. Ajustes*\n{itens}\n\n"

    bloco_atuacoes = ""
    if secoes["atuacoes"]:
        itens = "\n".join(f"• {i}" for i in secoes["atuacoes"])
        bloco_atuacoes = f"🔧 *2\\. Atuações Seguintes*\n{itens}\n\n"

    # Se não separou, joga tudo em ajustes
    if not secoes["ajustes"] and not secoes["atuacoes"]:
        corpo = negrito_equipamentos(texto)
        bloco_ajustes = f"📋 *Anotação*\n{corpo}\n\n"

    linha_label = f"L{linha}" if linha != "galpao" else "Galpão"

    nota = (
        f"{cfg['emoji']} *{tipo} — {linha_label} \\({data_curta}\\)*\n"
        f"📅 {hoje} às {hora} \\| 🏷️ {tipo} \\| 📍 {cfg['local']}\n"
        f"{'─' * 28}\n\n"
        f"{bloco_ajustes}"
        f"{bloco_atuacoes}"
        f"{'─' * 28}\n"
        f"🏷️ {tags}"
    )
    return nota

# ── HANDLERS ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *CaderInteliBot ativo\\!*\n\n"
        "Manda a anotação bruta aqui\\.\n"
        "Mencione *512*, *513* ou *514* → identifico a linha automaticamente\\.\n\n"
        "Ou usa os botões abaixo para fixar a linha antes de digitar\\.",
        parse_mode="MarkdownV2",
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
            f"{cfg['emoji']} *{label} ativa\\!*\nAgora escreva sua anotação:",
            parse_mode="MarkdownV2",
        )

async def receber_anotacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if len(texto) < 5:
        await update.message.reply_text("✏️ Anotação muito curta\\. Escreva mais detalhes\\.", parse_mode="MarkdownV2")
        return

    linha_forcada = context.user_data.pop("linha_ativa", None)

    try:
        nota = formatar_anotacao(texto, linha_forcada)
        linha = linha_forcada or detectar_linha(texto)
        cfg   = LINE_CONFIG[linha]
        label = f"L{linha}" if linha != "galpao" else "Galpão"

        await update.message.reply_text(
            f"✅ {cfg['emoji']} *Salvo — {label}*\n\n{nota}",
            parse_mode="MarkdownV2",
            reply_markup=KEYBOARD,
        )
        logger.info("Anotação salva | %s | %s", label, update.effective_user.first_name)

    except Exception as e:
        logger.error("Erro ao formatar: %s", e)
        # Fallback: salva sem formatação
        await update.message.reply_text(
            f"✅ Anotação salva\\!\n\n_{texto}_",
            parse_mode="MarkdownV2",
        )

# ── MAIN ───────────────────────────────────────────────────────────────────────
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
