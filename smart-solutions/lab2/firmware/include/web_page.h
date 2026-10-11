#pragma once

static const char LAB2_INDEX_HTML[] PROGMEM = R"HTML(
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AtomS3 Lab 2</title>
<style>body{font:15px sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem}
label{display:block;margin:.8rem 0}input{width:100%;box-sizing:border-box;padding:.4rem}
button{margin:.4rem .4rem .4rem 0;padding:.5rem}.note{color:#555}.error{color:#a00}</style>
</head><body><h1>AtomS3 · Lab 2</h1>
<p class="note">Post-office settings foundation. Hardware validation is TODO.</p>
<label>Wi-Fi SSID<input id="ssid" autocomplete="off"></label>
<label>Wi-Fi password<input id="wifiPass" type="password" autocomplete="new-password"></label>
<label>Post-office URL<input id="serverUrl" placeholder="https://lab.example"></label>
<label>Atom API key<input id="atomKey" type="password" autocomplete="new-password"
 placeholder="leave blank to keep stored key"></label>
<label>Polling interval (ms)<input id="pollMs" type="number" min="250" max="60000"></label>
<label><input id="devHttp" type="checkbox" style="width:auto"> Allow HTTP for local development only</label>
<button onclick="save()">SAVE SETTINGS</button><button onclick="testServer()">TEST SERVER HEALTH</button>
<p id="status"></p><hr>
<p>Pressure: unavailable — calibration and sensor integration TODO.</p>
<p class="note">The test performs one GET /health request. It never polls or claims a robot job.</p>
<script>
const statusEl=document.getElementById('status');
async function load(){try{const r=await fetch('/settings');const s=await r.json();
ssid.value=s.ssid||'';serverUrl.value=s.server_url||'';pollMs.value=s.poll_interval_ms||1000;
devHttp.checked=!!s.dev_http;statusEl.textContent='Mode: '+s.wifi_mode+' · '+s.post_office_status;
}catch(e){statusEl.textContent='Load failed: '+e.message;statusEl.className='error'}}
async function save(){const f=new URLSearchParams();f.set('ssid',ssid.value.trim());
f.set('wifi_pass',wifiPass.value);f.set('server_url',serverUrl.value.trim());
f.set('atom_key',atomKey.value);f.set('poll_interval_ms',pollMs.value);
f.set('dev_http',devHttp.checked?'1':'0');const r=await fetch('/settings',{method:'POST',
headers:{'Content-Type':'application/x-www-form-urlencoded'},body:f});const t=await r.text();
statusEl.textContent=t;statusEl.className=r.ok?'':'error';wifiPass.value='';atomKey.value=''}
async function testServer(){statusEl.textContent='Testing health endpoint…';const r=await fetch('/test/post-office',{method:'POST'});
const t=await r.text();statusEl.textContent=t;statusEl.className=r.ok?'':'error'}load();
</script></body></html>)HTML";
