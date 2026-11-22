import os, subprocess, sys, tempfile, time
from pathlib import Path
import httpx
root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(dir=root/'integration-staging') as directory:
    env=dict(os.environ, DB_PATH=str(Path(directory)/'test.db'), PORT='18080', DEBUG='false', HOST='127.0.0.1')
    process=subprocess.Popen([sys.executable, str(root/'run_server.py')], cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for attempt in range(40):
            try:
                response=httpx.get('http://127.0.0.1:18080/health',timeout=1)
                if response.status_code==200: break
            except httpx.HTTPError: pass
            if process.poll() is not None: raise RuntimeError('Server exited')
            time.sleep(.25)
        else: raise RuntimeError('Server failed to start')
        assert httpx.get('http://127.0.0.1:18080/api/films').json()==[]
        payload={'name':'Smoke','email':'smoke@example.com','password':'test12345'}
        assert httpx.post('http://127.0.0.1:18080/api/auth/register',json=payload).status_code==201
        response=httpx.post('http://127.0.0.1:18080/api/auth/login',json=payload)
        assert response.status_code==200
        assert response.json()['user']['name']=='Smoke'
        print('Live server: health, empty database catalogue, registration and login passed')
    finally:
        process.terminate()
        process.wait(timeout=10)
