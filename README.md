\# SentinelX



SentinelX is a distributed monitoring and self-healing platform being developed as part of the COM668 Computing Project.



The project is designed to monitor smart, industrial, and edge computing environments using a lightweight software agent, a backend API, a database layer, and a web-based dashboard. The system will collect device health metrics, detect abnormal behaviour, display live monitoring data, and support basic recovery actions.



\## Project Status



This project is currently in active development.



The first development target is to build a complete end-to-end monitoring pipeline:



```text

Python Agent → FastAPI Backend → PostgreSQL Database → React Dashboard

```



\## Planned Core Features



\* User authentication

\* Role-based access control

\* Device registration

\* Lightweight monitoring agent

\* Agent heartbeat reporting

\* CPU, memory, and disk metric collection

\* Backend metric ingestion API

\* PostgreSQL metric storage

\* Web dashboard for device status

\* Alert generation

\* Basic anomaly detection

\* Recovery action logging

\* Testing and validation evidence



\## Intended Architecture



SentinelX will be structured as a multi-component system:



```text

agent/       Lightweight Python monitoring agent

backend/     FastAPI backend API

frontend/    React, Vite, TypeScript dashboard

database/    Database schema and seed data

docs/        Technical documentation

scripts/     Development and setup scripts

tests/       Testing resources where applicable

```



\## Technology Stack



The planned development stack is:



| Layer           | Technology                            |

| --------------- | ------------------------------------- |

| Frontend        | React, Vite, TypeScript, Tailwind CSS |

| Backend         | Python, FastAPI                       |

| Database        | PostgreSQL                            |

| Agent           | Python, psutil                        |

| Testing         | Pytest, Postman                       |

| Version Control | Git and GitHub                        |



\## Academic Context



This project is being developed for the COM668 Computing Project module. The implementation will be supported by professional software engineering practices, including version control, testing, documentation, requirements traceability, and structured evaluation.



\## Development Approach



The project will be developed incrementally. The initial focus is to deliver a small but complete working system before adding advanced features.



Priority order:



1\. Backend setup

2\. Database setup

3\. Device registration

4\. Agent heartbeat

5\. Metric collection

6\. Dashboard display

7\. Alerts

8\. Anomaly detection

9\. Recovery action logging

10\. Testing and documentation



\## Repository Notice



This repository is intended to contain the clean SentinelX source code and technical documentation only. Coursework reports, submission files, and university evidence documents are stored separately in the COM668 project submission folder.



