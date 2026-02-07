# Azure DevOps Pipeline – GeneXus Java Application Deployment with Docker and Azure Repos

## Overview

This project implements a **CI/CD pipeline using Azure DevOps** to build, deploy, and publish a **GeneXus-generated Java application**.

The pipeline automates the full lifecycle: building the Knowledge Base, generating a WAR file, deploying it into a Docker container running Apache Tomcat on a remote server, and pushing the WAR artifact to **Azure Repos** for versioning and traceability.

---

## High-Level Workflow

1. Pipeline is triggered on changes to the main branch.
2. GeneXus Knowledge Base is updated and built.
3. A WAR deployment package is generated.
4. The WAR file is finalized and prepared.
5. The application is deployed to a remote Docker container.
6. The WAR artifact is committed and pushed to Azure Repos.

---

## Technologies Used

- Azure DevOps Pipelines – CI/CD orchestration
- GeneXus 18 (Java) – Low-code Java application generation
- MSBuild – Build automation
- Java / Apache Tomcat – Runtime environment
- Docker – Containerized deployment
- SSH / SCP – Secure remote access
- Batch scripts (.bat) – Automation
- Git / Azure Repos – Artifact versioning

---

## Pipeline Steps

### 1. Update Knowledge Base
Synchronizes and updates the GeneXus Knowledge Base using TeamDev tasks.

### 2. Build Knowledge Base
Compiles the GeneXus Java application and generates binaries.

### 3. Create WAR Package
Generates the deployment project and builds the WAR file.

### 4. Finalize WAR File
Applies final configuration to the WAR file for deployment.

### 5. Deploy to Remote Docker Container
Stops Tomcat, deploys the WAR inside the container, and restarts services.

### 6. Push WAR to Azure Repos
Commits and pushes the WAR artifact to Azure Repos.

---

## Security Considerations

- Secrets are managed using Azure DevOps Variable Groups
- No credentials are hardcoded
- SSH connections are non-interactive

---

## Conclusion

This pipeline provides an enterprise-ready solution for deploying GeneXus Java applications using Docker and Azure Repos.
