"""Demo for using OxyGent with multiple LLMs and an agent."""

import asyncio

from oxygent import MAS, oxy
from oxygent.utils.env_utils import get_env_var

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
    ),
    # Technical expert - Detailed technical feasibility analysis framework
    oxy.ChatAgent(
        name="tech_expert",
        llm_model="default_llm",
        description="AI product technical feasibility expert",
        prompt="""You are a senior technical architect and AI systems expert, responsible for comprehensive technical feasibility assessments.

Analysis Framework:
1. **Tech Stack Evaluation**
   - Recommended core tech stack (NLP models, dialogue management, knowledge base, etc.)
   - Comparison: open source vs commercial solutions
   - Maturity and stability assessment

2. **System Architecture Design**
   - Overall system architecture recommendations
   - Key technical components and module breakdown
   - Data flow and processing pipeline
   - Scalability and performance considerations

3. **Technical Challenges & Solutions**
   - Identification of major technical challenges
   - Proposed targeted solutions
   - Technical risk estimation and mitigation strategies

4. **Development Resource Estimation**
   - Required team structure
   - Estimated development timeline
   - Learning curve and training needs

Please output in a structured format, including a technical feasibility conclusion (score from 1 to 10) and key recommendations.""",
    ),
    # Business analyst - In-depth business value analysis
    oxy.ChatAgent(
        name="business_expert",
        llm_model="default_llm",
        description="AI product business value evaluation expert",
        prompt="""You are an experienced business analyst and product strategist, focused on assessing the business value of AI products.

Analysis Framework:
1. **Market Opportunity Analysis**
   - Target market size and growth potential
   - Competitor analysis and differentiation strategy
   - Customer pain points and value proposition

2. **Business Model Design**
   - Revenue model suggestions (SaaS, pay-per-use, etc.)
   - Cost structure analysis
   - Profitability forecast

3. **Return on Investment Analysis**
   - Initial cost estimation
   - Expected returns and payback period
   - Key financial metrics (NPV, IRR, breakeven)

4. **Implementation Strategy**
   - Go-to-market strategy
   - Customer acquisition and retention
   - Business growth roadmap

5. **Key Success Factors**
   - Key performance indicators (KPIs)
   - Milestone planning
   - Resource allocation recommendations

Please output in a structured format, including a business feasibility conclusion (score from 1 to 10) and key recommendations.
""",
    ),
    # Risk assessment expert - Comprehensive risk management framework
    oxy.ChatAgent(
        name="risk_expert",
        llm_model="default_llm",
        description="AI project risk management expert",
        prompt="""You are a professional risk management expert specialized in AI projects. You are only responsible for identifying, evaluating, and managing risks. Ignore all other aspects.

**Important Constraint: Only analyze from a risk management perspective. Do not touch technical, legal, or business issues.**

Risk Assessment Framework:
1. **Technical Risks**
   - Underperforming AI model
   - Unanticipated technical complexity
   - Third-party dependency
   - Data quality and acquisition risks

2. **Market Risks**
   - Changing market demand
   - Intensifying competition
   - Customer adoption risk
   - Risk of technological substitution

3. **Operational Risks**
   - Staff turnover
   - Project management challenges
   - Budget overruns
   - Timeline delays

4. **Compliance & Security Risks**
   - Data privacy and security
   - AI ethics and bias
   - Regulatory changes
   - Intellectual property issues

For each risk item, please provide:
- Probability (Low / Medium / High)
- Impact (Low / Medium / High)
- Risk level (Low / Medium / High / Critical)
- Mitigation measures
- Contingency plan

Finally, provide an overall risk rating and key risk control suggestions.""",
    ),
    # Legal expert - Comprehensive compliance analysis
    oxy.ChatAgent(
        name="legal_expert",
        llm_model="default_llm",
        description="AI product legal compliance and IP expert",
        prompt="""You are a professional legal expert specializing in AI-related compliance and intellectual property protection. You should ignore all non-legal aspects.

**Important Constraint: Only analyze from a legal perspective. Do not discuss technical, business, or risk issues.**

Compliance Analysis Framework:
1. **Data Compliance**
   - Personal Information Protection Law (PIPL) compliance
   - Cross-border data transfer regulations
   - User consent and notification mechanism
   - Data storage and processing standards

2. **AI Governance Compliance**
   - Regulations on algorithmic recommendation
   - Applicability of deep synthesis rules
   - AI ethics review requirements
   - Transparency and explainability of algorithms

3. **Business Compliance**
   - Industry-specific regulations (e.g., customer service)
   - Consumer protection laws
   - Advertising law compliance
   - Sector-specific legal requirements

4. **Intellectual Property Protection**
   - Core patent strategy recommendations
   - Trademark and copyright protection
   - Open-source software compliance
   - Third-party IP infringement risks

5. **Contracts and Agreements**
   - Key points in customer service agreements
   - Data processing agreement templates
   - Vendor contracts
   - Employee NDAs

Please provide specific compliance advice, legal risk assessments, and required legal documentation checklist.""",
    ),
    # ParallelAgent - Collects all expert opinions
    oxy.ParallelAgent(
        name="expert_panel",
        llm_model="default_llm",
        desc="Expert panel parallel evaluation",
        permitted_tool_name_list=[
            "tech_expert",
            "business_expert",
            "risk_expert",
            "legal_expert",
        ],
        is_master=True,
    ),
]


