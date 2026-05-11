# Kubernetes Auditory Guide — Chapters 5 & 6
### Namespaces + Deployments | Practical Session Guide

**Reading material:** The Kubernetes Book (2026 edition) — Nigel Poulton & Pushkar Joglekar | Chapter 5: Virtual clusters with Namespaces | Chapter 6: Kubernetes Deployments

---

## Before You Start

Create a fresh cluster for this chapter. A small one is enough — 1 server, 1 agent:

```powershell
k3d cluster create kube3 -s 1 -a 1
```

Fix kubectl connection (Windows). Every time you create a new cluster the port changes, so you need to do this each time:

```powershell
docker ps
```

Look for the `k3d-kube3-serverlb` container and find the port mapped to `6443`:
```
0.0.0.0:59940->6443/tcp   ← your port is 59940 (yours will be different every time)
```

Then point kubectl to that port:
```powershell
kubectl config set-cluster k3d-kube3 --server=https://127.0.0.1:59940
# replace 59940 with whatever port you found above
```

Verify:
```powershell
kubectl get nodes
```

Expected output:
```
NAME                  STATUS   ROLES                  AGE   VERSION
k3d-kube3-server-0   Ready    control-plane,master   30s   v1.27.4+k3s1
k3d-kube3-agent-0    Ready    <none>                 25s   v1.27.4+k3s1
```

---

## Chapter 5 — Namespaces

### 1. What are Namespaces?

Namespaces are a native way to divide a single Kubernetes cluster into **multiple virtual clusters**.

They are designed as an easy way to apply quotas and policies to groups of objects. Think of a real office building: one building, many departments — each with its own space, access cards, and budget. Namespaces work the same way.

| What they ARE good for | What they are NOT good for |
|---|---|
| Grouping objects by team or environment (Dev / Test / Prod) | Strong workload isolation |
| Applying resource quotas per namespace | Isolating hostile or untrusted workloads |
| Access control per namespace | Replacing separate clusters for security |

> ⚠️ A compromised Pod in one namespace CAN interact with other namespaces. For real isolation between hostile workloads, use separate clusters.

Most Kubernetes objects are **namespaced** — meaning they belong to a specific namespace. These include Pods, Services, and Deployments. If you don't explicitly define a target namespace when deploying, the object lands in the `default` namespace.

---

### 2. Inspecting Namespaces

List all namespaces in the cluster:

```powershell
kubectl get namespaces
```

Expected output:
```
NAME              STATUS   AGE
default           Active   5d5h
kube-system       Active   5d5h
kube-public       Active   5d5h
kube-node-lease   Active   5d5h
```

Four namespaces exist by default:

| Namespace | Purpose |
|---|---|
| `default` | Where objects land if you don't specify a namespace |
| `kube-system` | DNS, metrics server, control plane components |
| `kube-public` | Objects that need to be readable by anyone, including unauthenticated users |
| `kube-node-lease` | Node heartbeats and managing node leases |

---

### 3. Which Resources are Namespaced?

Not all Kubernetes resources belong to a namespace. You can check with:

```powershell
kubectl api-resources
```

Look at the `NAMESPACED` column:

```
NAME                    SHORTNAMES   NAMESPACED   KIND
nodes                   no           false        Node
persistentvolumes       pv           false        PersistentVolume
pods                    po           true         Pod
services                svc          true         Service
deployments             deploy       true         Deployment
replicationcontrollers  rc           true         ReplicationController
secrets                              true         Secret
serviceaccounts         sa           true         ServiceAccount
```

Resources with `NAMESPACED: false` are cluster-wide — they don't belong to any namespace. Nodes and PersistentVolumes are examples of this.

---

### 4. Creating and Managing Namespaces

**Imperatively** — quick, one-off:

```powershell
kubectl create ns hydra
```

```
namespace/hydra created
```

**Declaratively** — from a manifest (preferred, version-controllable):

```powershell
kubectl apply -f 00-namespace.yml
```

```
namespace/flask-app created
```

The manifest:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: flask-app
  labels:
    env: demo
```

List all namespaces to confirm:

```powershell
kubectl get ns
```

```
NAME              STATUS   AGE
default           Active   5m46s
kube-system       Active   5m46s
kube-public       Active   5m46s
kube-node-lease   Active   5m46s
hydra             Active   5m23s
flask-app         Active   2m19s
```

Delete a namespace — this removes everything inside it:

```powershell
kubectl delete ns hydra
```

```
namespace "hydra" deleted
```

---

### 5. Set kubectl to Work in a Specific Namespace

When working in a namespace for a longer period, you don't want to type `--namespace flask-app` on every command. Set it as the default for the current context:

```powershell
kubectl config set-context --current --namespace flask-app
```

```
Context "k3d-kube3" modified.
```

Verify it took effect:

```powershell
kubectl config view --minify | grep namespace
```

```
    namespace: flask-app
