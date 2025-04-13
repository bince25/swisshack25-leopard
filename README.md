# Synapse Protocol

<div align="center">
  <img src="frontend/public/synapse-logo.png" alt="Synapse Protocol Logo" width="101" height="132" />
  
  <h3>Decentralized Payment Network for Autonomous Agents</h3>
  
  <p>
    <a href="https://synapse-protocol.org" target="_blank">Website</a> •
    <a href="https://synapse-protocol.org/dashboard" target="_blank">Live Demo</a>
  </p>
</div>

## 🌐 Overview

Synapse Protocol is a decentralized payment infrastructure enabling autonomous agents to transact directly with each other using RLUSD on the XRP Ledger. The protocol creates a trustless financial backbone for the emerging machine-to-machine economy, allowing AI agents, bots, and digital services to earn, spend, and establish payment channels without human intermediaries.

*[➡ Explore the Synapse Protocol Demo](https://synapse-protocol.org)*

## 🔑 Key Features

- *Agent-to-Agent Payments*: Direct value transfers between autonomous AI systems with on-chain settlement
- *Multi-Agent Orchestration*: Route tasks through specialized agent networks with automatic payment distribution
- *XRP Ledger Integration*: Built on XRP's fast, low-cost settlement layer with RLUSD stablecoin support
- *Wallet Management*: Secure agent identities with programmatic wallet creation and trustline management
- *Real-time Transaction Visualization*: Interactive network graph showing agent relationships and payment flows
- *Transaction History*: Complete audit trail of all inter-agent payments and transfers

## 🛠 Technology Stack

- *Frontend*: Next.js 15, React 19, TypeScript, Tailwind CSS
- *Blockchain*: XRP Ledger integration via xrpl.js
- *Visualization*: React Force Graph for real-time agent network visualization
- *Data Processing*: PapaParse, SheetJS for data handling
- *Wallet Integration*: Crossmark XRP wallet compatibility
- *State Management*: Custom React hooks and context API
- *Styling*: Advanced Tailwind CSS with custom animations
- *Agent Communication*: Socket.IO for real-time agent interaction

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ 
- Yarn or npm
- XRP Ledger Test Account (for running with real transactions)

## 💰 Wallet Setup

Synapse Protocol supports two wallet modes:

1. *Simulation Mode*: For testing without real transactions (default)
2. *Real Transaction Mode*: Using the XRP Testnet

To enable real transactions:

1. Set NEXT_PUBLIC_USE_REAL_TRANSACTIONS="true" in your .env.local
2. Follow the wallet setup guide in REAL_TRANSACTION_INTEGRATION.md
3. Create trustlines for each agent (available through the UI)

## 🔄 Agent Workflow

Agents in Synapse Protocol work together as follows:

1. A user submits a task through the interface
2. The orchestrator agent analyzes the task and selects specialized agents
3. The orchestrator initiates payment transactions to each selected agent
4. Selected agents perform their specialized tasks, receiving RLUSD payments
5. Results flow back to the orchestrator and are presented to the user
6. All transactions are recorded on the XRP Ledger with payment proofs

## 📊 Dashboard Features

- *Agent Network Visualization*: Interactive force-directed graph of agents
- *Transaction History*: Complete log of all agent-to-agent payments
- *Real-time Transaction Animation*: Visual representation of token flows
- *Wallet Status Monitoring*: Track wallet initialization and balances
- *XRP Ledger Integration*: Link directly to transactions on the XRPL explorer

## 🔐 Security Considerations

- All agent wallets are secured with proper key management
- Transactions are verified on-chain for maximum transparency
- Trustlines ensure agents can only receive tokens they're authorized for
- For production use, additional security measures are recommended (See SECURITY.md)

## 🌟 Why Visit Synapse Protocol?

*[Visit synapse-protocol.org](https://synapse-protocol.org)* to experience:

- The *live interactive demo* showcasing dynamic agent interactions
- A *visual representation* of the machine-to-machine economy in action
- *Real-time transaction flows* between intelligent agents
- *Technical documentation* on implementing agent-based payment systems
- *Integration guides* for connecting your own agents to the protocol

Synapse Protocol represents the future of autonomous economic interactions, providing a glimpse into how intelligent systems will transact value in the coming machine economy. The website offers both technical demos for developers and accessible explanations for those interested in the future of decentralized finance and artificial intelligence.

---

<div align="center">
  <p>Built with ❤ by the Synapse Protocol Team</p>
  <p>
    <a href="https://synapse-protocol.org">Website</a>
  </p>
</div>
