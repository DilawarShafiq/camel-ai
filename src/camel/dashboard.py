"""Camel AI web dashboard — the enterprise-grade local UI.

`camel dashboard` starts a local web server and opens a real browser dashboard:
type a URL to audit, watch the health score + findings, and see everything on
your screen. Built on starlette + uvicorn (already dependencies via mcp), so it
adds nothing new to install.
"""

from __future__ import annotations

import json
import webbrowser

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from . import config
from .runner import full_web_audit


async def _home(request):
    return HTMLResponse(_PAGE)


async def _status(request):
    b = config.get_brain()
    import platform
    return JSONResponse({
        "brain": (f"{b['provider']} · {b['model']}" if b else "not configured"),
        "configured": config.is_configured(),
        "platform": f"{platform.system()} {platform.machine()}",
    })


async def _audit(request):
    body = await request.json()
    url = (body.get("url") or "").strip()
    if not url:
        return JSONResponse({"error": "Enter a URL"}, status_code=400)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    real = bool(body.get("real_browser"))
    profile = None
    if real:
        import os
        profile = os.path.join(str(config.CONFIG_DIR), "browser-profile")
        os.makedirs(profile, exist_ok=True)
    result = await full_web_audit(url, headless=not real, max_elements=30,
                                  user_profile=profile)
    return JSONResponse({
        "summary": result["summary"],
        "findings": result["findings"],
        "html": result["html"],
        "login_wall": result["audit"].get("login_wall", False),
    })


async def _run(request):
    body = await request.json()
    goal = (body.get("goal") or "").strip()
    if not goal:
        return JSONResponse({"error": "Enter a goal"}, status_code=400)
    if not config.is_configured():
        return JSONResponse({"error": "Connect a brain first (camel setup)"}, status_code=400)
    from .agent import provider_from_config, run_audit
    text = await run_audit(provider_from_config(), goal, headless=False)
    return JSONResponse({"result": text})


async def _jobs(request):
    from . import scheduler
    if request.method == "POST":
        body = await request.json()
        action = body.get("action")
        if action == "add":
            scheduler.add_job(body["task"], kind=body.get("kind", "audit"),
                              every=body.get("every", "day"), at=body.get("at", "09:00"))
        elif action == "remove":
            scheduler.remove_job(body["id"])
    return JSONResponse({"jobs": scheduler.list_jobs()})


async def _see(request):
    out = {"windows": [], "screen": None}
    try:
        from .vision import VisionSession
        shot = VisionSession().screenshot()
        out["screen"] = f"{shot['screen_width']}x{shot['screen_height']}"
    except Exception:
        pass
    try:
        from .desktop import DesktopSession
        out["windows"] = [w["title"] for w in DesktopSession().list_windows()
                          if w.get("title")]
    except Exception:
        pass
    return JSONResponse(out)


app = Starlette(routes=[
    Route("/", _home),
    Route("/api/status", _status),
    Route("/api/audit", _audit, methods=["POST"]),
    Route("/api/run", _run, methods=["POST"]),
    Route("/api/jobs", _jobs, methods=["GET", "POST"]),
    Route("/api/see", _see),
])


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    import uvicorn
    url = f"http://{host}:{port}"
    print(f"\n  Camel AI dashboard → {url}\n  (Ctrl+C to stop)\n")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    uvicorn.run(app, host=host, port=port, log_level="warning")


