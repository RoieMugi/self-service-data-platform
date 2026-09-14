# Local Kubernetes exercises

Session 019 used Docker Desktop kind, one node, Kubernetes v1.36.1 on Windows.
The API connects to the existing Compose PostgreSQL; this is not a deployment
of the full processing platform. Commands below are reproduction instructions,
not an instruction to rerun cleanup or create resources automatically.

## Prerequisites and ownership

- Docker Desktop Kubernetes running; verify `kubectl config current-context`
  reports `docker-desktop` and `kubectl get nodes` reports Ready.
- Local image `data-platform-api:terraform-lab` from [the Terraform lab](../Terraform/README.md).
- Compose PostgreSQL running, with port 5432 published and existing lab credentials.
  Kubernetes does not own that database or its volume. Do not reapply migration 003
  to the previously upgraded database.
- Run the commands from the repository root in PowerShell.
- The API Deployment and Service plus platform-db Secret were retained at close.
  The storage practice Pod, PVC, and backing PV were deleted.

## Load the API image into the node

An image listed by Docker was not initially available to the kind node runtime;
the Pod reported ErrImageNeverPull with imagePullPolicy: Never. Enable Docker
Desktop's Show system containers setting to see the node in `docker ps`.
Verify its actual name before using this session's name below.

```powershell
docker image save -o "$env:TEMP\platform-api-terraform-lab.tar" data-platform-api:terraform-lab
docker cp "$env:TEMP\platform-api-terraform-lab.tar" desktop-control-plane:/var/platform-api-terraform-lab.tar
docker exec desktop-control-plane ls -lh /var/platform-api-terraform-lab.tar
docker exec desktop-control-plane ctr --namespace k8s.io images import /var/platform-api-terraform-lab.tar
```

Check each result before continuing. Copies to /tmp reported success but were
not visible to exec in this session; /var worked. The cause was not established.
`k8s.io` here is a containerd namespace, not a Kubernetes workload namespace.
New nodes need their own image import. Source changes also require a new image
build/import and deliberate rollout; Kubernetes does not build this Dockerfile.
Temporary archives remain unless cleaned up separately.

## Database Secret and API

Verify network access from an existing API Pod, if one is already running:

```powershell
kubectl exec deployment/platform-api -- python -c "import socket; s = socket.create_connection(('host.docker.internal', 5432), timeout=5); print('Database port reachable'); s.close()"
```

Create the Secret once if absent, using the existing local study credentials.
This command contains a password and can be retained in terminal history. The
Deployment references the Secret; its YAML alone does not recreate credentials.

```powershell
kubectl create secret generic platform-db --from-literal=DATABASE_URL='postgresql://platform_user:platform_pass@host.docker.internal:5432/platform_db'
kubectl apply -f .\kubernetes\api-deployment.yml
kubectl apply -f .\kubernetes\api-service.yml
kubectl rollout status deployment/platform-api --timeout=60s
kubectl logs deployment/platform-api --tail=30
kubectl port-forward service/platform-api 8090:8000
```

Keep the last command running. Open `http://localhost:8090/health` and
`http://localhost:8090/db-health`; verified results were healthy and database
connected. ClusterIP is internal access; localhost port-forward does not expose
the API to a second computer. LAN access was discussed only.

For the replacement exercise, delete only the API Pod:

```powershell
kubectl delete pod -l app=platform-api
kubectl get pods -l app=platform-api
```

The Deployment maintains one replica. Verify a new Pod name and Running status.
Stop the old port-forward with Ctrl+C and reconnect before checking /health.
An occupied local 8090 port prevented a second forward during the session.
No readiness/liveness probes are configured; Running alone is not an HTTP check.

## Persistent storage exercise

```powershell
kubectl get storageclass
kubectl apply -f .\kubernetes\storage-practice-pvc.yml
kubectl apply -f .\kubernetes\storage-practice-pod.yml
kubectl wait --for=condition=Ready pod/storage-practice --timeout=60s
kubectl get pod/storage-practice pvc/storage-practice
```

The standard class used WaitForFirstConsumer and Delete. Expect the 1Gi claim
to become Bound after the Pod consumes it. ReadWriteOnce is a one-node writable
mount mode, not a one-Pod limit. The Pod reuses the API image but sleeps instead
of starting the API, with storage mounted at /practice.

Write once, then replace the standalone Pod and read without rewriting:

```powershell
kubectl exec storage-practice -- python -c "from pathlib import Path; p = Path('/practice/session19.txt'); p.write_text('Persistent storage works', encoding='utf-8'); print(p.read_text(encoding='utf-8'))"
kubectl delete pod storage-practice
kubectl apply -f .\kubernetes\storage-practice-pod.yml
kubectl wait --for=condition=Ready pod/storage-practice --timeout=60s
kubectl exec storage-practice -- python -c "from pathlib import Path; print(Path('/practice/session19.txt').read_text(encoding='utf-8'))"
```

The session verified `Persistent storage works` after recreation. Unlike the API
Deployment, this standalone Pod must be recreated manually.

## Deliberate practice cleanup

Record the backing volume name from `kubectl get pvc storage-practice` first.
The following deletes the practice data as well as the workload:

```powershell
kubectl delete pod storage-practice
kubectl delete pvc storage-practice
```

Verify the recorded PV name returns NotFound with `kubectl get pv <volume-name>`.
Recreating the claim allocates new storage; it does not restore the old file.
This cleanup was completed in Session 019. API resources, Secret, Compose data,
and manifests were retained. Full cluster reset and database cleanup are not
part of these instructions.

See [Session 019](../docs/sessions/019-local-kubernetes.md) for evidence, scope,
remaining work, and the separate discussion of queries and CSV downloads.
