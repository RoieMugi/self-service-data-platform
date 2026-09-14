# Session 019 - Local Kubernetes

**Dates:** 2026-09-09 through 2026-09-11 (Asia/Jerusalem)

**Status:** Complete for the agreed deployment, Secret, and storage exercises.

## Objective and workflow

Learn local Kubernetes through our API, using Docker Desktop kind with one node.
The user created manifests and ran all infrastructure commands. The assistant
explained one step at a time, then received permission to update documentation
and cosmetic formatting at session close.

## Work completed, step by step

1. Reviewed all three existing READMEs, study notes, timeline, recent session
   records, saved repository memory skills, and relevant source/configuration.
2. Planned cluster setup, an API Deployment/Service, and configuration/storage
   exercises. Kept the no-cloud-budget learning scope from Session 018.
3. Enabled Docker Desktop Kubernetes using kind, one node, version v1.36.1.
   Downloads failed with unexpected EOF for kindest/node:v1.36.1 and later an
   anonymous-token response for envoyproxy/envoy:v1.36.7. The node image manual
   pull succeeded; an Envoy retry was suggested. The user later showed Running.
   Hotspot instability was a possible cause, not a confirmed root cause.
4. Verified current context docker-desktop and desktop-control-plane Ready.
5. Identified the existing data-platform-api:terraform-lab image, ID prefix
   2b9546b2d300, from the Terraform exercise.
6. Created/applied api-deployment.yml with one replica, app: platform-api labels,
   imagePullPolicy: Never, and container port 8000. The Pod reported
   ErrImageNeverPull: the image was not available in the node runtime.
7. Enabled Show system containers in Docker Desktop. docker ps then exposed
   desktop-control-plane, kind-cloud-provider, and kind-registry-mirror.
8. Exported the image to the Windows temporary directory. Copying the archive
   into the node's /tmp reported success, but ls and ctr could not find it,
   including an immediate copy/read retry. Container timestamps alone did not
   establish recreation; the cause remains unresolved.
9. Copied the archive to /var/platform-api-terraform-lab.tar instead and verified
   its presence (92M). Imported it with ctr --namespace k8s.io images import.
   The API Pod subsequently reached 1/1 Running with zero restarts.
10. Read Uvicorn logs: application startup complete, listening on 0.0.0.0:8000.
11. Created/applied a ClusterIP Service selecting app: platform-api, port 8000
    to targetPort 8000. Port-forwarded local 8090 to the Service and verified
    /health returned {"status":"healthy"} in the browser.
12. Deleted an API Pod. The Deployment's controller chain created a replacement,
    observed as platform-api-7d6f6669ff-5rblq, 1/1 Running, zero restarts.
13. Resolved a local 8090 bind conflict by stopping the old port-forward and
    restarting it. Verified /health again against the replacement Pod.
14. Explained ConfigMaps and Secrets; ConfigMaps were not implemented. Verified
    a TCP connection from the API Pod to host.docker.internal:5432 using Python.
15. Created platform-db Secret with DATABASE_URL using existing local study
    credentials and the host address. Added env/valueFrom/secretKeyRef to the
    Deployment, applied, and verified a successful rollout.
16. Reconnected port-forward and verified /db-health returned
    {"status":"healthy","database":"connected"}. PostgreSQL remained in Compose.
17. Inspected StorageClasses: standard (default) and hostpath both used
    rancher.io/local-path, Delete reclaim policy, WaitForFirstConsumer, and no
    volume expansion. Explained delayed binding and ReadWriteOnce semantics.
18. Created/applied a 1Gi standard PVC and a standalone practice Pod reusing the
    API image with a sleeping Python command and the claim mounted at /practice.
    Verified the Pod Running and PVC Bound.
19. Wrote /practice/session19.txt containing Persistent storage works. Deleted
    only the Pod, recreated it from YAML, waited for Ready, and read the original
    file without rewriting it. The contents survived Pod replacement.
20. With explicit user agreement, deleted the practice Pod and PVC. The backing
    PV pvc-80d7c59d-c53a-4ddd-b9df-01081b89d851 returned NotFound afterward.
21. At authorized close, added this record and Kubernetes reproduction guidance,
    updated current roadmap/status documents, and normalized YAML whitespace.

## Scope discussion and estimates

The user wants a simulated company computer on the same local network to upload
CSV files, query tables derived from them, and download query results as CSV.
Explained server-side Compose versus a browser or HTTP client on the second
computer, localhost versus the server's LAN address, and optional GUI access.
No LAN exposure, query endpoint, CSV-result endpoint, or GUI was implemented.

The original deployment estimate was 1-3 sessions including 019, targeting
019-021. This session completed the main Kubernetes exercises; reproduction,
optional ConfigMap practice, and any remaining deployment wrap-up require review
at Session 020. Phase 1 was not declared complete automatically.

A separate provisional estimate of 3-5 additional learning sessions was discussed
for the expanded workflow: about 3 using /docs, 4-5 with a basic GUI. Assumptions:
small CSVs, one selected dataset per query, bounded SQL/result execution, and local
access. Joins, multi-user access, and saved query history were outside the estimate.
The user is considering assistant implementation versus a hybrid learning process;
no implementation mode was chosen or authorized for that future work.

## Files and final ownership

- kubernetes/api-deployment.yml: one API replica and Secret reference.
- kubernetes/api-service.yml: internal Service on port 8000.
- kubernetes/storage-practice-pvc.yml and storage-practice-pod.yml: retained exercises.
- kubernetes/README.md: prerequisites, verified import path, reproduction, cleanup.
- Root README, Terraform README, session index/timeline, and this session record.
- Kubernetes API Deployment, Service, and platform-db Secret were retained.
- Practice Pod, PVC, and PV were removed; their sample file is not recoverable by
  recreating the manifests. No database data or database volume was removed.
- Terraform API and Compose database were observed running during the session;
  Terraform ownership was unchanged. The existing cAdvisor container was untouched.
- Image archives in Windows TEMP and node /var were not cleaned up in this session.
- Final port-forward state was not confirmed; localhost access needs it running.
- The comma-named api-deployment,yml appeared in editor tabs but was absent from
  the on-disk directory at close; no duplicate file was deleted by the assistant.

## Verification, limitations, and next step

Runtime results are user-supplied terminal output and screenshots. No pytest,
Docker build, Terraform apply, cluster mutation, commit, or push was run by the
assistant at close. The 96-test result remains historical from Session 017.
Close checks covered documentation links and whitespace; no new runtime claim
is based on the cosmetic edits.

This verifies API health/database connectivity, not full processing through the
Kubernetes API. MinIO/RabbitMQ/worker integration is not configured for this lab.
No readiness/liveness probes were added. Imported images must be supplied again
after node recreation and updated deliberately after source changes. The Secret
is an external prerequisite, not created by applying the Deployment YAML.
The local volume exercise proves persistence across Pod replacement, not cluster
deletion, disk loss, or backup recovery. ConfigMaps remain conceptual. Worker
restart from Session 017 and final Grafana visuals remain unconfirmed/deferred.

Next: review retained resources and reproduction prerequisites in Session 020,
then agree remaining local milestone tasks and the separate query/CSV/LAN scope.