```

From this point on, all kubectl commands target the `flask-app` namespace automatically.

---

### 6. Deploy Postgres into the Namespace

In our docker-compose, Postgres was the `db` service. In Kubernetes we deploy it as a simple Pod for now.

```powershell
kubectl apply -f 01-postgres.yml
```

```
pod/postgres created
```

Check it's running:

```powershell
kubectl get pods
```

```
NAME       READY   STATUS    RESTARTS   AGE
postgres   1/1     Running   0          30s
```

> 📝 **Note for students:** In production you'd use a `StatefulSet` for a database — it handles stable network identity and ordered restarts. For this demo, a simple Pod is enough to illustrate the concept.

> ⚠️ **No Service yet.** Without a Service, nothing in the cluster can reach this Postgres Pod by name. The Flask backend will start and respond, but will report it cannot connect to the database — that's expected and intentional. Services are next week — that's when the two will finally be able to talk to each other.

---

### 7. Deploying to a Namespace

There are two ways to target a specific namespace when deploying:

**Imperatively** — pass the flag on the command line:
```powershell
kubectl apply -f 02-backend-deploy.yml --namespace flask-app
```

**Declaratively** — set `namespace:` in the manifest itself (preferred):
```yaml
metadata:
  name: flask-backend
  namespace: flask-app    # <<==== namespace declared here
```

Since we already set the context to `flask-app` in step 5, we don't need to pass the flag — kubectl already knows where to deploy.

---

### 8. Namespace Cleanup

```powershell
kubectl delete ns flask-app
```

This deletes **everything** inside the namespace in one command — Pods, Deployments, everything. Very convenient for cleanup between demos.

Reset context back to default:

```powershell
kubectl config set-context --current --namespace default
```

```
Context "k3d-kube3" modified.
```

---

## Chapter 6 — Deployments

### 9. Why Deployments?

In the previous chapter we deployed bare Pods. A bare Pod has no one watching over it — if it dies, it stays dead. Nobody reschedules it. Nobody replaces it.

Deployments wrap Pods and add cloud-native features:

| Feature | What it means |
|---|---|
| Self-healing | Crashed Pod? Kubernetes replaces it automatically |
| Scaling | Run 1 replica or 100 with one command |
| Rolling updates | Deploy v2.0 with zero downtime |
| Versioned rollbacks | Something broke? Revert to v1.0 instantly |

> ⚠️ **Requirement:** Your app must be **stateless** to benefit fully from Deployments — it must survive being killed and replaced at any time. Our Flask backend is stateless (all state lives in Postgres), so it's a perfect fit.

---

### 10. The Deployment → ReplicaSet → Pod Hierarchy

Deployments don't manage Pods directly. There's a middle layer:

```
Deployment       →  manages rollouts and rollbacks
  └── ReplicaSet →  manages scaling and self-healing
        └── Pod  →  runs your container
```

- **ReplicaSet** — ensures the right number of Pod replicas are always running. Provides self-healing and scaling.
- **Deployment** — manages ReplicaSets. When you update your app, the Deployment creates a new ReplicaSet for the new version and gradually scales it up while scaling the old one down. Old ReplicaSets are kept (scaled to 0) to enable rollbacks.

You write one **Deployment** manifest. Kubernetes automatically creates the ReplicaSet and the Pods. You never interact with ReplicaSets directly.

---

### 11. Desired State vs Observed State

This is the core mental model of Kubernetes — it applies to everything, but Deployments make it very visible.

- **Desired state** — what you declare in your manifest (e.g. 5 replicas of `flask-lab:1.0`)
- **Observed state** — what's actually running in the cluster right now
- **Reconciliation** — the continuous process of making observed state match desired state

The Deployment Controller runs in the control plane and watches the cluster constantly. The moment it sees a difference between desired and observed state — a Pod crashed, a node died, you changed the replica count — it immediately acts to fix it. You declare *what* you want, Kubernetes figures out *how* to make it happen.

---

### 12. Anatomy of the Deployment Manifest

```yaml
apiVersion: apps/v1               # Deployments live in the apps/v1 API group
kind: Deployment
metadata:
  name: flask-backend             # must be a valid DNS name
  namespace: flask-app
