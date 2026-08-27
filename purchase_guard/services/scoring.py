def severity_from_score(score):
    score = float(score or 0)
    if score >= 80:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"

def weighted_score(checks):
    total = 0
    for check in checks:
        total += float(check.get("score", 0))
    return min(100, round(total))

def risk_score_to_status(score):
    return severity_from_score(score)
