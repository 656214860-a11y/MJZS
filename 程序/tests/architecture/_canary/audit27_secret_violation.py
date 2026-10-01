def leak():
    token = os.getenv('SECRET')
    print(token)
