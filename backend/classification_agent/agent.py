from celery import Celery

app = Celery('classification_worker')

@app.task
def classify_contract(contract_text: str, contract_id: str):
    return {"status": "ok"}
