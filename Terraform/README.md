# Local Terraform exercises

Session 018 uses Windows Docker Desktop for a no-cloud-budget learning simulation.
Terraform 1.15.8 and kreuzwerker/docker 4.6.0 were verified in the session.

## Exercises

| Directory | Managed resources | Last verified state |
|-----------|-------------------|---------------------|
| docker-lab | Nginx image and container | Destroyed; configuration retained |
| api-lab | Source-built platform image and API container | Running; database health verified |

Both use localhost port 8089, so run only one unchanged exercise at a time.
The provider connects to npipe:////./pipe/dockerDesktopLinuxEngine; other operating
systems or Docker endpoints require adapting the provider host.

## Reproduce the API lab

Prerequisites: Docker Desktop Linux engine running, Terraform available, and the
repository cloned. The existing Compose database must be healthy on network
data-platform-engineering_default, with the lab credentials in docker-compose.yml.
If the Compose environment is absent, prepare it separately from the project root
with `docker compose up -d db`; verify the actual network name and adapt the lab
configuration if the Compose project name differs. Terraform does not create this
database or network. Existing local databases must not have migration 003 reapplied.

From the repository root:

```powershell
cd .\Terraform\api-lab
terraform init
terraform plan
terraform apply
```

Review each plan before approving. The image resource builds the root Dockerfile;
the container references the resulting image ID. Visit localhost:8089/health and
localhost:8089/db-health; the latter should report healthy/database connected.
Full processing needs additional storage/broker configuration and a running worker.

Eight file hashes trigger rebuilds when Terraform next evaluates changed source,
including app/query_executor.py added during the backend feature extension.
Extend that explicit list when adding application files. This is not a file watcher.

## State, version control, and cleanup

Commit main.tf and .terraform.lock.hcl from each lab. Ignore .terraform/, *.tfstate,
*.tfstate.*, and saved plans named *.tfplan. State can contain credentials; the
configuration also explicitly includes local study credentials.

Each directory has independent local state. Preserve it while managing its existing
resources; a fresh clone does not automatically adopt containers from another state.

To remove a lab, run `terraform plan -destroy` in its directory, review the resources,
then `terraform destroy`. API-lab cleanup removes its image and container, not the
Compose database or network. Configuration remains for recreation; database backup
and restoration are separate from infrastructure recreation.

See [Session 018](../docs/sessions/018-local-terraform.md) for the learning sequence
and verification evidence.

## Kubernetes follow-up

Session 023 (2026-11-10) refreshed the Terraform API lab after the backend changes.
The user verified a two-resource replacement, API health, database connectivity,
and a subsequent no-change plan. The API and Compose database were retained.
This did not refresh the Kubernetes node's imported image or configure full
processing dependencies. See [Session 023](../docs/sessions/023-deployment-wrap-up.md).

Session 019 reused data-platform-api:terraform-lab in a separate Kubernetes lab.
The image was exported and imported into the kind node; Terraform does not manage
that copy or the Kubernetes resources. Compose still owns PostgreSQL. See
[the Kubernetes guide](../kubernetes/README.md) for reproduction and current limits.
