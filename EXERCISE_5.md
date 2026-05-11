# Kubernetes Auditory Guide
### Chapters 1-3 | Practical Session Guide

---

## Before You Start

### kubectl
`kubectl` is the CLI tool for controlling Kubernetes clusters. It sits on your local machine and talks to the Kube API Server — it's your cockpit for everything k8s related. Every time you want to deploy, inspect, scale, or delete something in k8s, you use kubectl.

The command pattern is always:
```powershell
kubectl [action] [object] [name]
# examples:
kubectl get pods
kubectl delete deployment nginx-deployment
kubectl apply -f nginx-deployment.yaml
```

### k3d
`k3d` is a tool that runs a lightweight Kubernetes distribution called **k3s** inside Docker containers. Instead of needing real separate machines for your cluster nodes, k3d spins them up as Docker containers on your laptop — making it perfect for local development and learning.

> 💡 **For students:** kubectl is how you talk to any Kubernetes cluster — local or production. k3d is just a convenient way to get a local cluster running quickly without needing real machines or a cloud provider.

Make sure Docker Desktop is running, then verify your tools:
```powershell
kubectl version --client
k3d version
```

---

## 1. What is Kubernetes?

Kubernetes (pronounced *koo-ber-net-eez*, shortened to **k8s**) is an **application orchestrator**. It:
- Deploys your containerized applications
- Scales them up and down based on demand
- Self-heals when things break
- Performs zero-downtime rolling updates and rollbacks

> 💡 **For students:** Think of Kubernetes as a manager for your containers. You tell it what you want running, and it makes sure that's always the case — even if things crash, nodes fail, or traffic spikes.

---

## 2. The Declarative Model

The most important mental model in Kubernetes. You never say *"start a container on node 3"*. Instead you declare **what you want** and Kubernetes figures out how to make it happen:

```
Desired state (what you declared)
        vs
Observed state (what's actually running)
        → differences → actions
```

This loop runs **constantly**. Pod dies? K8s replaces it. Node fails? K8s reschedules everything. You never have to intervene.

---

## 3. Cluster Architecture

A Kubernetes cluster has two types of nodes:

### Control Plane Nodes (the "brain")
- **API Server** — everything talks through this. `kubectl`, workers, controllers — all go through the API server. It's the single entry point for the entire cluster.
- **etcd** — a key-value database that stores the entire cluster state. K8s's memory.
- **Scheduler** — decides *which* worker node a Pod should run on, based on available resources.
- **Controller Manager** — the reconciliation loop. Constantly watches: *is what's running matching what I asked for?* If not, it acts.

### Worker Nodes (the "muscle")
- **Kubelet** — the k8s agent on each worker. Watches the API server for orders and executes them. Doesn't think, just executes and reports.
- **Container Runtime** — actually starts/stops containers (containerd in k3s).
- **Kube-proxy** — handles networking between pods (IP addresses, routing, load balancing).

> 💡 **For students:** You never talk to workers directly. Everything goes:
> ```
> You (kubectl) → API Server → etcd stores it → Scheduler assigns it → Kubelet executes it
> ```

---

## 4. Setting Up Your Cluster

### Create the cluster

The cluster is always step zero — without it there's nowhere to deploy anything. Think of it like: you need a server before you can run an app.

The number of nodes depends entirely on your use case:
- **For learning/dev** → 1 server, 1 agent is enough
- **For production** → control plane nodes always in odd numbers (3, 5, 7) for HA, worker nodes as many as your workload needs

For this auditory we'll spin up 3 control plane nodes and 5 worker nodes:

```powershell
k3d cluster create mycluster --servers 3 --agents 5 -p "8080:80@loadbalancer"
```

- `--servers 3` → 3 control plane nodes (always odd numbers for HA — because of how etcd voting works)
- `--agents 5` → 5 worker nodes
- `-p "8080:80@loadbalancer"` → maps port 8080 on your laptop to the cluster load balancer

> 💡 **For students:** k3d runs each node as a Docker container on your machine. Run `docker ps` after this and you'll see all 9 containers (3 servers + 5 agents + 1 load balancer). In real production these would be separate physical or cloud machines.

### A note on Ingress and Traefik

Port 8080 maps to the k3d load balancer, which forwards all traffic to **Traefik** — the ingress controller that k3s ships with by default. Think of Traefik as a smart gatekeeper sitting in front of your cluster:

