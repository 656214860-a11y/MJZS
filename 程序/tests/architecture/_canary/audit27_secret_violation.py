def log_leak():
    token = os.getenv('SECRET')
    print(token)


def json_leak():
    token = os.getenv('SECRET')
    return json.dumps({'token': token})


def prompt_leak(client):
    token = os.getenv('SECRET')
    return client.send_prompt(f'key={token}')
