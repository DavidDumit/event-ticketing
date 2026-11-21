# Event Ticketing & Check-in

A web app for a university student association: organisers create events and
sell tickets, door volunteers check people in and see attendance reports.

> **Assignment 2 in progress.** The Assignment 1 monolith has been split into two
> services along the seam from ADR-2. This is the initial services structure;
> SQL Server, migrations, CI/CD and the Azure deployment come next.

## Structure

| Folder | What it is | Owns |
|---|---|---|
| `services/tickets/` | Tickets service: events, selling, cancelling, ticket validation (JSON API) | its own database: `events`, `tickets` |
| `services/checkin/` | Check-in service: door check-ins and attendance reports (JSON API) | its own database: `check_ins` |
| `ui/` | Static UI (one HTML page + `config.js`), served by nginx locally; calls both services from the browser | — |

Each service has its own `Dockerfile`, `requirements.txt`, schema and tests.

**The seam.** Check-in never reads the tickets database. It calls the tickets
service over HTTP (`tickets_client.py`) for two things:
`GET /tickets/{code}/validate?event_id=` and `GET /events/{id}`.
Every call has a timeout (`TICKETS_TIMEOUT_S`). If tickets is down, a check-in
returns `503 TicketsUnavailable` and the report degrades to check-in's own numbers.

## Run the whole system

Once, create your local `.env` with your own passwords (it is gitignored, never commit it):

```bash
cp .env.example .env     # then edit the three passwords
```

Then:

```bash
docker compose up --build
```

Compose starts SQL Server, runs `db/init.sql` once (the `db-init` job: one database and one
login per service, idempotent), then the two services and the UI. On Apple Silicon, enable
*Use Rosetta for x86_64/amd64 emulation* in Docker Desktop for the SQL Server image.

| URL | What |
|---|---|
| http://localhost:8080 | UI: create events, issue and cancel tickets, door check-in, attendance report, health of both services |
| http://localhost:8001/health | Tickets service |
| http://localhost:8002/health | Check-in service |

Partial failure: `docker compose stop tickets`, then check-in still answers
`/health` with 200 and check-ins return a clear 503.

## Run one service without Docker

```bash
cd services/tickets            # or services/checkin
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PORT=8001 python app.py        # check-in: PORT=8002 TICKETS_URL=http://localhost:8001 python app.py
```

## Azure deployment (initial setup, run once)

Everything runs in my Azure for Students subscription, in **germanywestcentral** (one of the
five regions my subscription allows), in one resource group:

| Resource | Name |
|---|---|
| Resource group | `rg-ddumitrescu-ieu2024` |
| Storage static website (the UI, the public address) | `ddumitrescuieu2024ui` |
| Managed identity the pipeline signs in as (OIDC) | `ddumitrescu-ieu2024-github` |
| Container Apps environment (+ its Log Analytics workspace) | `ddumitrescu-ieu2024-env` |
| Container Apps | `ddumitrescu-ieu2024-tickets`, `ddumitrescu-ieu2024-checkin` |
| SQL server + one serverless database per service (free offer) | `ddumitrescu-ieu2024-sql`: `ddumitrescu-ieu2024-tickets-db`, `ddumitrescu-ieu2024-checkin-db` |

These are the commands I ran, in **bash** (zsh breaks the `repo:...:ref:` subject in step 6).
Passwords are generated into shell variables and go straight into Azure and GitHub secrets;
they are never written to a file. After this, only the CD pipeline changes anything.

