from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
operations=[]; events={}
def page(b): return '<!doctype html><meta charset="utf-8"><title>NEXXUS Logistica</title><style>body{font-family:Arial;max-width:900px;margin:40px auto;background:#f4f5f7;padding:20px}.card{background:white;padding:20px;margin:12px 0;border-radius:10px}input{padding:9px;margin:5px;width:90%}button,a{padding:9px 13px;background:#222;color:white;border:0;border-radius:6px;text-decoration:none}</style>'+b
class App(BaseHTTPRequestHandler):
 def send_page(self,b,code=200):
  d=page(b).encode(); self.send_response(code); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(d))); self.end_headers(); self.wfile.write(d)
 def redirect(self,p): self.send_response(303); self.send_header('Location',p); self.end_headers()
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/':
   cards=''.join('<div class="card"><h3>Operacao #%s</h3><p>%s → %s · %s · <b>%s</b></p><a href="/operation?id=%s">Abrir</a></div>'%(o['id'],o['origin'],o['destination'],o['quantity'],o['state'],o['id']) for o in operations)
   self.send_page('<h1>NEXXUS LOGISTICA</h1><p><a href="/new">+ Nova operacao</a></p>'+(cards or '<div class="card">Nenhuma operacao.</div>')); return
  if p.path=='/new':
   self.send_page('<h1>Nova operacao</h1><form method="post" action="/create"><div class="card">Cliente<br><input name="client" required>Quantidade<br><input name="quantity" required>Unidade<br><input name="unit" value="kg" required>Origem<br><input name="origin" required>Destino<br><input name="destination" required>Recurso<br><input name="resource" required>Capacidade<br><input name="capacity" required><br><button>Criar e validar</button></div></form>'); return
  if p.path=='/operation':
   oid=int(parse_qs(p.query).get('id',['0'])[0]); o=next((x for x in operations if x['id']==oid),None)
   if not o: self.send_page('<h1>Operacao nao encontrada</h1>',404); return
   timeline=''.join('<li><b>%s</b> — %s</li>'%(e[0],e[1]) for e in events.get(oid,[])); s=o['state']
   if s=='PLANEADA': a='<form method="post" action="/action"><input type=hidden name=id value="%s"><input type=hidden name=action value=start><button>Iniciar execucao</button></form>'%oid
   elif s=='EM_EXECUCAO': a='<form method="post" action="/action"><input type=hidden name=id value="%s"><input type=hidden name=action value=event><input name=description placeholder="Saiu de A as 10h" required><button>Registar evento</button></form><form method="post" action="/action"><input type=hidden name=id value="%s"><input type=hidden name=action value=exception><input name=description placeholder="Avaria" required><button>Registar excecao</button></form><form method="post" action="/action"><input type=hidden name=id value="%s"><input type=hidden name=action value=complete><input name=result placeholder="Resultado" required><input name=evidence placeholder="Evidencia/POD" required><button>Concluir</button></form>'%(oid,oid,oid)
   elif s=='EXCECAO': a='<div class="card"><b>⚠ Excecao — necessita intervencao</b><p>%s</p><form method="post" action="/action"><input type=hidden name=id value="%s"><input type=hidden name=action value=replan><input name=description placeholder="Novo plano" required><button>Replanear e retomar</button></form></div>'%(o['exception'],oid)
   else: a='<div class="card"><b>Resultado:</b> %s<br><b>Evidencia:</b> %s</div>'%(o.get('result',''),o.get('evidence',''))
   self.send_page('<h1>Operacao #%s</h1><div class="card">%s · %s %s · %s → %s · %s · <b>%s</b></div>%s<div class="card"><h2>Linha do tempo</h2><ol>%s</ol></div>'%(oid,o['client'],o['quantity'],o['unit'],o['origin'],o['destination'],o['resource'],s,a,timeline)); return
  self.send_page('<h1>404</h1>',404)
 def do_POST(self):
  n=int(self.headers.get('Content-Length',0)); d=parse_qs(self.rfile.read(n).decode()); q=lambda k:d.get(k,[''])[0].strip()
  if self.path=='/create':
   qty=float(q('quantity')); cap=float(q('capacity'))
   if qty<=0 or cap<qty or q('origin')==q('destination'): self.send_page('<h1>Validacao falhou</h1><p>Verifique quantidade, capacidade e origem/destino.</p>',400); return
   oid=len(operations)+1; operations.append({'id':oid,'client':q('client'),'quantity':qty,'unit':q('unit'),'origin':q('origin'),'destination':q('destination'),'resource':q('resource'),'capacity':cap,'state':'PLANEADA'}); events[oid]=[('demanda_validada','Plano inicial criado')]; self.redirect('/operation?id=%s'%oid); return
  if self.path=='/action':
   oid=int(q('id')); o=next(x for x in operations if x['id']==oid); a=q('action'); desc=q('description')
   if a=='start': o['state']='EM_EXECUCAO'; events[oid].append(('inicio','Execucao iniciada'))
   elif a=='event': events[oid].append(('evento',desc))
   elif a=='exception': o['state']='EXCECAO'; o['exception']=desc; events[oid].append(('excecao',desc))
   elif a=='replan': o['state']='EM_EXECUCAO'; events[oid].append(('replaneamento',desc))
   elif a=='complete': o['state']='CONCLUIDA'; o['result']=q('result'); o['evidence']=q('evidence'); events[oid].append(('conclusao',o['result']))
   self.redirect('/operation?id=%s'%oid); return
  self.redirect('/')
if __name__=='__main__': print('NEXXUS Logistica: http://localhost:8000'); HTTPServer(('0.0.0.0',8000),App).serve_forever()
