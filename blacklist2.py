# === PROTOBUF BYPASS HACK (DON'T REMOVE) ===
import sys, types
import google.protobuf
dummy = types.ModuleType('google.protobuf.runtime_version')
dummy.ValidateProtobufRuntimeVersion = lambda *a, **kw: None
class FakeDomain: PUBLIC = 1
dummy.Domain = FakeDomain
sys.modules['google.protobuf.runtime_version'] = dummy
# ===========================================

from flask import Flask, request, jsonify, send_file
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json

# Yahan agar protobuf downgrade (3.20.3) ke baad bhi error aaye toh in imports ko comment kar dena
import like_pb2
import like_count_pb2
import uid_generator_pb2

from google.protobuf.message import DecodeError
import base64
import time
import io
import zipfile
from proto import FreeFire_pb2
from google.protobuf import json_format
import urllib3
from PIL import Image
import threading

# SSL Warnings hide karne ke liye
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Memory cache for Vercel 
MEMORY_TOKENS = []


# ============================================================
# BACKGROUND TOKEN AUTO-REFRESH THREAD
# Startup pe tokens generate hote hain, phir har 6 ghante baad
# App band nahi hogi — daemon thread hai
# ============================================================
def _background_token_refresh():
    """Har 6 ghante mein uidpass.json se tokens refresh karta hai."""
    import time
    # Startup pe ek baar zaroor chalao
    try:
        count = update_tokens(10)
        app.logger.info(f"[STARTUP] {count} tokens generate hue uidpass.json se.")
    except Exception as e:
        app.logger.error(f"[STARTUP] Token generate error: {e}")
    while True:
        time.sleep(21600)  # 6 ghante = 21600 seconds
        try:
            app.logger.info("[AUTO-REFRESH] 6 ghante complete — tokens refresh ho rahe hain...")
            count = update_tokens(10)
            app.logger.info(f"[AUTO-REFRESH] {count} naye tokens ban gaye.")
        except Exception as e:
            app.logger.error(f"[AUTO-REFRESH] Error: {e}")


def start_token_refresh_thread():
    t = threading.Thread(target=_background_token_refresh, daemon=True)
    t.start()

# ============================================================
# JWT TOKEN GENERATOR LOGIC 
# ============================================================
def fetch_access_token_sync(cred_str):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = cred_str + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    resp = requests.post(url, data=payload, headers=headers)
    data = resp.json()
    return data.get("access_token", ""), data.get("open_id", "")

def update_tokens(limit=10):
    global MEMORY_TOKENS
    try:
        with open("uidpass.json", "r") as f:
            accounts = json.load(f)

        new_tokens = []
        app.logger.info(f"Generating {limit} new JWT tokens...")
        for acc in accounts[:limit]:
            try:
                cred_str = f"uid={acc['uid']}&password={acc['password']}"
                access_token, open_id = fetch_access_token_sync(cred_str)
                if not access_token: continue

                login_req = FreeFire_pb2.LoginReq()
                json_format.ParseDict({
                    "open_id": open_id,
                    "open_id_type": "4",
                    "login_token": access_token,
                    "orign_platform_type": "4"
                }, login_req)
                proto_bytes = login_req.SerializeToString()

                MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
                MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
                cipher = AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV)
                pad_len = AES.block_size - (len(proto_bytes) % AES.block_size)
                padded = proto_bytes + bytes([pad_len] * pad_len)
                encrypted = cipher.encrypt(padded)

                url = "https://loginbp.ggblueshark.com/MajorLogin"
                headers = {
                    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)",
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                    "Content-Type": "application/octet-stream",
                    "Expect": "100-continue",
                    "X-Unity-Version": "2018.4.11f1",
                    "X-GA": "v1 1",
                    "ReleaseVersion": "OB52"
                }
                
                resp = requests.post(url, data=encrypted, headers=headers)
                login_res = FreeFire_pb2.LoginRes()
                login_res.ParseFromString(resp.content)
                msg = json.loads(json_format.MessageToJson(login_res))
                token = msg.get('token')
                if token:
                    new_tokens.append({"token": token})
            except Exception as e:
                app.logger.error(f"Error generating token for {acc.get('uid')}: {e}")

        if new_tokens:
            MEMORY_TOKENS = new_tokens
            try:
                with open("tokens.json", "w") as f:
                    json.dump(new_tokens, f, indent=4)
            except: pass
        return len(new_tokens)
    except Exception as e:
        app.logger.error(f"Error in update_tokens: {e}")
        return 0

