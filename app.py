from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

operations = []
events = {}


def page(body):
    return '''<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXXUS Logística</title>
<style>
body{font-family:Arial,sans-serif;max-width:980px;margin:0 auto;background:#f5f6f8;padding:28px;color:#20242a}
h1,h2,h3{margin-top:0}.card{background:#fff;padding:24px;margin:16px 0;border-radius:12px;box-shadow:0 1px 4px #0001}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.field{margin-bottom:16px}.field label{display:block;font-weight:700;margin-bottom:6px}.field small{display:block;color:#68707a;margin-top:5px}
input,textarea,select{box-sizing:border-box;width:100%;padding:11px;border:1px solid #cbd0d6;border-radius:7px;font-size:15px}textarea{min-height:80px;resize:vertical}
button,a.button{display:inline-block;padding:11px 16px;background:#20242a;color:#fff;border:0;border-radius:7px;text-decoration:none;cursor:pointer;font-size:14px}
a.secondary{background:#e9ebee;color:#20242a}.section-title{font-size:18px;margin:4px 0 18px}.muted{color:#68707a}.status{font-weight:700}.flow{display:flex;gap:8px;flex-wrap:wrap}.step{padding:8px 11px;background:#eef0f2;border-radius:7px}.step.active{background:#20242a;color:#fff}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
</style>
</head><body>''' + body + '</body></html>'


