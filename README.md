# Аудиториска вежба 2 — Docker (9-13.2026)

---

## Чекор 1 — Стартување на база во контејнер

Pull и стартувај PostgreSQL image:

```bash
docker pull postgres:16.1
docker run --name pg-lab -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=secret -e POSTGRES_DB=labdb -p 54321:5432 -d postgres:16.1
```

Провери дека контејнерот работи:

```bash
docker ps
```

---

## Чекор 2 — Vibe-code на backend апликација

Користете ChatGPT / Copilot / Claude со следниот prompt:

> *"Create a simple Python Flask app with one POST /items endpoint that saves a name and description to a PostgreSQL database. All config (DB host, port, name, user, password) must come from environment variables. No hardcoded values."*

Структурата на проектот треба да изгледа вака:

```
app/
├── app.py
├── requirements.txt
└── .env
```

### `app.py`

```python
import os
import psycopg2
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", 5432),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.route("/items", methods=["POST"])
def create_item():
    data = request.get_json()
    name = data.get("name")
    description = data.get("description", "")

    if not name:
        return jsonify({"error": "name is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO items (name, description) VALUES (%s, %s) RETURNING id;",
        (name, description)
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"id": new_id, "name": name, "description": description}), 201

@app.route("/items", methods=["GET"])
def get_items():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM items;")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    items = [{"id": r[0], "name": r[1], "description": r[2]} for r in rows]
    return jsonify(items), 200


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("APP_PORT", 5000)))
```

### `requirements.txt`

```
flask
psycopg2-binary
python-dotenv
```

### `.env`

```env
DB_HOST=localhost
DB_PORT=54321
DB_NAME=labdb
DB_USER=admin
DB_PASSWORD=secret
APP_PORT=5000
```

---

## Чекор 3 — Стартување локално (без Docker)

```bash
cd app
pip install -r requirements.txt
export $(cat .env | xargs)
python app.py
```

---

## Чекор 4 — Тестирање и преглед во базата

Испрати POST барање:

```bash
curl -X POST http://localhost:5000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "description": "hello docker"}'
```

Или GET за да ги видиш сите записи:

```bash
curl http://localhost:5000/items
```

Провери директно во базата преку контејнерот:

```bash
docker exec -it pg-lab psql -U admin -d labdb \
  -c "SELECT * FROM items;"
```

✅ Податоците се запишани во базата.

---

## Чекор 5 — Пишување Dockerfile

Креирај `Dockerfile` во `app/` директориумот:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

what each lines mean?

Билдај image:

```bash
docker build -t flask-lab .
```

---

## Чекор 6 — Стартување на апликацијата во контејнер (со грешка)

```bash
docker run --name flask-app -e DB_HOST=localhost -e DB_PORT=54321 -e DB_NAME=labdb -e DB_USER=admin -e DB_PASSWORD=secret -p 5000:5000 flask-lab
```

Повтори го тест барањето:

```bash
curl -X POST http://localhost:5000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "test2", "description": "from container"}'
```

❌ **Грешка:** `connection refused` / `could not connect to server`

**Зошто?** `localhost` внатре во контејнерот не е твојот компјутер — тоа е самиот контејнер. Базата не е таму.

---

## Чекор 7 — Решавање со Docker network IP

Најди ја IP адресата на `pg-lab` контејнерот:

```bash
docker network inspect bridge \
  --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}}{{"\n"}}{{end}}'
```

Ќе добиеш нешто како `pg-lab: 172.17.0.2/16`. Сега рестартирај го `flask-app` со вистинскиот `DB_HOST`:

```bash
docker stop flask-app && docker rm flask-app

docker run --name flask-app -e DB_HOST=172.17.0.2 -e DB_PORT=5432 -e DB_NAME=labdb -e DB_USER=admin -e DB_PASSWORD=secret -p 5000:5000 flask-lab
```

what if i run it with -d flass-app
why is it now DB_PORT 5432 instead of 54321?

Тест повторно:

```bash
curl -X POST http://localhost:5000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "test3", "description": "fixed with IP"}'
```

✅ Работи — податоците се запишани.

---

## Чекор 8 — Заклучок и најава за следниот час

Размислете:

- Ако имаме 6 контејнери, треба рачно да ги наоѓаме IP адресите на сите?
- Ако контејнерот се рестартира, IP адресата може да се промени — што тогаш?

**Ова не скалира.**

Следниот час → **Docker Compose**, каде контејнерите комуницираат по **service name** наместо по IP адреса, а целата инфраструктура се дефинира во еден `docker-compose.yml` фајл.