```
browser:8080 → k3d load balancer → Traefik → ??? → your Service → your Pods
```

The problem is Traefik doesn't know where to send traffic unless you tell it. That's done with an **Ingress** object — a k8s resource that tells Traefik:

```
"When a request comes in for /nginx, forward it to nginx-service on port 80"
```

Without an Ingress, Traefik has no routing rules and returns `404 page not found`.

> 💡 **For students:** Ingress is a topic for a later chapter. For now we bypass Traefik entirely using `kubectl port-forward`, which creates a direct tunnel straight to your Service. In production the full flow would be:
> ```
> browser → cloud load balancer → Traefik (Ingress) → Service → Pods
> ```

```powershell
docker ps
```

### Fix kubectl connection (Windows only)

After cluster creation, kubectl might not connect. Find the API server port from `docker ps` — look for `k3d-mycluster-serverlb` and the port mapped to `6443`:

```
0.0.0.0:59940->6443/tcp   ← your port is 59940
```

Then point kubectl to it:
```powershell
kubectl config set-cluster k3d-mycluster --server=https://127.0.0.1:<PORT>
```

### Verify the cluster

```powershell
kubectl get nodes
```

Expected output:
```
NAME                     STATUS   ROLES                       AGE   VERSION
k3d-mycluster-agent-0    Ready    <none>                      ...   v1.31.5+k3s1
k3d-mycluster-agent-1    Ready    <none>                      ...   v1.31.5+k3s1
k3d-mycluster-agent-2    Ready    <none>                      ...   v1.31.5+k3s1
k3d-mycluster-agent-3    Ready    <none>                      ...   v1.31.5+k3s1
k3d-mycluster-agent-4    Ready    <none>                      ...   v1.31.5+k3s1
k3d-mycluster-server-0   Ready    control-plane,etcd,master   ...   v1.31.5+k3s1
k3d-mycluster-server-1   Ready    control-plane,etcd,master   ...   v1.31.5+k3s1
k3d-mycluster-server-2   Ready    control-plane,etcd,master   ...   v1.31.5+k3s1
```

- `Ready` → node is healthy and accepting work
- `control-plane,etcd,master` → brain nodes. Notice `etcd` is listed here — the database runs on the control plane
- `<none>` → worker nodes, no special role, they just run your apps

### Check system pods

Before deploying anything, look at what k8s already has running:

```powershell
kubectl get pods -A
```

> 💡 **For students:** The `-A` flag means `--all-namespaces`. Without it, kubectl only shows the `default` namespace where your apps live. K8s runs its own components as pods in the `kube-system` namespace — this proves k8s manages itself the same way it manages your apps.

Key system pods you'll see:
- `coredns` — DNS server for the cluster. Makes Services reachable by name inside the cluster.
- `metrics-server` — collects CPU/RAM usage from all nodes. Needed for autoscaling.
- `traefik` — ingress controller. Handles incoming traffic from outside the cluster.
- `svclb-traefik` (one per node) — a **DaemonSet** in action: automatically runs exactly one pod on every node in the cluster.

---

## 5. Pods

A Pod is the **atomic unit of scheduling** in Kubernetes — like a container is in Docker, like a VM is in virtualization.

Key things to know:
- A Pod is a logical wrapper around one or more containers
- Simplest use case: one container per Pod
- **Pods are mortal** — once a Pod dies, it never comes back. A new one is created in its place with a new name and a new IP address
- **Pods are immutable** — to update a Pod, the old one is destroyed and a new one is created
- Scaling means adding more Pods, not more containers inside a Pod

> 💡 **For students:** You almost never deploy raw Pods directly. You always wrap them in a higher-level controller like a Deployment — so k8s can manage, heal, and scale them for you.

---

## 6. Deployments

A Deployment is a higher-level object that wraps Pods and adds:
- **Self-healing** — replaces failed pods automatically
- **Scaling** — increase/decrease replicas with one command
- **Rolling updates** — update your app version with zero downtime
- **Rollbacks** — go back to a previous version if something breaks

### Deploy nginx

Create a file called `nginx-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
```

