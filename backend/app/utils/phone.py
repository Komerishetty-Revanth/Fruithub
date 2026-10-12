import re


def normalize_indian_phone(raw: str) -> str | None:
    """Returns +91XXXXXXXXXX, or None if this is not a valid Indian mobile number."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        return None
    return "+91" + digits