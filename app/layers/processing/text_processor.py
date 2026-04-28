"""
Layer 2: Processing — Clinical Text Preprocessor
=================================================
Full preprocessing pipeline applied to raw clinical notes before NLP encoding.

Pipeline (in order):
  1. remove_template_text  — strip EHR boilerplate / note headers
  2. expand_contractions   — normalise negation-bearing contractions
  3. lowercase             — case normalisation
  4. remove_special_chars  — keep [a-z0-9 ] only
  5. preserve_negations    — (CRITICAL) prefix negated tokens with NEG_
  6. lemmatize             — spaCy lemmatisation (NEG_ tokens handled safely)

CONSTRAINT: No negation word is ever dropped. Every negation is preserved
as a NEG_<base_lemma> token so downstream sentiment/classification layers
receive correct polarity signals.

All individual steps log their transformation (no silent preprocessing).
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Contraction expansion map
# Expand BEFORE lowercasing so pattern matching is unambiguous.
# ─────────────────────────────────────────────────────────────────────────────
_CONTRACTIONS: dict[str, str] = {
    "can't": "cannot",
    "cannot": "cannot",
    "won't": "will not",
    "wouldn't": "would not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "hasn't": "has not",
    "haven't": "have not",
    "hadn't": "had not",
    "couldn't": "could not",
    "shouldn't": "should not",
    "mightn't": "might not",
    "mustn't": "must not",
    "i'm": "i am",
    "i've": "i have",
    "i'll": "i will",
    "i'd": "i would",
    "he's": "he is",
    "she's": "she is",
    "it's": "it is",
    "they're": "they are",
    "we're": "we are",
    "you're": "you are",
    "they've": "they have",
    "we've": "we have",
    "you've": "you have",
    "they'll": "they will",
    "we'll": "we will",
    "you'll": "you will",
    "n't": " not",   # generic suffix catch-all
}

# Compile a single regex that tries each contraction key (longest first)
_CONTRACTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_CONTRACTIONS, key=len, reverse=True)) + r")\b",
    flags=re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# EHR boilerplate / template patterns
# ─────────────────────────────────────────────────────────────────────────────
_TEMPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(patient name|date of birth|dob|mrn|medical record number)[^\n]*", re.I),
    re.compile(r"\b(admission date|discharge date|attending physician)[^\n]*", re.I),
    re.compile(r"\b(signed by|reviewed by|electronically signed|auto.?generated)[^\n]*", re.I),
    re.compile(r"\b(see above|as per previous note|per report|refer to|as noted)[^\n]*", re.I),
    re.compile(r"(?m)^\s*(cc|hpi|pmh|ros|pe|assessment|plan|medications|allergies)\s*:\s*"),
    re.compile(r"-{2,}"),        # horizontal rules — — —
    re.compile(r"\[\s*\]"),      # empty checkboxes [ ]
]

# ─────────────────────────────────────────────────────────────────────────────
# Negation triggers (post-lowercase, post-special-char removal)
# ─────────────────────────────────────────────────────────────────────────────
_NEGATION_WORDS: frozenset[str] = frozenset({
    "not", "no", "never", "neither", "nor", "without", "cannot",
    "cant", "wont", "dont", "doesnt", "didnt", "isnt", "arent",
    "wasnt", "werent", "hasnt", "havent", "hadnt", "couldnt",
    "wouldnt", "shouldnt", "mightnt", "mustnt",
})

_NEG_PREFIX = "NEG"

# ─────────────────────────────────────────────────────────────────────────────
# spaCy — lazy-loaded singleton
# ─────────────────────────────────────────────────────────────────────────────
_nlp = None
_nlp_attempted = False


def _get_nlp():
    global _nlp, _nlp_attempted
    if _nlp_attempted:
        return _nlp
    _nlp_attempted = True
    try:
        import spacy  # noqa: PLC0415
        _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        logger.info("[TextProcessor] spaCy 'en_core_web_sm' loaded successfully.")
    except OSError:
        logger.error(
            "[TextProcessor] spaCy model 'en_core_web_sm' not found. "
            "Run:  python -m spacy download en_core_web_sm. "
            "Lemmatization will be skipped."
        )
        _nlp = None
    return _nlp


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Remove template text
# ─────────────────────────────────────────────────────────────────────────────
def remove_template_text(text: str) -> str:
    before = len(text)
    for pattern in _TEMPLATE_PATTERNS:
        text = pattern.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    logger.debug(
        "[TextProcessor] Step 1 — Template removal: %d → %d chars (%d removed).",
        before, len(text), before - len(text),
    )
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Expand contractions
# ─────────────────────────────────────────────────────────────────────────────
def expand_contractions(text: str) -> str:
    def _replace(match: re.Match) -> str:
        return _CONTRACTIONS.get(match.group(0).lower(), match.group(0))

    result = _CONTRACTION_RE.sub(_replace, text)
    changed = text != result
    logger.debug("[TextProcessor] Step 2 — Contractions expanded: %s.", changed)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Lowercase
# ─────────────────────────────────────────────────────────────────────────────
def lowercase(text: str) -> str:
    result = text.lower()
    logger.debug("[TextProcessor] Step 3 — Lowercased.")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Remove special characters (keep a-z, 0-9, space)
# ─────────────────────────────────────────────────────────────────────────────
def remove_special_characters(text: str) -> str:
    result = re.sub(r"[^a-z0-9\s]", " ", text)
    result = re.sub(r"\s+", " ", result).strip()
    logger.debug("[TextProcessor] Step 4 — Special characters removed.")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Preserve negations (CRITICAL — must never drop a negation)
# ─────────────────────────────────────────────────────────────────────────────
def preserve_negations(text: str) -> str:
    """
    Scans tokens left-to-right. When a negation trigger is encountered the
    immediately following content word is prefixed with NEG_, preserving the
    negation trigger itself in the output so surrounding context is retained.

    Example:
        "patient does not feel happy and is not eating"
        → "patient does not NEG_feel happy and is not NEG_eating"
    """
    words = text.split()
    result: list[str] = []
    pending = False

    for word in words:
        if word in _NEGATION_WORDS:
            pending = True
            result.append(word)
        elif pending:
            result.append(f"{_NEG_PREFIX}_{word}")
            pending = False
        else:
            result.append(word)

    neg_count = sum(1 for w in result if w.startswith(f"{_NEG_PREFIX}_"))
    logger.debug(
        "[TextProcessor] Step 5 — Negation preservation: %d NEG_ token(s) created.",
        neg_count,
    )
    return " ".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Lemmatize (spaCy)
# ─────────────────────────────────────────────────────────────────────────────
def lemmatize(text: str) -> str:
    """
    Lemmatize each token.  NEG_-prefixed tokens are handled by:
      1. Stripping the prefix.
      2. Lemmatizing the base form.
      3. Re-attaching the prefix.
    This preserves polarity through lemmatization.
    """
    nlp = _get_nlp()
    if nlp is None:
        logger.warning("[TextProcessor] Step 6 — Lemmatization SKIPPED (spaCy unavailable).")
        return text

    tokens = text.split()
    result: list[str] = []

    for tok in tokens:
        if tok.startswith(f"{_NEG_PREFIX}_"):
            base = tok[len(_NEG_PREFIX) + 1:]
            doc = nlp(base)
            lemma = doc[0].lemma_ if len(doc) > 0 else base
            result.append(f"{_NEG_PREFIX}_{lemma}")
        else:
            doc = nlp(tok)
            lemma = doc[0].lemma_ if len(doc) > 0 else tok
            result.append(lemma)

    logger.debug(
        "[TextProcessor] Step 6 — Lemmatization complete. Token count: %d.", len(result)
    )
    return " ".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def preprocess_text(raw_text: str) -> str:
    """
    Execute the full six-step preprocessing pipeline and return cleaned_text.
    Every step is logged; no silent transformation occurs.

    Returns
    -------
    cleaned_text : str
    """
    logger.info(
        "[TextProcessor] BEGIN preprocessing — input length: %d chars.", len(raw_text)
    )

    text = remove_template_text(raw_text)
    text = expand_contractions(text)
    text = lowercase(text)
    text = remove_special_characters(text)
    text = preserve_negations(text)
    text = lemmatize(text)

    logger.info(
        "[TextProcessor] END preprocessing — output length: %d chars. "
        "Preview: '%.120s'",
        len(text),
        text,
    )
    return text.strip()
