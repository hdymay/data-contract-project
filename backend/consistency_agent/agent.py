from celery import Celery

app = Celery('consistency_validation_worker')

@app.task
def validate_contract(contract_data: dict, contract_id: str):
    return {"status": "ok"}
