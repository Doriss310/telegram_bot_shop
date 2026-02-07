def _split_parts(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(",")]


def parse_format_labels(format_data: str | None) -> list[str]:
    if not format_data:
        return []
    labels = [label.strip() for label in str(format_data).split(",")]
    return [label for label in labels if label]


def format_stock_item(item: str, format_data: str | None, html: bool = False) -> str:
    labels = parse_format_labels(format_data)
    if not labels:
        return f"<code>{item}</code>" if html else str(item)
    values = _split_parts(item)
    lines = []
    for idx, label in enumerate(labels):
        value = values[idx] if idx < len(values) else ""
        if html:
            if value:
                lines.append(f"{label}: <code>{value}</code>")
            else:
                lines.append(f"{label}:")
        else:
            if value:
                lines.append(f"{label}: {value}")
            else:
                lines.append(f"{label}:")
    return "\n".join(lines).strip()


def format_stock_items(items: list[str], format_data: str | None, html: bool = False) -> list[str]:
    return [format_stock_item(item, format_data, html=html) for item in items]
