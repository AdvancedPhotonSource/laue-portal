from celery import Celery

result_backend = 'db+sqlite:///results.sqlite'
app = Celery('hello', broker='amqp://guest@localhost//', backend=result_backend)

@app.task
def hello():
    return 'hello world'


app.start()