```bash
# 1. Subscription and region
az login                                   # pick "Azure for Students"
az policy assignment list --query "[?displayName=='Allowed resource deployment regions'].parameters" -o json
PREFIX=ddumitrescu-ieu2024
RG=rg-$PREFIX
LOCATION=germanywestcentral
SQL_LOCATION=$LOCATION                     # if the free SQL offer isn't available here, use another allowed region
UI_STORAGE=ddumitrescuieu2024ui
GH_REPO=DavidDumit/event-ticketing

# 2. Providers and resource group
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace $p --wait
done
az group create -n $RG -l $LOCATION
RG_ID=$(az group show -n $RG --query id -o tsv)

# 3. The UI: Storage static website
az storage account create -n $UI_STORAGE -g $RG -l $LOCATION --sku Standard_LRS --kind StorageV2
az storage blob service-properties update --account-name $UI_STORAGE --auth-mode key \
  --static-website true --index-document index.html
UI_ORIGIN=$(az storage account show -n $UI_STORAGE -g $RG --query primaryEndpoints.web -o tsv)
echo "Public address: $UI_ORIGIN"

# 4. SQL server, two serverless databases on the free offer, one contained user each
SQL_ADMIN_PASSWORD="Adm1-$(openssl rand -hex 16)"       # used once below, not stored
TICKETS_DB_PASSWORD="Tk1-$(openssl rand -hex 16)"
CHECKIN_DB_PASSWORD="Ck1-$(openssl rand -hex 16)"
az sql server create -n $PREFIX-sql -g $RG -l $SQL_LOCATION --admin-user sqladmin --admin-password "$SQL_ADMIN_PASSWORD"
az sql server firewall-rule create -g $RG -s $PREFIX-sql -n AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
for svc in tickets checkin; do
  az sql db create -g $RG -s $PREFIX-sql -n $PREFIX-$svc-db \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 1 --min-capacity 0.5 \
    --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause
done
MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g $RG -s $PREFIX-sql -n setup-my-ip --start-ip-address $MY_IP --end-ip-address $MY_IP
sqlcmd_az() {   # sqlcmd from the SQL Server image, encrypted connection to Azure SQL
  docker run --rm --platform linux/amd64 mcr.microsoft.com/mssql/server:2022-latest \
    /opt/mssql-tools18/bin/sqlcmd -S "$PREFIX-sql.database.windows.net" -U sqladmin -P "$SQL_ADMIN_PASSWORD" -b "$@"
}
sqlcmd_az -d $PREFIX-tickets-db -Q "CREATE USER tickets_user WITH PASSWORD = '$TICKETS_DB_PASSWORD';
  ALTER ROLE db_ddladmin ADD MEMBER tickets_user; ALTER ROLE db_datareader ADD MEMBER tickets_user; ALTER ROLE db_datawriter ADD MEMBER tickets_user;"
sqlcmd_az -d $PREFIX-checkin-db -Q "CREATE USER checkin_user WITH PASSWORD = '$CHECKIN_DB_PASSWORD';
  ALTER ROLE db_ddladmin ADD MEMBER checkin_user; ALTER ROLE db_datareader ADD MEMBER checkin_user; ALTER ROLE db_datawriter ADD MEMBER checkin_user;"
az sql server firewall-rule delete -g $RG -s $PREFIX-sql -n setup-my-ip     # close it again

# 5. Container Apps (placeholder image; the first deploy replaces it and sets the env vars)
az extension add --name containerapp --upgrade
az containerapp env create -n $PREFIX-env -g $RG -l $LOCATION        # also creates the Log Analytics workspace
for svc in tickets checkin; do
  az containerapp create -n $PREFIX-$svc -g $RG --environment $PREFIX-env \
    --image mcr.microsoft.com/k8se/quickstart:latest \
    --ingress external --target-port 8000 --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi
done
# No ingress CORS: CORS is done in the services' code (UI_ORIGIN), see the guide.

# 6. The pipeline's identity: user-assigned managed identity + federated credentials (OIDC)
az identity create -n $PREFIX-github -g $RG -l $LOCATION
CLIENT_ID=$(az identity show -n $PREFIX-github -g $RG --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show -n $PREFIX-github -g $RG --query principalId -o tsv)
az role assignment create --assignee-object-id $PRINCIPAL_ID --assignee-principal-type ServicePrincipal \
  --role Contributor --scope $RG_ID
az identity federated-credential create -g $RG --identity-name $PREFIX-github -n github-main \
  --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange \
  --subject "repo:${GH_REPO}:ref:refs/heads/main"
NUMERIC_SUBJECT=$(gh api repos/${GH_REPO} --jq '"repo:\(.owner.login)@\(.owner.id)/\(.name)@\(.id):ref:refs/heads/main"')
az identity federated-credential create -g $RG --identity-name $PREFIX-github -n github-main-ids \
  --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange \
  --subject "$NUMERIC_SUBJECT"

# 7. GitHub secrets and variables (gh auth login first)
gh secret set AZURE_CLIENT_ID       -R $GH_REPO --body "$CLIENT_ID"
gh secret set AZURE_TENANT_ID       -R $GH_REPO --body "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID -R $GH_REPO --body "$(az account show --query id -o tsv)"
gh secret set TICKETS_DB_PASSWORD   -R $GH_REPO --body "$TICKETS_DB_PASSWORD"
gh secret set CHECKIN_DB_PASSWORD   -R $GH_REPO --body "$CHECKIN_DB_PASSWORD"
gh variable set PREFIX         -R $GH_REPO --body "$PREFIX"
gh variable set RESOURCE_GROUP -R $GH_REPO --body "$RG"
gh variable set UI_STORAGE     -R $GH_REPO --body "$UI_STORAGE"

# 9. Read access for the professors
for prof in amartini@faculty.ie.edu bserra@faculty.ie.edu; do
  az role assignment create --assignee $prof --role Reader --scope $RG_ID
done
```

