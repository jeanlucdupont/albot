flowchart TD
    A[Start: What do you need most?] --> B{Latency & runtime needs}
    B -->|Ultra-low latency\nLong or steady runtime| VMs[Virtual Machines]
    B -->|Low to medium latency\nShort/episodic runtime| C{Compliance & control}
    C -->|Strict control\nCustom OS/Networking| CON[Containers (K8s/ECS)]
    C -->|Managed & event-driven OK| S[Serverless (Functions/FAAS)]

    A --> D{Traffic pattern}
    D -->|Spiky/bursty| S
    D -->|Predictable/steady| CON

    A --> E{Portability priority}
    E -->|High (avoid lock-in)| CON
    E -->|Low/Medium| S

    A --> F{Operational model}
    F -->|Full control of infra| VMs
    F -->|App focus, infra abstracted| S

    VMs ---|Pros: Max control; no runtime limits| P1(( ))
    VMs ---|Cons: Highest ops burden & cost| P2(( ))

    CON ---|Pros: Portable; good scaling & cost| P3(( ))
    CON ---|Cons: Orchestration complexity| P4(( ))

    S ---|Pros: Pay-per-use; fast to build| P5(( ))
    S ---|Cons: Cold starts; provider lock-in| P6(( ))