> 💡 **YAML explained:**
> - `apiVersion: apps/v1` → Deployments belong to the `apps` API group. Core objects like Pods use `v1`, app controllers use `apps/v1`
> - `replicas: 3` → we want 3 instances of nginx running at all times
> - `labels: app: nginx` → a tag that connects Pods to their Deployment and later to a Service
> - `image: nginx:latest` → the Docker image to run inside the container

**Replicas = Pods.** Each replica is one pod running your container. `replicas: 3` means k8s creates 3 identical pods:

```
Deployment (replicas: 3)
    ├── Pod 1 → nginx container
    ├── Pod 2 → nginx container
    └── Pod 3 → nginx container
```

Each pod is an independent, fully running instance of your app. They all do the same thing and the Service load balances traffic between them. One pod, one replica — always a 1:1 relationship.

Apply it:
```powershell
kubectl apply -f nginx-deployment.yaml
```

Check the deployment:
```powershell
kubectl get deployments
```

Watch pods come up:
```powershell
kubectl get pods -w
```

> 💡 The `-w` flag means **watch** — updates live as status changes. You'll see pods go from `ContainerCreating` → `Running`. Hit `Ctrl+C` to stop.

Once running you'll see something like:
```
NAME                                READY   STATUS    RESTARTS   AGE
nginx-deployment-54b9c68f67-kk9bx   1/1     Running   0          2m
nginx-deployment-54b9c68f67-mwfvs   1/1     Running   0          2m
nginx-deployment-54b9c68f67-wdzff   1/1     Running   0          2m
```

The pod name is auto-generated:
```
nginx-deployment  -  54b9c68f67  -  kk9bx
[deployment name] - [replicaset id] - [random pod id]
```

---

## 7. Demo — Self-Healing

Delete one pod manually:
```powershell
kubectl delete pod <pod-name>
```

Watch what happens immediately:
```powershell
kubectl get pods -w
```

> 💡 **What to explain:** The Deployment controller detected only 2 pods running when desired state is 3. It immediately scheduled a brand new pod. Notice the old pod name is gone forever — replaced by a completely new pod with a new name and new IP. This is the reconciliation loop:
> ```
> Desired state: 3 pods
> Observed state: 2 pods
> Difference → action → new pod scheduled
> ```

---

## 8. Scaling

Kubernetes scales in two directions and it's important to understand the difference:

**Scale your app (more pods)** — when you need more instances to handle traffic:
```
1 nginx pod → 6 nginx pods (spread across your worker nodes)
```

**Scale your cluster (more nodes)** — when your workers are running out of CPU/RAM and there's no room to schedule new pods. More nodes = more capacity for pods.

> 💡 **For students:** Think of it this way — too much traffic to your app? Add more pods. Not enough room in the cluster to run those pods? Add more worker nodes. One is scaling your app, the other is scaling your infrastructure.

When workers are full, new pods can't be scheduled — they'll just sit in `Pending` state waiting for space. In real cloud environments a **Cluster Autoscaler** handles this automatically, adding and removing nodes based on demand.

### Demo — Scale up
```powershell
kubectl scale deployment nginx-deployment --replicas=6
kubectl get pods -w
```

> 💡 **What to explain:** K8s spun up 3 new pods instantly. The existing 3 kept running untouched — zero downtime. You just changed a number, k8s handled everything else. This is the declarative model — you declared the desired state as 6, k8s acted on the difference.

### Demo — Scale down
```powershell
kubectl scale deployment nginx-deployment --replicas=2
kubectl get pods
```

> 💡 **What to explain:** K8s immediately terminated 4 pods and kept exactly 2. Same concept, opposite direction. K8s keeps the oldest pods by default and terminates the newest ones.

Scale back to 3 for the next demos:
```powershell
kubectl scale deployment nginx-deployment --replicas=3
```

---

## 9. Services

Pods die and get replaced constantly, and every new pod gets a **different IP address**. So you can never reliably say "my nginx is at 10.0.0.5" because tomorrow that pod might be gone.

A Service sits in front of your pods and gives you a **stable endpoint that never changes**, regardless of what's happening to the pods behind it:

```
User → Service (stable IP + stable DNS name) → Pod 1
                                              → Pod 2
                                              → Pod 3
```

The Service constantly watches which pods match its selector and updates its list automatically. Pod dies? Service removes it. New pod comes up? Service adds it. You never notice.

