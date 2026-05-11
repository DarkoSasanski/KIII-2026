# Kubernetes Auditory Guide — Chapter 4
### Working with Pods

**Reading material:** The Kubernetes Book (2025 edition) — Nigel Poulton & Pushkar Joglekar | Chapter 4: Working with Pods

---

## Before You Start

Create a fresh cluster for this chapter. A small one is enough — 1 server, 1 agent:

```powershell
k3d cluster create kube2 -s 1 -a 1
```

Fix kubectl connection (Windows). Every time you create a new cluster the port changes, so you need to do this each time:

```powershell
docker ps
```

Look for the `k3d-kube2-serverlb` container and find the port mapped to `6443`:
```
0.0.0.0:59940->6443/tcp   ← your port is 59940 (yours will be different every time)
```

Then point kubectl to that port:
```powershell
kubectl config set-cluster k3d-kube2 --server=https://127.0.0.1:59940
# replace 59940 with whatever port you found above
```

Verify:
```powershell
kubectl get nodes
```

---

## 1. Everything Runs in a Pod

Every application on Kubernetes runs in a Pod. This is the central organizing principle — not optional, not configurable, just how k8s works.

The relationship between Pods and apps is direct:

- Deploy an app → new Pod created
- Terminate the app → Pod gets destroyed
- Scale up → new Pods get scheduled
- Scale down → Pods get removed
- Update the app → old Pods replaced with new ones

> 💡 **For students:** Pods are not just a thin wrapper. They add a substantial set of operational capabilities on top of your containers — labels, health probes, restart policies, resource limits, scheduling controls, security policies, and more.

---

## 2. Pod Anatomy — The Shared Execution Environment

All containers in the same Pod share one execution environment built from Linux namespaces:

- **net namespace** — shared IP address, port range, routing table. This is why containers in the same Pod talk to each other over `localhost`
- **pid namespace** — shared process tree
- **mnt namespace** — shared filesystems and volumes
- **UTS namespace** — shared hostname
- **IPC namespace** — shared Unix domain sockets and shared memory

### Single-container Pod
The container has full exclusive access to the Pod's IP, port range and routing table.

### Multi-container Pod
All containers share the same IP and port range. Two containers in the same Pod cannot both listen on port 80 — they need different ports. They communicate with each other via `localhost:<port>`.

```
Pod IP: 10.0.10.15
  ├── Main container    → 10.0.10.15:80
  └── Sidecar container → 10.0.10.15:5000
```

> 💡 **For students:** Containers in different Pods always get different IPs. Containers in the same Pod share one IP but use different ports.

---

## 3. The Pod Network

Every Pod gets its own unique IP address on a flat internal network called the **pod network**. This network spans all nodes in the cluster, meaning every Pod can talk directly to every other Pod — even if they're running on different nodes on different physical networks.

```
Node 1 (Network A)    Node 2 (Network B)    Node 3 (Network C)
   Pod: 10.0.10.6        Pod: 10.0.10.7        Pod: 10.0.10.8
         |                      |                      |
         └──────────── Pod network ────────────────────┘
                    (flat overlay network)
```

The pod network is implemented by a CNI (Container Network Interface) plugin — in k3s this is Flannel by default. You choose the CNI plugin at cluster build time.

### Pod DNS

Every Pod also gets a DNS name based on its IP:
```
<pod-ip-dashes>.<namespace>.pod.<cluster-domain>

# Example: Pod with IP 172.17.0.3 in default namespace
172-17-0-3.default.pod.cluster.local
```

> 💡 **Important:** Pod IPs and DNS names change every time a Pod is replaced with a new one. Applications should never rely on a Pod's IP or DNS name for stable addressing — that's what **Services** are for.

### Pod hostnames

Every container in a Pod inherits its hostname from the Pod's `metadata.name`. All containers in a multi-container Pod share the same hostname.

Pod names must be valid DNS names: use only `a-z`, `0-9`, hyphens, and periods.

