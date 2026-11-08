"""Writes the short messages RepKin shows in its speech bubble.

The server collects the facts and the model only writes the words, so the
model never has to guess a number or an exercise. If Ollama is down, slow, or
gives an empty answer, we show a pre-written line instead of an error.

Three kinds of message:
    greeting  - the user just opened the app
    workout   - the user just logged an exercise
    idle      - the user has been sitting on the home screen for a while
"""

import logging
import random
import re
from dataclasses import dataclass, field
from datetime import timedelta
from collections import namedtuple

from django.utils import timezone

from .models_exercise import ExerciseLog
from .models_repkin import Repkin
from .ollama_client import OllamaUnavailable, chat

logger = logging.getLogger(__name__)

KINDS = ("greeting", "workout", "idle")

RECENT_EXERCISE_LIMIT = 5

# How long a bubble message may be. We ASK the model to stay under MAX_WORDS
# (a request it usually follows) and we ENFORCE MAX_MESSAGE_CHARS when cleaning
# its reply (a hard limit it can't ignore). Keep the character limit a little
# above what the word limit normally produces.
MAX_WORDS = 15
MAX_MESSAGE_CHARS = 150

# Separate safety limit on the previous message that gets sent back into the
# prompt. It is not about reply length. Keep it >= MAX_MESSAGE_CHARS.
MAX_LAST_MESSAGE_CHARS = 200

DEFAULT_NAME = "RepKin"

# What we return: the text to show, and whether it came from the fallback list.
RepkinMessage = namedtuple("RepkinMessage", ["text", "used_fallback"])

FALLBACK_LINES = {
    "greeting": [
        "Welcome back! I'm so glad you're here.",
        "Hey you! Ready to move a little today?",
        "There you are! I was hoping you'd stop by.",
    ],
    "workout": [
        "Nice work! Every rep counts.",
        "You showed up and did the work. I'm proud of you!",
        "Another one in the books. Great job!",
    ],
    "idle": [
        "Just cheering you on from over here!",
        "A little stretch never hurt anyone. Want to try one?",
        "You're doing great. Keep it up!",
    ],
}


# --------------------------------------------------------------------------
# Step 1: gather the facts (only ever for the user we were given)
# --------------------------------------------------------------------------

@dataclass
class Facts:
    repkin_name: str = DEFAULT_NAME
    mood: str = ""
    favorite_activity: str = ""
    favorite_food: str = ""
    recent_exercises: list = field(default_factory=list)  # newest first
    just_logged: list = field(default_factory=list)
    exercises_this_week: int = 0


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def describe_duration(seconds):
    minutes, secs = divmod(seconds, 60)
    parts = []
    if minutes:
        parts.append(plural(minutes, "minute"))
    if secs or not minutes:
        parts.append(plural(secs, "second"))
    return " ".join(parts)


