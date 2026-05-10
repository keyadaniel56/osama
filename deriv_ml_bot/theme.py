"""
UI Theme and Colors for Deriv ML Bot
Provides colored output and emojis for better visual experience
"""

import os
from datetime import datetime

# ANSI Color codes
class Colors:
    # Basic colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BLACK = '\033[30m'
    GRAY = '\033[90m'
    
    # Bright colors
    BRIGHT_RED = '\033[1;91m'
    BRIGHT_GREEN = '\033[1;92m'
    BRIGHT_YELLOW = '\033[1;93m'
    BRIGHT_BLUE = '\033[1;94m'
    BRIGHT_MAGENTA = '\033[1;95m'
    BRIGHT_CYAN = '\033[1;96m'
    
    # Background colors
    BG_RED = '\033[101m'
    BG_GREEN = '\033[102m'
    BG_YELLOW = '\033[103m'
    BG_BLUE = '\033[104m'
    BG_MAGENTA = '\033[105m'
    BG_CYAN = '\033[106m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    
    # Reset
    RESET = '\033[0m'
    END = '\033[0m'

# Emojis for different events
class Emojis:
    # Trading
    WIN = "🎉"
    LOSS = "💥"
    TRADE = "📈"
    MONEY = "💰"
    ROCKET = "🚀"
    FIRE = "🔥"
    
    # Phases
    PHASE_1 = "🎯"
    PHASE_2 = "⚡"
    RECOVERY = "🛡️"
    
    # Status
    CONNECTED = "🔗"
    LOADING = "⏳"
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    
    # Market
    BULL = "🐂"
    BEAR = "🐻"
    CHART = "📊"
    SIGNAL = "📡"
    
    # Symbols
    STAR = "⭐"
    DIAMOND = "💎"
    CROWN = "👑"
    LIGHTNING = "⚡"

def colored_text(text: str, color: str, style: str = "") -> str:
    """Apply color and style to text"""
    return f"{style}{color}{text}{Colors.RESET}"

def format_profit(profit: float) -> str:
    """Format profit with colors and emojis"""
    if profit > 0:
        return colored_text(f"{Emojis.MONEY} +${profit:.2f}", Colors.BRIGHT_GREEN, Colors.BOLD)
    elif profit < 0:
        return colored_text(f"💸 -${abs(profit):.2f}", Colors.BRIGHT_RED, Colors.BOLD)
    else:
        return colored_text(f"💰 ${profit:.2f}", Colors.YELLOW)

def format_win_rate(win_rate: float) -> str:
    """Format win rate with colors"""
    if win_rate >= 90:
        return colored_text(f"{win_rate:.1f}%", Colors.BRIGHT_GREEN, Colors.BOLD)
    elif win_rate >= 80:
        return colored_text(f"{win_rate:.1f}%", Colors.GREEN)
    elif win_rate >= 70:
        return colored_text(f"{win_rate:.1f}%", Colors.YELLOW)
    elif win_rate >= 60:
        return colored_text(f"{win_rate:.1f}%", Colors.MAGENTA)
    else:
        return colored_text(f"{win_rate:.1f}%", Colors.RED)

def format_phase(phase: str, over: int, over_target: int, under: int, under_target: int) -> str:
    """Format phase information with colors and emojis"""
    if "recovery" in phase.lower():
        emoji = Emojis.RECOVERY
        color = Colors.BRIGHT_MAGENTA
    else:  # PHASE_2
        emoji = Emojis.PHASE_2
        color = Colors.BRIGHT_CYAN
    
    # Format OVER/UNDER progress
    over_progress = colored_text(f"{over}/{over_target}", Colors.GREEN if over == over_target else Colors.YELLOW)
    under_progress = colored_text(f"{under}/{under_target}", Colors.GREEN if under == under_target else Colors.YELLOW)
    
    return f"{emoji} {colored_text(phase.upper(), color, Colors.BOLD)} | OVER: {over_progress} | UNDER: {under_progress}"

def format_trade_result(result: str, profit: float) -> str:
    """Format trade result with colors and emojis"""
    if result.upper() == "WIN":
        return f"{Emojis.WIN} {colored_text('WIN', Colors.BRIGHT_GREEN, Colors.BOLD)} | {format_profit(profit)}"
    else:
        return f"{Emojis.LOSS} {colored_text('LOSS', Colors.BRIGHT_RED, Colors.BOLD)} | {format_profit(profit)}"

def format_confidence(confidence: float) -> str:
    """Format confidence with colors"""
    if confidence >= 0.90:
        return colored_text(f"{confidence:.2f}", Colors.BRIGHT_GREEN, Colors.BOLD)
    elif confidence >= 0.80:
        return colored_text(f"{confidence:.2f}", Colors.GREEN)
    elif confidence >= 0.70:
        return colored_text(f"{confidence:.2f}", Colors.YELLOW)
    else:
        return colored_text(f"{confidence:.2f}", Colors.MAGENTA)

