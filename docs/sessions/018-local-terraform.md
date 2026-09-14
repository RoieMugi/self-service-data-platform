# Session 018 - Local Terraform Learning Simulation

**Date:** 2026-09-09 (Asia/Jerusalem)

**Status:** Complete for the local Terraform learning scope.

## Objective and scope decision

Learn infrastructure as code through disposable Docker resources and our actual
API. The user explicitly chose a no-cloud-budget local simulation: understanding
the tools is the goal, not production efficiency or a large environment. This
replaces the planned cloud provisioning exercise. Cloud IAM and managed services
remain conceptual; local Kubernetes is the next checkpoint.

The user made configuration changes and ran all Docker/Terraform commands. The
assistant provided one-step explanations, reviewed files and supplied evidence,
and received explicit authority to edit documentation and cosmetic structure at close.

## Work completed, step by step

1. Reviewed repository READMEs, study notes, timeline, recent sessions, memory
   skills, and worker code. Corrected the session count from 017 to 018 because
   Session 017 was already complete.
2. Explained Terraform through a simple example, construction analogy, and
   professional discussion of configuration, providers, state, plan, and apply.
   Compared possible AWS resources with the agreed local simulation.
3. Installed Terraform through WinGet. Restarting VS Code refreshed PATH;
   the user verified Terraform 1.15.8 on Windows AMD64.
4. Diagnosed Docker's unavailable Linux-engine pipe. Starting Docker Desktop
   restored connectivity; user output showed client/server 29.7.2 and Desktop 4.87.0.
5. Created Terraform/docker-lab/main.tf with kreuzwerker/docker 4.6.0 and the
   Docker Desktop Linux named pipe. Initialized the provider and lock file.
6. Declared an nginx:alpine image and disposable container, mapping localhost
   port 8088 to port 80. Reviewed a two-resource plan, applied it, and verified
   the Nginx welcome page. A subsequent plan reported no changes.
7. Changed the published port to 8089. Reviewed and applied container replacement
   (1 added, 1 destroyed) and verified the new browser address.
8. Explained that Terraform executes on invocation rather than continuously
   reconciling resources, and distinguished configuration from a generated plan.
9. Previewed destruction and removed both Nginx lab resources. The user supplied
   `Destroy complete! Resources: 2 destroyed.` Configuration remains on disk.
10. Created a separate api-lab configuration. Built the repository Dockerfile
    manually, inspected the local image ID, and initially referenced that ID in
    one Terraform-managed API container on localhost:8089, container port 8000.
11. Applied the API container and verified /health returned healthy.
12. Inspected the Compose database: it was exited on
    data-platform-engineering_default. Started data-platform-db and verified healthy.
13. Added DATABASE_URL using the existing local lab credentials and attached
    the Terraform API to the Compose network. Applied container replacement and
    verified /db-health returned healthy with database connected.
14. Added Git ignore patterns for provider downloads, state/backups, and saved
    *.tfplan files. Verified only configuration and lock files appeared as
    untracked Terraform files. Explained that these become GitHub evidence after
    a future commit/push; no Git publication occurred in this session.
15. Replaced the machine-specific image ID with docker_image.api.image_id.
    Added an image build using abspath("${path.module}/../..") as the project-root
    context. Applied 2 additions and 1 destruction; browser evidence confirmed
    database connectivity, followed by a no-change plan.
16. Added seven explicit filesha256 triggers for Dockerfile, requirements.txt,
    app/main.py, app/messaging.py, app/worker.py, app/__init__.py, and .dockerignore.
    Applied 2 additions and 2 destructions to establish the trigger baseline.
    The user verified no changes and continued health afterward.
17. Added a temporary comment to main.py. A plan showed only the main fingerprint
    changed and proposed replacing both image and container. Did not apply this
    temporary edit. Removed the comment; the final plan returned no changes.
18. At authorized close, recorded the session and revised the local roadmap.
    Added blank-line separation in api-lab/main.tf and .gitignore only; no
    application behavior was changed.

## Verification and final state

- Runtime evidence above was supplied by the user; the assistant did not execute
  Docker, Terraform, pytest, or infrastructure mutations.
- Latest reported plan: `No changes. Your infrastructure matches the configuration.`
- API lab image/container remain present; PostgreSQL was started and connectivity
  verified. Last applied API container ID:
  ce8a13cfafe00d53fc98e8d248d471ba980bfbcfc1e23f09f705e959072e70e5.
- Nginx lab resources were destroyed; its configuration remains reusable.
- app/main.py has no net change after the comment exercise.
- No application tests were rerun; 96 passing tests remains the historical
  Session 017 user report, not a Session 018 test result.
- Final cosmetic whitespace edits were not followed by another runtime apply.

## Files and ownership

- Terraform/docker-lab/main.tf and .terraform.lock.hcl: disposable Nginx example.
- Terraform/api-lab/main.tf and .terraform.lock.hcl: source-built API example.
- .gitignore: Terraform local artifacts excluded.
- README.md, docs/sessions/README.md, TIMELINE.md, this record, and
  Terraform/README.md: roadmap, evidence, and reproduction guidance.
- Terraform manages the API lab container and image. Compose manages the database,
  persistent database volume, and shared network. No database migration was applied.

## Limits and next checkpoint

- This is a Windows Docker Desktop simulation using a hardcoded named pipe and
  Compose network name. It is not a standalone cloud deployment.
- API lab verifies health/database access only; MinIO, RabbitMQ, and worker settings
  are not configured for full processing through this API container.
- The explicit trigger list must be extended for new application files. Detection
  occurs on Terraform invocation; there is no background watcher. A later source-edit
  rebuild was previewed, not applied; initial trigger installation was applied.
- Local credentials remain in configuration and may appear in ignored state.
- Both lab configurations use host port 8089; do not run both unchanged together.
- Worker restart after Session 017 remains unconfirmed. Interrupted-run recovery
  and final Grafana visual checks remain deferred.
- Next: Session 019 local Kubernetes, starting with capacity/setup assessment and
  small explained tasks. Estimate 1-3 further sessions (019-021) provisionally for
  the revised local learning milestone, depending on setup and verification.
- No commit, push, cloud resources, or paid account setup was performed.
