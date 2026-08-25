# Platform Engineering Study Notes

## Progress

# Data Platform Engineering Roadmap

> A long-term learning and portfolio project documenting my progression from Data Engineer to Platform Engineer and eventually AI Data Platform Engineer.

---

# About Me

I currently work as a **Data Engineer** with experience primarily in:

- Microsoft Azure Fabric
- AWS (S3, Athena)
- DuckDB
- SQL
- Python
- PySpark / Spark
- Power BI
- ETL / ELT Pipelines
- Data Warehousing

While my day-to-day work focuses on building data pipelines, my long-term goal is different:

> **I want to build the platforms that data engineers use—not just the pipelines that run on them.**

This repository documents that journey.

---

# Career Vision

Rather than following the traditional path:

```
Junior Data Engineer
        ↓
Senior Data Engineer
```

I want to evolve toward:

```
Data Engineer
        ↓
Senior Data Engineer
        ↓
Platform Engineer
        ↓
AI Data Platform Engineer
        ↓
Principal / Staff Engineer
```

The objective is to understand **how modern data platforms are built**, not only how to use them.

---

# What is a Data Platform Engineer?

Instead of asking:

> "How do I move data?"

A Platform Engineer asks:

> "How do I build the infrastructure that allows everyone else to move data?"

A modern Data Platform typically includes:

- Data Lake
- Metadata Services
- Data Catalog
- Orchestration
- Data Quality
- Monitoring & Observability
- Authentication & Authorization
- Infrastructure as Code
- CI/CD
- Internal APIs
- Self-Service Developer Platform

The goal is to build something similar in spirit to platforms such as Microsoft Fabric or Databricks.

---

# Roadmap

## Phase 1 — Cloud Foundations

Become cloud agnostic.

Topics:

- Docker
- Kubernetes
- Terraform
- GitHub Actions
- Infrastructure as Code
- Secrets Management
- Networking
- IAM

Goal:

Be comfortable deploying and managing infrastructure in any cloud.

---

## Phase 2 — Modern Data Stack

Learn the technologies that power today's data platforms.

Storage

- Delta Lake
- Apache Iceberg
- Apache Hudi

Streaming

- Apache Kafka

Orchestration

- Apache Airflow
- Dagster

Transformation

- dbt

Monitoring

- Prometheus
- Grafana

---

## Phase 3 — Distributed Systems

Understand **why** distributed systems work.

Topics include:

- CAP Theorem
- Consensus
- Raft
- Paxos
- Replication
- Fault Tolerance
- Leader Election
- Storage Engines
- Query Optimizers

Recommended books:

- Designing Data-Intensive Applications
- Database Internals

---

## Phase 4 — Build a Platform

The objective is no longer to build an ETL pipeline.

Instead, build an entire platform.

Example architecture:

```
                Users
                  │
          REST / FastAPI
                  │
           Authentication
                  │
            API Gateway
                  │
           Metadata Service
                  │
          Orchestration Layer
                  │
         Spark / Batch Jobs
                  │
      Delta / Iceberg Storage
                  │
          DuckDB Analytics
                  │
        Monitoring & Alerts
```

---

# Future Direction

Eventually extend the platform with AI capabilities.

Possible additions:

- LLM Gateway
- Agent Framework
- RAG
- Vector Database
- MCP Servers
- Prompt Versioning
- Evaluation Pipelines
- Cost Monitoring
- Multi-Agent Workflows

Resulting architecture:

```
Users

↓

API Gateway

↓

Authentication

↓

LLM Router

↓

Vector Database

↓

Metadata Store

↓

DuckDB

↓

Data Lake

↓

Cloud Storage
```

---

# Planned Projects

## Project 1

Infrastructure as Code

Learn to deploy infrastructure using Terraform.

---

## Project 2

Containerized Data Platform

Deploy services with Docker and Kubernetes.

---

## Project 3

Streaming Platform

Build a Kafka-based streaming system.

---

## Project 4

Lakehouse

Create a Delta Lake / Iceberg based platform.

---

## Project 5

Observability

Integrate monitoring, logging and alerting.

---

## Project 6

Self-Service Platform

Allow users to create data pipelines through APIs.

---

## Project 7

AI Data Platform

Integrate LLMs, RAG, tool calling and agents into the platform.

---

# Repository Structure

```
platform-engineering-roadmap/

│
├── docs/
│
├── notes/
│
├── projects/
│   ├── project-01-iac/
│   ├── project-02-docker/
│   ├── project-03-kubernetes/
│   ├── project-04-kafka/
│   ├── project-05-lakehouse/
│   ├── project-06-observability/
│   └── project-07-ai-platform/
│
├── architecture/
│
├── diagrams/
│
├── scripts/
│
└── README.md
```

