from datetime import datetime


def format_currency(amount: float, currency: str = "USD") -> str:
    return f"${amount:,.2f}" if currency == "USD" else f"{amount:,.2f} {currency}"


def format_datetime(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_bytes(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes} PB"


def truncate(text: str, max_length: int = 100) -> str:
    return text[:max_length] + "..." if len(text) > max_length else text