---

## 4. Static Pods vs Controller-managed Pods

There are two ways to deploy Pods and they behave very differently:

### Static Pods (deploy directly from a manifest)

```powershell
kubectl apply -f pod.yml
```

You write a YAML and deploy the Pod directly. No one is watching over it — the only thing keeping it alive is the Kubelet on the node it's running on.

- Gets deployed and assigned an IP and DNS name
- If the container crashes, Kubelet will try to restart it locally — but that's it
- If the node dies — the Pod dies with it, forever. No one reschedules it elsewhere

**No scaling** — you can't say "give me 3 replicas of this". You'd have to manually create 3 separate YAML files and deploy them one by one. Nothing manages the count for you.

**No rolling updates** — if you want to update your app to a new version, you have to manually delete the Pod and create a new one. There's no Controller to do it gradually while keeping the others running.

**No self-healing at cluster level** — if the node dies, the Kubelet dies with it and nobody reschedules the Pod on another node. It's just gone.

> 💡 Static Pods give you none of the reasons you chose Kubernetes in the first place. They're essentially just "run this container on this node" — you could do that with plain Docker. The power of k8s only kicks in when a Controller is involved.

### Controller-managed Pods (deploy via Deployment, DaemonSet, StatefulSet)

```powershell
kubectl apply -f deployment.yml
```

The Controller Manager on the control plane constantly watches these Pods. If a Pod dies for any reason — node failure, crash, eviction — the Controller notices the difference between desired state and observed state and immediately schedules a new Pod on a healthy node.

- Monitored by the Controller Manager on the control plane
- If a Pod becomes irreparable, the Controller creates a new one on a healthy node
- Supports scaling, rolling updates, rollbacks, self-healing — all automatic
- The new Pod gets a new IP and DNS name — **this is why Pods must be stateless**

The difference in a nutshell:
```
Static Pod:    you → manually do everything
Deployment:    you → declare desired state → Controller handles everything
```

> 💡 **For students:** Think of it like this — a static Pod is a worker with no manager. If something goes wrong, nobody notices. A Controller-managed Pod is a worker with a manager watching over them. If something goes wrong, the manager immediately finds a replacement. Always use a Controller in production.

---

## 5. Pod Lifecycle

A Pod moves through these phases:

```
Submitted to API → Pending → Running → Succeeded (short-lived)
                                     → stays Running (long-lived)
                                     → Failed (error)
```

1. **Pending** — Pod submitted to the API server, scheduler is finding a node, images may still be downloading
2. **Running** — Pod assigned to a node, all containers are running
3. **Succeeded** — all containers completed successfully (batch jobs, short-lived tasks)
4. **Failed** — one or more containers terminated with an error

Long-lived apps (web servers, databases) stay in **Running** indefinitely. Short-lived apps (batch jobs) move to **Succeeded** when done.

### Pods are mortal

When a Pod dies it is **replaced**, not restarted. The new Pod is a completely new object with a new name, new IP, and no retained state. This happens in all these scenarios: node failure, scaling up/down, rolling updates, rollbacks.

> 💡 **For students:** When people say "k8s restarted the pod" they really mean "k8s replaced it with a new one". It's not the same thing.

### Pods are immutable

You cannot modify a running Pod. If you need to change it — delete it and create a new one with the updated spec. K8s prevents changes to running Pod configuration (container name, ports, resource limits etc).

---

## 6. Restart Policies

Restart policies apply to **individual containers** inside a Pod, not to the Pod itself. Configured via `spec.restartPolicy`:

- **`Always`** (default) — Kubelet always restarts a failed container. Use for long-lived services
- **`OnFailure`** — Kubelet only restarts if the container exits with a non-zero error code. Use for batch workloads
- **`Never`** — Kubelet never restarts. Use when failure is handled externally

> 💡 **Important distinction:** Restart policy controls container restarts **within a Pod on the same node**. It does NOT protect against node failure. Only a Controller can reschedule a Pod on a different node if the node dies.

