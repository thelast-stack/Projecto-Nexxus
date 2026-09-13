from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from nexxus_logistica import Demand, LogisticsUnit, Point, Resource, create_plan, create_operation, validate_demand, create_replanned_plan, LogisticsException, ExceptionState, OperationState

DEMANDS={}; RESOURCES={}; PLANS={}; OPERATIONS={}; EXCEPTIONS={}; MEASUREMENTS={}

def page(body):
    return '<!doctype html><html lang="pt"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEXXUS Logística</title><style>body{font-family:Arial;max-width:980px;margin:auto;background:#f5f6f8;padding:24px;color:#20242a}.card{background:#fff;padding:22px;margin:14px 0;border-radius:10px;box-shadow:0 1px 4px #0001}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.field{margin:10px 0}.field label{display:block;font-weight:bold;margin-bottom:5px}input,textarea,select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #ccd1d6;border-radius:6px}button,a.btn{padding:10px 14px;background:#20242a;color:white;border:0;border-radius:6px;text-decoration:none;cursor:pointer}a.secondary{background:#e8eaed;color:#20242a}.muted{color:#68707a}.flow span{display:inline-block;padding:7px 10px;background:#e9ebee;border-radius:6px;margin:3px}.active{background:#20242a!important;color:white}.ok{padding:10px;background:#e9f6ec}.warn{padding:10px;background:#fff1d8}</style><body>'+body+'</body></html>'

def val(data,k): return data.get(k,[''])[0].strip()
def form(handler):
    n=int(handler.headers.get('Content-Length',0)); return parse_qs(handler.rfile.read(n).decode())

