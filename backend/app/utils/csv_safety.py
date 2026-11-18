"""CSV helpers shared by the export API and tests."""

FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def neutralize_csv_formula(value: object) -> object:
    """Prefix string cells that spreadsheets would evaluate as formulas with a quote."""
    if isinstance(value, str) and value.startswith(FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value
