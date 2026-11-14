# Local Terraform API lab

This is a small infrastructure exercise. Terraform builds the repository's API image and starts one API container on Docker Desktop. PostgreSQL and its data remain owned by the main Compose project. This lab does not deploy RabbitMQ, object storage, a worker, or the full processing workflow.

The `docker-lab/` directory is an independent Nginx exercise. Both labs use localhost port 8089 by default, so run one at a time.

## API lab prerequisites

- Windows Docker Desktop with its Linux engine and the Terraform CLI. The provider configuration in [api-lab/main.tf](api-lab/main.tf) uses the Windows Docker named pipe; adapt it for another Docker endpoint.
- A healthy Compose database and the `data-platform-engineering_default` network. A different Compose project name requires a matching network change in the lab configuration.
- The local demo database URL supplied through `TF_VAR_database_url`. Terraform does not create or migrate the database.

From the repository root in PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db
cd .\Terraform\api-lab
$env:TF_VAR_database_url = 'postgresql://<user>:<password>@db:5432/<database>'
terraform init
terraform plan
terraform apply
```

Review the plan before applying. Replace the placeholders with URL-safe values from your local `.env`. The host is `db` because this container joins the Compose network. The API is available at `http://127.0.0.1:8089/health`; `/db-health` should report a database connection. A successful health check does not mean the full pipeline is configured.

The image resource hashes an explicit list of source files. Add newly introduced application files to its triggers if changes to them should rebuild the image on the next plan. Terraform is not a source watcher.

## State and cleanup

The configurations and provider lockfiles are versioned. Local state, plans, and populated variable files are ignored. State and Docker metadata can contain the database URL even though Terraform marks its input sensitive; keep them local. Each lab has independent state, and a fresh clone does not automatically adopt an existing container.

To remove the API lab, run `terraform plan -destroy`, inspect the plan, then `terraform destroy` from `Terraform/api-lab`. This removes the lab image and container, not the Compose database or network. See the [Kubernetes API lab](../kubernetes/README.md) for a separate deployment exercise.