class App(BaseHTTPRequestHandler):
    def send_page(self,b,code=200):
        d=page(b).encode(); self.send_response(code); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(d))); self.end_headers(); self.wfile.write(d)
    def redirect(self,p): self.send_response(303); self.send_header('Location',p); self.end_headers()
    def do_GET(self):
        p=urlparse(self.path)
        if p.path=='/':
            cards=''.join(f'<div class="card"><h3>Demanda #{d.id}</h3><p>{d.unit.quantity:g} {d.unit.unit} · {d.origin.name} → {d.destination.name}</p><p><b>{d.state.value}</b></p><a class="btn" href="/operation?id={d.id}">Abrir</a></div>' for d in DEMANDS.values())
            return self.send_page('<h1>NEXXUS LOGÍSTICA</h1><p class="muted">Demanda → Planeamento → Preparação → Execução → Exceção/Replaneamento → Resultado.</p><p><a class="btn" href="/new">+ Nova demanda</a></p>' + (cards or '<div class="card">Nenhuma demanda.</div>'))
        if p.path=='/new':
            return self.send_page('''<h1>Nova demanda</h1><p class="muted">Aqui descrevemos apenas a necessidade. Recurso e capacidade entram no planeamento.</p><form method="post" action="/create"><div class="card"><h3>Quem solicita?</h3><div class="field"><label>Cliente / solicitante *</label><input name="client" required></div></div><div class="card"><h3>O que precisa ser movimentado?</h3><div class="grid"><div class="field"><label>Descrição *</label><input name="description" placeholder="Ex.: Farinha de trigo" required></div><div class="field"><label>Quantidade *</label><input name="quantity" type="number" min="0.01" step="0.01" required></div><div class="field"><label>Unidade *</label><select name="unit"><option>t</option><option>kg</option><option>un</option></select></div></div></div><div class="card"><h3>De onde para onde?</h3><div class="grid"><div class="field"><label>Origem *</label><input name="origin" required></div><div class="field"><label>Destino *</label><input name="destination" required></div></div></div><div class="card"><h3>Quando e em que condições?</h3><div class="grid"><div class="field"><label>Prazo</label><input name="deadline" type="datetime-local"></div><div class="field"><label>Condições / restrições</label><input name="conditions"></div></div><div class="field"><label>Observações</label><textarea name="notes"></textarea></div></div><button>Criar e validar demanda</button> <a class="btn secondary" href="/">Cancelar</a></form>''')
        if p.path=='/operation':
            oid=val(parse_qs(p.query),'id'); d=DEMANDS.get(oid); op=OPERATIONS.get(oid)
            if not d: return self.send_page('<h1>Demanda não encontrada</h1>',404)
            state=op.state if op else d.state
            flow='<div class="flow"><span class="active">Demanda</span><span class="active">Planeamento</span><span class="active">Operação</span><span class="active">Execução</span><span>Resultado</span></div>'
            pedido=f'<div class="card"><h2>Demanda</h2><p><b>Solicitante:</b> {d.conditions[0] if d.conditions else "—"}</p><p><b>O que:</b> {getattr(d,"description","")} · <b>Quantidade:</b> {d.unit.quantity:g} {d.unit.unit}</p><p><b>Origem:</b> {d.origin.name} → <b>Destino:</b> {d.destination.name}</p><p><b>Prazo:</b> {d.deadline or "não definido"}</p><p><b>Estado:</b> {state.value}</p></div>'
            action=''
            if not op:
                action=f'<div class="card"><h2>Planeamento</h2><p>Escolha o recurso e a capacidade para esta demanda.</p><form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="plan"><div class="grid"><div class="field"><label>Recurso *</label><input name="resource" placeholder="Camião 01" required></div><div class="field"><label>Capacidade ({d.unit.unit}) *</label><input name="capacity" type="number" min="0.01" step="0.01" required></div></div><button>Criar plano</button></form></div>'
            elif state==OperationState.PLANNED:
                action=f'<div class="card"><h2>Operação planeada</h2><p>Plano v{PLANS[oid].version} · Recurso: {RESOURCES[oid].name} · Capacidade: {RESOURCES[oid].capacity:g} {d.unit.unit}</p><p>Etapas: '+', '.join(s.name for s in op.stages)+f'</p><form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="prepare"><button>Preparar operação</button></form></div>'
            elif state==OperationState.PREPARED:
                action=f'<div class="card"><h2>Operação preparada</h2><p>Todas as etapas estão preparadas.</p><form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="start"><button>Iniciar execução</button></form></div>'
            elif state==OperationState.IN_EXECUTION:
                current=next((s for s in op.stages if s.state.value=='in_execution'),None); pending=next((s for s in op.stages if s.state.value=='prepared'),None)
                stage_action=''
                if current: stage_action=f'<p>Etapa em execução: <b>{current.name}</b></p><form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="complete_stage"><input type="hidden" name="stage_id" value="{current.id}"><button>Concluir etapa</button></form>'
                elif pending: stage_action=f'<p>Próxima etapa: <b>{pending.name}</b></p><form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="start_stage"><input type="hidden" name="stage_id" value="{pending.id}"><button>Iniciar etapa</button></form>'
                action=f'<div class="card"><h2>Execução</h2>{stage_action}<hr><form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="event"><div class="field"><label>Evento</label><input name="description" placeholder="Ex.: Saiu da origem às 10h" required></div><button>Registar evento</button></form><hr><form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="exception"><div class="field"><label>Exceção</label><input name="description" placeholder="Ex.: Avaria do veículo" required></div><button>Registar exceção</button></form></div>'
                if all(s.state.value=='completed' for s in op.stages): action+='<div class="card"><form method="post" action="/action"><input type="hidden" name="id" value="%s"><input type="hidden" name="action" value="complete"><div class="grid"><div class="field"><label>Resultado</label><input name="result" required></div><div class="field"><label>Evidência</label><input name="evidence" required></div></div><button>Concluir operação</button></form></div>'%oid
            elif state==OperationState.EXCEPTION:
                ex=op.exceptions[-1]; action=f'<div class="card warn"><h2>⚠ Exceção — necessita intervenção</h2><p><b>Tipo:</b> {ex.type} · <b>Gravidade:</b> {ex.severity}</p><p><b>Impacto:</b> {ex.impact}</p><form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="replan"><div class="field"><label>Decisão / novo plano</label><input name="description" placeholder="Ex.: Substituir veículo" required></div><button>Replanear e retomar</button></form></div>'
            else:
                m=MEASUREMENTS.get(oid,{})
                action=f'<div class="card ok"><h2>Operação concluída</h2><p><b>Resultado:</b> {op.result}</p><p><b>Evidência:</b> {op.evidence}</p><p><b>Desvio de duração:</b> {m.get("duration_deviation_hours","—")} h</p></div>'
            timeline=''.join(f'<li>{e.timestamp:%H:%M:%S} — <b>{e.type}</b> — {e.description}</li>' for e in op.events) if op else '<li>Demanda criada e validada</li>'
            stages=''.join(f'<li>{s.sequence}. {s.name} — <b>{s.state.value}</b></li>' for s in op.stages) if op else ''
            return self.send_page(f'<h1>Demanda #{oid}</h1>{flow}{pedido}{action}<div class="card"><h2>Etapas</h2><ol>{stages}</ol></div><div class="card"><h2>Linha do tempo</h2><ol>{timeline}</ol></div><a class="btn secondary" href="/">Voltar</a>')
        return self.send_page('<h1>404</h1>',404)
    def do_POST(self):
        d=form(self); q=lambda k:val(d,k)
        if self.path=='/create':
            try: qty=float(q('quantity'))
            except ValueError: qty=0
            if qty<=0 or not q('client') or not q('description') or not q('origin') or not q('destination') or q('origin')==q('destination'): return self.send_page('<h1>Validação falhou</h1><p>Preencha solicitante, descrição, quantidade, origem e destino corretamente.</p>',400)
            oid=f"D-{len(DEMANDS)+1:03d}"; deadline=datetime.fromisoformat(q('deadline')) if q('deadline') else None
            demand=Demand(oid,LogisticsUnit(f"U-{len(DEMANDS)+1:03d}",qty,q('unit')),Point(f"P-{len(DEMANDS)+1:03d}A",q('origin')),Point(f"P-{len(DEMANDS)+1:03d}B",q('destination')),deadline,conditions=[q('client'),q('conditions'),q('notes')])
            demand.description=q('description'); validate_demand(demand); DEMANDS[oid]=demand; self.redirect('/operation?id='+oid); return
        if self.path=='/action':
            oid=q('id'); d=DEMANDS[oid]; action=q('action'); op=OPERATIONS.get(oid)
            if action=='plan':
                try: cap=float(q('capacity'))
                except ValueError: cap=0
                r=Resource(f"R-{oid}",q('resource'),cap,d.unit.unit); p=create_plan(d,r,f"P-{oid}-v1"); o=create_operation(d,p,f"O-{oid}"); RESOURCES[oid]=r; PLANS[oid]=p; OPERATIONS[oid]=o
            elif action=='prepare': op.prepare()
            elif action=='start': op.start()
            elif action=='start_stage': next(s for s in op.stages if s.id==q('stage_id')).start()
            elif action=='complete_stage': next(s for s in op.stages if s.id==q('stage_id')).complete()
            elif action=='event': op.register_event('event',q('description'))
            elif action=='exception':
                e=LogisticsException(f"X-{oid}-{len(op.exceptions)+1}",q('description'),'media','impacto operacional',stage_id=next((s.id for s in op.stages if s.state.value=='in_execution'),None)); EXCEPTIONS[e.id]=e; op.register_exception(e)
            elif action=='replan':
                old=PLANS[oid]; r=RESOURCES[oid]; p=create_replanned_plan(d,r,f"P-{oid}-v{old.version+1}",old); PLANS[oid]=p; ex=op.exceptions[-1]; ex.evaluate(q('description'),'replanear'); ex.treat(q('description')); op.replan(p); ex.close()
            elif action=='complete': op.complete(q('result'),q('evidence')); MEASUREMENTS[oid]=measure_operation(d.unit.quantity,d.unit.quantity,8,9.5)
            self.redirect('/operation?id='+oid); return
        self.redirect('/')

if __name__=='__main__': HTTPServer(('0.0.0.0',8000),App).serve_forever()