class App(BaseHTTPRequestHandler):
    def send_page(self, body, code=200):
        data = page(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, path):
        self.send_response(303)
        self.send_header('Location', path)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/':
            cards = ''.join(
                '<div class="card"><h3>Demanda #%s</h3>'
                '<p>%s · %s %s · %s → %s</p>'
                '<p class="status">Estado: %s</p>'
                '<a class="button" href="/operation?id=%s">Abrir</a></div>'
                % (o['id'], o['client'], o['quantity'], o['unit'], o['origin'],
                   o['destination'], o['state'], o['id'])
                for o in operations
            )
            self.send_page(
                '<h1>NEXXUS LOGÍSTICA</h1>'
                '<p class="muted">Necessidades logísticas → planeamento → execução → resultado.</p>'
                '<p><a class="button" href="/new">+ Nova demanda</a></p>'
                + (cards or '<div class="card">Nenhuma demanda registada.</div>')
            )
            return

        if parsed.path == '/new':
            self.send_page('''
<h1>Nova demanda</h1>
<p class="muted">Nesta etapa descreva o que precisa ser realizado. O recurso e o planeamento serão definidos depois.</p>

<form method="post" action="/create">
<div class="card">
  <div class="section-title">1. Quem solicita?</div>
  <div class="field">
    <label>Cliente / solicitante *</label>
    <input name="client" placeholder="Ex.: Cliente ABC" required>
    <small>Identifica quem originou a necessidade logística.</small>
  </div>
</div>

<div class="card">
  <div class="section-title">2. O que precisa ser movimentado?</div>
  <div class="grid">
    <div class="field">
      <label>O que será movimentado? *</label>
      <input name="description" placeholder="Ex.: Farinha de trigo" required>
    </div>
    <div class="field">
      <label>Quantidade *</label>
      <input name="quantity" type="number" min="0.01" step="0.01" placeholder="Ex.: 20" required>
    </div>
    <div class="field">
      <label>Unidade de medida *</label>
      <select name="unit" required>
        <option value="t">toneladas (t)</option>
        <option value="kg">quilogramas (kg)</option>
        <option value="un">unidades (un)</option>
        <option value="paletes">paletes</option>
        <option value="caixas">caixas</option>
        <option value="volumes">volumes</option>
      </select>
    </div>
  </div>
</div>

<div class="card">
  <div class="section-title">3. De onde para onde?</div>
  <div class="grid">
    <div class="field">
      <label>Origem *</label>
      <input name="origin" placeholder="Ex.: Fábrica Viana" required>
    </div>
    <div class="field">
      <label>Destino *</label>
      <input name="destination" placeholder="Ex.: Armazém Luanda" required>
    </div>
  </div>
</div>

<div class="card">
  <div class="section-title">4. Quando e em que condições?</div>
  <div class="grid">
    <div class="field">
      <label>Data limite</label>
      <input name="deadline" type="date">
      <small>Quando a necessidade deve estar satisfeita.</small>
    </div>
    <div class="field">
      <label>Hora limite</label>
      <input name="deadline_time" type="time">
    </div>
  </div>
  <div class="field">
    <label>Condições / restrições</label>
    <textarea name="conditions" placeholder="Ex.: carga seca, horário de receção, cuidados especiais..."></textarea>
  </div>
  <div class="field">
    <label>Observações</label>
    <textarea name="notes" placeholder="Informação adicional relevante para o planeamento."></textarea>
  </div>
</div>

<div class="card">
  <p class="muted"><b>O que ainda não é definido aqui:</b> veículo, motorista, recurso, capacidade, rota ou plano. Essas decisões pertencem à etapa de planeamento.</p>
  <button type="submit">Criar e validar demanda</button>
  <a class="button secondary" href="/">Cancelar</a>
</div>
</form>''')
            return

        if parsed.path == '/operation':
            query = parse_qs(parsed.query)
            oid = int(query.get('id', ['0'])[0])
            operation = next((x for x in operations if x['id'] == oid), None)
            if not operation:
                self.send_page('<h1>Demanda não encontrada</h1>', 404)
                return

            timeline = ''.join('<li><b>%s</b> — %s</li>' % e for e in events.get(oid, []))
            state = operation['state']

            if state == 'DEMANDA_VALIDADA':
                action = '''<div class="card"><h2>Próxima etapa</h2>
<p>A demanda está validada. Agora o NEXXUS pode entrar no planeamento e procurar recursos/capacidade.</p>
<form method="post" action="/action">
<input type="hidden" name="id" value="%s"><input type="hidden" name="action" value="plan">
<div class="grid"><div class="field"><label>Recurso</label><input name="resource" placeholder="Ex.: Camião 01" required></div>
<div class="field"><label>Capacidade</label><input name="capacity" type="number" min="0.01" step="0.01" required></div></div>
<button>Confirmar planeamento</button></form></div>''' % oid
            elif state == 'PLANEADA':
                action = '''<div class="card"><h2>Operação planeada</h2><p>Recurso alocado: <b>%s</b> · Capacidade: <b>%s</b></p>
<form method="post" action="/action"><input type="hidden" name="id" value="%s"><input type="hidden" name="action" value="start"><button>Iniciar execução</button></form></div>''' % (operation['resource'], operation['capacity'], oid)
            elif state == 'EM_EXECUCAO':
                action = '''<div class="card"><h2>Execução</h2>
<form method="post" action="/action"><input type="hidden" name="id" value="%s"><input type="hidden" name="action" value="event">
<div class="field"><label>Evento ocorrido</label><input name="description" placeholder="Ex.: Saiu da origem às 10h" required></div><button>Registar evento</button></form>
<hr>
<form method="post" action="/action"><input type="hidden" name="id" value="%s"><input type="hidden" name="action" value="exception">
<div class="field"><label>Exceção</label><input name="description" placeholder="Ex.: Avaria do veículo" required></div><button>Registar exceção</button></form>
<hr>
<form method="post" action="/action"><input type="hidden" name="id" value="%s"><input type="hidden" name="action" value="complete">
<div class="grid"><div class="field"><label>Resultado</label><input name="result" placeholder="Ex.: Entrega realizada" required></div><div class="field"><label>Evidência</label><input name="evidence" placeholder="Ex.: POD-001 / assinatura" required></div></div><button>Concluir operação</button></form></div>''' % (oid, oid, oid)
            elif state == 'EXCECAO':
                action = '''<div class="card"><h2>⚠ Exceção — necessita intervenção</h2><p>%s</p>
<form method="post" action="/action"><input type="hidden" name="id" value="%s"><input type="hidden" name="action" value="replan">
<div class="field"><label>Novo plano / decisão</label><input name="description" placeholder="Ex.: Substituir veículo e retomar às 14h" required></div><button>Replanear e retomar</button></form></div>''' % (operation.get('exception', ''), oid)
            else:
                action = '<div class="card"><h2>Resultado</h2><p><b>Resultado:</b> %s</p><p><b>Evidência:</b> %s</p></div>' % (operation.get('result', ''), operation.get('evidence', ''))

            self.send_page('''
<h1>Demanda #%s</h1>
<div class="flow"><span class="step active">Demanda</span><span class="step">Planeamento</span><span class="step">Execução</span><span class="step">Resultado</span></div>
<div class="card"><h2>Pedido</h2>
<p><b>Solicitante:</b> %s</p><p><b>O que:</b> %s · <b>Quantidade:</b> %s %s</p>
<p><b>Origem:</b> %s → <b>Destino:</b> %s</p><p><b>Prazo:</b> %s %s</p>
<p><b>Condições:</b> %s</p><p><b>Observações:</b> %s</p><p class="status">Estado: %s</p></div>
%s
<div class="card"><h2>Linha do tempo</h2><ol>%s</ol></div>
<a class="button secondary" href="/">Voltar</a>''' % (
                oid, operation['client'], operation['description'], operation['quantity'], operation['unit'],
                operation['origin'], operation['destination'], operation.get('deadline', 'Não definida'),
                operation.get('deadline_time', ''), operation.get('conditions', 'Nenhuma'),
                operation.get('notes', 'Nenhuma'), state, action, timeline))
            return

        self.send_page('<h1>404</h1>', 404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = parse_qs(self.rfile.read(length).decode())
        q = lambda key: data.get(key, [''])[0].strip()

        if self.path == '/create':
            try:
                quantity = float(q('quantity'))
            except ValueError:
                quantity = 0

            if quantity <= 0 or not q('client') or not q('description') or not q('origin') or not q('destination') or q('origin') == q('destination'):
                self.send_page('<h1>Validação falhou</h1><p>Verifique solicitante, item, quantidade e origem/destino.</p>', 400)
                return

            oid = len(operations) + 1
            operations.append({
                'id': oid,
                'client': q('client'),
                'description': q('description'),
                'quantity': quantity,
                'unit': q('unit'),
                'origin': q('origin'),
                'destination': q('destination'),
                'deadline': q('deadline'),
                'deadline_time': q('deadline_time'),
                'conditions': q('conditions'),
                'notes': q('notes'),
                'state': 'DEMANDA_VALIDADA'
            })
            events[oid] = [('demanda', 'Demanda criada e validada')]
            self.redirect('/operation?id=%s' % oid)
            return

        if self.path == '/action':
            oid = int(q('id'))
            operation = next(x for x in operations if x['id'] == oid)
            action = q('action')

            if action == 'plan':
                try:
                    capacity = float(q('capacity'))
                except ValueError:
                    capacity = 0
                if capacity < operation['quantity']:
                    self.send_page('<h1>Planeamento não pode ser confirmado</h1><p>A capacidade disponível é inferior à quantidade da demanda.</p>', 400)
                    return
                operation['resource'] = q('resource')
                operation['capacity'] = capacity
                operation['state'] = 'PLANEADA'
                events[oid].append(('planeamento', 'Recurso %s alocado com capacidade %s' % (q('resource'), capacity)))

            elif action == 'start':
                operation['state'] = 'EM_EXECUCAO'
                events[oid].append(('inicio', 'Execução iniciada'))

            elif action == 'event':
                events[oid].append(('evento', q('description')))

            elif action == 'exception':
                operation['state'] = 'EXCECAO'
                operation['exception'] = q('description')
                events[oid].append(('excecao', q('description')))

            elif action == 'replan':
                operation['state'] = 'EM_EXECUCAO'
                events[oid].append(('replaneamento', q('description')))

            elif action == 'complete':
                operation['state'] = 'CONCLUIDA'
                operation['result'] = q('result')
                operation['evidence'] = q('evidence')
                events[oid].append(('conclusao', operation['result']))

            self.redirect('/operation?id=%s' % oid)
            return

        self.redirect('/')


if __name__ == '__main__':
    print('NEXXUS Logística: http://localhost:8000')
    HTTPServer(('0.0.0.0', 8000), App).serve_forever()
