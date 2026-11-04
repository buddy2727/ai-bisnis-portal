import os
import sqlite3
import hashlib
import json
import secrets
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "drm_license.db")
EBOOK_HTML_PATH = r"d:\EBOOK\AI-BISNIS-EBOOK\09_FINAL\AI-Untuk-Bisnis-100Plus.html"

app = FastAPI(title="Budianto Ebook DRM Portal")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE NOT NULL,
        buyer_name TEXT NOT NULL,
        buyer_email TEXT NOT NULL,
        buyer_phone TEXT,
        created_at TEXT NOT NULL,
        max_devices INTEGER DEFAULT 2,
        is_active INTEGER DEFAULT 1
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT NOT NULL,
        device_fingerprint TEXT NOT NULL,
        device_name TEXT,
        user_agent TEXT,
        ip_address TEXT,
        registered_at TEXT NOT NULL,
        last_accessed_at TEXT NOT NULL,
        UNIQUE(license_key, device_fingerprint),
        FOREIGN KEY(license_key) REFERENCES licenses(license_key)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS access_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT,
        device_fingerprint TEXT,
        ip_address TEXT,
        action TEXT,
        status TEXT,
        timestamp TEXT NOT NULL
    )
    """)
    cursor.execute("SELECT COUNT(*) FROM licenses")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO licenses (license_key, buyer_name, buyer_email, buyer_phone, created_at, max_devices)
        VALUES ('AI-BUDIANTO-DEMO-2026', 'Pelanggan Demo', 'demo@bisnis.com', '081234567890', datetime('now'), 2)
        """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_device_access(license_key: str, fingerprint: str, user_agent: str, ip: str):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM licenses WHERE license_key = ? AND is_active = 1", (license_key,))
    lic = cursor.fetchone()
    if not lic:
        conn.close()
        return False, "Lisensi tidak ditemukan atau sudah dinonaktifkan."
    
    cursor.execute("SELECT * FROM devices WHERE license_key = ? AND device_fingerprint = ?", (license_key, fingerprint))
    dev = cursor.fetchone()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if dev:
        cursor.execute("UPDATE devices SET last_accessed_at = ?, ip_address = ? WHERE id = ?", (now_str, ip, dev["id"]))
        conn.commit()
        conn.close()
        return True, "Authorized"
    
    cursor.execute("SELECT COUNT(*) as cnt FROM devices WHERE license_key = ?", (license_key,))
    count = cursor.fetchone()["cnt"]
    max_dev = lic["max_devices"]
    
    if count >= max_dev:
        cursor.execute("""
        INSERT INTO access_logs (license_key, device_fingerprint, ip_address, action, status, timestamp)
        VALUES (?, ?, ?, 'NEW_DEVICE_ATTEMPT', 'BLOCKED_MAX_DEVICES_REACHED', ?)
        """, (license_key, fingerprint, ip, now_str))
        conn.commit()
        conn.close()
        return False, f"AKSES DITOLAK: Batas maksimal ({max_dev} perangkat) untuk lisensi ini telah tercapai. Anda tidak dapat membuka ebook ini di perangkat ketiga."
    
    dev_name = "Desktop / Laptop" if ("Windows" in user_agent or "Macintosh" in user_agent or "Linux" in user_agent) else "Smartphone / Tablet"
    cursor.execute("""
    INSERT INTO devices (license_key, device_fingerprint, device_name, user_agent, ip_address, registered_at, last_accessed_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (license_key, fingerprint, dev_name, user_agent[:250], ip, now_str, now_str))
    
    cursor.execute("""
    INSERT INTO access_logs (license_key, device_fingerprint, ip_address, action, status, timestamp)
    VALUES (?, ?, ?, 'NEW_DEVICE_REGISTERED', 'SUCCESS', ?)
    """, (license_key, fingerprint, ip, now_str))
    
    conn.commit()
    conn.close()
    return True, "Authorized"

LOGIN_HTML = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Portal Baca Resmi — AI Untuk Bisnis by Budianto</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/fingerprintjs2/2.1.4/fingerprint2.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: radial-gradient(circle at 50% 20%, #0b152d, #030712);
      color: #f8fafc;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .auth-card {
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid #1e3a8a;
      backdrop-filter: blur(12px);
      border-radius: 20px;
      padding: 40px;
      max-width: 480px;
      width: 100%;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
      text-align: center;
    }
    .badge {
      display: inline-block;
      background: linear-gradient(135deg, #d97706, #fbbf24);
      color: #030712;
      font-weight: 800;
      font-size: 11px;
      padding: 4px 12px;
      border-radius: 20px;
      letter-spacing: 1px;
      margin-bottom: 16px;
    }
    h1 {
      font-size: 24px;
      font-weight: 900;
      color: #ffffff;
      margin-bottom: 8px;
      line-height: 1.25;
    }
    p.sub {
      font-size: 13.5px;
      color: #94a3b8;
      margin-bottom: 24px;
      line-height: 1.5;
    }
    .input-group {
      text-align: left;
      margin-bottom: 18px;
    }
    label {
      display: block;
      font-size: 12px;
      font-weight: 700;
      color: #cbd5e1;
      margin-bottom: 6px;
      letter-spacing: 0.5px;
    }
    input {
      width: 100%;
      padding: 13px 16px;
      background: #0b1329;
      border: 1.5px solid #1e293b;
      border-radius: 10px;
      color: #ffffff;
      font-size: 14.5px;
      font-family: inherit;
      outline: none;
      transition: all 0.2s;
    }
    input:focus {
      border-color: #38bdf8;
      box-shadow: 0 0 12px rgba(56, 189, 248, 0.3);
    }
    .btn-login {
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #2563eb, #0284c7);
      border: none;
      border-radius: 10px;
      color: #ffffff;
      font-size: 15px;
      font-weight: 800;
      cursor: pointer;
      transition: all 0.2s;
      margin-top: 10px;
    }
    .btn-login:hover {
      opacity: 0.95;
      transform: translateY(-1px);
      box-shadow: 0 8px 20px rgba(37, 99, 235, 0.4);
    }
    .error-box {
      display: none;
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid #ef4444;
      color: #fca5a5;
      padding: 12px;
      border-radius: 8px;
      font-size: 13px;
      margin-bottom: 18px;
      text-align: left;
      line-height: 1.4;
    }
    .device-info {
      background: rgba(30, 41, 59, 0.5);
      border: 1px dashed #334155;
      border-radius: 10px;
      padding: 12px;
      margin-top: 24px;
      font-size: 11.5px;
      color: #94a3b8;
      text-align: left;
      line-height: 1.5;
    }
    .device-info strong { color: #38bdf8; }
  </style>
</head>
<body>
  <div class="auth-card">
    <div class="badge">SISTEM VALIDASI LISENSI RESMI</div>
    <h1>AI UNTUK BISNIS</h1>
    <p class="sub">The Master Playbook 100+ Industri<br>Karya Eksklusif: <strong>Budianto</strong></p>

    <div id="errorBox" class="error-box"></div>

    <form id="loginForm">
      <div class="input-group">
        <label>KODE LISENSI ANDA (DARI LYNK.ID)</label>
        <input type="text" id="licenseKey" placeholder="Contoh: AI-BUDIANTO-XXXX-XXXX" required>
      </div>

      <button type="submit" id="submitBtn" class="btn-login">Verifikasi &amp; Buka Ebook</button>
    </form>

    <div class="device-info">
      🔒 <strong>Ketentuan Akses Lisensi:</strong><br>
      • Lisensi ini berlaku untuk <strong>maksimal 2 perangkat</strong> (misal: 1 HP + 1 Laptop).<br>
      • Perangkat ke-3 otomatis diblokir oleh server keamanan.<br>
      • Hak Cipta dilindungi undang-undang atas nama <strong>Budianto</strong>.
    </div>
  </div>

  <script>
    let deviceFingerprint = null;

    if (window.Fingerprint2) {
      Fingerprint2.get(function(components) {
        var values = components.map(function(pair) { return pair.value; });
        deviceFingerprint = Fingerprint2.x64hash128(values.join(''), 31);
      });
    }

    document.getElementById('loginForm').addEventListener('submit', async function(e) {
      e.preventDefault();
      var errBox = document.getElementById('errorBox');
      var submitBtn = document.getElementById('submitBtn');
      var licenseKey = document.getElementById('licenseKey').value.trim();

      if (!deviceFingerprint) {
        var nav = window.navigator;
        var screen = window.screen;
        var str = nav.userAgent + screen.width + screen.height + screen.colorDepth;
        var hash = 0;
        for (var i = 0; i < str.length; i++) {
          hash = ((hash << 5) - hash) + str.charCodeAt(i);
          hash |= 0;
        }
        deviceFingerprint = 'DEV-' + Math.abs(hash).toString(16);
      }

      submitBtn.innerText = 'Memverifikasi Perangkat...';
      submitBtn.disabled = true;
      errBox.style.display = 'none';

      try {
        var res = await fetch('/api/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            license_key: licenseKey,
            fingerprint: deviceFingerprint
          })
        });
        var data = await res.json();
        
        if (data.success) {
          sessionStorage.setItem('drm_token', data.token);
          sessionStorage.setItem('buyer_info', JSON.stringify(data.buyer));
          window.location.href = '/reader';
        } else {
          errBox.innerText = data.message;
          errBox.style.display = 'block';
          submitBtn.innerText = 'Verifikasi & Buka Ebook';
          submitBtn.disabled = false;
        }
      } catch (err) {
        errBox.innerText = 'Terjadi kesalahan jaringan. Silakan coba lagi.';
        errBox.style.display = 'block';
        submitBtn.innerText = 'Verifikasi & Buka Ebook';
        submitBtn.disabled = false;
      }
    });
  </script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request, key: Optional[str] = None):
    return HTMLResponse(content=LOGIN_HTML)

@app.post("/api/verify")
async def verify_api(request: Request):
    try:
        body = await request.json()
        license_key = body.get("license_key", "").strip()
        fingerprint = body.get("fingerprint", "").strip()
    except Exception:
        return JSONResponse({"success": False, "message": "Format data tidak valid."}, status_code=400)
    
    if not license_key or not fingerprint:
        return JSONResponse({"success": False, "message": "Kode lisensi dan tanda perangkat diperlukan."}, status_code=400)
    
    user_agent = request.headers.get("user-agent", "Unknown")
    client_ip = request.client.host if request.client else "Unknown"
    
    allowed, message = check_device_access(license_key, fingerprint, user_agent, client_ip)
    
    if not allowed:
        return JSONResponse({"success": False, "message": message}, status_code=403)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT buyer_name, buyer_email, buyer_phone FROM licenses WHERE license_key = ?", (license_key,))
    buyer = cursor.fetchone()
    conn.close()
    
    token = hashlib.sha256(f"{license_key}:{fingerprint}:BUDIANTO_SECRET_2026".encode()).hexdigest()
    
    return {
        "success": True,
        "token": token,
        "buyer": {
            "name": buyer["buyer_name"],
            "email": buyer["buyer_email"],
            "phone": buyer["buyer_phone"],
            "key": license_key
        }
    }

READER_HTML = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Membaca Ebook — AI Untuk Bisnis by Budianto</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 0;
      background: #0f172a;
      color: #1e293b;
      font-family: 'Plus Jakarta Sans', sans-serif;
      overflow-x: hidden;
      user-select: none;
      -webkit-user-select: none;
    }
    .top-bar {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 58px;
      background: #0b1329;
      border-bottom: 1.5px solid #1e3a8a;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      z-index: 9999;
      color: #ffffff;
      box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .brand-title {
      font-size: 15px;
      font-weight: 800;
      color: #38bdf8;
      letter-spacing: 0.5px;
    }
    .user-pill {
      font-size: 11.5px;
      background: #1e293b;
      border: 1px solid #334155;
      padding: 6px 14px;
      border-radius: 20px;
      color: #94a3b8;
    }
    .user-pill strong { color: #fbbf24; }
    .btn-exit {
      background: #dc2626;
      color: white;
      border: none;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 11.5px;
      font-weight: 700;
      cursor: pointer;
    }
    .reader-container {
      max-width: 960px;
      margin: 80px auto 40px auto;
      background: #ffffff;
      padding: 40px 60px;
      border-radius: 12px;
      box-shadow: 0 10px 40px rgba(0,0,0,0.4);
      position: relative;
    }
    .watermark-grid {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      pointer-events: none;
      z-index: 9998;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-around;
      align-content: space-around;
      opacity: 0.12;
      overflow: hidden;
    }
    .watermark-item {
      transform: rotate(-25deg);
      font-size: 15px;
      font-weight: 800;
      color: #000000;
      white-space: nowrap;
      padding: 40px;
    }
    @media print {
      body { display: none !important; }
    }
  </style>
</head>
<body oncontextmenu="return false;" onkeydown="return preventKeys(event);">
  <div class="top-bar">
    <div class="brand-title">📘 AI UNTUK BISNIS — THE MASTER PLAYBOOK</div>
    <div class="user-pill" id="userPill">Memuat lisensi...</div>
    <button class="btn-exit" onclick="logout()">Keluar</button>
  </div>

  <div class="watermark-grid" id="watermarkGrid"></div>

  <div class="reader-container" id="bookContent">
    <div style="text-align: center; padding: 60px; color: #64748b;">
      <h3>Sedang memuat dokumen terenkripsi...</h3>
    </div>
  </div>

  <script>
    var token = sessionStorage.getItem('drm_token');
    var buyerRaw = sessionStorage.getItem('buyer_info');

    if (!token || !buyerRaw) {
      alert('Sesi tidak valid atau telah berakhir. Silakan login kembali.');
      window.location.href = '/';
    }

    var buyer = JSON.parse(buyerRaw);
    document.getElementById('userPill').innerHTML = 'Lisensi: <strong>' + buyer.email + '</strong>';

    var wmContainer = document.getElementById('watermarkGrid');
    var wmText = 'Dilisensikan Kepada: ' + buyer.email + ' • Hak Cipta © 2026 Budianto';
    for (var i = 0; i < 24; i++) {
      var el = document.createElement('div');
      el.className = 'watermark-item';
      el.innerText = wmText;
      wmContainer.appendChild(el);
    }

    async function loadContent() {
      try {
        var res = await fetch('/api/book-content', {
          headers: { 'Authorization': 'Bearer ' + token }
        });
        if (res.ok) {
          var html = await res.text();
          document.getElementById('bookContent').innerHTML = html;
        } else {
          alert('Akses konten ditolak oleh server.');
          window.location.href = '/';
        }
      } catch (err) {
        document.getElementById('bookContent').innerHTML = '<p style="color:red;">Gagal memuat konten. Periksa koneksi Anda.</p>';
      }
    }
    loadContent();

    function preventKeys(e) {
      if ((e.ctrlKey && (e.key === 'p' || e.key === 's' || e.key === 'u')) || e.key === 'F12') {
        e.preventDefault();
        alert('Fitur penyimpanan, pencetakan, dan inspeksi kode dinonaktifkan demi perlindungan hak cipta.');
        return false;
      }
    }

    function logout() {
      sessionStorage.clear();
      window.location.href = '/';
    }
  </script>
</body>
</html>"""

@app.get("/reader", response_class=HTMLResponse)
async def reader_page(request: Request):
    return HTMLResponse(content=READER_HTML)

@app.get("/api/book-content")
async def get_book_content(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if os.path.exists(EBOOK_HTML_PATH):
        with open(EBOOK_HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            start = content.find("<body>")
            end = content.find("</body>")
            if start != -1 and end != -1:
                inner_html = content[start+6:end]
            else:
                inner_html = content
            return HTMLResponse(content=inner_html)
    else:
        return HTMLResponse(content="<h1>File buku sedang disiapkan di server.</h1>")

@app.post("/api/webhook/lynkid")
async def lynkid_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored"}
    
    buyer_email = data.get("customer_email") or data.get("email") or "buyer@lynk.id"
    buyer_name = data.get("customer_name") or data.get("name") or "Pembeli Lynk.id"
    buyer_phone = data.get("customer_phone") or data.get("phone") or ""
    
    random_part = secrets.token_hex(4).upper()
    random_part2 = secrets.token_hex(4).upper()
    license_key = f"AI-BUD-{random_part}-{random_part2}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO licenses (license_key, buyer_name, buyer_email, buyer_phone, created_at, max_devices)
    VALUES (?, ?, ?, ?, ?, 2)
    """, (license_key, buyer_name, buyer_email, buyer_phone, now_str))
    conn.commit()
    conn.close()
    
    print(f"[Lynk.id Webhook] License generated for {buyer_email}: {license_key}")
    return {"status": "success", "license_key": license_key}

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT l.*, COUNT(d.id) as device_count 
    FROM licenses l 
    LEFT JOIN devices d ON l.license_key = d.license_key 
    GROUP BY l.id 
    ORDER BY l.id DESC
    """)
    licenses = cursor.fetchall()
    conn.close()
    
    rows = ""
    for lic in licenses:
        rows += f"""
        <tr>
          <td><strong>{lic['license_key']}</strong></td>
          <td>{lic['buyer_name']}<br><small style="color:#64748b;">{lic['buyer_email']}</small></td>
          <td><span style="font-weight:bold; color:{'#16a34a' if lic['device_count'] <= 1 else '#ea580c'};">{lic['device_count']} / {lic['max_devices']}</span></td>
          <td>{'✅ Aktif' if lic['is_active'] else '❌ Dinonaktifkan'}</td>
          <td><a href="/admin/reset?key={lic['license_key']}" style="color:#dc2626; font-weight:bold; text-decoration:none;">Reset Perangkat</a></td>
        </tr>
        """
        
    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Admin Dashboard — DRM Lisensi Budianto</title>
  <style>
    body {{ font-family: sans-serif; background: #f8fafc; padding: 30px; }}
    .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
    th, td {{ padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: left; font-size: 14px; }}
    th {{ background: #f1f5f9; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>🔑 Dashboard Lisensi Ebook (Maksimal 2 Perangkat)</h2>
    <p>Kelola lisensi pembeli, kuota perangkat, dan integrasi Lynk.id.</p>
    <table>
      <thead>
        <tr>
          <th>Kode Lisensi</th>
          <th>Nama &amp; Email Pembeli</th>
          <th>Perangkat Terdaftar</th>
          <th>Status</th>
          <th>Aksi</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/admin/reset")
async def reset_device(key: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices WHERE license_key = ?", (key,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin")

if __name__ == "__main__":
    import uvicorn
    print("Starting Budianto DRM Server on http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