spec:
  replicas: 5                     # <<==== number of Pod replicas to run
  selector:
    matchLabels:
      app: flask-backend          # <<==== the Deployment manages all Pods with this label
  revisionHistoryLimit: 5         # keep 5 old ReplicaSets for rollback
  progressDeadlineSeconds: 300    # fail the rollout if it takes longer than 5 min
  minReadySeconds: 10             # wait 10s before considering a new Pod "ready"
  strategy:
    type: RollingUpdate           # <<==== controls how updates happen
    rollingUpdate:
      maxUnavailable: 1           # at most 1 Pod down at any time during update
      maxSurge: 2                 # at most 2 extra Pods above replica count during update
  template:                       # <<==== everything below here is the Pod template
    metadata:
      labels:
        app: flask-backend        # <<==== must match selector.matchLabels above
    spec:
      containers:
        - name: flask-backend
          image: dsasanski/flask-lab:1.0
          ports:
            - containerPort: 5000
          env:
            - name: DB_HOST
              value: db           # will resolve via a Service next week
            - name: DB_PORT
              value: "5432"
            - name: DB_NAME
              value: labdb
            - name: DB_USER
              value: admin
            - name: DB_PASSWORD
              value: secret
```

> 💡 **The selector is the glue.** `matchLabels: app: flask-backend` tells the Deployment which Pods it owns. The Pod template must produce Pods with that exact same label — if they don't match, the Deployment can't manage them.

> 💡 **One Deployment = one Pod template.** If your app has a frontend and a backend, you write two separate Deployment manifests. A Deployment CAN manage multiple Pods — but they're all replicas of the same template, not different apps.

You can always ask kubectl what fields a Deployment supports:
```powershell
kubectl explain deployment --recursive
kubectl explain deployment.spec.strategy
```

---

### 13. Deploying the App

First, recreate the namespace and deploy Postgres:

```powershell
kubectl apply -f 00-namespace.yml
kubectl apply -f 01-postgres.yml
```

Then deploy the backend:

```powershell
kubectl apply -f 02-backend-deploy.yml
```

```
deployment.apps/flask-backend created
```

Check the Deployment:

```powershell
kubectl get deploy flask-backend
```

```
NAME            READY   UP-TO-DATE   AVAILABLE   AGE
flask-backend   5/5     5            5           2m34s
```

Check the Pods:

```powershell
kubectl get pods
```

```
NAME                             READY   STATUS    RESTARTS   AGE
flask-backend-6bbb5f8946-2xkpq   1/1     Running   0          2m
flask-backend-6bbb5f8946-7tqzr   1/1     Running   0          2m
flask-backend-6bbb5f8946-fplm2   1/1     Running   0          2m
flask-backend-6bbb5f8946-nxp4s   1/1     Running   0          2m
flask-backend-6bbb5f8946-wqbtj   1/1     Running   0          2m
postgres                         1/1     Running   0          3m
```

> 💡 **Pod names:** Kubernetes generates them as `<deployment-name>-<replicaset-hash>-<random>`. Every Pod gets a unique name.

The Deployment automatically created a ReplicaSet — check it:

```powershell
kubectl get rs
```

```
NAME                       DESIRED   CURRENT   READY   AGE
flask-backend-6bbb5f8946   5         5         5       5m43s
```

Get full details about the Deployment:

```powershell
kubectl describe deploy flask-backend
```

The output shows the selector, replica counts, rolling update strategy, Pod template, and at the bottom — the Events section showing the rollout history. This is the first place to look when something isn't behaving as expected.

---

### 14. Access the App

Services are next week — for now use `kubectl port-forward` directly to a Pod:

```powershell
# Copy one of the pod names from kubectl get pods
kubectl port-forward pod/flask-backend-6bbb5f8946-2xkpq 5000:5000
```

Open `http://localhost:5000/version` in your browser:

```json
{"version": "1.0", "app": "flask-lab"}
```

Open `http://localhost:5000/items`:

```json
{"message": "Database not available"}
```

This is expected — the app starts and responds, but can't reach Postgres because there's no Service yet. That's next week.

> 💡 **For students:** `port-forward` is a debug and development tool. It tunnels traffic from your local machine to one specific Pod. It's not load balanced — traffic only goes to the one Pod you named. Next week's Services will expose all 5 replicas properly.

---

### 15. Self-Healing Demo

Delete one of the Pods and watch Kubernetes replace it:

```powershell
kubectl delete pod flask-backend-6bbb5f8946-2xkpq
```

Immediately watch what happens:

```powershell
kubectl get pods --watch
```

