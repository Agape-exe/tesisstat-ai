"""Isolated visual QA. Synthetic sources; local provider; no Qwen3 credentials."""
from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.modules.research.dev_app import ResearchDevSettings, create_app
from scripts.demo_context_chat import seed
from scripts.demo_multiagent import DemoProvider
import uvicorn

folder = ROOT / '.cache/uxui-final-qa'
settings = ResearchDevSettings(_env_file=None, cloudflare_account_id='', cloudflare_api_token='', cloudflare_model='simulado-local-sin-red', research_db_path=folder/'qa.sqlite3', research_documents_path=folder/'documents', research_datasets_path=folder/'datasets', cors_origins=['http://127.0.0.1:5179', 'http://127.0.0.1:5180'])
app = create_app(settings=settings, conversation_provider=DemoProvider())
client = TestClient(app)
def call(method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else None
if not client.get('/api/research/projects').json():
    seed(app, include_analysis=False)
    projects = call('GET', '/api/research/projects')
    populated = next(p for p in projects if '1:' in p['title'])
    empty = next(p for p in projects if '2:' in p['title'])
    root = f"/api/research/projects/{populated['id']}"
    document = call('GET', root+'/documents')[0]
    dr = root+f"/documents/{document['id']}"
    call('POST', dr+'/extract')
    review = call('GET', dr+'/methodology/review/status')
    content = review['content']
    finding = lambda value: {'value': value, 'kind':'manual', 'evidence':[]}
    content['general_problem'] = finding('¿Cómo se relacionan las horas y el rendimiento en esta muestra ficticia?')
    content['specific_objectives'] = [finding(s) for s in ['Describir las horas de estudio de la muestra ficticia.', 'Describir el rendimiento de los casos sintéticos.', 'Examinar la relación entre las dos variables sintéticas.']]
    content['observation_design'] = finding('Observaciones independientes')
    review = call('PUT', dr+'/methodology/review', json={'version': review['version'], 'content':content})
    call('POST', dr+'/methodology/review/confirm', json={'version':review['version']})
    config = call('GET', root+'/package/configuration')
    call('PUT', root+'/package/configuration', json=config)
    package = call('POST', root+'/package/build')
    record = call('POST', root+'/analysis/plan', json={'package_id':package['id'], 'hypothesis_id':package['hypotheses'][0]['id']})
    plan_root = root+f"/analysis/plans/{record['plan']['id']}"
    call('POST', plan_root+'/approve', json={'confirm':True, 'proposal_token':record['proposal_token']})
    call('POST', plan_root+'/execute')
    (folder/'ids.json').write_text(json.dumps({'populated':populated['id'],'empty':empty['id']}),encoding='utf-8')
if __name__ == '__main__': uvicorn.run(app,host='127.0.0.1',port=8022)