# Example usage
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="""
        Project Background:
        We are a mid-sized e-commerce company with a customer service team of 50 people handling over 5,000 inquiries per day. Main types of inquiries include:
        - Order status inquiries (40%)
        - Product information (30%)
        - After-sales service (20%)
        - Other issues (10%)

        Project Goals:
        We aim to build an intelligent customer service system that can:
        1. Automatically handle over 80% of common questions
        2. Provide 24/7 support
        3. Reduce labor costs by over 30%
        4. Improve customer satisfaction to above 90%

        Current Resources:
        - Tech team: 10 members (including 2 AI engineers)
        - Budget: 2 million RMB
        - Timeline: Aim to launch MVP within 6 months
        - Data: 500,000 historical customer service records over the past 2 years

        Specific Requirements:
        1. Support both text and voice interactions
        2. Integrate with existing CRM and order system
        3. Support multi-turn conversations and context understanding
        4. Include human handoff mechanism
        5. Require high availability (99.9%+)

        Please conduct a comprehensive evaluation and give a clear recommendation on whether to proceed with the project.
        """
        )


async def test():
    async with MAS(oxy_space=oxy_space) as mas:
        query = """
      Project Background:
         We are a mid-sized e-commerce company with a customer service team of 50 people handling over 5,000 inquiries per day. Main types of inquiries include:
         - Order status inquiries (40%)
         - Product information (30%)
         - After-sales service (20%)
         - Other issues (10%)

         Project Goals:
         We aim to build an intelligent customer service system that can:
         1. Automatically handle over 80% of common questions
         2. Provide 24/7 support
         3. Reduce labor costs by over 30%
         4. Improve customer satisfaction to above 90%

         Current Resources:
         - Tech team: 10 members (including 2 AI engineers)
         - Budget: 2 million RMB
         - Timeline: Aim to launch MVP within 6 months
         - Data: 500,000 historical customer service records over the past 2 years

         Specific Requirements:
         1. Support both text and voice interactions
         2. Integrate with existing CRM and order system
         3. Support multi-turn conversations and context understanding
         4. Include human handoff mechanism
         5. Require high availability (99.9%+)

         Please conduct a comprehensive evaluation and give a clear recommendation on whether to proceed with the project.
      """
        await mas.start_web_service(first_query=query)


if __name__ == "__main__":
    asyncio.run(test())
