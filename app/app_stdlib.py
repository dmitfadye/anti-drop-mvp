"""Анти-Дроп MVP — LEGACY фолбэк на stdlib (T10–T12 исправлены, но путь не поддерживается).

Основной путь — FastAPI (main.py). Этот файл оставлен для офлайн-диагностики ядра
на машине без зависимостей. Отличия от основного пути зафиксированы:
- квиз отдаётся БЕЗ правильных ответов (как в /api/content);
- НЕ выставлять в сеть (однопоточный, без лимитов кроме базового cap тела).
Запуск: python3 app_stdlib.py  ->  http://localhost:8000
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.alerts import SUPPORTED_LANGS, build_stop_drop_alert
from src.detector import analyze_transactions
from src.quiz import QUIZ, STORIES, check_quiz
from src.sim_security import start_number_change

PORT = 8000
MAX_BODY = 1_000_000  # T12: базовый предел тела POST (фолбэк не для сети)

# T10: публичный квиз без correct — как в FastAPI /api/content.
PUBLIC_QUIZ = [{"q": item["q"], "options": item["options"]} for item in QUIZ]

PAGE = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Анти-Дроп — защита от дроп-схем</title>
<style>
*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
body{margin:0;background:#0f172a;color:#e2e8f0}
header{background:linear-gradient(90deg,#dc2626,#f59e0b);color:#fff;padding:18px 24px}
header h1{margin:0;font-size:22px}header p{margin:4px 0 0;opacity:.95;font-size:14px}
main{max-width:980px;margin:0 auto;padding:20px}
.tabs{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.tabs button{border:0;border-radius:10px;padding:10px 18px;cursor:pointer;font-size:15px;background:#1e293b;color:#e2e8f0}
.tabs button.active{background:#f59e0b;color:#111}
.card{background:#1e293b;border-radius:14px;padding:18px;margin-bottom:16px;border:1px solid #334155}
.card h2{margin-top:0;font-size:18px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
button.primary{background:#22c55e;border:0;color:#06270f;font-weight:700;border-radius:10px;padding:12px 18px;cursor:pointer;font-size:15px}
button.danger{background:#dc2626;border:0;color:#fff;font-weight:700;border-radius:10px;padding:12px 18px;cursor:pointer;font-size:15px}
button.ghost{background:#334155;border:0;color:#fff;border-radius:10px;padding:10px 14px;cursor:pointer}
select,input{border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;padding:10px;font-size:15px}
.badge{display:inline-block;padding:6px 14px;border-radius:20px;font-weight:700}
.green{background:#166534}.yellow{background:#92400e}.red{background:#991b1b;animation:blink 1s infinite}
@keyframes blink{50%{opacity:.6}}
#alertBox{display:none;background:#7f1d1d;border:3px solid #ef4444;border-radius:14px;padding:18px;margin-bottom:16px}
#alertBox.show{display:block}
#alertBox pre{white-space:pre-wrap;background:#450a0a;padding:12px;border-radius:8px;color:#fecaca}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{border-bottom:1px solid #334155;padding:6px;text-align:left}
.story{background:#0f172a;border-left:4px solid #f59e0b;padding:10px 12px;margin:8px 0;border-radius:0 8px 8px 0}
.q{margin:12px 0;padding:12px;background:#0f172a;border-radius:8px}
.q label{display:block;margin:6px 0;cursor:pointer}
.ok{color:#4ade80}.fail{color:#f87171}
.bar{height:14px;background:#334155;border-radius:7px;overflow:hidden;margin:8px 0}
.bar>div{height:100%;background:linear-gradient(90deg,#22c55e,#f59e0b,#dc2626)}
small.mut{color:#94a3b8}
</style></head><body>
<header><h1>🛡️ Анти-Дроп: защита и адаптация</h1>
<p>Сервис финансовой безопасности для нерезидентов • 115-ФЗ • ст. 187 УК РФ • MVP хакатона</p></header>
<main>
<div class="tabs">
<button class="active" onclick="tab('dash',this)">📊 Дашборд мониторинга</button>
<button onclick="tab('quiz',this)">🎓 Онбординг + квиз</button>
<button onclick="tab('sim',this)">📱 Смена номера</button>
</div>

<div id="t-dash">
<div class="card"><h2>1. Мониторинг карты <span id="scoreBadge" class="badge green">GREEN • 0</span></h2>
<div class="bar"><div id="scoreBar" style="width:0%"></div></div>
<div class="row">
<label>Язык алерта: <select id="lang"><option value="ru">Русский</option><option value="uz">O'zbekcha</option><option value="tg">Тоҷикӣ</option><option value="ky">Кыргызча</option><option value="en">English</option><option value="zh">中文</option><option value="ar">العربية</option></select></label>
<button class="ghost" onclick="loadScenario('normal')">✅ Норма</button>
<button class="danger" onclick="loadScenario('attack')">🔥 Симулировать атаку вербовщика</button>
<button class="primary" onclick="analyze()">🔍 Проверить</button>
</div><small class="mut">Атака = 5 мелких входящих от разных людей за 25 мин + вывод дальше. Детектор ищет транзит, веер, обнал, ночь, SIM.</small></div>
<div id="alertBox"><h2 id="alertTitle" style="margin-top:0"></h2><pre id="alertBody"></pre>
<div class="row"><button class="primary" onclick="alert('Обращение №'+Math.floor(Math.random()*9000+1000)+' создано. Поддержка свяжется за 2 минуты. Карта временно заморожена на исходящие.')">📞 Связаться с поддержкой</button>
<button class="ghost" onclick="document.getElementById('alertBox').classList.remove('show')">Я всё понял, скрыть</button></div></div>
<div class="card"><h2>Транзакции</h2><div style="overflow-x:auto"><table><thead><tr><th>Время</th><th>Тип</th><th>Сумма ₽</th><th>Контрагент</th></tr></thead><tbody id="txTable"></tbody></table></div></div>
<div class="card"><h2>Почему так решили (объяснимый скоринг)</h2><ul id="reasons"><li><small class="mut">Нажмите «Проверить».</small></li></ul></div>
</div>

<div id="t-quiz" style="display:none">
<div class="card"><h2>📚 Микро-сторис: почему нельзя отдавать карту</h2><div id="stories"></div></div>
<div class="card"><h2>📝 Квиз — кешбэк 100 ₽ за ≥4 правильных</h2><div id="quizBox"></div>
<div class="row"><button class="primary" onclick="sendQuiz()">Получить результат</button></div><div id="quizRes" style="margin-top:10px"></div></div>
</div>

<div id="t-sim" style="display:none">
<div class="card"><h2>📱 Безопасная смена номера (защита от перехвата SMS)</h2>
<div class="row"><input id="oldP" placeholder="Старый: +79160000001" value="+79160000001"><input id="newP" placeholder="Новый: +79160000002" value="+79160000002"></div>
<div class="row" style="margin-top:8px"><label><input type="checkbox" id="otpO"> SMS-код со старого ✓</label><label><input type="checkbox" id="otpN"> SMS-код с нового ✓</label>
<button class="primary" onclick="sendSim()">Сменить номер</button></div>
<div id="simRes" style="margin-top:10px"></div>
<small class="mut">Без кода со старого номера смену запрещаем. После смены — 24ч кулдаун: P2P до 5 000 ₽.</small></div>
</div>
</main>
<script>
let TXNS=[];
const SCEN={
normal:[
["2026-10-06 09:00","incoming_salary",60000,"работодатель"],
["2026-10-06 12:10","purchase",1200,"магнит"],
["2026-10-06 18:40","purchase",800,"аптека"],
["2026-10-07 09:15","purchase",1500,"пятёрочка"]],
attack:[
["2026-10-07 13:00","incoming_salary",15000,"стройка"],
["2026-10-07 14:02","incoming_p2p",3000,"отправитель_1"],
["2026-10-07 14:07","incoming_p2p",2500,"отправитель_2"],
["2026-10-07 14:12","incoming_p2p",4000,"отправитель_3"],
["2026-10-07 14:20","incoming_p2p",1800,"отправитель_4"],
["2026-10-07 14:25","incoming_p2p",3500,"отправитель_5"],
["2026-10-07 14:40","outgoing_p2p",9000,"кошелёк_вербовщика"],
["2026-10-07 14:45","cash_withdraw",5000,"банкомат"]]};
function tab(id,btn){document.querySelectorAll('.tabs button').forEach(b=>b.classList.remove('active'));btn.classList.add('active');
["dash","quiz","sim"].forEach(t=>document.getElementById('t-'+t).style.display=t===id?"block":"none");}
function loadScenario(k){TXNS=SCEN[k].map((r,i)=>({id:String(i),user_id:"u777",ts:r[0]+":00",type:r[1],amount:r[2],counterparty:r[3],device_id:"dev_X",sim_changed_days_ago:k==="attack"?1:90}));renderTx();analyze();}
function renderTx(){document.getElementById('txTable').innerHTML=TXNS.map(t=>`<tr><td>${t.ts.slice(5)}</td><td>${t.type}</td><td>${t.amount}</td><td>${t.counterparty}</td></tr>`).join("");}
async function analyze(){if(!TXNS.length)loadScenario('normal');
const lang=document.getElementById('lang').value;
const r=await(await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({transactions:TXNS,lang})})).json();
const b=document.getElementById('scoreBadge');b.textContent=r.level+' • '+r.score;
b.className='badge '+(r.level==='RED'?'red':r.level==='YELLOW'?'yellow':'green');
document.getElementById('scoreBar').style.width=r.score+'%';
document.getElementById('reasons').innerHTML=r.reasons.map(x=>`<li>${x}</li>`).join("");
const ab=document.getElementById('alertBox');
if(r.alert){ab.classList.add('show');document.getElementById('alertTitle').textContent=r.alert.title+' ('+r.alert.lang_name+')';document.getElementById('alertBody').textContent=r.alert.body;}
else ab.classList.remove('show');}
const STORIES=__STORIES__,QUIZ=__QUIZ__;
document.getElementById('stories').innerHTML=STORIES.map(s=>`<div class="story"><b>${s.emoji} ${s.title}</b><br>${s.text}</div>`).join("");
document.getElementById('quizBox').innerHTML=QUIZ.map((q,i)=>`<div class="q"><b>В${i+1}. ${q.q}</b>${q.options.map((o,j)=>`<label><input type="radio" name="q${i}" value="${j}"> ${o}</label>`).join("")}</div>`).join("");
async function sendQuiz(){const ans=QUIZ.map((_,i)=>{const el=document.querySelector(`input[name=q${i}]:checked`);return el?+el.value:-1;});
const r=await(await fetch('/api/quiz',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers:ans})})).json();
document.getElementById('quizRes').innerHTML=`<b class="${r.passed?'ok':'fail'}">${r.message} (${r.score}/${r.total})</b>`+r.details.map(d=>`<div><span class="${d.ok?'ok':'fail'}">${d.ok?'✓':'✗'}</span> ${d.explain}</div>`).join("");}
async function sendSim(){const body={old_phone:document.getElementById('oldP').value,new_phone:document.getElementById('newP').value,otp_ok_old:document.getElementById('otpO').checked,otp_ok_new:document.getElementById('otpN').checked};
const r=await(await fetch('/api/sim',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
document.getElementById('simRes').innerHTML=r.ok?`<b class="ok">${r.message}</b><br>Лимиты: ${r.limits.note}<br>`+r.checklist.map(c=>`<div>${c}</div>`).join(""):`<b class="fail">Запрещено:</b><br>`+r.errors.map(e=>`<div>• ${e}</div>`).join("");}
loadScenario('normal');
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj: dict, code: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, html: str):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlparse(self.path).path in ("/", "/index.html"):
            html = PAGE.replace("__STORIES__", json.dumps(STORIES, ensure_ascii=False)).replace(
                "__QUIZ__", json.dumps(PUBLIC_QUIZ, ensure_ascii=False))
            self._html(html)
        elif self.path == "/api/langs":
            self._json(SUPPORTED_LANGS)
        else:
            self.send_error(404, "Not found")  # T11: только ASCII в reason

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._json({"error": "Некорректный Content-Length"}, 400)
        if length > MAX_BODY:  # T12: не читаем сверх лимита
            return self._json({"error": "Тело запроса слишком большое"}, 413)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "Некорректный JSON"}, 400)
        path = urlparse(self.path).path

        if path == "/api/analyze":
            txns = body.get("transactions", [])
            lang = body.get("lang", "ru")
            res = analyze_transactions(txns)
            out = dict(res)
            if res["level"] == "RED":
                m = res["metrics"]
                out["alert"] = build_stop_drop_alert(
                    lang, m.get("small_incoming_60m_sum", 0),
                    m.get("small_incoming_60m_senders", 0), res["score"])
            else:
                out["alert"] = None
            return self._json(out)

        if path == "/api/quiz":
            return self._json(check_quiz(body.get("answers", [])))

        if path == "/api/sim":
            return self._json(start_number_change(
                body.get("old_phone", ""), body.get("new_phone", ""),
                bool(body.get("otp_ok_old")), bool(body.get("otp_ok_new"))))

        return self._json({"error": "Unknown API"}, 404)


def main():
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🛡️  Анти-Дроп MVP: http://localhost:{PORT}\n"
          "Демо жюри: нажмите «Симулировать атаку вербовщика».\nОстановка: Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")


if __name__ == "__main__":
    main()
