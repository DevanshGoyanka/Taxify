import urllib.request, json
req = urllib.request.Request('https://uatocpservices.incometax.gov.in/v1/auth/login', method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('clientId', '4fea04621c7b5660dbb12b959a29b0ee')
req.add_header('clientSecret', 'e754ceb48732c4e197658f76bcc69037')
req.add_header('accessMode', 'API')
req.add_header('User-Agent', 'PostmanRuntime/7.28.4')
req.add_header('Accept', '*/*')
req.add_header('Accept-Encoding', 'gzip, deflate, br')
req.add_header('Connection', 'keep-alive')
data = {'data': 'eyJzZXJ2aWNlTmFtZSI6IkVyaUxvZ2luU2VydmljZSIsImVudGl0eSI6IkVSSVAwMTMxODEiLCJwYXNzIjoiRTlNVmJESmdUOUxLNXhpRW5OYkExQT09IiwidGltZVN0YW1wIjoiMjAyNi0wNy0xOFQxNjowNjoxNi43MTlaIn0=', 'sign': 'mock_signature_for_testing', 'eriUserId': 'ERIP013181'}
try:
    with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8')) as f:
        print(f.read().decode('utf-8'))
except Exception as e:
    print('Error:', e)
    if hasattr(e, 'read'):
        try:
            print(e.read().decode('utf-8'))
        except:
            pass