```
NAME                             READY   STATUS        RESTARTS   AGE
flask-backend-6bbb5f8946-2xkpq   0/1     Terminating   0          5m
flask-backend-6bbb5f8946-7tqzr   1/1     Running       0          5m
flask-backend-6bbb5f8946-fplm2   1/1     Running       0          5m
flask-backend-6bbb5f8946-nxp4s   1/1     Running       0          5m
flask-backend-6bbb5f8946-wqbtj   1/1     Running       0          5m
flask-backend-6bbb5f8946-hk9mn   0/1     Pending       0          0s
flask-backend-6bbb5f8946-hk9mn   1/1     Running       0          3s
```

The ReplicaSet controller saw 4 Pods where it expected 5 and immediately scheduled a replacement. The whole process takes a few seconds.

> 💡 **Reconciliation in action.** This is the desired state vs observed state loop working in real time. You declared "I want 5 replicas" — the moment that's no longer true, Kubernetes fixes it. You didn't ask it to. You didn't even notice. That's the point.

---

### 16. Scaling

Scale down to 3 replicas imperatively:

```powershell
kubectl scale deploy flask-backend --replicas 3
```

```
deployment.apps/flask-backend scaled
```

```powershell
kubectl get deploy
```

```
NAME            READY   UP-TO-DATE   AVAILABLE   AGE
flask-backend   3/3     3            3           10m
```

Re-apply the manifest to bring it back to 5:

```powershell
kubectl apply -f 02-backend-deploy.yml
```

```powershell
kubectl get deploy
```

```
NAME            READY   UP-TO-DATE   AVAILABLE   AGE
flask-backend   5/5     5            5           12m
```

> ⚠️ **Important lesson:** Imperative changes like `kubectl scale` are immediately overridden the next time you `kubectl apply` the manifest. Always update the manifest and apply it — never rely on imperative changes as your source of truth.

---

### 17. Rolling Update — v1.0 → v2.0

With 5 replicas running v1.0, update to v2.0. The only change in the manifest is the image tag.

The strategy we configured:
- `maxUnavailable: 1` → at most 1 Pod down at any moment
- `maxSurge: 2` → can spin up 2 extra Pods above the replica count during the transition
- `minReadySeconds: 10` → waits 10 seconds before marking a new Pod as ready

Apply the v2.0 manifest:

```powershell
kubectl apply -f 02-backend-deploy-v2.yml
```

Watch the rollout in real time:

```powershell
kubectl rollout status deployment flask-backend
```

```
Waiting for deployment "flask-backend" rollout to finish: 4 out of 5 new replicas have been updated...
Waiting for deployment "flask-backend" rollout to finish: 4 out of 5 new replicas have been updated...
Waiting for deployment "flask-backend" rollout to finish: 1 old replicas are pending termination...
deployment "flask-backend" successfully rolled out
```

Kubernetes brought up new Pods (v2.0) one by one while terminating old ones (v1.0), always keeping at least 4 Pods running. Zero downtime.

Check that two ReplicaSets now exist — one for each version:

```powershell
kubectl get rs
```

```
NAME                        DESIRED   CURRENT   READY   AGE
flask-backend-7975c755b6    5         5         5       2m      ← v2.0 (active)
flask-backend-6bbb5f8946    0         0         0       28m     ← v1.0 (kept for rollback)
```

The old ReplicaSet is scaled to 0 but kept. That's intentional — it's how rollback works.

Confirm v2.0 is running — port-forward and hit `/version`:

```powershell
kubectl port-forward pod/flask-backend-7975c755b6-<hash> 5000:5000
```

```json
{"version": "2.0", "app": "flask-lab"}
```

---

### 18. Pause and Resume a Rollout

You can pause a rollout mid-way — useful for canary testing where you want to observe the new version on a subset of Pods before continuing:

```powershell
kubectl rollout pause deploy flask-backend
```

```
deployment.apps/flask-backend paused
```

Check the state — some Pods will be on the old version, some on the new:

```powershell
kubectl describe deploy flask-backend
```

Look at `OldReplicaSets` and `NewReplicaSet` at the bottom — both will have replicas.

Resume when you're satisfied:

```powershell
kubectl rollout resume deploy flask-backend
```

```
deployment.apps/flask-backend resumed
```

---

### 19. Rollback

Check rollout history:

```powershell
kubectl rollout history deployment flask-backend
```

```
REVISION   CHANGE-CAUSE
1          <none>
2          <none>
```

Revision 1 is v1.0, revision 2 is v2.0. Roll back to revision 1:

```powershell
kubectl rollout undo deployment flask-backend --to-revision=1
```

```
deployment.apps/flask-backend rolled back
```

