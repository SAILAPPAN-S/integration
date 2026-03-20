"""
Bilingual Chat Server with Real-time Moderation
================================================
Single unified Flask + SocketIO app combining:
  - Content moderation (keyword filtering)
  - Real-time bilingual chat (EN ↔ JA via Argos Translate)
  - REST endpoint for HTTP-based message sending
  - User profile page

Run:
    pip install flask flask-socketio flask-cors eventlet argostranslate
    python app.py
"""

import json
import re
import uuid
import logging
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = "bilingual-chat-secret"

# NOTE: Restrict origins in production, e.g. cors_allowed_origins=["https://yourdomain.com"]
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

CHAT_ROOM = "bilingual_chat"

# ---------------------------------------------------------------------------
# Translation setup  (lazy — runs once, non-fatal on failure)
# ---------------------------------------------------------------------------

_translation_ready = False


def setup_languages() -> bool:
    """Install EN↔JA Argos Translate packages. Returns True on success."""
    global _translation_ready
    try:
        import argostranslate.package
        import argostranslate.translate  # noqa: F401 – verify importable

        log.info("Updating Argos package index…")
        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()

        pairs = [("en", "ja"), ("ja", "en")]
        for from_code, to_code in pairs:
            pkg = next(
                (p for p in available if p.from_code == from_code and p.to_code == to_code),
                None,
            )
            if pkg:
                argostranslate.package.install_from_path(pkg.download())
                log.info("Installed %s→%s translation package.", from_code, to_code)
            else:
                log.warning("Package %s→%s not found in index.", from_code, to_code)

        _translation_ready = True
        log.info("Translation ready.")
        return True
    except Exception as exc:
        log.warning("Translation setup failed (%s). Messages will pass through untranslated.", exc)
        return False


def translate_text(text: str, from_lang: str, to_lang: str) -> str:
    """Translate text; return original on any failure."""
    if not _translation_ready:
        return text
    try:
        import argostranslate.translate
        return argostranslate.translate.translate(text, from_lang, to_lang)
    except Exception as exc:
        log.warning("Translation error (%s→%s): %s", from_lang, to_lang, exc)
        return text  # graceful fallback


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------

_TOXIC_KEYWORDS = [
    # profanity
    "fuck", "shit", "bitch", "asshole", "damn", "hell", "cunt",
    # slurs
    "nigger", "faggot", "retard", "spic", "kike", "chink",
    # violence
    "kill", "murder", "rape", "bomb", "die", "slaughter",
    # explicit
    "porn", "sex", "orgasm", "tits", "cock", "pussy",
]

_TOXIC_PATTERN = re.compile(
    r"(?i)\b(" + "|".join(re.escape(k) for k in _TOXIC_KEYWORDS) + r")\b"
)


def moderate(text: str) -> dict:
    """
    Returns:
        {'action': 'allow'}
        {'action': 'block', 'reason': str, 'matches': list[str]}
    """
    clean = text.strip()
    if not clean:
        return {"action": "allow"}

    matches = list({m.lower() for m in _TOXIC_PATTERN.findall(clean)})
    if matches:
        return {
            "action": "block",
            "reason": "Inappropriate language detected",
            "matches": matches,
        }
    return {"action": "allow"}


def _log_blocked(user_id: str, room_id: str, text: str, matches: list[str]) -> None:
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "room_id": room_id,
        "text": text,
        "matched": matches,
        "action": "blocked",
        "timestamp": datetime.utcnow().isoformat(),
    }
    log.warning("BLOCKED MESSAGE:\n%s\n%s", json.dumps(entry, indent=2), "-" * 50)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "moderation": "active",
        "translation": "ready" if _translation_ready else "unavailable",
    })


@app.route("/api/send", methods=["POST"])
def send_message():
    """HTTP endpoint for sending a message (moderation applied)."""
    data = request.get_json(silent=True) or {}
    missing = [k for k in ("user_id", "text", "room_id") if k not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    user_id = data["user_id"]
    text = data["text"]
    room_id = data["room_id"]

    result = moderate(text)
    if result["action"] == "block":
        _log_blocked(user_id, room_id, text, result["matches"])
        return jsonify({
            "success": False,
            "error": result["reason"],
            "blocked_words": result["matches"],
        }), 400

    message = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "room_id": room_id,
        "text": text,
        "created_at": datetime.utcnow().isoformat(),
    }
    log.info("ALLOWED — user %s: %s", user_id, text)
    return jsonify({"success": True, "message": message, "action": "sent"})


@app.route("/profile")
def profile():
    profile_data = {
        "name": "田中 太郎 (Taro Tanaka)",
        "bio_en": (
            "AI/ML Engineer building real-time chat systems with Flask and SocketIO. "
            "Passionate about production ML deployments."
        ),
        "bio_ja": (
            "AI/MLエンジニア。FlaskとSocketIOでリアルタイムチャットシステムを構築中。"
            "プロダクションレベルのMLデプロイに情熱を注いでいます。"
        ),
        "lang": "en",
    }
    return render_template("profile.html", profile=profile_data)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/usera")
def usera():
    return render_template("usera.html")


@app.route("/userb")
def userb():
    return render_template("userb.html")


# ---------------------------------------------------------------------------
# SocketIO events
# ---------------------------------------------------------------------------

@socketio.on("connect")
def handle_connect():
    join_room(CHAT_ROOM)
    emit("status", {"connected": True, "message": "Connected to bilingual chat!"})


@socketio.on("disconnect")
def handle_disconnect():
    log.info("Client disconnected.")


@socketio.on("send_message")
def handle_message(data):
    """
    Expected payload:
        { "sender": "usera" | "userb", "text": "<message>" }

    UserA writes English  → UserA sees EN, UserB sees JA
    UserB writes Japanese → UserB sees JA, UserA sees EN
    """
    # --- Input validation ---
    if not isinstance(data, dict):
        emit("error", {"message": "Invalid payload."})
        return

    sender = data.get("sender", "").strip()
    text = data.get("text", "").strip()

    if sender not in ("usera", "userb"):
        emit("error", {"message": "sender must be 'usera' or 'userb'."})
        return

    if not text:
        emit("error", {"message": "Message text cannot be empty."})
        return

    # --- Moderation ---
    result = moderate(text)
    if result["action"] == "block":
        _log_blocked(
            user_id=sender,
            room_id=CHAT_ROOM,
            text=text,
            matches=result["matches"],
        )
        emit("moderation_block", {
            "reason": result["reason"],
            "blocked_words": result["matches"],
        })
        return

    # --- Translation & broadcast ---
    message_id = str(uuid.uuid4())
    log.info("Message from %s: %s", sender, text)

    if sender == "usera":
        # UserA writes EN → translate to JA for UserB
        translated = translate_text(text, "en", "ja")
        original_lang, translated_lang = "en", "ja"
    else:
        # UserB writes JA → translate to EN for UserA
        translated = translate_text(text, "ja", "en")
        original_lang, translated_lang = "ja", "en"

    socketio.emit(
        "receive_message",
        {
            "id": message_id,
            "sender": sender,
            "text": text,               # original (shown to sender's side)
            "translated_text": translated,  # shown to the other side
            "original_lang": original_lang,
            "translated_lang": translated_lang,
            "timestamp": datetime.utcnow().isoformat(),
        },
        room=CHAT_ROOM,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    setup_languages()  # non-blocking: failures are logged, not raised
    log.info("Starting bilingual chat server on http://0.0.0.0:5000")
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