# ============================================================
# MAIN API LOGIC (All Helper Functions Retained)
# ============================================================
def load_tokens():
    global MEMORY_TOKENS
    if MEMORY_TOKENS: return MEMORY_TOKENS
    try:
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
        if tokens:
            MEMORY_TOKENS = tokens
            return tokens
    except Exception as e:
        pass
    return []


def get_valid_token():
    """
    Token deta hai. Agar tokens nahi mile (expired ya empty) toh
    turant uidpass.json se naye generate karta hai.
    """
    global MEMORY_TOKENS
    tokens = load_tokens()
    if tokens:
        return tokens[0]['token']
    # Tokens nahi mile — abhi naye banao
    app.logger.warning("[TOKEN] Tokens nahi mile, abhi generate kar raha hoon...")
    MEMORY_TOKENS = []
    count = update_tokens(10)
    if count > 0:
        tokens = load_tokens()
        if tokens:
            return tokens[0]['token']
    app.logger.error("[TOKEN] Naya token bhi nahi ban paya!")
    return None


def get_token_with_fallback(uid, server_name, check_fn):
    """
    Pehle existing token se try karo. Agar error aaye (expired/rejected)
    toh turant force-refresh karke dobara try karo.
    check_fn: check_fn(uid, server_name, token) -> (result, error)
    """
    global MEMORY_TOKENS
    token = get_valid_token()
    if not token:
        return None, "No tokens available aur naya bhi nahi ban paya"
    result, error = check_fn(uid, server_name, token)
    if error:
        app.logger.warning(f"[TOKEN] Error: {error} — force-refresh kar raha hoon...")
        MEMORY_TOKENS = []
        count = update_tokens(10)
        if count > 0:
            token = get_valid_token()
            if token:
                result, error = check_fn(uid, server_name, token)
    return result, error

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        return None

async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB52"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                if response.status != 200:
                    return response.status
                return await response.text()
    except Exception as e:
        return None

async def send_multiple_requests(uid, server_name, url):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None: return None
        
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None: return None
        
        tasks = []
        tokens = load_tokens()
        if not tokens: return None
        
        for i in range(100):
            token = tokens[i % len(tokens)]["token"]
            tasks.append(send_request(encrypted_uid, token, url))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    except Exception as e:
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except: return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    return encrypt_message(protobuf_data) if protobuf_data else None

def get_server_url(server_name, endpoint):
    if server_name == "IND":
        base = "https://client.ind.freefiremobile.com"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        base = "https://client.us.freefiremobile.com"
    else:
        base = "https://clientbp.ggpolarbear.com"
    return f"{base}/{endpoint}"

def make_request(encrypt, server_name, token):
    try:
        url = get_server_url(server_name, "GetPlayerPersonalShow")
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB52"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False)
        if response.status_code != 200:
            return None
        
        items = like_count_pb2.Info()
        items.ParseFromString(response.content)
        return items
    except Exception as e:
        return None

# ============================================================
# ✅ BAN CHECK HELPER
# ============================================================
def check_ban_status(uid, server_name, token):
    try:
        encrypt = enc(uid)
        if not encrypt: return None, "Encryption failed"
        
        url = get_server_url(server_name, "GetPlayerPersonalShow")
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB52"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False)
        
        if response.status_code != 200: return None, f"Server returned {response.status_code}"
        
        from proto import AccountPersonalShow_pb2
        info = AccountPersonalShow_pb2.AccountPersonalShowInfo()
        info.ParseFromString(response.content)
        basic = info.basic_info
        
        is_deleted = basic.is_deleted
        account_id = basic.account_id
        credit_info = info.credit_score_info
        credit_score = credit_info.credit_score if credit_info else None
        
        ban_result = {
            "uid": uid,
            "account_id": str(account_id),
            "nickname": basic.nickname,
            "region": basic.region or server_name,
            "is_banned": is_deleted,
            "ban_status": "BANNED" if is_deleted else "ACTIVE",
            "credit_score": credit_score,
            "credit_warning": credit_score < 60 if credit_score else False,
        }
        return ban_result, None
    except Exception as e:
        return None, str(e)