def describe_when(logged_at, today):
    days = (today - timezone.localtime(logged_at).date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def describe_exercise(log, today):
    """One line of plain facts, e.g. 'Push Ups: 3 sets of 10 reps (today)'."""
    if log.sets and log.reps:
        amount = f"{plural(log.sets, 'set')} of {plural(log.reps, 'rep')}"
    elif log.duration_seconds:
        amount = describe_duration(log.duration_seconds)
    elif log.distance_miles is not None:
        miles = float(log.distance_miles)
        amount = f"{miles:g} mile" + ("" if miles == 1 else "s")
    else:
        amount = "no details recorded"
    when = describe_when(log.logged_at, today)
    return f"{log.get_exercise_type_display()}: {amount} ({when})"


def gather_facts(user, just_logged_ids=None):
    """Collect what RepKin knows about this user, and nothing about anyone else."""
    facts = Facts()
    today = timezone.localdate()

    repkin = Repkin.objects.filter(owner=user).first()
    if repkin is not None:
        facts.repkin_name = repkin.name or DEFAULT_NAME
        facts.mood = repkin.mood
        facts.favorite_activity = repkin.favorite_activity
        facts.favorite_food = repkin.favorite_food

    # Every query starts from this user's own logs.
    own_logs = ExerciseLog.objects.filter(user=user).order_by("-logged_at", "-id")

    recent = list(own_logs[:RECENT_EXERCISE_LIMIT])
    facts.recent_exercises = [describe_exercise(log, today) for log in recent]

    if just_logged_ids:
        just_logged = list(own_logs.filter(id__in=just_logged_ids))
    else:
        just_logged = recent[:1]
    facts.just_logged = [describe_exercise(log, today) for log in just_logged]

    week_ago = timezone.now() - timedelta(days=7)
    facts.exercises_this_week = own_logs.filter(logged_at__gte=week_ago).count()
    return facts


# --------------------------------------------------------------------------
# Step 2: build the prompt
# --------------------------------------------------------------------------

def app_exercise_names():
    return ", ".join(label for _, label in ExerciseLog.EXERCISE_CHOICES)


def eligible_topics(facts):
    """Topics RepKin can talk about when idle, given what we actually know."""
    topics = ["encouragement", "tip"]
    if facts.favorite_food:
        topics.append("favorite_food")
    if facts.favorite_activity:
        topics.append("favorite_activity")
    if facts.exercises_this_week:
        topics.append("weekly_progress")
    if facts.recent_exercises:
        topics.append("recent_exercise")
    return topics


def describe_topic(topic, facts):
    return {
        "encouragement": "a little general encouragement to keep moving",
        "tip": (
            "one simple, gentle idea they could try, chosen from these "
            f"exercises: {app_exercise_names()}"
        ),
        "favorite_food": f"your favorite food ({facts.favorite_food}), in a playful way",
        "favorite_activity": (
            f"your favorite activity ({facts.favorite_activity}), "
            "and invite them to join you"
        ),
        "weekly_progress": (
            f"the {plural(facts.exercises_this_week, 'exercise')} they logged "
            "in the last 7 days, and cheer them on"
        ),
        "recent_exercise": "their most recent logged exercise",
    }[topic]


def tidy_last_message(text):
    """The previous message may come from the browser, so treat it as untrusted:
    one line, limited length."""
    return " ".join(str(text or "").split())[:MAX_LAST_MESSAGE_CHARS]


def situation_for(kind, facts, topic):
    if kind == "greeting":
        return (
            "The user just opened the app. Greet them warmly and welcome them back. "
            "If they have logged exercises you may mention the most recent one; "
            "if not, gently invite them to log their first."
        )
    if kind == "workout":
        if facts.just_logged:
            return (
                "The user just finished logging the exercise(s) listed under "
                "'Just logged'. Congratulate them, and mention what they did."
            )
        return (
            "The user just logged an exercise, but you don't have its details. "
            "Congratulate them in general terms without naming any exercise or number."
        )
    return (
        "The user has been sitting on the home screen for a while. "
        f"Say something short and friendly about: {describe_topic(topic, facts)}."
    )


def build_messages(kind, facts, topic=None, last_message=""):
    """Return the message list for chat().

    We send ONE user message and no system message, so the persona in your
    Modelfile stays in charge of RepKin's personality.
    """
    lines = [
        f"You are {facts.repkin_name}, the user's RepKin companion. "
        "Write ONE message for the speech bubble on their home screen.",
        "",
        f"Situation: {situation_for(kind, facts, topic)}",
        "",
        "Facts about you:",
        f"- Name: {facts.repkin_name}",
    ]
    if facts.mood:
        lines.append(f"- Mood: {facts.mood}")
    if facts.favorite_activity:
        lines.append(f"- Favorite activity: {facts.favorite_activity}")
    if facts.favorite_food:
        lines.append(f"- Favorite food: {facts.favorite_food}")

    lines += ["", "Facts about the user's exercise (this is everything you know):"]
    if kind == "workout" and facts.just_logged:
        lines.append("Just logged:")
        lines += [f"- {item}" for item in facts.just_logged]
    elif facts.recent_exercises:
        lines.append("Recent exercises, newest first:")
        lines += [f"- {item}" for item in facts.recent_exercises]
    else:
        lines.append("- They haven't logged any exercises yet.")
    if facts.exercises_this_week:
        lines.append(
            f"- Exercises logged in the last 7 days: {facts.exercises_this_week}"
        )

    lines += [
        "",
        "Rules:",
        f"- Write ONE short sentence, under {MAX_WORDS} words.",
        "- Speak directly to the user in your own voice. Plain text only: no "
        "quotation marks, no lists, and no emojis.",
        "- Never invent exercises, numbers, or achievements. Only use the facts above.",
        "- No medical advice, no diet advice, and never push the user to overdo it.",
    ]
    if last_message:
        lines.append(
            "- Don't repeat or closely paraphrase your previous message, "
            f"which was: {last_message}"
        )
    return [{"role": "user", "content": "\n".join(lines)}]


# --------------------------------------------------------------------------
# Step 3: clean up whatever the model says
# --------------------------------------------------------------------------

# Emoji and emoji-style symbols. Ordinary letters, accents, digits, and
# punctuation (apostrophes, hyphens, dashes, ellipses) are not in these ranges.
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"      # pictographs, faces, flags, and most emoji
    "\u2300-\u23FF"              # watch, alarm clock, and similar
    "\u2600-\u27BF"              # sun, check marks, sparkles, and similar
    "\u2B00-\u2BFF"              # stars and big arrows
    "\u200D\u20E3\uFE0E\uFE0F"   # joiners, keycaps, emoji style selectors
    "]+"
)