### Service types
- `ClusterIP` — only reachable inside the cluster. For pod-to-pod communication. Default.
- `NodePort` — exposes the app on a port on every node. Reachable from outside, mostly for testing.
- `LoadBalancer` — creates an external load balancer with a public IP. For production on cloud providers.

### How Services find Pods — Labels

This is the glue of the whole system. Services don't find pods by name or IP — they find them by **labels**:

```
Deployment creates pods with:      Service looks for pods with:
  labels:                            selector:
    app: nginx          →              app: nginx
```

Any pod with the label `app: nginx` automatically becomes part of this Service's pool. Add more pods with that label and the Service includes them instantly.

### Create the Service

Create a file called `nginx-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  selector:
    app: nginx
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: LoadBalancer
```

> 💡 **YAML explained:**
> - `selector: app: nginx` → find all pods with this label and send traffic to them
> - `port: 80` → the port the Service listens on inside the cluster
> - `targetPort: 80` → the port on the actual container to forward traffic to
> - `type: LoadBalancer` → expose it externally

The three port concepts:
```
Outside world
      ↓
NodePort (auto-assigned, 30000-32767)   ← external access
      ↓
port: 80                                ← Service listens here inside cluster
      ↓
targetPort: 80                          ← actual container port
```

Apply it:
```powershell
kubectl apply -f nginx-service.yaml
kubectl get services
```

You'll see:
```
NAME            TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
kubernetes      ClusterIP      10.43.0.1      <none>        443/TCP        38m
nginx-service   LoadBalancer   10.43.69.108   <pending>     80:32506/TCP   30s
```

- `kubernetes` → default Service k8s creates so pods can talk to the API server. Ignore it.
- `CLUSTER-IP` → stable internal IP, always reachable inside the cluster
- `EXTERNAL-IP: <pending>` → on a real cloud provider this would get a public IP. On local k3d it stays pending — no real cloud load balancer exists
- `80:32506` → two ports, two different ways to reach the Service:
  - `80` → the Service port, used for internal cluster traffic (pod to pod)
  - `32506` → the NodePort, auto-assigned by k8s (always between 30000-32767). This lets you reach the Service from outside the cluster by hitting any node's IP on this port: `http://<node-ip>:32506`. In our k3d setup the nodes are Docker containers without accessible IPs, so we can't use this — but on a real cluster or bare-metal setup this would work. In production on cloud providers you'd never expose NodePorts directly to users — you'd always go through a LoadBalancer or Ingress instead.

### Access nginx in the browser

Since we're running locally, use port-forward to create a direct tunnel to the Service:

```powershell
kubectl port-forward service/nginx-service 8080:80
```

Open `http://localhost:8080` → nginx welcome page.

> 💡 **Why port-forward?** Port 8080 on our cluster is mapped to Traefik (k3d's built-in ingress controller), not directly to nginx. `port-forward` bypasses Traefik and creates a direct tunnel to your Service. This is a dev/debugging tool — not for production. In production, traffic flows:
> ```
> browser → cloud load balancer → Ingress controller → Service → pods
> ```

---

## 10. Demo — Service Resilience

This is the best demo. While `port-forward` is still running and browser is open at `http://localhost:8080`:

Open a **new terminal** and delete a pod:
```powershell
kubectl delete pod <pod-name>
```

Immediately refresh your browser.

> 💡 **What to explain:** The page still loads. The Service automatically routed traffic to the other running pods. Zero downtime, zero intervention. This is exactly why Services exist — they abstract the unstable world of pods behind a stable endpoint. The user never knew a pod just died.

---



## Key Takeaways for Students

1. **Kubernetes = orchestrator** — declare what you want, k8s makes it happen and keeps it that way forever
2. **Declarative > imperative** — describe the desired state, not the steps to get there
3. **Pods are mortal** — they die and get replaced. Never rely on a specific pod's IP or name
4. **Services are stable** — always access your app through a Service, never directly through a pod
5. **Labels are the glue** — everything in k8s is connected through labels and selectors
6. **The reconciliation loop never stops** — k8s is constantly watching and fixing

---

## 11. Cleanup

At the end of the auditory, delete the cluster:

```powershell
k3d cluster delete mycluster
```

This wipes everything — nodes, pods, deployments, services. Clean slate for the next session.

---

*Kubernetes Auditory Guide | Chapters 1-3 | Continuous Integration and Delivery 2023*