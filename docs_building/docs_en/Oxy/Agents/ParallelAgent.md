# ParallelAgent
---

## Definition
Agent that executes tasks in parallel across multiple team members.

## Applicable Scenarios
Suppose you need to use agents to accomplish business needs, and if the capacity of the agent model is small,
you can use agent clusters to enhance your thinking skills. OxyGent natively supports the parallel work of agents,
which can synthesize the execution results of multiple groups of agents and automatically summarize and reflect. 
You can arrange agents like a real work organization without worrying about conflicts between agents.

## Configuration Options

### Parameters


| Parameter       | Type / Allowed value | Default | Description                                                                                                      |
| --------------- | -------------------- | ------- | ---------------------------------------------------------------------------------------------------------------- |
| *None declared* | —                    | —       | `ParallelAgent` adds **no new dataclass fields**; it inherits every parameter from `LocalAgent` (and its bases). |


### Methods


| Method                        | Coroutine (async) | Return Value  | Purpose (concise)                                                                                                                                                                     |
| ----------------------------- | ----------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_execute(self, oxy_request)` | Yes               | `OxyResponse` | Distributes the incoming task to all permitted tools **concurrently**, collects their outputs, then uses the agent’s LLM to summarise those parallel results into a single response.  |

### Inherited
 Please refer to the [LocalAgent](../../../../docs/development/api/agent/local_agent.md) class for inherited parameters and methods.
 
## Quick start

This code demonstrates the design of a Multi-Agent System (MAS) for conducting comprehensive feasibility assessments of AI product projects. 
The system employs `ParallelAgent` to schedule multiple expert teams to work in parallel, achieving a true agentic working model:
- tech_expert: Expert in assessing the technical feasibility of AI products;
- business_expert: Expert in assessing the commercial value of AI products;
- risk_expert: Expert in AI-project risk assessment;
- legal_expert: Expert in legal compliance for AI products;
```python
    oxy_space = [
    oxy.HttpLLM(
        name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),

    # ─────────────── Expert agents ───────────────

    # Technical expert – detailed technical-feasibility framework
    oxy.ChatAgent(
        name="tech_expert",
        llm_model=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        description="Expert in assessing the technical feasibility of AI products",
        prompt="""You are a seasoned technical architect and AI-system specialist
responsible for a comprehensive technical-feasibility analysis.

**Analysis framework**

1. **Technology-stack assessment**
   - Recommended core stack (NLP models, dialog management, knowledge base, etc.)
   - Comparison of open-source vs. commercial solutions
   - Maturity and stability assessment

2. **System-architecture design**
   - Overall architectural recommendations
   - Key technical components and module breakdown
   - Data flow and processing pipeline
   - Scalability and performance considerations

3. **Technical challenges & solutions**
   - Identification of major technical hurdles
   - Targeted solution proposals
   - Technical-risk estimation and mitigation strategies

4. **Development-resource assessment**
   - Required staffing profile
   - Estimated development timeline
   - Technology learning curve

Please output in a *structured* format, including
• A clear technical-feasibility score (1-10) and
• Key recommendations."""
    ),

    # Business analyst – in-depth business-value analysis
    oxy.ChatAgent(
        name="business_expert",
        llm_model=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        description="Expert in assessing the commercial value of AI products",
        prompt="""You are an experienced business analyst and product-strategy
specialist focused on evaluating the commercial value of AI products.

**Analysis framework**

1. **Market-opportunity analysis**
   - Target-market size and growth potential
   - Competitor analysis and differentiation
   - Customer pain points and value proposition

2. **Business-model design**
   - Suggested revenue models (SaaS subscription, pay-per-use, etc.)
   - Cost-structure analysis
   - Profitability forecast

3. **Return-on-investment analysis**
   - Estimated initial investment
   - Expected returns and payback period
   - Key financial metrics (NPV, IRR, break-even)

4. **Go-to-market strategy**
   - Product-launch strategy
   - Customer acquisition and retention
   - Growth-path planning

5. **Critical success factors**
   - Key performance indicators (KPIs)
   - Milestone planning
   - Resource-allocation advice

Please output in a *structured* format, including
• A clear business-feasibility score (1-10) and
• Key recommendations."""
    ),

    # Risk-management expert – comprehensive risk framework
    oxy.ChatAgent(
        name="risk_expert",
        llm_model=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        description="Expert in AI-project risk identification, assessment and control",
        prompt="""You are a professional risk-management expert focused solely on
risk identification, assessment and control for AI projects.
**Important constraint: analyse only from a risk perspective – do *not*
cover technical, legal or business aspects.**

**Risk-assessment framework**

1. **Technical risks**
   - AI-model performance below expectations
   - Technical-complexity overruns
   - Third-party dependency risks
   - Data-quality and acquisition risks

2. **Market risks**
   - Changes in market demand
   - Intensifying competition
   - Customer-acceptance risks
   - Technological substitution

3. **Operational risks**
   - Staff attrition
   - Project-management risks
   - Budget overruns
   - Schedule delays

4. **Compliance & security risks**
   - Data privacy & security
   - AI ethics & bias
   - Regulatory changes
   - Intellectual-property risks

For each risk item provide:
- Probability (Low / Medium / High)
- Impact (Low / Medium / High)
- Risk level (Low / Medium / High / Critical)
- Specific mitigation measures
- Contingency-plan suggestions

Finally give an overall risk rating and core risk-control advice."""
    ),

    # Legal expert – comprehensive compliance analysis
    oxy.ChatAgent(
        name="legal_expert",
        llm_model=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        description="Expert in legal compliance and IP protection for AI products",
        prompt="""You are a professional tech lawyer focused on AI-product
compliance and intellectual-property protection – no need to consider
other dimensions.
**Important constraint: analyse only from a legal perspective – do *not*
cover technical, business or risk topics.**

**Compliance-analysis framework**

1. **Data compliance**
   - Personal-Information Protection Law (PIPL) requirements
   - Cross-border data-transfer rules
   - User consent & transparency mechanisms
   - Data-storage & processing norms

2. **AI governance compliance**
   - AI-algorithm recommendation regulations
   - Applicability of deep-synthesis rules
   - AI ethics review requirements
   - Algorithm transparency & explainability

3. **Business compliance**
   - Sector-specific regulations for customer service
   - Consumer-rights protection
   - Advertising-law requirements
   - Industry-specific compliance rules

4. **Intellectual-property protection**
   - Core-technology patent-strategy suggestions
   - Trademark & copyright protection
   - Open-source software compliance
   - Third-party IP-infringement risks

5. **Contracts & agreements**
   - Key points for customer-service agreements
   - Data-processing-agreement templates
   - Supplier cooperation contracts
   - Employee confidentiality agreements

Provide concrete compliance advice, legal-risk assessment
and a checklist of necessary legal documents."""
    ),

    # ParallelAgent to gather all expert opinions in parallel
    oxy.ParallelAgent(
        name="expert_panel",
        llm_model=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        desc="Expert panel for parallel analysis",
        permitted_tool_name_list=[
            "tech_expert", "business_expert", "risk_expert", "legal_expert"
        ],
        is_master=True,
    ),
]

# ─────────────── Usage example ───────────────
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="""
Project background:
We are a mid-sized e-commerce company. Our 50-person customer-service team
handles 5,000+ inquiries per day. The main inquiry types are:
- Order-status queries (40 %)
- Product-information queries (30 %)
- After-sales service (20 %)
- Other issues (10 %)

Project goals:
Build an intelligent customer-service system that can:
1. Automatically handle 80 %+ of common questions
2. Provide 24 × 7 service capability
3. Reduce labour costs by 30 %+
4. Increase customer satisfaction to 90 %+

Current resources:
- Technical team: 10 people (including 2 AI engineers)
- Budget: CNY 2 million
- Timeline: MVP launch within 6 months
- Data: ~500 k conversation records from the last 2 years

Specific requirements:
1. Support both text and voice interaction
2. Integrate with existing CRM and order systems
3. Support multi-turn conversation and context understanding
4. Provide a human hand-off mechanism
5. Require high availability (≥ 99.9 %)

Please conduct a comprehensive evaluation and give a clear
recommendation on whether to start this project.
"""
        )

if __name__ == "__main__":
    asyncio.run(main())
```