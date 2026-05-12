# Setup guide — hello_agent

End-to-end configuration to get this project deploying. The flow:

1. [Prerequisites](#1-prerequisites) — what your account/workspace need to have first
2. [Unity Catalog setup](#2-unity-catalog-setup) — catalogs, grants, run-as identities
3. [Local development](#3-local-development) — Databricks CLI profiles for dev work
4. [Fill in `databricks.yml`](#4-fill-in-databricksyml) — workspace hosts and run-as
5. [CI/CD credentials](#5-cicd-credentials) — secrets and variables for the chosen platform
6. [First deploy](#6-first-deploy) — validate and deploy to dev

---

## 1. Prerequisites

- Three Databricks workspaces (dev, staging, prod). They can be separate workspaces or environments within one workspace, as long as you can scope catalogs and identities per environment.
- A Unity Catalog metastore attached to each workspace, with permission to create catalogs (or someone who can create them for you).
- An Azure account with permission to create app registrations (for the staging and prod service principals).
- A GitHub repository to push this project to.

---

## 2. Unity Catalog setup

### 2a. Create catalogs

This project expects one catalog per environment:

| Environment | Default catalog name |
|---|---|
| dev | `hello_agent_dev` |
| staging | `hello_agent_staging` |
| prod | `hello_agent_prod` |

If your org has different catalog naming conventions, override the `catalog` value under each target in `databricks.yml`.

In each workspace, as a metastore or catalog admin:

```sql
CREATE CATALOG IF NOT EXISTS hello_agent_dev;
CREATE CATALOG IF NOT EXISTS hello_agent_staging;
CREATE CATALOG IF NOT EXISTS hello_agent_prod;
```

### 2b. Grant permissions to the deploying identity

The user (for dev) or service principal (for staging/prod) that runs `databricks bundle deploy` needs these grants on the relevant catalog:

```sql
GRANT USE CATALOG ON CATALOG hello_agent_<env> TO `<identity>`;
GRANT CREATE SCHEMA ON CATALOG hello_agent_<env> TO `<identity>`;
```

The bundle creates the schema (`hello_agent`) inside the catalog on first deploy, so the deploying identity also needs to be able to create volumes inside that schema:

```sql
GRANT CREATE VOLUME ON SCHEMA hello_agent_<env>.hello_agent TO `<identity>`;
```

`WRITE VOLUME` on the `artifacts` volume is granted automatically to the volume's creator. If you delegate volume creation, grant `WRITE VOLUME` explicitly to whoever runs MLflow.

### 2c. Create service principals (staging + prod)

Production-mode targets in `databricks.yml` use `run_as` to define who the bundle's resources execute as. The default is the deploying user (you), which is fine for getting started but not for real production.

For Azure:

1. In the Azure portal → Azure Active Directory → App registrations → New registration. Create one app for staging and one for prod.
2. For each app, generate a client secret under Certificates & secrets. Save the Application (client) ID, Directory (tenant) ID, and client secret value — you'll add these to CI/CD secrets later.
3. In each Databricks workspace, add the Azure service principal as a workspace user (Account Console → User Management → Service Principals → Add) and grant it the Unity Catalog permissions from step 2b.
4. Update `databricks.yml` to reference the SP in `run_as`:

   ```yaml
   targets:
     staging:
       run_as:
         service_principal_name: <staging-app-id>
     prod:
       run_as:
         service_principal_name: <prod-app-id>
   ```


---

## 3. Local development

Configure a Databricks CLI profile for your dev workspace so you can run `databricks bundle validate` and `databricks bundle deploy` from your machine.

```bash
databricks auth login --host https://<your-dev-workspace>.azuredatabricks.net --profile dev
```

This stores credentials in `~/.databrickscfg`. Verify with `databricks current-user me --profile dev`.

Optional: profiles for staging and prod can be configured the same way if you need to inspect or troubleshoot those workspaces locally. Day-to-day deploys to staging and prod go through CI/CD, not your machine.

Sync dependencies:

```bash
uv sync
```

`databricks-connect` is a dev dependency — pin it in `pyproject.toml` to match your cluster's runtime version if you'll be running Spark code locally against a remote cluster.

---

## 4. Fill in `databricks.yml`

Open `databricks.yml` and replace the TODO placeholders:

```yaml
targets:
  dev:
    workspace:
      host: https://<your-dev-workspace>.azuredatabricks.net
  staging:
    workspace:
      host: https://<your-staging-workspace>.azuredatabricks.net
  prod:
    workspace:
      host: https://<your-prod-workspace>.azuredatabricks.net
```

If you set up service principals in step 2c, update `run_as` for staging and prod:

```yaml
targets:
  staging:
    run_as:
      service_principal_name: <staging-sp-application-id>
  prod:
    run_as:
      service_principal_name: <prod-sp-application-id>
```

---

## 5. CI/CD credentials

### GitHub Actions

In the repository, go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `STAGING_AZURE_SP_TENANT_ID` | Directory (tenant) ID of the staging app registration |
| `STAGING_AZURE_SP_APPLICATION_ID` | Application (client) ID of the staging app registration |
| `STAGING_AZURE_SP_CLIENT_SECRET` | Client secret value for the staging app |
| `PROD_AZURE_SP_TENANT_ID` | Tenant ID for the prod app registration |
| `PROD_AZURE_SP_APPLICATION_ID` | Application ID for the prod app registration |
| `PROD_AZURE_SP_CLIENT_SECRET` | Client secret value for the prod app |


Under **Settings → Actions → General → Workflow permissions**, enable "Read and write permissions" so jobs can comment on PRs if you extend the workflows to do so.


---

## 6. First deploy

From your machine, with the dev profile from step 3:

```bash
databricks bundle validate -t dev --profile dev
databricks bundle deploy -t dev --profile dev
```

The first deploy creates the schema and the `artifacts` volume in `hello_agent_dev`. The MLflow experiment is created under `/Shared/hello_agent/dev` with the volume as artifact location.

After this, pushes to `main` deploy to staging via CI/CD, and tags matching `v*` deploy to prod.

---

## Troubleshooting

**`token refresh: Refresh token is invalid`** — your CLI profile's OAuth token has expired. Re-run `databricks auth login --profile <name>`.

**`schema does not exist` or `volume does not exist`** — the bundle creates these on deploy. If you destroyed the bundle (`bundle destroy`) and now deploy fails, run `bundle deploy` again; it will recreate them.

**`CREATE SCHEMA permission denied`** — the deploying identity needs `CREATE SCHEMA` on the catalog. See section 2b.

**`run_as.service_principal_name not found`** — the SP must exist in the workspace as a service principal user (not just in the IdP). See section 2c.

**Production mode rejected my deploy** — `mode: production` enforces that the bundle doesn't use user-scoped paths and that `run_as` is set. If you haven't set up service principals yet, change `run_as` to use your username temporarily, or deploy to dev only.
