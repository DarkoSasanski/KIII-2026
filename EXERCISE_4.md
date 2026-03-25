# Аудиториска вежба 3 — Docker Compose + GitHub Actions CI/CD

---

## Чекор 1 — Docker Compose

Наместо да стартуваме контејнери еден по еден со `docker run`, Docker Compose ни овозможува да ја опишеме целата инфраструктура во еден `docker-compose.yaml` фајл.

Создај `docker-compose.yaml` во root на проектот:

```yaml
services:
  backend:
    image: ${DOCKERHUB_USERNAME}/flask-lab:latest
    ports:
      - "5000:5000"
    environment:
      DB_HOST: db
      DB_PORT: 5432
      DB_NAME: labdb
      DB_USER: admin
      DB_PASSWORD: secret
    depends_on:
      - db

  db:
    image: postgres:16.1
    ports:
      - "54321:5432"
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: labdb
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Забележи:
- `DB_HOST: db` — контејнерот за backend го достигнува PostgreSQL по **service name** `db`, не по IP адреса
- `depends_on` — Compose го стартува `db` пред `backend`
- `volumes` — податоците во базата се **persistent**, не се губат при `docker-compose down`
- `${DOCKERHUB_USERNAME}` — се чита од `.env` фајл или од environment на shell-от

Стартувај:

```bash
export DOCKERHUB_USERNAME=tvojoto_ime
docker-compose up
```

Или со `.env` фајл (Compose го чита автоматски):

```env
DOCKERHUB_USERNAME=tvojoto_ime
```

```bash
docker-compose up
```

Провери:

```bash
curl http://localhost:5000/items
```

Запри ги контејнерите (со зачувување на volumes):

```bash
docker-compose down
```

Запри и избриши ги volumes:

```bash
docker-compose down -v
```

> **Дискусија:** Зошто `docker-compose down -v` е опасно во production?

---

## Чекор 2 — Зошто `image:` наместо `build:`?

Во претходната вежба имавме нешто вака:

```yaml
backend:
  build: .        # Compose сам го билда image-от секој пат
```

Ова е соодветно за локален development, но **не е добра практика за production** зашто:

- Секој `docker-compose up` потенцијално билда нов image
- Нема гаранција дека истиот код е деплојран на секој сервер
- Нема верзионирање — не знаеш точно кој image е пуштен

Со `image: username/flask-lab:latest` го користиме **веќе билдан и тестиран image** кој живее на DockerHub. Ова значи:

```
CI/CD pipeline → билда → тестира → push на DockerHub → deploy го зема готовиот image
```

✅ Секој environment (dev, staging, production) го стартува **ист image**.

---

## Чекор 3 — GitHub Actions: Структура на workflow

GitHub Actions е CI/CD платформа вградена во GitHub. Секој workflow е `.yml` фајл во `.github/workflows/`.

Создај `.github/workflows/docker-build-push.yml`:

```yaml
name: Docker Build and Push

on:
  push:
    branches:
      - main
```

`on: push: branches: main` значи — овој workflow се извршува автоматски при секој push на `main` branch.

> **Дискусија:** Кога би додале `pull_request` наместо или покрај `push`?

---

## Чекор 4 — Job 1: Lint и Security Scan

```yaml
jobs:
  lint:
    name: Lint & Security Scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Lint Dockerfile (hadolint)
        uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: Dockerfile

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install bandit
        run: pip install bandit

      - name: Security scan (bandit)
        run: bandit -r app.py
```

Две алатки:

**hadolint** — линтер за Dockerfile. Проверува дали Dockerfile следи best practices:
- Дали користиш `COPY` наместо `ADD`?
- Дали pin-уваш верзии на пакети?
- Дали комбинираш `RUN` команди со `&&`?

**bandit** — SAST (Static Application Security Testing) алатка за Python. Скенира за безбедносни проблеми:
- Hardcoded passwords
- SQL injection ризици
- Небезбедни криптографски функции
- Небезбедна употреба на `subprocess`, `eval`, итн.

> **Дискусија:** Што е разликата помеѓу `lint` и `security scan`? Може ли кодот да помине lint а да биде небезбеден?

---

## Чекор 5 — Job 2: Build & Push со услов (`needs`)

```yaml
  build-push:
    name: Build & Push to DockerHub
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Log in to DockerHub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build and push image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ secrets.DOCKERHUB_USERNAME }}/flask-lab:latest
```

Клучната линија е:

```yaml
needs: lint
```

Ова значи — `build-push` job **нема да се стартува** доколку `lint` job не поминал успешно. Ако hadolint или bandit најдат проблем, image-от **нема да биде билдан и push-нат**.

```
push → lint (hadolint + bandit)
              ↓ ако помине
         build-push → DockerHub
```

❌ Ако lint fail-ува → build-push се прескокнува, DockerHub не се ажурира.

✅ Ако lint помине → image се билда и push-ува.

> **Дискусија:** Зошто е важно да не push-уваме image ако security scan fail-ува?

---

## Чекор 6 — GitHub Secrets

Забележи дека credentials не се директно во кодот:

```yaml
username: ${{ secrets.DOCKERHUB_USERNAME }}
password: ${{ secrets.DOCKERHUB_TOKEN }}
```

`secrets.*` се читаат од **GitHub Repository Secrets** — енкриптирани вредности кои не се видливи во логовите.

Додај ги на: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Вредност |
|--------|----------|
| `DOCKERHUB_USERNAME` | Твоето DockerHub username |
| `DOCKERHUB_TOKEN` | DockerHub Access Token (не password!) |

За да генерираш DockerHub token: **DockerHub → Account Settings → Security → New Access Token**

> **Дискусија:** Зошто користиме Access Token наместо password? Што се случува ако некој го добие token-от?

---

## Чекор 7 — Тест на pipeline-от

Направи промена во кодот и push-ни на `main`:

```bash
git add .
git commit -m "add docker-compose and CI/CD workflow"
git push origin main
```

Оди на **GitHub → Actions** tab и следи го извршувањето:

1. `lint` job се стартува
2. hadolint го скенира Dockerfile
3. bandit го скенира `app.py`
4. Ако се успешни → `build-push` job се стартува
5. Image се push-ува на DockerHub

Провери на DockerHub дека image-от е таму:

```
https://hub.docker.com/r/<твоето_ime>/flask-lab
```

---

## Чекор 8 — Заклучок

Со оваа вежба имплементиравме основен CI/CD pipeline:

```
git push
    ↓
GitHub Actions
    ↓
Lint + Security Scan    ← го штити квалитетот и безбедноста
    ↓ (само ако помине)
Docker Build + Push     ← го автоматизира deployment artifact-от
    ↓
DockerHub               ← централен image registry
    ↓
docker-compose up       ← го стартува апликацијата со готов image
```

Размислете:

- Сега имаме `latest` tag — ако push-нуваме нов image, старата верзија е изгубена. Како би решиле верзионирање?
- Ако `docker-compose up` го повлекува `latest` — кога точно добива новиот image?
- Дали `depends_on` во Compose гарантира дека базата е **готова** или само дека е **стартувана**?

