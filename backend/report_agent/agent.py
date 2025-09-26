from celery import Celery

app = Celery('report_worker')

@app.task
def generate_report(validation_results: dict, contract_id: str):
    return {"status": "ok"}