Practical guideline:
- Long-lived apps wrapped in Deployments/StatefulSets/DaemonSets → `Always`
- Short-lived apps wrapped in Jobs/CronJobs → `OnFailure` or `Never`

---

## 7. Writing Your First Pod Manifest

Every k8s object is defined in a YAML file called a **manifest**. Every manifest has four top-level fields:

```yaml
kind: Pod                 # what type of object
apiVersion: v1            # which API version/group
metadata:                 # identifies the object
  name: hello-pod
  labels:
    zone: prod
    version: v1
spec:                     # desired state — containers, volumes, resources
  containers:
  - name: hello-ctr
    image: nigelpoulton/k8sbook:1.0
    ports:
    - containerPort: 8080
```

> 💡 **YAML fields explained:**
> - `kind` — tells k8s what type of object we're defining
> - `apiVersion` — the API group and version. Format is `<api-group>/<version>`. For core objects like Pods the group is omitted so it's just `v1`
> - `metadata.name` — identifies the resource and becomes the hostname for all containers in the Pod
> - `metadata.labels` — key/value pairs that create relationships between objects (how Services find Pods)
> - `spec` — defines the containers, their images, ports, and resource requirements

You can always ask kubectl what fields an object supports:
```powershell
kubectl explain pods --recursive
kubectl explain pod.spec.restartPolicy
```

---

## 8. Deploying Your First Pod

Clone the book repo which has ready-made manifests:
```powershell
git clone https://github.com/nigelpoulton/TheK8sBook.git
cd TheK8sBook/pods
```

Deploy the Pod:
```powershell
kubectl apply -f pod.yml
```

Watch it come up:
```powershell
kubectl get pods --watch
```

Expected output when running:
```
NAME        READY   STATUS    RESTARTS   AGE
hello-pod   1/1     Running   0          87s
```

---

## 9. Inspecting Pods with kubectl

### Basic listing
```powershell
kubectl get pods                    # list pods in default namespace
kubectl get pods -o wide            # more columns: node, IP, etc
kubectl get pods -o yaml            # full YAML with desired state (spec) and observed state (status)
kubectl get pods --watch            # watch live updates
```