# ============================================================
# ✅ WISHLIST HELPER FUNCTION
# ============================================================
def check_wishlist(uid, server_name, token):
    try:
        encrypt = enc(uid)
        if not encrypt: return None, "Encryption failed"
        
        url = get_server_url(server_name, "GetWishListItems")
        edata = bytes.fromhex(encrypt)
        headers = {
            'Host': "client.ind.freefiremobile.com",
            'User-Agent': "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            'Accept': "*/*",
            'Accept-Encoding': "deflate, gzip",
            'Authorization': f"Bearer {token}",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB52",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2022.3.47f1"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False)
        
        if response.status_code != 200:
            return None, f"Server returned {response.status_code} - {response.text}"
        
        raw = response.content
        if not raw: return {"uid": uid, "wishlist_data": []}, None
        
        wish_items = []
        pos = 0
        
        def read_varint(data, p):
            result = 0; shift = 0
            while p < len(data):
                b = data[p]; p += 1
                result |= (b & 0x7f) << shift
                shift += 7
                if not (b & 0x80): break
            return result, p
        
        while pos < len(raw):
            try:
                tag, pos = read_varint(raw, pos)
                field = tag >> 3
                wire = tag & 7
                
                if wire == 0:
                    val, pos = read_varint(raw, pos)
                    wish_items.append({"field": field, "value": val})
                elif wire == 2:
                    length, pos = read_varint(raw, pos)
                    content = raw[pos:pos+length]
                    pos += length
                    inner_pos = 0
                    inner_vals = []
                    while inner_pos < len(content):
                        try:
                            itag, inner_pos = read_varint(content, inner_pos)
                            ifield = itag >> 3
                            iwire = itag & 7
                            if iwire == 0:
                                ival, inner_pos = read_varint(content, inner_pos)
                                inner_vals.append({"field": ifield, "value": ival})
                        except: break
                    wish_items.append({"field": field, "nested": inner_vals})
                elif wire == 5:
                    val = int.from_bytes(raw[pos:pos+4], 'little'); pos += 4
                    wish_items.append({"field": field, "value": val, "type": "32bit"})
                else: break
            except: break
        
        return {"uid": uid, "server": server_name, "wishlist_data": wish_items}, None
    except Exception as e:
        return None, str(e)


# ============================================================
# 📥 ASYNC IMAGE DOWNLOADER
# ============================================================
async def fetch_visible_image(session, item_id):
    url_community = f"https://freefire.api.ffmod.com/images/items/{item_id}.webp"
    try:
        async with session.get(url_community) as resp:
            if resp.status == 200:
                img_data = await resp.read()
                with Image.open(io.BytesIO(img_data)) as img:
                    png_buffer = io.BytesIO()
                    img.save(png_buffer, format="PNG")
                    return f"{item_id}.png", png_buffer.getvalue()
    except: pass
    
    url_astc = f"https://dl-tata.freefireind.in/live/ABHotUpdates/IconCDN/android/{item_id}_sa.astc"
    try:
        async with session.get(url_astc) as resp:
            if resp.status == 200:
                return f"{item_id}_sa.astc", await resp.read()
    except: pass
    
    url_png = f"https://dl-tata.freefireind.in/live/ABHotUpdates/IconCDN/android/{item_id}.png"
    try:
        async with session.get(url_png) as resp:
            if resp.status == 200:
                return f"{item_id}_official.png", await resp.read()
    except: pass
    return None, None

async def download_visible_images(item_ids):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_visible_image(session, val) for val in item_ids]
        return await asyncio.gather(*tasks)


# ============================================================
# API ROUTES
# ============================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "Developer": "Rolex",
        "endpoints": {
            "ban": "/ban?uid=<uid>&server_name=IND",
            "blacklist": "/blacklist?uid=<uid>&server_name=IND",
            "update_bio": "/update_bio?uid=<uid>&token=<token>&bio=<bio>&server_name=IND",
            "wishlist_json": "/wishlist?uid=<uid>&server_name=IND",
            "wishlist_zip":  "/wishlist_zip?uid=<uid>&server_name=IND"
        }
    })

@app.route('/cron', methods=['GET'])
def trigger_cron():
    count = update_tokens(10)
    return jsonify({"message": f"Generated {count} tokens."})

# ============================================================
# 1. BAN CHECK ROUTE
# ============================================================
@app.route('/ban', methods=['GET'])
def handle_ban_check():
    uid = request.args.get("uid")
    if not uid: return jsonify({"error": "UID is required"}), 400

    try:
        server_name = request.args.get("server_name", "IND").upper()
        result, error = get_token_with_fallback(uid, server_name, check_ban_status)
        if error: return jsonify({"error": error}), 500

        return jsonify({
            "Developer": "Rolex ❤️‍🔥",
            "uid": result["uid"],
            "account_id": result["account_id"],
            "nickname": result["nickname"],
            "region": result["region"],
            "ban_status": result["ban_status"],
            "is_banned": result["is_banned"],
            "credit_score": result["credit_score"],
            "credit_warning": result["credit_warning"],
            "status": 200
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# 2. BLACKLIST CHECK ROUTE (NEW)
# ============================================================
@app.route('/blacklist', methods=['GET'])
def handle_blacklist_check():
    uid = request.args.get("uid")
    if not uid: return jsonify({"error": "UID is required"}), 400
    server_name = request.args.get("server_name", "IND").upper()

    try:
        def _blacklist_check(uid, server_name, token):
            url = get_server_url(server_name, "GetMatchmakingBlacklist")
            encrypt = enc(uid)
            if not encrypt: return None, "Encryption failed"
            edata = bytes.fromhex(encrypt)
            headers = {
                'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
                'Connection': "Keep-Alive",
                'Accept-Encoding': "gzip",
                'Authorization': f"Bearer {token}",
                'Content-Type': "application/x-www-form-urlencoded",
                'Expect': "100-continue",
                'X-Unity-Version': "2018.4.11f1",
                'X-GA': "v1 1",
                'ReleaseVersion': "OB52"
            }
            resp = requests.post(url, data=edata, headers=headers, verify=False)
            if resp.status_code == 200:
                return {"content": resp.content, "status_code": resp.status_code}, None
            return None, f"Server returned {resp.status_code}"

        result, error = get_token_with_fallback(uid, server_name, _blacklist_check)
        if error: return jsonify({"error": error}), 500

        is_blacklisted = len(result["content"]) > 10
        return jsonify({
            "Developer": "Rolex ❤️‍🔥",
            "uid": uid,
            "is_blacklisted": is_blacklisted,
            "raw_size": len(result["content"]),
            "status": "Success"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# === HELPER: PURE PYTHON PROTOBUF ENCODER ===
def encode_varint(value):
    if value == 0: return b'\x00'
    res = bytearray()
    while value > 0:
        b = value & 0x7F
        value >>= 7
        if value > 0: b |= 0x80
        res.append(b)
    return bytes(res)

# ============================================================
# ============================================================
# 3. BIO CHANGER ROUTE (ALL-IN-ONE MASTER API)
# ============================================================
@app.route('/update_bio', methods=['GET'])
def handle_update_bio():
    uid = request.args.get('uid')
    new_bio = request.args.get('bio')
    server_name = request.args.get("server_name", "IND").upper()
    
    # 1. Direct Garena Token (JWT)
    jwt_token = request.args.get('token')
    
    # 2. Facebook / Google Access Token
    access_token = request.args.get('access_token')
    
    # Dummy Open ID (Agar user ne nahi di, toh script khud laga legi)
    open_id = request.args.get('open_id', '100088889999222') 
    
    # Type 2 = Facebook, Type 1 = Google (Default Facebook set hai)
    login_type = request.args.get('type', '2') 

    if not all([uid, new_bio]):
        return jsonify({"error": "Missing uid or bio"}), 400

    try:
                                # --- ⚡ MAGIC: AUTO CONVERT ANY TOKEN TO JWT (WITHOUT OPEN_ID) ---
        if not jwt_token and access_token:
            
            # 🚀 HACK 1: DECODE TOKEN (Agar token ke andar hi ID chupi ho - For Guests/FB)
            if not open_id and access_token.count('.') == 2:
                try:
                    import base64
                    import json
                    # Token ka beech wala hissa payload hota hai
                    payload = access_token.split('.')[1]
                    # Base64 padding fix
                    payload += '=' * (-len(payload) % 4)
                    decoded_payload = base64.b64decode(payload).decode('utf-8')
                    token_data = json.loads(decoded_payload)
                    
                    # Token ke andar se ID nikalna
                    if 'sub' in token_data:
                        open_id = token_data['sub']
                    elif 'user_id' in token_data:
                        open_id = token_data['user_id']
                    elif 'open_id' in token_data:
                        open_id = token_data['open_id']
                        
                    if open_id:
                        login_type = '4' # Default guest maan lete hain
                except Exception as e:
                    pass # Decode fail hua toh agle hack par jayega

            # 🚀 HACK 2: FACEBOOK TOKEN (EAA...) REVERSE LOOKUP
            if not open_id and access_token.startswith("EAA"):
                try:
                    fb_res = requests.get(f"https://graph.facebook.com/me?access_token={access_token}").json()
                    if 'id' in fb_res:
                        open_id = fb_res['id']
                        login_type = '2' # FB Type
                    else:
                        return jsonify({"error": "Facebook Token Invalid hai ya expire ho gaya hai!"}), 400
                except:
                    return jsonify({"error": "Facebook API se connect nahi ho paya!"}), 500

            # 🚀 HACK 3: GARENA REWARD WEB TOKEN (980c...) REVERSE LOOKUP
            elif not open_id and len(access_token) > 100 and not access_token.startswith("EAA"):
                try:
                    reward_url = "https://recompensas.recargajogo.com.br/api/user"
                    headers_web = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Cookie": f"access_token={access_token}"
                    }
                    web_res = requests.get(reward_url, headers=headers_web).json()
                    
                    if 'userInfo' in web_res and 'open_id' in web_res['userInfo']:
                        open_id = web_res['userInfo']['open_id']
                        login_type = str(web_res['userInfo'].get('platform', '4')) 
                except:
                    pass

            # Agar abhi bhi open_id nahi mili (Yani Garena ka info endpoint chahiye)
            if not open_id:
                return jsonify({"error": "Yeh token pehchana nahi gaya! Server ID decode nahi kar paya, iske liye open_id sath me dena padega."}), 400

            # 🚀 THE FINAL ATTACK: Dono cheezein mil gayi, ab Garena MajorLogin ko bhejo!
            import base64
            from Crypto.Cipher import AES
            from google.protobuf import json_format
            from proto import FreeFire_pb2
            
            login_req = FreeFire_pb2.LoginReq()
            json_format.ParseDict({
                "open_id": open_id,
                "open_id_type": str(login_type),
                "login_token": access_token,
                "orign_platform_type": str(login_type)
            }, login_req)
            proto_bytes = login_req.SerializeToString()
            
            MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
            MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
            cipher = AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV)
            pad_len = AES.block_size - (len(proto_bytes) % AES.block_size)
            padded = proto_bytes + bytes([pad_len] * pad_len)
            encrypted = cipher.encrypt(padded)
            
            url_login = "https://loginbp.ggblueshark.com/MajorLogin"
            headers_login = {
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/octet-stream",
                "X-Unity-Version": "2018.4.11f1",
                "ReleaseVersion": "OB52"
            }
            
            resp_login = requests.post(url_login, data=encrypted, headers=headers_login, verify=False)
            
            try:
                login_res = FreeFire_pb2.LoginRes()
                login_res.ParseFromString(resp_login.content)
                msg = json.loads(json_format.MessageToJson(login_res))
                jwt_token = msg.get('token')
                
                if not jwt_token:
                    return jsonify({"error": "Garena ne token reject kar diya.", "garena_reply": msg}), 401
            except Exception:
                return jsonify({
                    "error": "Garena Server Reject! Tera access_token expire hai ya platform match nahi hua."
                }), 401
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # ---------------------------------------------------------

        # Agar dono me se koi bhi token nahi mila
        if not jwt_token:
            return jsonify({"error": "Bhai token ya access_token dono mein se koi ek dena zaroori hai!"}), 400

        # --- ⚡ BIO CHANGE LOGIC (DOUBLE LAYER HACK) ---
        url = get_server_url(server_name, "UpdateSocialBasicInfo")
        
        uid_val = int(uid)
        bio_bytes = new_bio.encode('utf-8')
        
        # Inner Box Creation
        inner_box = b'\x08' + encode_varint(uid_val) 
        inner_box += b'\x4a' + encode_varint(len(bio_bytes)) + bio_bytes 
        
        # Outer Box Creation
        final_raw_proto = b'\x0a' + encode_varint(len(inner_box)) + inner_box
        
        encrypt = encrypt_message(final_raw_proto)
        if not encrypt: return jsonify({"error": "Encryption failed"}), 500
        edata = bytes.fromhex(encrypt)

        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {jwt_token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB52"
        }

        resp = requests.post(url, data=edata, headers=headers, verify=False)
        
        if resp.status_code == 200:
            return jsonify({
                "Developer": "Rolex ❤️‍🔥",
                "uid": uid, 
                "new_bio": new_bio, 
                "status": "Success",
                "method_used": "Facebook Access Token Converted" if access_token else "Direct JWT Token",
                "message": "Bio Changed Successfully in Game!"
            })
        return jsonify({"error": f"Server returned {resp.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ============================================================
# 4. WISHLIST JSON ROUTE
# ============================================================
@app.route('/wishlist', methods=['GET'])
def handle_wishlist_check():
    uid = request.args.get("uid")
    if not uid: return jsonify({"error": "UID required"}), 400
    server_name = request.args.get("server_name", "IND").upper()

    tokens = load_tokens()
    if not tokens: update_tokens(5); tokens = load_tokens()
    if not tokens: return jsonify({"error": "No tokens"}), 500

    token = tokens[0]['token']
    result, error = check_wishlist(uid, server_name, token)

    if error:
        update_tokens(5); tokens = load_tokens()
        if tokens: result, error = check_wishlist(uid, server_name, tokens[0]['token'])

    if error: return jsonify({"error": error}), 500
    
    new_wishlist_data = []
    for item in result.get("wishlist_data", []):
        item_copy = item.copy()
        if item.get("value", 0) > 100000:
            item_copy["icon_link"] = f"https://freefire.api.ffmod.com/images/items/{item['value']}.webp"
        
        new_nested = []
        for nested in item.get("nested", []):
            nested_copy = nested.copy()
            if nested.get("value", 0) > 100000:
                nested_copy["icon_link"] = f"https://freefire.api.ffmod.com/images/items/{nested['value']}.webp"
            new_nested.append(nested_copy)
        item_copy["nested"] = new_nested
        new_wishlist_data.append(item_copy)
    
    result["wishlist_data"] = new_wishlist_data
    return jsonify(result)

# ============================================================
# 5. WISHLIST ZIP DOWNLOADER ROUTE
# ============================================================
@app.route('/wishlist_zip', methods=['GET'])
def handle_wishlist_zip():
    uid = request.args.get("uid")
    if not uid: return jsonify({"error": "UID required"}), 400
    server_name = request.args.get("server_name", "IND").upper()

    tokens = load_tokens()
    if not tokens: update_tokens(5); tokens = load_tokens()
    if not tokens: return jsonify({"error": "No tokens"}), 500

    token = tokens[0]['token']
    result, error = check_wishlist(uid, server_name, token)

    if error:
        update_tokens(5); tokens = load_tokens()
        if tokens: result, error = check_wishlist(uid, server_name, tokens[0]['token'])

    if error: return jsonify({"error": error}), 500

    item_ids = set()
    for item in result.get("wishlist_data", []):
        if item.get("value", 0) > 100000:
            item_ids.add(item["value"])
        for nested in item.get("nested", []):
            if nested.get("value", 0) > 100000:
                item_ids.add(nested["value"])

    if not item_ids:
        return jsonify({"error": "Wishlist is empty or no valid items found."}), 404

    files = asyncio.run(download_visible_images(item_ids))

    valid_files = [(fname, fdata) for fname, fdata in files if fname and fdata]
    
    if not valid_files:
        return jsonify({"error": "Wishlist items mili, par Garena aur Community dono servers se photos download nahi ho payi."}), 404

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, filedata in valid_files:
            zf.writestr(filename, filedata)
            
    memory_file.seek(0)
    
    return send_file(
        memory_file, 
        mimetype='application/zip', 
        as_attachment=True, 
        download_name=f"{uid}_FreeFire_Wishlist.zip"
    )

if __name__ == '__main__':
    start_token_refresh_thread()
    app.run(debug=True, use_reloader=False)