def format_stake(stake: float, is_martingale: bool = False) -> str:
    """Format stake with colors and indicators"""
    if is_martingale:
        return colored_text(f"${stake:.2f}", Colors.BRIGHT_YELLOW, Colors.BOLD) + f" {Emojis.FIRE}"
    else:
        return colored_text(f"${stake:.2f}", Colors.CYAN)

def print_banner():
    """Print startup banner"""
    banner = f"""
{Colors.BRIGHT_CYAN}╔══════════════════════════════════════════════════════════════╗
║                    {Colors.WHITE}{Colors.BOLD}DERIV ML TRADING BOT{Colors.RESET}{Colors.BRIGHT_CYAN}                    ║
║                     {Emojis.ROCKET} Powered by AI {Emojis.ROCKET}                      ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}

{colored_text('🎯 Phase-Based Strategy:', Colors.BRIGHT_BLUE, Colors.BOLD)}
  {Emojis.PHASE_2} Main Phase: OVER 1 / UNDER 8 (2 trades each)  
  {Emojis.RECOVERY} Recovery: UNDER 5 / OVER 4 (3 trades each) + Martingale

{colored_text('🛡️ Risk Management:', Colors.BRIGHT_GREEN, Colors.BOLD)}
  • Recovery triggers after any loss
  • Martingale: 2x → 4x → 8x max stake
  • Market bias detection & adaptation
  • Multi-symbol switching for opportunities

{colored_text('⚡ Starting trading session...', Colors.BRIGHT_YELLOW)}
"""
    print(banner)

def print_connection_status(status: str, account_id: str = "", symbol: str = ""):
    """Print connection status"""
    if status == "connected":
        print(f"{Emojis.CONNECTED} {colored_text('Connected', Colors.BRIGHT_GREEN, Colors.BOLD)}")
        if account_id:
            print(f"{Emojis.SUCCESS} {colored_text('Authorized as:', Colors.GREEN)} {colored_text(account_id, Colors.WHITE, Colors.BOLD)}")
        if symbol:
            print(f"{Emojis.CHART} {colored_text('Trading symbol:', Colors.CYAN)} {colored_text(symbol, Colors.BRIGHT_CYAN, Colors.BOLD)}")
    elif status == "error":
        print(f"{Emojis.ERROR} {colored_text('Connection failed', Colors.BRIGHT_RED, Colors.BOLD)}")

def print_collecting_ticks(current: int, total: int):
    """Print tick collection progress"""
    percentage = (current / total) * 100
    bar_length = 20
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    print(f"{Emojis.LOADING} {colored_text('Collecting ticks...', Colors.YELLOW)} [{colored_text(bar, Colors.BRIGHT_BLUE)}] {colored_text(f'{current}/{total}', Colors.WHITE)} ({percentage:.1f}%)")

def print_trade_execution(contract_type: str, stake: float, confidence: float, source: str, phase: str, is_martingale: bool = False):
    """Print trade execution with full theming"""
    # Determine trade direction and color
    if "OVER" in contract_type:
        direction = f"{Emojis.BULL} {colored_text('OVER', Colors.BRIGHT_GREEN, Colors.BOLD)}"
    else:
        direction = f"{Emojis.BEAR} {colored_text('UNDER', Colors.BRIGHT_RED, Colors.BOLD)}"
    
    # Extract barrier from contract type
    barrier = contract_type.split('_')[-1]
    
    # Format source
    source_colored = colored_text(source.upper(), Colors.BRIGHT_MAGENTA if source == "ml" else Colors.BRIGHT_CYAN)
    
    print(f"""
{Emojis.TRADE} {colored_text('TRADE EXECUTED', Colors.WHITE, Colors.BOLD)}
├─ Direction: {direction} {barrier}
├─ Stake: {format_stake(stake, is_martingale)}
├─ Confidence: {format_confidence(confidence)}
├─ Source: {source_colored}
└─ Phase: {colored_text(phase.upper(), Colors.BRIGHT_BLUE)}
""")

def print_recovery_trigger():
    """Print recovery mode activation"""
    print(f"""
{Colors.BG_YELLOW}{Colors.BLACK} ⚠️  RECOVERY MODE ACTIVATED  ⚠️ {Colors.RESET}

{Emojis.RECOVERY} {colored_text('Switching to Recovery Phase', Colors.BRIGHT_MAGENTA, Colors.BOLD)}
{Emojis.FIRE} {colored_text('Martingale Strategy Enabled', Colors.BRIGHT_YELLOW, Colors.BOLD)}
{Emojis.DIAMOND} {colored_text('UNDER 5 / OVER 4 Trading', Colors.BRIGHT_CYAN, Colors.BOLD)}
""")

def get_timestamp() -> str:
    """Get formatted timestamp"""
    return colored_text(datetime.now().strftime("%H:%M:%S"), Colors.GRAY)