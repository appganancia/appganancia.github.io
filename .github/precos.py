"""Gera precos.json: o total que o checkout da Cakto cobra em cada pais, para a landing mostrar o mesmo valor.

Le a tabela de paises que o proprio checkout traz embutida (preco local, cambio, margem e imposto de cada pais)
e soma a tarifa de servico (US$ 0,99, convertida com 3% de margem, mais o imposto do pais), que nao vem na tabela.
Conta conferida contra o resumo do checkout em 26/10/2026: Mexico MXN 174,85, Colombia COP 25.415.

uso: python .github/precos.py  ->  escreve precos.json na raiz do site
"""
import json, re, sys, urllib.request
from datetime import datetime, timezone

FRONT, UPSELL = 'fecwm9c', 'izf22iu'
TARIFA_USD, TARIFA_MARGEM = 0.99, 0.03
SEM_CENTAVOS = {'COP', 'CLP', 'PYG', 'CRC', 'ARS', 'JPY', 'KRW', 'HUF', 'ISK', 'VND', 'IDR'}
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'

def paises(oferta):
    req = urllib.request.Request(f'https://pay.cakto.com.br/{oferta}', headers={'User-Agent': UA, 'Accept-Language': 'es'})
    html = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'ignore')
    partes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, flags=re.S)
    rsc = ''.join(json.loads('"' + p + '"') for p in partes)
    i = rsc.find('{"international":true')
    if i < 0:
        raise SystemExit(f'tabela de paises nao encontrada no checkout {oferta}')
    obj, _ = json.JSONDecoder().raw_decode(rsc[i:])
    return {c['country_code']: c for c in obj['countries']}

def margem(c):
    m = ((c.get('spread') or {}).get('methods') or {}).get('credit_card') or {}
    return float(m.get('percentage') or c.get('spread_percentage') or 0) / 100

def total(c):
    """preco local (ja com margem e imposto) + tarifa de servico com imposto, no cartao"""
    fx = c.get('fx') or {}
    taxa = float(fx.get('rate') or 1)
    margem_tarifa = 0 if fx.get('usd_native') else TARIFA_MARGEM  # quem paga em dolar paga US$ 0,99 cravados
    imp = float(c.get('tax_percentage') or 0) / 100
    tarifa = TARIFA_USD * taxa * (1 + margem_tarifa) * (1 + imp)
    return float(c['price_local']) + tarifa

def arred(v, moeda):
    return round(v) if moeda in SEM_CENTAVOS else round(v, 2)

def main():
    f, u = paises(FRONT), paises(UPSELL)
    saida = {}
    for cc, c in sorted(f.items()):
        if c.get('price_local') is None:  # pais onde o checkout nao vende (o Brasil, no produto em dolar)
            continue
        moeda = c['currency']
        item = {'moeda': moeda, 'front': arred(total(c), moeda)}
        b = (c.get('bumps') or [None])[0]
        if b: item['bump'] = arred(float(b['price_local']), moeda)
        if cc in u: item['upsell'] = arred(total(u[cc]), moeda)
        if c.get('tax_name'): item['imposto'] = c['tax_name']
        saida[cc] = item
    if len(saida) < 50 or 'MX' not in saida:
        raise SystemExit('tabela incompleta, nao grava')
    try:  # sem mudanca de preco, nao reescreve (evita commit a cada rodada so pela data)
        if json.load(open('precos.json', encoding='utf-8')).get('paises') == saida:
            print('sem mudanca'); return
    except (OSError, ValueError):
        pass
    doc = {'atualizado': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paises': saida}
    open('precos.json', 'w', encoding='utf-8').write(json.dumps(doc, ensure_ascii=False, separators=(',', ':')))
    print('ok', len(saida), 'paises; MX', saida['MX'], '; CO', saida.get('CO'))

if __name__ == '__main__':
    main()
