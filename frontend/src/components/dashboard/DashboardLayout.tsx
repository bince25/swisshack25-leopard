import React, { useState, useEffect } from "react";
import { Zap, Activity, ExternalLink, Shield } from "lucide-react";
import { Agent, AgentNetwork as AgentNetworkType } from "@/types/agent";
import { Transaction } from "@/types/transaction";
import AgentNetwork from "@/components/network/AgentNetwork";
import TransactionHistory from "@/components/transactions/TransactionHistory";
import AgentDetails from "@/components/agent/AgentDetails";
import PromptInput from "@/components/agent/PromptInput";
import StatusBar from "@/components/layout/StatusBar";

interface EnhancedDashboardProps {
  network: AgentNetworkType;
  transactions: Transaction[];
  balance: number;
  selectedAgent: Agent | null;
  selectedAgents: Agent[];
  processing: boolean;
  onAgentSelect: (agent: Agent) => void;
  onCloseDetails: () => void;
  onPromptSubmit: (prompt: string) => Promise<void>;
  onTransactionComplete: () => void;
  walletStatus?: {
    initialized: string[];
    pending: string[];
    failed: string[];
  };
  onBalanceUpdate: (amount: number) => void;
  isMobile?: boolean;
}

// Dashboard component with enhanced UI
const EnhancedDashboard: React.FC<EnhancedDashboardProps> = ({
  network,
  transactions,
  balance,
  selectedAgent,
  selectedAgents,
  processing,
  onAgentSelect,
  onCloseDetails,
  onPromptSubmit,
  onTransactionComplete,
  walletStatus,
  onBalanceUpdate,
  isMobile = false,
}) => {
  const [showGlowEffects, setShowGlowEffects] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<string>("network");

  // Enable glow effects after a short delay for better performance
  useEffect(() => {
    const timer = setTimeout(() => setShowGlowEffects(true), 1000);
    return () => clearTimeout(timer);
  }, []);

  const mainAgent = network.nodes.find((node) => node.id === "main-agent");

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white overflow-hidden">
      {/* Enhanced Header with Glassmorphism */}
      <header className="relative z-10 backdrop-blur-md bg-gray-900/80 border-b border-gray-700/50">
        {/* Background gradient decorations */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div
            className={`absolute top-0 left-1/4 w-1/3 h-1 bg-gradient-to-r from-transparent via-blue-500 to-transparent ${
              showGlowEffects ? "opacity-70" : "opacity-0"
            } blur-sm transition-opacity duration-1000`}
          ></div>
          <div
            className={`absolute bottom-0 right-1/3 w-1/4 h-px bg-gradient-to-r from-transparent via-indigo-500 to-transparent ${
              showGlowEffects ? "opacity-50" : "opacity-0"
            } transition-opacity duration-1000 delay-300`}
          ></div>
        </div>

        {/* Status Bar with Crossmark integration */}
        <StatusBar
          balance={balance}
          network="XRP Testnet"
          transactionCount={transactions.length}
          mainAgent={mainAgent}
          agents={network.nodes}
          onTransactionComplete={onTransactionComplete}
          onBalanceUpdate={onBalanceUpdate}
          walletStatus={walletStatus}
          hideCrossmark={isMobile}
        />
      </header>

      {/* Main Content with improved grid-based layout */}
      <div className="flex-1 overflow-hidden relative">
        {/* Background decorative elements */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {showGlowEffects && (
            <>
              <div className="absolute top-10 left-1/4 w-40 h-40 rounded-full bg-blue-600/10 blur-3xl"></div>
              <div className="absolute bottom-10 right-1/4 w-60 h-60 rounded-full bg-indigo-700/10 blur-3xl"></div>
              <div className="absolute top-1/3 right-1/3 w-20 h-20 rounded-full bg-purple-600/10 blur-xl"></div>
            </>
          )}

          <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAwIiBoZWlnaHQ9IjYwMCIgdmlld0JveD0iMCAwIDYwMCA2MDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CiAgPGRlZnM+CiAgICA8cGF0dGVybiBpZD0iZ3JpZCIgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBwYXR0ZXJuVW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzMzMzc0RCIgc3Ryb2tlLXdpZHRoPSIxIiAvPgogICAgPC9wYXR0ZXJuPgogIDwvZGVmcz4KICA8cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMGYxNzJhIiBvcGFjaXR5PSIwLjgiIC8+CiAgPHJlY3QgeD0iMCIgeT0iMCIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0idXJsKCNncmlkKSIgb3BhY2l0eT0iMC4wNSIgLz4KPC9zdmc+')] opacity-30"></div>
        </div>

        {/* Mobile content - Full screen tabs for mobile view */}
        <div className="md:hidden w-full flex flex-col h-full">
          <div className="flex-1 overflow-hidden h-full">
            {activeTab === "network" && (
              <div className="h-full">
                <AgentNetwork
                  network={network}
                  onNodeClick={onAgentSelect}
                  selectedAgents={selectedAgents.map((agent) => agent.id)}
                  processingTransaction={processing}
                />
              </div>
            )}

            {activeTab === "transactions" && (
              <div className="p-4 h-[calc(100vh-120px)] overflow-auto">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-base font-bold">Recent Transactions</h2>
                </div>
                <TransactionHistory
                  transactions={transactions}
                  agents={network.nodes}
                />
              </div>
            )}

            {activeTab === "prompt" && (
              <div className="p-4 h-[calc(100vh-120px)] overflow-auto">
                <PromptInput
                  onSubmit={onPromptSubmit}
                  selectedAgents={selectedAgents}
                  isProcessing={processing}
                />
              </div>
            )}
          </div>

          {/* Agent Details overlay for mobile */}
          {selectedAgent && (
            <div className="fixed inset-0 z-50 flex items-end p-4 bg-black/40 backdrop-blur-sm">
              <div className="w-full max-h-[80vh] overflow-auto rounded-t-2xl animate-slideUp">
                <AgentDetails
                  agent={selectedAgent}
                  onClose={onCloseDetails}
                  recentTransactions={transactions
                    .filter(
                      (tx) =>
                        tx.from === selectedAgent.id ||
                        tx.to === selectedAgent.id
                    )
                    .slice(0, 5)}
                />
              </div>
            </div>
          )}
        </div>

        {/* Desktop Grid Layout - Hidden on mobile */}
        <div className="hidden md:grid md:grid-cols-12 h-full">
          {/* Network Visualization - Takes 8 columns */}
          <div className="col-span-8 relative bg-gradient-network overflow-hidden border-r border-gray-700/50">
            {/* Cyberpunk grid overlay */}
            <div
              className={`absolute inset-0 z-0 cyberpunk-grid ${
                processing ? "grid-active" : ""
              } ${selectedAgent ? "grid-focused" : ""}`}
            >
              <div className="absolute inset-0 cyberpunk-grid-lines"></div>
              <div className="absolute inset-0 cyberpunk-grid-glow"></div>
              {processing && (
                <div className="absolute inset-0 cyberpunk-grid-pulse"></div>
              )}
            </div>

            {/* Floating particles */}
            <div className="absolute inset-0 z-1 pointer-events-none">
              <div className="particle particle-1"></div>
              <div className="particle particle-2"></div>
              <div className="particle particle-3"></div>
              <div className="particle particle-4"></div>
              <div className="particle particle-5"></div>
            </div>

            <div className="absolute top-2 left-2 z-10 bg-gray-800/70 backdrop-blur-md px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-700/50 flex items-center gap-1.5">
              <Activity size={14} className="text-blue-400" />
              <span>Agent Network Visualization</span>
            </div>

            <div className="h-full relative z-5">
              <AgentNetwork
                network={network}
                onNodeClick={onAgentSelect}
                selectedAgents={selectedAgents.map((agent) => agent.id)}
                processingTransaction={processing}
              />
            </div>
          </div>

          {/* Right Panel - 4 columns with auto-grid layout for sections */}
          <div className="col-span-4 flex flex-col overflow-hidden bg-gray-800/10">
            <div className="flex-1 flex flex-col overflow-y-scroll">
              {/* Agent Interaction */}
              <div className="p-4 relative border-b border-gray-700/50">
                <div className="rounded-xl bg-gray-800/40 backdrop-blur-sm border border-gray-700/30 shadow-lg overflow-hidden transition-all duration-300 hover:shadow-[0_0_20px_rgba(59,130,246,0.2)]">
                  {showGlowEffects && (
                    <div className="absolute top-0 left-1/4 right-1/4 h-px bg-gradient-to-r from-transparent via-blue-500 to-transparent opacity-70 blur-sm"></div>
                  )}
                  <div className="p-4">
                    <PromptInput
                      onSubmit={onPromptSubmit}
                      selectedAgents={selectedAgents}
                      isProcessing={processing}
                    />
                  </div>
                </div>
              </div>

              {/* Transactions */}
              <div className="flex-1 overflow-y-visible sm:max-h-96 max-h-none">
                <div className="p-4 h-full">
                  <div className="rounded-xl bg-gray-800/40 backdrop-blur-sm border border-gray-700/30 shadow-lg p-4 transition-all duration-300 h-full hover:shadow-[0_0_20px_rgba(59,130,246,0.2)] overflow-hidden flex flex-col">
                    <div className="mb-4 flex items-center justify-between">
                      <h2 className="text-lg font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
                        Recent Transactions
                      </h2>
                      <a
                        href="#"
                        className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                      >
                        View All <ExternalLink size={12} />
                      </a>
                    </div>

                    {/* TransactionHistory component with scrollable container */}
                    <div className="flex-1 overflow-y-auto pr-1">
                      <TransactionHistory
                        transactions={transactions}
                        agents={network.nodes}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Agent Details (conditionally rendered) */}
            {selectedAgent && (
              <div className="absolute bottom-4 right-4 left-4 z-20 max-h-[60%] overflow-auto">
                {/* Floating agent details card */}
                <div className="rounded-xl bg-gray-800/80 backdrop-blur-lg border border-gray-700/50 shadow-[0_0_20px_rgba(59,130,246,0.25)]">
                  <AgentDetails
                    agent={selectedAgent}
                    onClose={onCloseDetails}
                    recentTransactions={transactions
                      .filter(
                        (tx) =>
                          tx.from === selectedAgent.id ||
                          tx.to === selectedAgent.id
                      )
                      .slice(0, 5)}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Bottom Nav - Fixed position to ensure it's always visible */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 flex items-center justify-around border-t border-gray-800 bg-gray-900/95 backdrop-blur-lg py-3 z-10">
        <button
          className={`flex flex-col items-center justify-center gap-1 ${
            activeTab === "network" ? "text-blue-400" : "text-gray-500"
          }`}
          onClick={() => setActiveTab("network")}
        >
          <Activity size={20} />
          <span className="text-xs font-medium">Network</span>
        </button>
        <button
          className={`flex flex-col items-center justify-center gap-1 ${
            activeTab === "transactions" ? "text-blue-400" : "text-gray-500"
          }`}
          onClick={() => setActiveTab("transactions")}
        >
          <Zap size={20} />
          <span className="text-xs font-medium">Transactions</span>
        </button>
        <button
          className={`flex flex-col items-center justify-center gap-1 ${
            activeTab === "prompt" ? "text-blue-400" : "text-gray-500"
          }`}
          onClick={() => setActiveTab("prompt")}
        >
          <Shield size={20} />
          <span className="text-xs font-medium">Prompt</span>
        </button>
      </div>

      {/* Bottom glowing border */}
      {showGlowEffects && (
        <div className="hidden md:block h-px w-full bg-gradient-to-r from-transparent via-blue-500 to-transparent opacity-30"></div>
      )}

      {/* Add global CSS for animations and floating elements */}
      <style jsx global>{`
        @keyframes pulse {
          0%,
          100% {
            opacity: 0.6;
          }
          50% {
            opacity: 1;
          }
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(100%);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes shimmer {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(100%);
          }
        }

        @keyframes float {
          0% {
            transform: translateY(0px);
          }
          50% {
            transform: translateY(-5px);
          }
          100% {
            transform: translateY(0px);
          }
        }

        .animate-pulse {
          animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        .animate-fadeIn {
          animation: fadeIn 0.5s ease-out forwards;
        }

        .animate-slideUp {
          animation: slideUp 0.3s ease-out forwards;
        }

        .animate-shimmer {
          animation: shimmer 3s infinite;
        }

        .animate-float {
          animation: float 6s ease-in-out infinite;
        }

        /* Cyberpunk grid styling */
        .cyberpunk-grid-lines {
          background-image: linear-gradient(
              to right,
              rgba(59, 130, 246, 0.1) 1px,
              transparent 1px
            ),
            linear-gradient(
              to bottom,
              rgba(59, 130, 246, 0.1) 1px,
              transparent 1px
            );
          background-size: 40px 40px;
          opacity: 0.5;
        }

        .grid-active .cyberpunk-grid-lines {
          background-image: linear-gradient(
              to right,
              rgba(59, 130, 246, 0.2) 1px,
              transparent 1px
            ),
            linear-gradient(
              to bottom,
              rgba(59, 130, 246, 0.2) 1px,
              transparent 1px
            );
        }

        .grid-focused .cyberpunk-grid-glow {
          box-shadow: inset 0 0 50px rgba(59, 130, 246, 0.3);
        }

        .cyberpunk-grid-pulse {
          animation: gridPulse 3s infinite;
        }

        @keyframes gridPulse {
          0%,
          100% {
            opacity: 0.1;
          }
          50% {
            opacity: 0.3;
          }
        }

        /* Particle animations */
        .particle {
          position: absolute;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: rgba(59, 130, 246, 0.4);
          pointer-events: none;
        }

        .particle-1 {
          top: 20%;
          left: 10%;
          animation: particleFloat 8s infinite;
        }

        .particle-2 {
          top: 70%;
          left: 20%;
          animation: particleFloat 12s infinite;
        }

        .particle-3 {
          top: 40%;
          left: 70%;
          animation: particleFloat 10s infinite;
        }

        .particle-4 {
          top: 80%;
          left: 80%;
          animation: particleFloat 9s infinite;
        }

        .particle-5 {
          top: 30%;
          left: 50%;
          animation: particleFloat 11s infinite;
        }

        @keyframes particleFloat {
          0%,
          100% {
            transform: translate(0, 0);
            opacity: 0.4;
          }
          25% {
            transform: translate(10px, 10px);
            opacity: 0.6;
          }
          50% {
            transform: translate(5px, -5px);
            opacity: 0.8;
          }
          75% {
            transform: translate(-10px, 5px);
            opacity: 0.6;
          }
        }
      `}</style>
    </div>
  );
};

export default EnhancedDashboard;
