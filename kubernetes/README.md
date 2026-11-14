# Local Kubernetes API lab

These manifests deploy one API replica and a ClusterIP Service for a Kubernetes learning exercise. They do not deploy the full processing platform. PostgreSQL remains outside the cluster, and the API needs a separately created `platform-db` Secret.

The default Compose database port binds only to `127.0.0.1` on the host. A Pod cannot use that host binding through `host.docker.internal:5432`. Establish a deliberate Pod-reachable database route, or deploy a separate lab database in the cluster, before expecting `/db-health` to pass. Keep the main Compose loopback binding intact.

## Prerequisites

- A running local Kubernetes cluster and `kubectl` context pointed at it. The example image import below assumes Docker Desktop's `desktop-control-plane` node; discover the actual node name in your environment.
- The `data-platform-api:terraform-lab` image built by the [Terraform API lab](../Terraform/README.md), or an equivalent locally built image with that tag.
- A Pod-reachable PostgreSQL address and disposable local credentials. Kubernetes does not own or migrate the Compose database.

Verify your context and node before changing resources:

```powershell
kubectl config current-context
kubectl get nodes
docker ps
```

## Import the local image

The manifest sets `imagePullPolicy: Never`, so the image must exist in the node's container runtime. For Docker Desktop's kind-based node, from the repository root:

```powershell
docker image save -o "$env:TEMP\platform-api-terraform-lab.tar" data-platform-api:terraform-lab
docker cp "$env:TEMP\platform-api-terraform-lab.tar" desktop-control-plane:/var/platform-api-terraform-lab.tar
docker exec desktop-control-plane ctr --namespace k8s.io images import /var/platform-api-terraform-lab.tar
```

Replace the node name if yours differs. Rebuild, reimport, and restart the Deployment after image changes. The archive is temporary and can be removed after import.

## Deploy and check the API

Create the database Secret with a URL for the Pod-reachable database, then apply the manifests:

```powershell
kubectl create secret generic platform-db --from-literal=DATABASE_URL='postgresql://<user>:<password>@<reachable-db-host>:5432/<database>'
kubectl apply -f .\kubernetes\api-deployment.yml
kubectl apply -f .\kubernetes\api-service.yml
kubectl rollout status deployment/platform-api --timeout=60s
kubectl port-forward service/platform-api 8090:8000
```

Keep the port-forward running while checking `http://127.0.0.1:8090/health` and `/db-health`. The Secret command can leave its password in shell history; use only disposable lab credentials. The Service is internal to the cluster, and port-forward provides local access. A Running Pod alone does not prove database connectivity; these manifests do not configure readiness or liveness probes.

The separate `storage-practice-pvc.yml` and `storage-practice-pod.yml` demonstrate a persistent volume claim. Apply them only when you want that exercise. Deleting its PVC can delete its stored data, depending on the storage class policy. The [main Compose stack](../README.md) remains the reproducible route for the full CSV-to-Parquet workflow.
