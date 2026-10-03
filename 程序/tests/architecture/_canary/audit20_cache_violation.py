def publish_without_cache_event(gateway):
    gateway.replace_file('temporary.json', 'formal.json')
