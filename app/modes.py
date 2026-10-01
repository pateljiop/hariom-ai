MODES = {
    "coding": {"keywords": {"code","coding","bug","debug","python","javascript","repo","github","api","project"}},
    "study": {"keywords": {"study","exam","learn","syllabus","question","practice","revision"}},
    "freelance": {"keywords": {"client","freelance","lead","website","proposal","outreach","portfolio"}},
    "content": {"keywords": {"youtube","video","reel","instagram","thumbnail","script","content"}},
    "general": {"keywords": set()},
}


def detect_mode(request):
    words = {w.lower().strip(".,!?") for w in str(request).split()}
    scores = {
        name: len(words & data["keywords"])
        for name, data in MODES.items()
        if name != "general"
    }
    best = max(scores, key=scores.get, default="general")
    return best if scores.get(best, 0) else "general"