---

# Guiding Principle

This repository is not intended to showcase isolated technologies.

The objective is to understand how production-grade data platforms are designed, implemented, operated, and evolved.

Each project should answer one question:

> **"Why does this technology exist, and how does it fit into a complete platform?"**

---

# Long-Term Goal

Build a portfolio that demonstrates the ability to design and implement modern, cloud-native data platforms incorporating:

- Distributed Systems
- Platform Engineering
- Cloud Infrastructure
- Data Engineering
- DevOps
- AI Infrastructure

Ultimately, the aim is to become an engineer capable of building the platforms that other engineers rely on every day.

### 1. Distributed Systems

Covered: - CAP Theorem - Distributed Systems Fundamentals - Consensus -
Leader Election - Partitions - Fault Tolerance - Paxos - Raft

Key takeaway: Distributed systems exist because one computer is not
enough. They trade simplicity for scalability, availability, and
resilience.

------------------------------------------------------------------------

### 2. Platform Engineering

Covered: - Infrastructure as Code - Internal Developer Platforms -
Golden Paths - Self-Service - APIs - Platform UX

Key takeaway: Platform Engineering is about building the infrastructure
and developer experience that allows engineers to build products quickly
and safely.

------------------------------------------------------------------------

# DevOps

## Docker

### What Docker Solves

Developers historically faced the "Works on my machine" problem due to
different operating systems, library versions, and configurations.

Docker packages: - Application code - Runtime - Libraries -
Dependencies - Configuration

into a portable **Docker Image**.

### Core Concepts

#### Image

Blueprint (recipe) used to create containers.

#### Container

A running instance of an image.

Images are reusable. Containers can be started, stopped, recreated, or
deleted.

### Containers vs Virtual Machines

#### Virtual Machine

Includes: - Full Guest Operating System - Drivers - Libraries -
Application

Pros: - Strong isolation - Can run different operating systems

Cons: - Heavy - Slow startup - High RAM and disk usage

#### Docker Container

Includes: - Application - Dependencies - Runtime

Shares the host operating system kernel.

Pros: - Lightweight - Starts in seconds - Efficient resource usage

Cons: - Shares host kernel - Less isolated than VMs

### Why Containers Are Sometimes Temporary

Containers should live as long as the work they perform.

Temporary examples: - ETL jobs - Spark jobs - CI/CD testing - Data
conversion - ML training

Long-running examples: - PostgreSQL - Kafka - Airflow Scheduler - APIs -
Redis

### Persistent Data

Deleting a container removes its internal filesystem.

Persistent data should be stored in: - Docker Volumes - Bind Mounts

This allows containers to be replaced without losing data.

### Mental Model

Image = Recipe

Container = Cake

or

Image = Blueprint

Container = Running Building

------------------------------------------------------------------------

## GitHub Actions

### Purpose

GitHub Actions automates repetitive software delivery tasks.

Typical workflow:

Developer Pushes Code → Run Tests → Build Docker Image → Publish Image →
Deploy

### Core Concepts

#### Repository

Project stored on GitHub.

#### Event (Trigger)

Examples: - Push - Pull Request - Schedule - Manual trigger

#### Workflow

Complete automation pipeline.

#### Job

A major stage within a workflow.

#### Step

An individual command executed within a job.

### Runners

A Runner is the computer that executes workflow jobs.

#### GitHub-hosted Runner

-   Provided by GitHub
-   Temporary virtual machine
-   Fresh environment every run
-   Automatically managed

Most users use GitHub-hosted runners.

#### Self-hosted Runner

Your own computer or server executes workflows.

Useful when: - Internal company network access is required - Special
hardware (GPU, USB devices, sensors) - Custom operating system or
configuration

### Why One Job Per Runner?

Each runner executes a single job at a time.

GitHub scales by creating many runners in parallel.

One Runner ≠ One Workflow globally.

Thousands of workflows can execute simultaneously using thousands of
runners.

### Relationship Between Docker and GitHub Actions

GitHub Actions decides: WHEN automation runs.

Runner decides: WHERE it runs.

Docker decides: WHAT environment the application runs in.

Typical flow:

Git Push → GitHub Actions → GitHub-hosted Runner → Build Docker Image →
Run Tests → Publish Image → Deploy

------------------------------------------------------------------------

# Overall Learning Roadmap

Completed: - Distributed Systems - Platform Engineering - Docker -
GitHub Actions

Upcoming: - Docker Compose - Kubernetes - Helm - Terraform -
Observability - GitOps - Building an Internal Developer Platform