Watch the ReplicaSets flip — v1.0 scales back up, v2.0 scales down to 0:

```powershell
kubectl get rs
```

```
NAME                        DESIRED   CURRENT   READY   AGE
flask-backend-7975c755b6    0         0         0       10m     ← v2.0 (scaled down)
flask-backend-6bbb5f8946    5         5         5       36m     ← v1.0 (active again)
```

Check history again — notice revision 1 is gone, you now see 2 and 3:

```powershell
kubectl rollout history deployment flask-backend
```

```
REVISION   CHANGE-CAUSE
2          <none>
3          <none>
```

> 💡 **Why did revision 1 disappear?** When you roll back to revision 1, that revision becomes the current state — it gets renumbered as the latest revision (3). Revision 1 is consumed in the process.

Confirm we're back on v1.0:

```powershell
kubectl port-forward pod/flask-backend-6bbb5f8946-<hash> 5000:5000
```

```json
{"version": "1.0", "app": "flask-lab"}
```

---

## Full Cleanup

```powershell
kubectl delete ns flask-app
kubectl config set-context --current --namespace default
k3d cluster delete kube3
```

---

## Docker Compose → Kubernetes Mapping

| Docker Compose | Kubernetes equivalent | Notes |
|---|---|---|
| `service: backend` | Deployment | Adds self-healing, scaling, rollouts |
| `service: db` | Pod | StatefulSet in production |
| `depends_on: db` | App handles gracefully | Init containers are the k8s solution |
| `ports: "5000:5000"` | `kubectl port-forward` | Services next week |
| `environment:` | `env:` in container spec | Same concept, different syntax |
| `volumes: postgres_data` | PersistentVolumeClaim | Coming in a later chapter |
| networks (implicit) | Service DNS | Next week |

---

## Key Takeaways

1. **Namespaces** divide one cluster into multiple virtual clusters — good for environments and teams, not for security isolation
2. **Default namespace** is used if you don't specify one — always be explicit in production
3. **Deleting a namespace** deletes everything inside it
4. **Deployments** are the right way to run stateless apps — never deploy raw Pods in production
5. **ReplicaSets** handle self-healing and scaling; Deployments manage ReplicaSets and handle rollouts/rollbacks
6. **Desired state vs observed state** — declare what you want, the Deployment Controller makes it happen
7. **Rolling updates** replace Pods gradually, keeping the app available throughout
8. **Old ReplicaSets are kept** (scaled to 0) specifically to enable rollbacks
9. **`kubectl scale` is overridden** by the next `kubectl apply` — always update the manifest
10. **Without Services**, Pods cannot reach each other by name inside the cluster — that's next week

---

## Common Mistakes to Avoid

**"I can mix different apps in one Deployment"** — No. One Deployment manages one Pod template. Frontend and backend each need their own Deployment.

**"I'll use `kubectl scale` to manage replica counts"** — Don't. The next `kubectl apply` will override it back to whatever the manifest says. Update the manifest.

**"Deleting a namespace is safe to do carefully"** — It's not careful at all — it deletes everything inside with no confirmation. Make sure you're in the right namespace before running `kubectl delete ns`.

**"The old ReplicaSet is wasted resources"** — No. It's scaled to 0 (no Pods running, no resources consumed) and kept specifically for rollback. It costs you nothing.

**"Rolling back creates a new revision with the old image"** — Yes, exactly. A rollback is not an undo — it's a new forward deployment using an older configuration. That's why the revision number goes up, not down.

---

## Key Commands Reference

```powershell
# Namespaces
kubectl get ns
kubectl create ns <name>
kubectl delete ns <name>
kubectl config set-context --current --namespace <name>
kubectl config view --minify | grep namespace

# Deployments
kubectl apply -f <file>
kubectl get deploy
kubectl get deploy <name>
kubectl get pods
kubectl get rs
kubectl describe deploy <name>
kubectl scale deploy <name> --replicas <n>
kubectl explain deployment --recursive
kubectl explain deployment.spec.strategy

# Access (no Services yet)
kubectl port-forward pod/<pod-name> <local-port>:<container-port>

# Rollouts
kubectl rollout status deployment <name>
kubectl rollout history deployment <name>
kubectl rollout pause deploy <name>
kubectl rollout resume deploy <name>
kubectl rollout undo deployment <name> --to-revision=<n>

# Cleanup
kubectl delete -f <file>
kubectl delete ns <name>
k3d cluster delete <name>
```

---

*Kubernetes Auditory Guide | Chapters 5 & 6: Namespaces + Deployments | Continuous Integration and Delivery 2023*