_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Camel AI — Dashboard</title>
<style>
 :root{--bg:#0b0f19;--fg:#e5e7eb;--muted:#9aa4b2;--card:#111827;--accent:#4f8cff;--bd:#1f2937}
 *{box-sizing:border-box}body{margin:0;font:15px/1.55 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--fg)}
 header{padding:1.2rem 1.5rem;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:.6rem}
 header h1{font-size:1.3rem;margin:0}.badge{margin-left:auto;font-size:.8rem;color:var(--muted)}
 main{max-width:1000px;margin:0 auto;padding:1.5rem}
 .card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:1.2rem;margin-bottom:1.2rem}
 h2{font-size:1rem;margin:0 0 .8rem}
 input[type=text]{width:100%;padding:.7rem .9rem;border-radius:8px;border:1px solid var(--bd);background:#0d1117;color:var(--fg);font-size:1rem}
 .row{display:flex;gap:.7rem;align-items:center;margin-top:.7rem;flex-wrap:wrap}
 button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:.6rem 1.1rem;font-weight:600;cursor:pointer;font-size:.95rem}
 button.ghost{background:transparent;color:var(--fg);border:1px solid var(--bd)}
 label{color:var(--muted);font-size:.9rem;display:flex;gap:.4rem;align-items:center}
 .score{font-size:2.2rem;font-weight:800}.meta{color:var(--muted);font-size:.9rem}
 .finding{border:1px solid var(--bd);border-radius:8px;padding:.7rem .9rem;margin:.5rem 0}
 .sev{display:inline-block;color:#fff;font-size:.72rem;font-weight:700;padding:.05rem .5rem;border-radius:4px}
 .win{font-size:.9rem;color:var(--muted);padding:.15rem 0}
 .hidden{display:none}.spin{color:var(--muted)}
 a{color:var(--accent)}
</style></head><body>
<header><span style="font-size:1.4rem">🐫</span><h1>Camel AI</h1><span class="badge" id="brain">…</span></header>
<main>
 <div class="card">
  <h2>Test a website</h2>
  <input type="text" id="url" placeholder="example.com  or  your-app.com/login" value="https://example.com">
  <div class="row">
   <button id="run">▶ Run audit</button>
   <label><input type="checkbox" id="real"> Use my logged-in browser</label>
   <span id="status" class="spin"></span>
  </div>
 </div>
 <div class="card hidden" id="result">
  <h2>Result</h2>
  <div><span class="score" id="score">—</span><span class="meta">/100 health</span></div>
  <div class="meta" id="counts"></div>
  <div id="loginwarn" class="hidden" style="color:#fbbf24;margin-top:.5rem"></div>
  <div id="findings" style="margin-top:1rem"></div>
  <p style="margin-top:1rem"><a id="full" href="#" target="_blank">Open full report ↗</a></p>
 </div>
 <div class="card">
  <h2>Do a task (plain English)</h2>
  <input type="text" id="goal" placeholder="log into my portal and download this month's invoices">
  <div class="row"><button id="dorun">▶ Run task</button><span id="runstatus" class="spin"></span></div>
  <div id="runout" class="meta" style="margin-top:.6rem;white-space:pre-wrap"></div>
 </div>
 <div class="card">
  <h2>Scheduled jobs</h2>
  <div class="row">
   <select id="jkind" title="what the job does">
    <option value="audit">Audit a site</option>
    <option value="goal">Do a task</option>
   </select>
   <input type="text" id="jtask" placeholder="https://mysite.com" style="flex:2;min-width:200px">
   <select id="jevery" title="how often">
    <option value="day">daily at</option>
    <option value="hour">hourly</option>
   </select>
   <input type="text" id="jat" placeholder="09:00" value="09:00" style="width:74px">
   <button id="jadd">+ Add</button>
  </div>
  <p class="meta" id="jhint">“Audit a site” tests a URL on a schedule. Pick “Do a task” to run a plain-English goal (needs a brain).</p>
  <div id="joblist" style="margin-top:.7rem"></div>
  <p class="meta">Run <code>camel daemon</code> in a terminal to execute jobs unattended.</p>
 </div>
 <div class="card">
  <h2>See what's on your screen</h2>
  <div class="row"><button class="ghost" id="seebtn">👁 See my windows</button><span id="screen" class="meta"></span></div>
  <div id="wins"></div>
 </div>
</main>
<script>
const SEV={critical:'#dc2626',high:'#ea580c',medium:'#d97706',low:'#6b7280'};
fetch('/api/status').then(r=>r.json()).then(s=>{document.getElementById('brain').textContent='brain: '+s.brain});
document.getElementById('run').onclick=async()=>{
 const url=document.getElementById('url').value;
 const real=document.getElementById('real').checked;
 const st=document.getElementById('status'); st.textContent='Running… opening a browser and clicking every control';
 document.getElementById('run').disabled=true;
 try{
  const r=await fetch('/api/audit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,real_browser:real})});
  const d=await r.json(); if(d.error){st.textContent=d.error;return;}
  document.getElementById('result').classList.remove('hidden');
  document.getElementById('score').textContent=d.summary.score;
  document.getElementById('counts').textContent=`${d.summary.tested} controls · ${d.summary.dead_controls} dead · ${d.summary.a11y_issues} a11y · ${d.summary.console_errors} console errors`;
  const lw=document.getElementById('loginwarn');
  if(d.login_wall){lw.classList.remove('hidden');lw.textContent='🔒 This is a login page — sign in via "Use my logged-in browser" to test the app behind it.';}else{lw.classList.add('hidden');}
  const f=document.getElementById('findings'); f.innerHTML='';
  (d.findings||[]).slice(0,12).forEach(x=>{const el=document.createElement('div');el.className='finding';
   el.innerHTML=`<span class="sev" style="background:${SEV[x.severity]||'#6b7280'}">${x.id} ${x.severity.toUpperCase()}</span> <b>${x.title}</b><div class="meta">${x.suggested_fix}</div>`;f.appendChild(el);});
  const blob=new Blob([d.html],{type:'text/html'});document.getElementById('full').href=URL.createObjectURL(blob);
  st.textContent='Done.';
 }catch(e){st.textContent='Error: '+e;} finally{document.getElementById('run').disabled=false;}
};
document.getElementById('dorun').onclick=async()=>{
 const goal=document.getElementById('goal').value; const st=document.getElementById('runstatus');
 if(!goal){st.textContent='Enter a task';return;} st.textContent='Working…'; document.getElementById('dorun').disabled=true;
 try{const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal})});
  const d=await r.json(); document.getElementById('runout').textContent=d.error||d.result||''; st.textContent=d.error?'':'Done.';
 }catch(e){st.textContent='Error: '+e;} finally{document.getElementById('dorun').disabled=false;}
};
async function loadJobs(){const r=await fetch('/api/jobs');const d=await r.json();const el=document.getElementById('joblist');el.innerHTML='';
 (d.jobs||[]).forEach(j=>{const row=document.createElement('div');row.className='win';
  const when=j.every==='hour'?'hourly':('daily '+j.at);
  row.innerHTML=`• <b>${j.id}</b> ${j.kind}: "${j.task}" — ${when} <a href="#" data-id="${j.id}" style="margin-left:.5rem">remove</a>`;
  row.querySelector('a').onclick=async(e)=>{e.preventDefault();await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'remove',id:j.id})});loadJobs();};
  el.appendChild(row);});}
const jkind=document.getElementById('jkind'), jevery=document.getElementById('jevery');
jkind.onchange=()=>{document.getElementById('jtask').placeholder = jkind.value==='goal'
 ? 'e.g. log into my portal and email me any broken buttons' : 'https://mysite.com';};
document.getElementById('jadd').onclick=async()=>{const task=document.getElementById('jtask').value;
 const at=document.getElementById('jat').value||'09:00'; if(!task)return;
 await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({action:'add',task,kind:jkind.value,every:jevery.value,at})});
 document.getElementById('jtask').value=''; loadJobs();};
loadJobs();
document.getElementById('seebtn').onclick=async()=>{
 const r=await fetch('/api/see');const d=await r.json();
 document.getElementById('screen').textContent=d.screen?('screen '+d.screen):'';
 const w=document.getElementById('wins');w.innerHTML='';
 (d.windows||[]).forEach(t=>{const el=document.createElement('div');el.className='win';el.textContent='• '+t;w.appendChild(el);});
};
</script></body></html>"""