> 💡 **spec vs status:** In the YAML output, `spec` shows **desired state** (what you asked for) and `status` shows **observed state** (what's actually running). This is the declarative model in action — k8s constantly reconciles these two.

### Detailed inspection
```powershell
kubectl describe pod hello-pod
```

This gives a human-readable overview including name, namespace, labels, node assignment, IP, container details, conditions, and most importantly — **Events**. The Events section shows the full lifecycle: scheduling, image pulling, container creation, startup. This is the first place to look when a Pod isn't starting.

### Logs
```powershell
kubectl logs hello-pod                              # logs from the only/first container
kubectl logs hello-pod --container <container-name> # specific container in multi-container Pod
```

### Exec — run commands inside a running container
```powershell
# Run a single command and return output
kubectl exec hello-pod -- ps

# Open an interactive shell (like SSH into the container)
kubectl exec -it hello-pod -- sh

# For a specific container in a multi-container Pod
kubectl exec -it hello-pod --container <container-name> -- sh
```

> 💡 **For students:** `kubectl exec` is like `docker exec` — it lets you get inside a running container to inspect it. Use it for debugging only. Making persistent changes via exec is an anti-pattern — Pods are immutable, any changes you make will be lost when the Pod is replaced.

---

## 10. Verifying Pod Immutability

Try to edit a running Pod's container name, port, or resource limits:

```powershell
kubectl edit pod hello-pod
```

Change something immutable (like the container name) and save. Kubernetes will reject the change with a forbidden error — this is immutability in action.

---

## 11. Resource Requests and Limits

Every Pod should define resource requests and limits for its containers:

```yaml
spec:
  containers:
  - name: hello-ctr
    image: nigelpoulton/k8sbook:1.0
    resources:
      requests:         # minimums — used by the Scheduler
        cpu: 0.5
        memory: 256Mi
      limits:           # maximums — enforced by the Kubelet
        cpu: 1.0
        memory: 512Mi
```

**Requests** — tell the Scheduler the minimum CPU and memory a container needs. The Scheduler uses this to find a node with enough available resources. If no suitable node exists, the Pod stays `Pending`. In autoscaling environments, a pending Pod can trigger provisioning of a new node.

**Limits** — tell the Kubelet the maximum a container is allowed to consume. A container can burst above its requests (using spare node capacity) but never above its limits.

> 💡 **For students:** If you omit both requests and limits, the Scheduler can't know what the Pod needs and may schedule it to a node with insufficient resources. Always define them in production.

---

## 12. Multi-Container Pods

Multi-container Pods are used when two containers need to run very closely together — sharing the same network, volumes, or memory. The guiding principle is **single responsibility**: each container does one clearly defined thing.

> 💡 **Common mistake:** An app and its database should NOT be in the same Pod. They're separate services — put them in separate Pods and let them communicate over the pod network. Multi-container Pods are for tightly coupled helpers, not separate services.

There are two main patterns:

### Init Containers

Init containers run and complete **before** the main container starts. Kubernetes guarantees:
- Init containers start before any regular containers
- They run only once
- All init containers must complete successfully before the main container starts
- If multiple init containers are defined, they run sequentially
- If an init container fails, k8s retries it

Common use cases: waiting for a dependency (database, service) to be available, fetching config data, setting up file permissions.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: initpod
  labels:
    app: initializer
spec:
  initContainers:
  - name: init-ctr
    image: busybox:1.28.4
    command: ['sh', '-c', 'until nslookup k8sbook; do echo waiting for k8sbook service; sleep 1; done; echo Service found!']
  containers:
  - name: web-ctr
    image: nigelpoulton/web-app:1.0
    ports:
    - containerPort: 8080
```

The `init-ctr` keeps looping until a Service named `k8sbook` is resolvable via DNS. Only then does it exit and allow `web-ctr` to start.

Deploy it:
```powershell
kubectl apply -f initpod.yml
kubectl get pods --watch
```

You'll see `Init:0/1` — the init container is running, main container hasn't started yet:
```
NAME        READY   STATUS      RESTARTS   AGE
initpod     0/1     Init:0/1    0          4s
```

Deploy the service it's waiting for:
```powershell
kubectl apply -f initsvc.yml
```

Watch the init container exit and the main container start:
```
NAME        READY   STATUS    RESTARTS   AGE
initpod     1/1     Running   0          3m53s
```

### Sidecar Containers

Sidecar containers run **alongside** the main container for the entire life of the Pod. They add functionality without modifying the main app. Common examples: log scraping, metrics collection, service mesh proxies, git sync.

**Two ways to define sidecars — both are valid:**

**The book's approach** (classic, works on all k8s versions) — both containers defined in `spec.containers`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: git-sync
  labels:
    app: sidecar
spec:
  containers:
  - name: ctr-web                        # main container
    image: nginx
    volumeMounts:
    - name: html
      mountPath: /usr/share/nginx/
  - name: ctr-sync                       # sidecar container
    image: k8s.gcr.io/git-sync:v3.1.6
    volumeMounts:
    - name: html
      mountPath: /tmp/git
    env:
    - name: GIT_SYNC_REPO
      value: https://github.com/nigelpoulton/ps-sidecar.git
    - name: GIT_SYNC_BRANCH
      value: master
    - name: GIT_SYNC_DEPTH
      value: "1"
    - name: GIT_SYNC_DEST
      value: "html"
  volumes:
  - name: html
    emptyDir: {}
```

**The newer approach** (Kubernetes v1.29+ / stable in v1.33) — sidecar defined in `spec.initContainers` with `restartPolicy: Always`. This is what distinguishes it from a regular init container and gives k8s explicit lifecycle guarantees:

```yaml
spec:
  initContainers:
  - name: ctr-sync
    restartPolicy: Always        # this makes it a sidecar, not a regular init container
    image: k8s.gcr.io/git-sync:v3.1.6
    ...
  containers:
  - name: ctr-web
    image: nginx
    ...
```

With the newer approach, Kubernetes guarantees the sidecar will:
- Start **before** the main container
- Keep running **alongside** the main container
- Terminate **after** the main container

> 💡 The only real difference between the two approaches is the **startup order guarantee**. With the modern way k8s guarantees the sidecar is up and running before the main container starts — useful when the main container depends on the sidecar being ready (like needing content synced before nginx starts serving). With the classic way both start simultaneously with no guaranteed order.

> 💡 **For students:** The classic approach works fine and is what the book uses. The newer `initContainers` approach gives stronger lifecycle guarantees and is the direction k8s is heading. For the auditory, use whichever your cluster version supports.

Deploy it:
```powershell
kubectl apply -f sidecar-local.yml
kubectl get pods --watch
```

You'll see `2/2 Running` — both the sidecar and the main container are up:
```
NAME        READY   STATUS    RESTARTS   AGE
git-sync    2/2     Running   0          32s
```

### Sidecar Variations

Two named variations of the sidecar pattern worth knowing:

**Adapter** — takes output from the main container and reformats it for another system. Example: converting nginx access logs into Prometheus metrics format.

**Ambassador** — acts as a proxy that brokers connectivity to an external system. Example: routing database connections through a proxy that handles connection pooling or SSL termination.

Both are implemented as sidecar containers at the Kubernetes level — these are just conceptual categories.

---

## 13. Cleanup

When done, delete everything and destroy the cluster:

```powershell
# Delete individual objects
kubectl delete pod hello-pod initpod git-sync
kubectl delete svc k8sbook

# Or delete by manifest files
kubectl delete -f pod.yml -f initpod.yml -f initsvc.yml -f sidecar-local.yml

# Destroy the cluster
k3d cluster delete kube2
```

---

## Key Takeaways

1. **Everything runs in a Pod** — Pods are not optional, they are the atomic unit of scheduling
2. **Pods are mortal** — they are replaced, not restarted. Never design apps that depend on a specific Pod persisting
3. **Pods are immutable** — changes require creating a new Pod
4. **Pod lifecycle:** Pending → Running → Succeeded/Failed
5. **Restart policies apply to containers**, not Pods — they don't protect against node failure
6. **Always use a Controller** (Deployment, StatefulSet, DaemonSet) — never deploy raw static Pods in production
7. **Multi-container Pods share one execution environment** — same IP, same volumes, same hostname
8. **Init containers** prepare the environment and complete before the main container starts
9. **Sidecar containers** run alongside the main container for its full lifetime
10. **Always define resource requests and limits** — without them the Scheduler can't make good decisions
11. **Pod IPs and DNS names are ephemeral** — use Services for stable addressing

---

## Common Mistakes to Avoid

**"Two containers that work together belong in the same Pod"** — Not necessarily. Use the same Pod only when containers need to share network, volumes, or memory. Loosely coupled services belong in separate Pods.

**"All containers in the same Pod can use the same port"** — No. They share the same network namespace and port range. Two containers in the same Pod cannot both listen on port 8080.

**"A failed Pod is restarted"** — No. It is replaced with a new one with a new identity and IP. Only containers within a Pod can be restarted in place.

**"Restart policy restarts the Pod"** — No. It controls container restarts within a Pod on the same node. Node failure requires a Controller to reschedule the Pod elsewhere.

**"I can fix a running Pod via kubectl exec"** — Don't. Pods are immutable. Changes made inside a container don't persist when the Pod is replaced. Use exec for inspection only.

---

*Kubernetes Auditory Guide | Chapter 4: Working with Pods | Continuous Integration and Delivery 2023*