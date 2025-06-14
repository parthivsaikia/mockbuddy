import re

def extract_filler_words(text):
    filler_words = [
        "you know", "i mean", "i guess", "i suppose", "kind of", "sort of",
        "you see", "you get me", "to be honest", "if you ask me",
        "at the end of the day", "like i said", "if that makes sense",
        "all things considered", "on the other hand", "at the same time",
        "in my opinion", "personally", "as far as i know", "and stuff",
        "and things", "stuff like that", "things like that",
        "um", "uh", "erm", "er", "ah", "oh", "hmm", "huh", "mm", "mm-hmm",
        "uh-huh", "uh-oh", "okay", "alright", "right", "so", "like", "just",
        "actually", "basically", "literally", "seriously", "honestly",
        "totally", "completely", "absolutely", "definitely", "maybe",
        "perhaps", "possibly", "anyway", "well", "anyhow"
    ]

    text_lower = text.lower()
    count = 0

    multi_word_fillers = [w for w in filler_words if " " in w]
    for phrase in multi_word_fillers:
        count += text_lower.count(phrase)

    for phrase in multi_word_fillers:
        text_lower = text_lower.replace(phrase, "")

    single_word_fillers = set(w for w in filler_words if " " not in w)
    words = re.findall(r'\b\w+\b', text_lower)
    count += sum(1 for w in words if w in single_word_fillers)

    return count
