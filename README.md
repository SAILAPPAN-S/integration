# Chat Translator

A real-time bilingual chat application that enables seamless communication between an English speaker (UserA) and a Japanese speaker (UserB). Messages are translated instantly using offline machine translation powered by [Argos Translate](https://github.com/argosopentech/argos-translate).

## How It Works

- **UserA** types in English → UserB receives the message translated to Japanese
- **UserB** types in Japanese → UserA receives the message translated to English
- Translation happens server-side in real time via WebSockets

## Project Structure

```
Chat_Translator/
├── app.py               # Flask server with SocketIO and translation logic
├── requirements.txt     # Python dependencies
└── templates/
    ├── usera.html       # English speaker's chat interface
    └── userb.html       # Japanese speaker's chat interface
```

## Tech Stack

| Component        | Library / Tool              |
|------------------|-----------------------------|
| Web Framework    | Flask                       |
| Real-time Comms  | Flask-SocketIO + eventlet   |
| CORS Handling    | Flask-CORS                  |
| Translation      | Argos Translate (offline)   |
| Frontend         | Vanilla JS + Socket.IO CDN  |

## Getting Started

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd Chat_Translator
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

```bash
python app.py
```

The server will start at `http://localhost:5000`.

> **Note:** On first run, the app automatically downloads the English↔Japanese translation models from the Argos Translate package index. This requires an internet connection and may take a few minutes.

### Usage

Open two browser windows or tabs:

| User  | URL                          | Language |
|-------|------------------------------|----------|
| UserA | `http://localhost:5000/usera` | English  |
| UserB | `http://localhost:5000/userb` | Japanese |

Both users chat normally in their own language and receive the other's messages already translated.

## Configuration

The Flask secret key is set in `app.py`. For production, move it to an environment variable using a `.env` file and `python-dotenv`:

```env
SECRET_KEY=your-secret-key-here
```

## Dependencies

```
flask==3.0.3
flask-cors==4.0.1
argostranslate==1.9.5
python-dotenv==1.0.1
```