OPENING_QUOTES = "\"'“‘"
CLOSING_QUOTES = "\"'”’"
SENTENCE_ENDINGS = ".!?"


def clean_reply(text):
    """One line, no emojis, no wrapping quotes, short enough for the bubble."""
    text = EMOJI_PATTERN.sub(" ", text or "")
    text = " ".join(text.split())
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)  # "great job !" -> "great job!"
    if len(text) >= 2 and text[0] in OPENING_QUOTES and text[-1] in CLOSING_QUOTES:
        text = text[1:-1].strip()
    if len(text) > MAX_MESSAGE_CHARS:
        cut = text[:MAX_MESSAGE_CHARS]
        last_end = max(cut.rfind(mark) for mark in SENTENCE_ENDINGS)
        if last_end >= MAX_MESSAGE_CHARS // 4:
            text = cut[: last_end + 1]
        else:
            text = cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def fallback_message(kind, last_message, rng):
    lines = FALLBACK_LINES[kind]
    choices = [line for line in lines if line != last_message] or lines
    return RepkinMessage(rng.choice(choices), True)


# --------------------------------------------------------------------------
# Putting it together
# --------------------------------------------------------------------------

def generate_message(user, kind, *, just_logged_ids=None, last_message="", rng=None):
    """Return a RepkinMessage for this user. Never raises because Ollama is down."""
    if kind not in KINDS:
        raise ValueError(f"Unknown message kind: {kind!r}")
    rng = rng or random
    last_message = tidy_last_message(last_message)

    facts = gather_facts(user, just_logged_ids)
    topic = rng.choice(eligible_topics(facts)) if kind == "idle" else None
    messages = build_messages(kind, facts, topic=topic, last_message=last_message)

    try:
        reply = chat(messages)
    except OllamaUnavailable as error:
        logger.warning("Ollama unavailable, using a fallback line: %s", error)
        return fallback_message(kind, last_message, rng)

    text = clean_reply(reply)
    if not text:
        logger.warning("Ollama returned an empty reply, using a fallback line.")
        return fallback_message(kind, last_message, rng)
    return RepkinMessage(text, False)