### Deploying (CD)

`.github/workflows/cd.yml` runs on every push to `main`: it calls `ci.yml` (tests, then both
images pushed to GHCR tagged with the commit SHA), signs in to Azure as the managed identity
(OIDC, no stored Azure password), points each Container App at `ghcr.io/daviddumit/event-ticketing-<service>:<sha>`
with its `DATABASE_URL` as a Container Apps secret built from the GitHub secret, writes
`ui/config.js` with the services' Azure URLs, uploads `ui/` to the `$web` container, and
fails unless both `/health` endpoints return 200 within about 10 minutes.

Cold starts: both apps scale to zero and the databases pause after 60 idle minutes. The first
request then takes up to about a minute; the services retry the database connection with
backoff, and the UI shows "Waking up the services..." and retries reads.

Logs: `az containerapp logs show -n ddumitrescu-ieu2024-tickets -g rg-ddumitrescu-ieu2024 --follow`
(add `--type system` for start-up and probe events).

## Configuration (environment variables)

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `PORT` | both | `8000` | Port the service listens on (binds `0.0.0.0`) |
| `UI_ORIGIN` | both | `http://localhost:8080` | The only origin allowed by CORS |
| `GIT_SHA` | both | `dev` | Version reported by `/health` |
| `DATABASE_URL` | both | none, required (secret) | `mssql+pymssql://user:password@host:1433/db` of the service's own database; pending migrations in `migrations/` run on startup |
| `DB_CONNECT_ATTEMPTS` | both | `8` | Connection retries with backoff (1, 2, 4, 8, 15 s...) while SQL Server or a paused Azure SQL database wakes up |
| `TICKETS_URL` | checkin | `http://localhost:8001` | Base URL of the tickets service (`http://tickets:8000` in compose) |
| `TICKETS_TIMEOUT_S` | checkin | `2` | Timeout in seconds for calls to tickets |

## Tests and coverage (per service)

The tests run against a real SQL Server test database (`tickets_test` / `checkin_test`,
created by `db/init.sql`), never against the app's databases or Azure. With compose running:

```bash
cd services/tickets && TEST_DATABASE_URL="mssql+pymssql://sa:<MSSQL_SA_PASSWORD>@localhost:1433/tickets_test" pytest --cov=tickets --cov-report=term-missing
cd services/checkin && TEST_DATABASE_URL="mssql+pymssql://sa:<MSSQL_SA_PASSWORD>@localhost:1433/checkin_test" pytest --cov=checkin --cov-report=term-missing
```

In CI each job starts its own throwaway SQL Server container with a random password.

## Migrations

Each service owns its schema in `services/<name>/migrations/NNN_name.sql`. On startup the
service applies, in order and each in its own transaction, every file not yet listed in its
`schema_migrations` table. Applied files are never edited: a change is always a new file.

| Service | Migrations |
|---|---|
| tickets | `001_init.sql`: events and tickets |
| checkin | `001_init.sql`: check_ins; `002_add_gate.sql`: adds `gate` (NOT NULL, default `'main'`) to a table that already holds check-ins |

Migration 002 is deployed to Azure while the live check-in database already has check-ins;
those rows are kept and get gate `main`.

## Documentation

- `ADR.md`: architecture decisions (1-5 from Assignment 1, 6-8 from Assignment 2)
- `system.yaml`: the whole system (services, env vars, calls, Azure resources), checked in CI against the provided `system.schema.json` and against the code (`scripts/check_system.py`)
- `services/<name>/openapi.yaml`: the HTTP API of each service
- `AI_USAGE.md`: how AI was used, and how the accepted code works
