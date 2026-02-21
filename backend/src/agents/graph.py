"""
LangGraph pipeline — Aurea Underwriting Multi-Agent System
==========================================================

Agent execution order:

  START
    │
    ├──────────────────────────────────────────┬─────────────────────┐
    │                                          │                     │
    ▼                                          ▼                     ▼
  PropertyValuationAgent              FloodRiskAgent        LocalitySafetyAgent
  (geocode + IBEX planning)           (flood zone)          (Police UK crime data)
    │                                          │                     │
    │               EnvironmentalDataAgent ←───┘                     │
    │               (EPC property age)                               │
    └──────────────────────┬──────────────────────────────────────── ┘
                           │
                           ▼
                     PolicyAgent
            (RAG with ALL 4 scores known)
                   │
                   ▼
          CoordinatorAgent
         (LLM decision synthesis)
                   │
                   ▼
         ExplainabilityAgent
      (plain-English narrative + risk factors)
                   │
                  END

PropertyValuationAgent and FloodRiskAgent run in parallel (both need only
the address/postcode from the initial state). EnvironmentalDataAgent waits
for PropertyValuationAgent's coordinates, then runs. PolicyAgent runs only
after all three scoring agents have populated their scores.
"""

from langgraph.graph import StateGraph, END

from src.agents.state.assessment_state import AssessmentState
from src.agents.nodes.property_valuation_agent import property_valuation_agent
from src.agents.nodes.flood_risk_agent import flood_risk_agent
from src.agents.nodes.environmental_data_agent import environmental_data_agent
from src.agents.nodes.locality_safety_agent import locality_safety_agent
from src.agents.nodes.policy_agent import policy_agent
from src.agents.nodes.coordinator_agent import coordinator_agent
from src.agents.nodes.explainability_agent import explainability_agent


def build_graph():
    graph = StateGraph(AssessmentState)

    graph.add_node("PropertyValuationAgent", property_valuation_agent)
    graph.add_node("FloodRiskAgent", flood_risk_agent)
    graph.add_node("EnvironmentalDataAgent", environmental_data_agent)
    graph.add_node("LocalitySafetyAgent", locality_safety_agent)
    graph.add_node("PolicyAgent", policy_agent)
    graph.add_node("CoordinatorAgent", coordinator_agent)
    graph.add_node("ExplainabilityAgent", explainability_agent)

    # Fan-out: three parallel risk agents after PropertyValuationAgent
    graph.set_entry_point("PropertyValuationAgent")
    graph.add_edge("PropertyValuationAgent", "FloodRiskAgent")
    graph.add_edge("PropertyValuationAgent", "EnvironmentalDataAgent")
    graph.add_edge("PropertyValuationAgent", "LocalitySafetyAgent")

    # Fan-in: PolicyAgent waits for all three scoring agents
    graph.add_edge("FloodRiskAgent", "PolicyAgent")
    graph.add_edge("EnvironmentalDataAgent", "PolicyAgent")
    graph.add_edge("LocalitySafetyAgent", "PolicyAgent")

    # Sequential tail: Coordinator → Explainability → END
    graph.add_edge("PolicyAgent", "CoordinatorAgent")
    graph.add_edge("CoordinatorAgent", "ExplainabilityAgent")
    graph.add_edge("ExplainabilityAgent", END)

    return graph.compile()


assessment_graph = build_graph()
